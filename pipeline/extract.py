"""Extract source/ -> paper.md + figures/ (+ pages/ for the PDF path).

LaTeX is the primary path (see DECISIONS.md source-priority): comments and
preamble are stripped, math/tables are preserved verbatim as LaTeX, and
\\includegraphics targets are copied to figures/ under stable figN names.
HTML and PDF are fallbacks. paper.md stays LaTeX-preserving, not detex'd:
downstream skills zoom back into source/ via the IR's src pointers.
"""

from __future__ import annotations

import re
import shutil
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import pymupdf
import yaml

from pipeline import workspace

IMG_EXTS = (".png", ".jpg", ".jpeg", ".pdf", ".eps", ".gif")

_COMMENT_RE = re.compile(r"(?<!\\)%[^\n]*")
_EQ_RE = re.compile(
    r"\\begin\{(?:equation|align|gather|multline|eqnarray|flalign|alignat)\}"
)
_GRAPHICS_RE = re.compile(r"\\includegraphics(\*)?(\[[^\]]*\])?\s*\{")
_FIGENV_RE = re.compile(r"\\begin\{(figure\*?|wrapfigure)\}")
_ASSET_TOKEN_RE = re.compile(r"[\w./\\-]+\.(?:png|jpe?g|pdf|eps|gif)", re.I)
_MACRO_RE = re.compile(r"\\[a-zA-Z]+\*?")


class ExtractError(Exception):
    """Explicit, user-facing extraction failure."""


# --- pure LaTeX text helpers ------------------------------------------------


def strip_comments(tex: str) -> str:
    """Drop `%`-to-EOL comments; an escaped `\\%` stays."""
    return _COMMENT_RE.sub("", tex)


def document_body(tex: str) -> str:
    """Content between \\begin{document} and \\end{document}; whole text if absent."""
    b = tex.find("\\begin{document}")
    if b == -1:
        return tex
    start = b + len("\\begin{document}")
    e = tex.find("\\end{document}", start)
    return tex[start : e if e != -1 else len(tex)]


def count_equations(tex: str) -> int:
    """Numbered display-equation environments (starred/unnumbered excluded)."""
    return len(_EQ_RE.findall(tex))


def brace_arg(s: str, open_idx: int) -> tuple[str, int]:
    """Content of the `{...}` group at s[open_idx], plus the index past its close.

    Depth-aware, so nested groups (e.g. `\\iftoggle{c}{a}{b}`) are handled.
    """
    if s[open_idx] != "{":
        raise ValueError("brace_arg must start on '{'")
    depth = 0
    i = open_idx
    while i < len(s):
        c = s[i]
        if c == "\\":  # escaped char (\{ \} \\); the brace is literal, skip both
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[open_idx + 1 : i], i + 1
        i += 1
    raise ValueError("unbalanced braces")


def _within(root: Path, path: Path) -> bool:
    """True iff path is inside root once symlinks/`..` are resolved."""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def _resolve_one(source_dir: Path, token: str) -> Path | None:
    token = token.strip().replace("\\", "/").lstrip("/")
    if not token:
        return None
    candidates = [source_dir / token]
    if (source_dir / token).suffix.lower() not in IMG_EXTS:  # \includegraphics{fig}
        candidates += [source_dir / (token + ext) for ext in IMG_EXTS]
    for cand in candidates:
        # Untrusted source: a ../ path must not pull a file from outside source/.
        if cand.is_file() and _within(source_dir, cand):
            return cand
    return None


def resolve_asset(source_dir: Path, arg: str) -> Path | None:
    """First existing image file referenced by a \\includegraphics argument.

    The arg may wrap the path in macros (`\\iftoggle{hq}{A}{B}`); each candidate
    is tried in order and the first that exists on disk wins.
    """
    tokens = _ASSET_TOKEN_RE.findall(arg)
    if not tokens:
        cleaned = _MACRO_RE.sub(" ", arg)
        tokens = re.findall(r"[\w./\\-]+", cleaned)
    for tok in tokens:
        p = _resolve_one(source_dir, tok)
        if p is not None:
            return p
    return None


# --- captions ---------------------------------------------------------------


def _extract_caption(segment: str) -> str:
    i = segment.find("\\caption")
    if i == -1:
        return ""
    b = segment.find("{", i)
    if b == -1:
        return ""
    try:
        txt, _ = brace_arg(segment, b)
    except ValueError:
        return ""
    txt = _MACRO_RE.sub("", txt).replace("{", "").replace("}", "")
    return " ".join(txt.split())


