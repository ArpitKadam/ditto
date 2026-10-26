"""Resolve input (arXiv id/URL, local path, PDF URL) -> download source into the run workspace.

Source priority per DECISIONS.md: arXiv e-print LaTeX -> arXiv HTML -> PDF.
"""

from __future__ import annotations

import gzip
import io
import re
import shutil
import sys
import tarfile
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

import yaml

from pipeline import workspace

USER_AGENT = "ditto/0.1 (research-paper reproduction pipeline)"
TIMEOUT = 60

_NEW_ID = r"\d{4}\.\d{4,5}(?:v\d+)?"
_OLD_ID = r"[a-z][a-z-]*(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?"
_ID_RE = re.compile(rf"^(?:{_NEW_ID}|{_OLD_ID})$")
_ARXIV_PATH_RE = re.compile(
    rf"^/(?:abs|pdf|html|e-print|format)/({_NEW_ID}|{_OLD_ID})(?:\.pdf)?/?$"
)
_REPO_RE = re.compile(r"https?://(?:github|gitlab)\.com/[\w.-]+/[\w.-]+", re.I)
_INPUT_RE = re.compile(r"\\(?:input|include)\{([^}]+)\}")

LOCAL_KINDS = {".pdf": "pdf", ".tex": "latex", ".txt": "latex"}


class FetchError(Exception):
    """Explicit, user-facing fetch failure."""


@dataclass
class Resolved:
    kind: str  # arxiv | pdf_url | local
    arxiv_id: str | None = None
    url: str | None = None
    path: Path | None = None


def resolve_input(raw: str) -> Resolved:
    raw = raw.strip()
    if not raw:
        raise FetchError("empty input")

    candidate = raw.removeprefix("arXiv:").removeprefix("arxiv:")
    if _ID_RE.match(candidate):
        return Resolved(kind="arxiv", arxiv_id=candidate)

    if raw.startswith(("http://", "https://")):
        parsed = urllib.parse.urlparse(raw)
        if parsed.hostname and parsed.hostname.endswith("arxiv.org"):
            m = _ARXIV_PATH_RE.match(parsed.path)
            if not m:
                raise FetchError(f"unrecognized arXiv URL: {raw}")
            return Resolved(kind="arxiv", arxiv_id=m.group(1))
        if parsed.path.lower().endswith(".pdf"):
            return Resolved(kind="pdf_url", url=raw)
        raise FetchError(
            f"unsupported URL (only arXiv URLs and direct .pdf links): {raw}"
        )

    path = Path(raw)
    ext = path.suffix.lower()
    if path.exists():
        if ext not in LOCAL_KINDS:
            raise FetchError(
                f"unsupported local file type '{ext.lstrip('.')}' "
                f"(supported: pdf, tex, txt): {raw}"
            )
        return Resolved(kind="local", path=path)
    if ext in LOCAL_KINDS:
        raise FetchError(f"local file not found: {raw}")
    raise FetchError(
        f"unrecognized input (not an arXiv id/URL, PDF URL, or existing file): {raw}"
    )


def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise FetchError(f"download failed for {url}: {e}") from e


# --- LaTeX ------------------------------------------------------------------


def find_main_tex(source_dir: Path) -> Path:
    """The .tex file with \\documentclass, preferring one with \\begin{document}."""
    with_class, with_doc = [], []
    for p in sorted(source_dir.rglob("*.tex")):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "\\documentclass" in text:
            with_class.append(p)
            if "\\begin{document}" in text:
                with_doc.append(p)
    candidates = with_doc or with_class
    if not candidates:
        raise FetchError(f"no .tex file with \\documentclass under {source_dir}")
    for preferred in ("main.tex", "paper.tex", "ms.tex"):
        for p in candidates:
            if p.name == preferred:
                return p
    return candidates[0]


def _is_foreign_absolute(name: str) -> bool:
    r"""True if name has a drive, root, or UNC prefix under either path flavor.

    Windows-absolute names (C:/x, C:x, \\host\share, /\host, \\?\C:\x) are plain
    relative names on POSIX, so the containment check alone would miss them;
    on Windows, resolving a UNC target before that check can touch the network.
    """
    pw = PureWindowsPath(name)
    return bool(pw.drive or pw.root or PurePosixPath(name).is_absolute())


