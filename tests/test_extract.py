import pymupdf
import pytest

from pipeline import extract, workspace


# --- pure text helpers -----------------------------------------------------


def test_strip_comments_keeps_escaped_percent():
    src = "keep 100\\% of this % but drop this\nnext line % gone\n"
    out = extract.strip_comments(src)
    assert "100\\%" in out
    assert "but drop this" not in out
    assert "gone" not in out
    assert "next line" in out


def test_document_body_extracts_between_markers():
    src = "\\documentclass{article}\nPREAMBLE\n\\begin{document}\nBODY\n\\end{document}\nTRAILER"
    body = extract.document_body(src)
    assert "BODY" in body
    assert "PREAMBLE" not in body
    assert "TRAILER" not in body


def test_document_body_fragment_returns_all():
    src = "no document environment here"
    assert extract.document_body(src) == src


def test_count_equations_numbered_only():
    src = (
        "\\begin{equation}a=b\\end{equation}\n"
        "\\begin{align}x&=y\\\\z&=w\\end{align}\n"
        "\\begin{equation*}unnumbered\\end{equation*}\n"
        "\\begin{align*}also\\end{align*}\n"
    )
    assert extract.count_equations(src) == 2


def test_brace_arg_handles_nesting():
    s = "\\includegraphics{\\iftoggle{hq}{a/b.pdf}{c/d.pdf}}rest"
    open_idx = s.index("{")
    arg, end = extract.brace_arg(s, open_idx)
    assert arg == "\\iftoggle{hq}{a/b.pdf}{c/d.pdf}"
    assert s[end:] == "rest"


def test_brace_arg_skips_escaped_braces():
    s = r"x{a \} b}tail"  # a literal \} must not close the group early
    arg, end = extract.brace_arg(s, s.index("{"))
    assert arg == r"a \} b"
    assert s[end:] == "tail"


def test_resolve_asset_picks_existing_from_conditional(tmp_path):
    (tmp_path / "images").mkdir()
    real = tmp_path / "images" / "small.pdf"
    real.write_bytes(b"%PDF-1.4")
    arg = "\\iftoggle{hq}{images_hq/big.pdf}{images/small.pdf}"
    assert extract.resolve_asset(tmp_path, arg) == real


def test_resolve_asset_extensionless(tmp_path):
    (tmp_path / "diagram.png").write_bytes(b"x")
    assert extract.resolve_asset(tmp_path, "diagram") == tmp_path / "diagram.png"


def test_resolve_asset_missing_returns_none(tmp_path):
    assert extract.resolve_asset(tmp_path, "nope.png") is None


def test_resolve_asset_rejects_traversal(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    secret = tmp_path / "secret.png"          # sits outside source/
    secret.write_bytes(b"x")
    assert extract.resolve_asset(source, "../secret.png") is None


# --- latex extraction (offline, synthetic) ---------------------------------


def _png_bytes() -> bytes:
    # 1x1 pixel via pymupdf so the test needs no binary fixture on disk
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 1, 1), False)
    return pix.tobytes("png")