def _figure_captions(body: str) -> list[tuple[int, int, str]]:
    envs = []
    for m in _FIGENV_RE.finditer(body):
        # ponytail: first matching \end{...} closes the env. Nesting or a literal
        # \end{figure} inside caption text would misalign — neither occurs in real
        # arXiv sources. Upgrade to a depth-aware scan only if a paper breaks it.
        end_tag = "\\end{" + m.group(1) + "}"
        end = body.find(end_tag, m.end())
        if end == -1:
            end = len(body)
        envs.append((m.start(), end, _extract_caption(body[m.start() : end])))
    return envs


def _caption_for(pos: int, envs: list[tuple[int, int, str]]) -> str:
    for start, end, cap in envs:
        if start <= pos < end:
            return cap
    return ""


# --- title ------------------------------------------------------------------


def _title(run_dir: Path, raw: str) -> str:
    meta = run_dir / "fetch_meta.yaml"
    if meta.is_file():
        data = yaml.safe_load(meta.read_text(encoding="utf-8")) or {}
        if data.get("title"):
            return data["title"]
    m = re.search(r"\\title\s*\{", raw)
    if m:
        try:
            t, _ = brace_arg(raw, m.end() - 1)
        except ValueError:
            t = ""
        t = _MACRO_RE.sub("", t).replace("{", "").replace("}", "")
        if t.strip():
            return " ".join(t.split())
    return run_dir.name


# --- LaTeX path -------------------------------------------------------------


def _find_main_tex(source_dir: Path) -> Path:
    flat = source_dir / "main.flattened.tex"
    if flat.is_file():
        return flat
    candidates = sorted(source_dir.rglob("*.tex"))
    for p in candidates:
        if "\\documentclass" in p.read_text(encoding="utf-8", errors="replace"):
            return p
    if candidates:
        return candidates[0]
    raise ExtractError(f"no .tex file under {source_dir}")


def _rewrite_graphics(
    body: str, source_dir: Path, figures_dir: Path
) -> tuple[str, list[dict]]:
    envs = _figure_captions(body)
    out: list[str] = []
    cursor = 0
    seen: dict[str, dict] = {}
    figs: list[dict] = []
    for m in _GRAPHICS_RE.finditer(body):
        try:
            arg, arg_end = brace_arg(body, m.end() - 1)
        except ValueError:
            continue  # malformed; leave the raw text in place via final tail
        out.append(body[cursor:m.start()])
        opts = m.group(2) or ""
        resolved = resolve_asset(source_dir, arg)
        if resolved is None:
            out.append(body[m.start():arg_end])  # keep original reference
            cursor = arg_end
            continue
        rel = resolved.relative_to(source_dir).as_posix()
        key = resolved.resolve()  # dedup by real file, not the (possibly aliased) rel
        fig = seen.get(key)
        if fig is None:
            n = len(figs) + 1
            figname = f"fig{n}{resolved.suffix.lower()}"
            figures_dir.mkdir(exist_ok=True)
            shutil.copy2(resolved, figures_dir / figname)
            fig = {
                "id": f"fig{n}",
                "file": f"figures/{figname}",
                "original": rel,
                "caption": _caption_for(m.start(), envs),
            }
            seen[key] = fig
            figs.append(fig)
        out.append(f"\\includegraphics{opts}{{{fig['file']}}}")
        cursor = arg_end
    out.append(body[cursor:])
    return "".join(out), figs


def extract_latex(source_dir: Path, run_dir: Path) -> dict:
    raw = _find_main_tex(source_dir).read_text(encoding="utf-8", errors="replace")
    body = document_body(strip_comments(raw))
    new_body, figs = _rewrite_graphics(body, source_dir, run_dir / "figures")
    (run_dir / "paper.md").write_text(
        f"# {_title(run_dir, raw)}\n\n{new_body.strip()}\n", encoding="utf-8"
    )
    _write_figures_manifest(run_dir / "figures", figs)
    return {"source_kind": "latex", "equations": count_equations(body), "figures": len(figs)}


# --- PDF path (last resort) -------------------------------------------------