def flatten_latex(
    main: Path, _root: Path | None = None, _seen: set[Path] | None = None
) -> str:
    """Recursively inline \\input/\\include. Paths resolve against the root
    (main file's) directory, matching TeX compilation semantics.

    Missing files are left as a visible comment, never a crash.
    ponytail: also inlines occurrences inside comments; fine for arXiv sources,
    revisit if a paper comments out an \\input that must stay dead.
    """
    seen = _seen if _seen is not None else set()
    main = main.resolve()
    root = _root if _root is not None else main.parent
    if main in seen:
        return f"% ditto: cyclic input skipped {main.name}\n"
    seen.add(main)
    text = main.read_text(encoding="utf-8", errors="replace")

    def repl(m: re.Match) -> str:
        name = m.group(1).strip()
        # Reject drive/root/UNC names before joining or resolving anything.
        if _is_foreign_absolute(name):
            return f"% ditto: rejected out-of-tree {m.group(0)}"
        target = root / name
        if target.suffix == "":
            target = target.with_suffix(".tex")
        # Untrusted .tex from a downloaded e-print: an absolute path or ../
        # escape must not read files outside the source tree.
        try:
            target.resolve().relative_to(root.resolve())
        except (ValueError, OSError):
            return f"% ditto: rejected out-of-tree {m.group(0)}"
        if target.exists():
            return flatten_latex(target, root, seen)
        return f"% ditto: missing {m.group(0)}"

    return _INPUT_RE.sub(repl, text)


def _extract_eprint(data: bytes, source_dir: Path) -> str:
    """Unpack e-print bytes (gzipped tar or gzipped single .tex) into source_dir.

    Writes main.flattened.tex; returns 'latex'. Raises FetchError on anything
    unsafe or unrecognized.
    """
    source_dir.mkdir(parents=True, exist_ok=True)
    if data[:2] == b"\x1f\x8b":
        try:
            data = gzip.decompress(data)
        except (OSError, gzip.BadGzipFile) as e:
            raise FetchError(f"corrupt gzip from e-print: {e}") from e

    if tarfile.is_tarfile(io.BytesIO(data)):
        try:
            with tarfile.open(fileobj=io.BytesIO(data)) as tar:
                tar.extractall(source_dir, filter="data")
        except (tarfile.TarError, OSError) as e:
            raise FetchError(f"unsafe or corrupt e-print tarball: {e}") from e
    elif b"\\documentclass" in data:
        (source_dir / "main.tex").write_bytes(data)
    else:
        raise FetchError("e-print payload is neither a tarball nor a LaTeX file")

    main = find_main_tex(source_dir)
    (source_dir / "main.flattened.tex").write_text(
        flatten_latex(main), encoding="utf-8"
    )
    return "latex"


def _repo_candidates(text: str) -> list[str]:
    """Repo URLs in prose; sentence-ending punctuation is not part of the URL."""
    return sorted({m.rstrip(".,;:") for m in _REPO_RE.findall(text)})


# --- arXiv metadata ---------------------------------------------------------

_ATOM = "{http://www.w3.org/2005/Atom}"
_ARXIV = "{http://arxiv.org/schemas/atom}"


def fetch_arxiv_metadata(arxiv_id: str) -> dict:
    """Title/authors/year/abstract + official-repo candidates from the export API."""
    bare_id = re.sub(r"v\d+$", "", arxiv_id)
    url = (
        "https://export.arxiv.org/api/query?id_list="
        + urllib.parse.quote(bare_id, safe="")
    )
    payload = _download(url)
    # XXE / billion-laughs both require a DTD; a legitimate Atom feed has none.
    if b"<!DOCTYPE" in payload or b"<!ENTITY" in payload:
        raise FetchError("arXiv API response contains a DTD; refusing to parse")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as e:
        raise FetchError(f"arXiv API returned unparseable XML: {e}") from e
    entry = root.find(f"{_ATOM}entry")
    if entry is None:
        raise FetchError(f"arXiv export API returned no entry for {arxiv_id}")
    title = " ".join((entry.findtext(f"{_ATOM}title") or "").split())
    if not title or title == "Error":
        raise FetchError(f"arXiv id not found: {arxiv_id}")
    summary = " ".join((entry.findtext(f"{_ATOM}summary") or "").split())
    comment = " ".join((entry.findtext(f"{_ARXIV}comment") or "").split())
    published = entry.findtext(f"{_ATOM}published") or ""
    repos = _repo_candidates(f"{summary} {comment}")
    return {
        "arxiv_id": arxiv_id,
        "title": title,
        "authors": [
            name
            for a in entry.findall(f"{_ATOM}author")
            if (name := a.findtext(f"{_ATOM}name"))
        ],
        "year": int(published[:4]) if published[:4].isdigit() else None,
        "abstract": summary,
        "comment": comment or None,
        "official_repo_candidates": repos,
    }


