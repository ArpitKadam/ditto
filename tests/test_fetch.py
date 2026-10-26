import gzip
import io
import tarfile

import pytest

from pipeline import workspace
from pipeline.fetch import (
    FetchError,
    fetch,
    find_main_tex,
    flatten_latex,
    resolve_input,
)

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


# --- resolve_input ---------------------------------------------------------


@pytest.mark.parametrize(
    "raw,arxiv_id",
    [
        ("2106.09685", "2106.09685"),
        ("2106.09685v2", "2106.09685v2"),
        ("arXiv:2201.02177", "2201.02177"),
        ("https://arxiv.org/abs/2106.09685", "2106.09685"),
        ("https://arxiv.org/pdf/2106.09685", "2106.09685"),
        ("https://arxiv.org/pdf/2106.09685v1.pdf", "2106.09685v1"),
        ("https://arxiv.org/html/2201.02177v1", "2201.02177v1"),
        ("https://arxiv.org/e-print/2006.11239", "2006.11239"),
        ("hep-th/9901001", "hep-th/9901001"),
        ("https://arxiv.org/abs/hep-th/9901001", "hep-th/9901001"),
    ],
)
def test_resolve_arxiv(raw, arxiv_id):
    r = resolve_input(raw)
    assert r.kind == "arxiv"
    assert r.arxiv_id == arxiv_id


def test_resolve_local(tmp_path):
    p = tmp_path / "paper.pdf"
    p.write_bytes(MINIMAL_PDF)
    r = resolve_input(str(p))
    assert r.kind == "local"
    assert r.path == p


def test_resolve_pdf_url():
    r = resolve_input("https://example.com/papers/foo.pdf")
    assert r.kind == "pdf_url"
    assert r.url == "https://example.com/papers/foo.pdf"


@pytest.mark.parametrize(
    "raw",
    [
        "not a paper at all",
        "C:/definitely/missing/paper.pdf",
        "https://example.com/page.html",
    ],
)
def test_resolve_garbage_raises(raw):
    with pytest.raises(FetchError):
        resolve_input(raw)


def test_resolve_unsupported_extension(tmp_path):
    p = tmp_path / "paper.docx"
    p.write_bytes(b"junk")
    with pytest.raises(FetchError, match="docx"):
        resolve_input(str(p))


# --- latex flattening ------------------------------------------------------


def test_find_main_tex(tmp_path):
    (tmp_path / "macros.tex").write_text(r"\newcommand{\x}{1}")
    (tmp_path / "main.tex").write_text(
        "\\documentclass{article}\n\\begin{document}hi\\end{document}\n"
    )
    assert find_main_tex(tmp_path).name == "main.tex"


def test_flatten_resolves_nested_inputs(tmp_path):
    (tmp_path / "sections").mkdir()
    (tmp_path / "main.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\n"
        "\\input{sections/intro}\n\\include{outro}\n\\end{document}\n"
    )
    (tmp_path / "sections" / "intro.tex").write_text("INTRO\n\\input{sections/deep}\n")
    (tmp_path / "sections" / "deep.tex").write_text("DEEP")
    (tmp_path / "outro.tex").write_text("OUTRO")
    flat = flatten_latex(tmp_path / "main.tex")
    for token in ("INTRO", "DEEP", "OUTRO"):
        assert token in flat
    assert "\\input{" not in flat


@pytest.mark.parametrize(
    "payload",
    [
        "/etc/passwd",
        "../../../../secret",
        "C:/Windows/win.ini",
        "C:\\Windows\\win.ini",
        "\\\\server\\share\\x",
        "//server/share/x",
    ],
)
def test_flatten_rejects_out_of_tree_input(tmp_path, payload):
    outside = tmp_path.parent / "secret.tex"
    outside.write_text("TOPSECRET")
    (tmp_path / "main.tex").write_text(
        "\\documentclass{article}\n\\begin{document}"
        f"\\input{{{payload}}}\\end{{document}}"
    )
    flat = flatten_latex(tmp_path / "main.tex")
    assert "TOPSECRET" not in flat
    assert "rejected out-of-tree" in flat