def extract_pdf(source_dir: Path, run_dir: Path) -> dict:
    pdf = next(source_dir.glob("*.pdf"), None)
    if pdf is None:
        raise ExtractError(f"no .pdf under {source_dir}")
    figures_dir, pages_dir = run_dir / "figures", run_dir / "pages"
    texts: list[str] = []
    nfig = 0
    seen_xref: set[int] = set()
    with pymupdf.open(pdf) as doc:
        for i, page in enumerate(doc, start=1):
            texts.append(page.get_text())
            pages_dir.mkdir(exist_ok=True)
            page.get_pixmap(dpi=150).save(pages_dir / f"page{i:02d}.png")
            for img in page.get_images(full=True):
                xref = img[0]
                if xref in seen_xref:
                    continue
                seen_xref.add(xref)
                pix = pymupdf.Pixmap(doc, xref)
                if pix.n - pix.alpha > 3:  # CMYK -> RGB so PNG can hold it
                    pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                nfig += 1
                figures_dir.mkdir(exist_ok=True)
                pix.save(figures_dir / f"fig{nfig}.png")
    full_text = "\n\n".join(texts)
    (run_dir / "paper.md").write_text(
        f"# {_title(run_dir, '')}\n\n{full_text.strip()}\n", encoding="utf-8"
    )
    return {"source_kind": "pdf", "equations": count_equations(full_text), "figures": nfig}


# --- HTML path (fallback) ---------------------------------------------------


class _HTMLText(HTMLParser):
    _SKIP = {"script", "style", "head"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.imgs: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip += 1
        if tag == "img":
            src = dict(attrs).get("src")
            if src:
                self.imgs.append(src)

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.parts.append(data.strip())


def extract_html(source_dir: Path, run_dir: Path) -> dict:
    html_file = next(source_dir.glob("*.html"), None)
    if html_file is None:
        raise ExtractError(f"no .html under {source_dir}")
    parser = _HTMLText()
    parser.feed(html_file.read_text(encoding="utf-8", errors="replace"))
    figures_dir = run_dir / "figures"
    figs: list[dict] = []
    seen: set[str] = set()
    for src in parser.imgs:
        if src in seen:
            continue
        name = Path(urlsplit(src).path).name
        cand = source_dir / src
        if not (cand.is_file() and _within(source_dir, cand)):
            cand = source_dir / "assets" / name
        if cand.is_file() and _within(source_dir, cand):
            seen.add(src)
            n = len(figs) + 1
            figname = f"fig{n}{cand.suffix.lower() or '.png'}"
            figures_dir.mkdir(exist_ok=True)
            shutil.copy2(cand, figures_dir / figname)
            figs.append({"id": f"fig{n}", "file": f"figures/{figname}", "original": src, "caption": ""})
    (run_dir / "paper.md").write_text(
        f"# {_title(run_dir, '')}\n\n" + "\n\n".join(parser.parts) + "\n", encoding="utf-8"
    )
    _write_figures_manifest(figures_dir, figs)
    return {"source_kind": "html", "equations": 0, "figures": len(figs)}


# --- dispatch ---------------------------------------------------------------


def _write_figures_manifest(figures_dir: Path, figs: list[dict]) -> None:
    figures_dir.mkdir(parents=True, exist_ok=True)
    (figures_dir / "figures.yaml").write_text(
        yaml.safe_dump(figs, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


def _infer_kind(source_dir: Path) -> str:
    if (source_dir / "main.flattened.tex").is_file() or any(source_dir.glob("*.tex")):
        return "latex"
    if any(source_dir.glob("*.html")):
        return "html"
    if any(source_dir.glob("*.pdf")):
        return "pdf"
    raise ExtractError(f"cannot infer source kind from {source_dir}")


def extract(run_dir: Path | str) -> dict:
    """source/ -> paper.md + figures/ (+ pages/). Dispatches on manifest source_kind."""
    run_dir = Path(run_dir)
    kind = None
    manifest = run_dir / "manifest.yaml"
    if manifest.is_file():
        kind = (workspace.read_manifest(run_dir) or {}).get("source_kind")
    if not kind:
        kind = _infer_kind(run_dir / "source")
    dispatch = {"latex": extract_latex, "pdf": extract_pdf, "html": extract_html}
    if kind not in dispatch:
        raise ExtractError(f"unsupported source_kind: {kind!r}")
    return dispatch[kind](run_dir / "source", run_dir)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Extract a fetched run into paper.md + figures/.")
    parser.add_argument("run_dir", help="path to runs/<slug>/")
    args = parser.parse_args(argv)
    try:
        summary = extract(args.run_dir)
    except ExtractError as e:
        print(f"extract failed: {e}", file=sys.stderr)
        return 2
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