# --- HTML fallback ----------------------------------------------------------


def _fetch_arxiv_html(arxiv_id: str, source_dir: Path) -> str:
    url = f"https://arxiv.org/html/{arxiv_id}"
    page = _download(url).decode("utf-8", errors="replace")
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "paper.html").write_text(page, encoding="utf-8")
    assets = source_dir / "assets"
    for src in set(re.findall(r'<img[^>]+src="([^"]+)"', page)):
        asset_url = urllib.parse.urljoin(url + "/", src)
        parts = urllib.parse.urlparse(asset_url)
        # Untrusted page: an absolute src can smuggle file:// (local read) or an
        # internal host (SSRF). Only fetch http(s) assets from arxiv.org itself.
        if parts.scheme not in ("http", "https") or not (
            parts.hostname or ""
        ).endswith("arxiv.org"):
            continue
        name = Path(parts.path).name
        if not name:
            continue
        try:
            assets.mkdir(exist_ok=True)
            (assets / name).write_bytes(_download(asset_url))
        except FetchError:
            pass  # one broken asset never fails the fetch
    return "html"


# --- orchestration ----------------------------------------------------------


def _slug(resolved: Resolved) -> str:
    if resolved.kind == "arxiv":
        bare = re.sub(r"v\d+$", "", resolved.arxiv_id)
        return bare.replace("/", "-")
    if resolved.kind == "local":
        return re.sub(r"[^\w.-]+", "-", resolved.path.stem)
    return re.sub(r"[^\w.-]+", "-", Path(urllib.parse.urlparse(resolved.url).path).stem)


def fetch(raw: str, runs_dir: Path | str = Path("runs")) -> Path:
    """Any supported input -> populated runs/<slug>/ with source/, manifest, fetch_meta."""
    resolved = resolve_input(raw)
    run_dir = workspace.create_run(runs_dir, _slug(resolved))
    source_dir = run_dir / "source"
    meta: dict = {"input": raw, "resolved_kind": resolved.kind}

    if resolved.kind == "arxiv":
        data = _download(f"https://arxiv.org/e-print/{resolved.arxiv_id}")
        if data[:4] == b"%PDF":  # source unavailable; e-print served the PDF
            try:
                source_kind = _fetch_arxiv_html(resolved.arxiv_id, source_dir)
            except FetchError:
                (source_dir / "paper.pdf").write_bytes(data)
                source_kind = "pdf"
        else:
            source_kind = _extract_eprint(data, source_dir)
        try:
            meta.update(fetch_arxiv_metadata(resolved.arxiv_id))
        except FetchError as e:
            meta["metadata_error"] = str(e)  # source fetched; metadata is enrichment
        paper_id = re.sub(r"v\d+$", "", resolved.arxiv_id)

    elif resolved.kind == "pdf_url":
        data = _download(resolved.url)
        if data[:4] != b"%PDF":
            raise FetchError(f"URL did not return a PDF: {resolved.url}")
        (source_dir / (_slug(resolved) + ".pdf")).write_bytes(data)
        source_kind = "pdf"
        paper_id = _slug(resolved)

    else:  # local
        shutil.copy2(resolved.path, source_dir / resolved.path.name)
        source_kind = LOCAL_KINDS[resolved.path.suffix.lower()]
        if resolved.path.suffix.lower() == ".tex":
            (source_dir / "main.flattened.tex").write_text(
                flatten_latex(resolved.path), encoding="utf-8"
            )
        paper_id = _slug(resolved)

    meta.setdefault("official_repo_candidates", [])
    (run_dir / "fetch_meta.yaml").write_text(
        yaml.safe_dump(meta, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    workspace.write_manifest(run_dir, workspace.new_manifest(paper_id, source_kind))
    return run_dir


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Fetch a paper into a ditto run workspace."
    )
    parser.add_argument("input", help="arXiv id/URL, local pdf/tex/txt, or PDF URL")
    parser.add_argument("--runs-dir", default="runs")
    args = parser.parse_args(argv)
    try:
        run_dir = fetch(args.input, runs_dir=args.runs_dir)
    except FetchError as e:
        print(f"fetch failed: {e}", file=sys.stderr)
        return 2
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