def test_flatten_missing_input_tolerated(tmp_path):
    (tmp_path / "main.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\\input{ghost}\\end{document}"
    )
    flat = flatten_latex(tmp_path / "main.tex")
    assert "ghost" in flat  # left visible, not a crash


def test_repo_candidates_strip_sentence_punctuation():
    from pipeline.fetch import _repo_candidates

    text = (
        "Our code is at https://github.com/microsoft/LoRA. "
        "See also https://gitlab.com/a/b-c, and nothing else."
    )
    assert _repo_candidates(text) == [
        "https://github.com/microsoft/LoRA",
        "https://gitlab.com/a/b-c",
    ]


# --- fetch: local + safety -------------------------------------------------


def test_fetch_local_pdf(tmp_path):
    pdf = tmp_path / "myPaper.pdf"
    pdf.write_bytes(MINIMAL_PDF)
    run_dir = fetch(str(pdf), runs_dir=tmp_path / "runs")
    assert (run_dir / "source" / "myPaper.pdf").read_bytes() == MINIMAL_PDF
    manifest = workspace.read_manifest(run_dir)
    assert manifest["source_kind"] == "pdf"
    assert (run_dir / "fetch_meta.yaml").exists()


def test_fetch_garbage_is_explicit_error(tmp_path):
    with pytest.raises(FetchError):
        fetch("!!definitely garbage!!", runs_dir=tmp_path / "runs")


def test_eprint_traversal_rejected(tmp_path):
    from pipeline.fetch import _extract_eprint

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo("../evil.tex")
        data = b"\\documentclass{article}"
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    gz = gzip.compress(buf.getvalue())
    with pytest.raises(FetchError):
        _extract_eprint(gz, tmp_path / "source")
    assert not (tmp_path.parent / "evil.tex").exists()


def test_eprint_single_gzipped_tex(tmp_path):
    from pipeline.fetch import _extract_eprint

    tex = b"\\documentclass{article}\n\\begin{document}x\\end{document}\n"
    kind = _extract_eprint(gzip.compress(tex), tmp_path / "source")
    assert kind == "latex"
    flat = tmp_path / "source" / "main.flattened.tex"
    assert flat.exists()
    assert b"documentclass" in flat.read_bytes()


def test_html_assets_reject_nonarxiv_and_filescheme(tmp_path, monkeypatch):
    import pipeline.fetch as fetch_mod

    page = (
        '<img src="file:///etc/passwd">'
        '<img src="http://169.254.169.254/meta">'
        '<img src="fig1.png">'
    )
    downloaded: list[str] = []

    def fake_download(url: str) -> bytes:
        downloaded.append(url)
        return page.encode() if url.endswith("2201.02177") else b"PNGDATA"

    monkeypatch.setattr(fetch_mod, "_download", fake_download)
    fetch_mod._fetch_arxiv_html("2201.02177", tmp_path / "source")
    page_url = "https://arxiv.org/html/2201.02177"
    asset_fetches = [u for u in downloaded if u != page_url]
    assert asset_fetches == ["https://arxiv.org/html/2201.02177/fig1.png"]


# --- network (explicit: uv run pytest -m network) --------------------------

PAPERS = ["2106.09685", "2006.11239", "2201.02177"]


@pytest.mark.network
@pytest.mark.parametrize("arxiv_id", PAPERS)
def test_fetch_test_papers_eprint(tmp_path, arxiv_id):
    run_dir = fetch(arxiv_id, runs_dir=tmp_path / "runs")
    manifest = workspace.read_manifest(run_dir)
    assert manifest["source_kind"] == "latex"
    assert (run_dir / "source" / "main.flattened.tex").exists()
    assets = [
        p
        for p in (run_dir / "source").rglob("*")
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".pdf", ".eps"}
    ]
    assert assets, "expected figure assets in the e-print tarball"
    meta = (run_dir / "fetch_meta.yaml").read_text(encoding="utf-8")
    assert "title" in meta