def test_extract_latex_end_to_end(tmp_path):
    run = workspace.create_run(tmp_path / "runs", "synthetic")
    src = run / "source"
    (src / "images").mkdir()
    (src / "images" / "arch.png").write_bytes(_png_bytes())
    (src / "main.flattened.tex").write_text(
        "\\documentclass{article}\n"
        "\\title{Synthetic Paper}\n"
        "\\begin{document}\n"
        "% a comment that must vanish\n"
        "Intro text.\n"
        "\\begin{equation}E=mc^2\\end{equation}\n"
        "\\begin{figure}\n"
        "\\includegraphics[width=0.5\\textwidth]{images/arch.png}\n"
        "\\caption{The architecture.}\n"
        "\\end{figure}\n"
        "\\begin{table}\\begin{tabular}{cc}a&b\\end{tabular}\\end{table}\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    summary = extract.extract(run)

    paper = (run / "paper.md").read_text(encoding="utf-8")
    assert summary["source_kind"] == "latex"
    assert summary["equations"] == 1
    assert summary["figures"] == 1
    assert "comment that must vanish" not in paper
    assert "E=mc^2" in paper                      # equation preserved verbatim
    assert "\\begin{tabular}" in paper            # table survives as latex
    assert "figures/fig1.png" in paper            # rewritten to stable name
    assert (run / "figures" / "fig1.png").exists()

    figs = workspace_yaml(run / "figures" / "figures.yaml")
    assert figs[0]["id"] == "fig1"
    assert figs[0]["original"] == "images/arch.png"
    assert "architecture" in figs[0]["caption"].lower()


def test_extract_latex_dedupes_repeated_asset(tmp_path):
    run = workspace.create_run(tmp_path / "runs", "dup")
    src = run / "source"
    (src / "d.png").write_bytes(_png_bytes())
    (src / "main.flattened.tex").write_text(
        "\\begin{document}\n"
        "\\includegraphics{d.png}\n\\includegraphics{d.png}\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    summary = extract.extract(run)
    assert summary["figures"] == 1
    assert not (run / "figures" / "fig2.png").exists()


# --- pdf extraction (offline, synthetic) -----------------------------------


def test_extract_pdf(tmp_path):
    run = workspace.create_run(tmp_path / "runs", "pdfpaper")
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello from a PDF paper.")
    doc.save(run / "source" / "paper.pdf")
    doc.close()
    workspace.write_manifest(run, workspace.new_manifest("pdfpaper", "pdf"))

    summary = extract.extract(run)
    assert summary["source_kind"] == "pdf"
    assert "Hello from a PDF paper." in (run / "paper.md").read_text(encoding="utf-8")
    assert (run / "pages" / "page01.png").exists()


# --- html extraction (offline, synthetic) ----------------------------------


def test_extract_html(tmp_path):
    run = workspace.create_run(tmp_path / "runs", "htmlpaper")
    src = run / "source"
    (src / "assets").mkdir()
    (src / "assets" / "f.png").write_bytes(_png_bytes())
    (src / "paper.html").write_text(
        "<html><body><h1>Title</h1><p>Readable body text.</p>"
        "<script>ignore()</script><img src='assets/f.png'></body></html>",
        encoding="utf-8",
    )
    workspace.write_manifest(run, workspace.new_manifest("htmlpaper", "html"))

    summary = extract.extract(run)
    paper = (run / "paper.md").read_text(encoding="utf-8")
    assert summary["source_kind"] == "html"
    assert "Readable body text." in paper
    assert "ignore()" not in paper
    assert summary["figures"] == 1
    assert (run / "figures" / "fig1.png").exists()


# helper: read yaml list
def workspace_yaml(path):
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


# --- network: real papers --------------------------------------------------

# (min equations, min figures) — loose lower bounds calibrated from real sources:
# observed LoRA (4, 8), DDPM (16, 18), Grokking (0, 11). Grokking uses inline /
# \[..\] math, so it has zero *numbered* display equations by design.
PAPERS = {"2106.09685": (3, 6), "2006.11239": (12, 15), "2201.02177": (0, 9)}


@pytest.mark.network
@pytest.mark.parametrize("arxiv_id", list(PAPERS))
def test_extract_real_papers(tmp_path, arxiv_id):
    from pipeline import fetch

    run = fetch.fetch(arxiv_id, runs_dir=tmp_path / "runs")
    summary = extract.extract(run)
    min_eq, min_fig = PAPERS[arxiv_id]
    assert summary["equations"] >= min_eq
    assert summary["figures"] >= min_fig
    assert (run / "paper.md").stat().st_size > 500
    copied = list((run / "figures").glob("fig[0-9]*"))
    assert len(copied) == summary["figures"]
