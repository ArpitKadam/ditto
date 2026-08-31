import pymupdf
import pytest

from pipeline import rasterize


def _pdf_figure(path):
    doc = pymupdf.open()
    page = doc.new_page(width=100, height=80)
    page.insert_text((10, 40), "figure")
    doc.save(path)
    doc.close()


def test_rasterize_pdf_to_png(tmp_path):
    fig = tmp_path / "fig1.pdf"
    _pdf_figure(fig)
    out = rasterize.rasterize(fig)
    assert out == tmp_path / "fig1.png"
    assert out.stat().st_size > 0
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_rasterize_idempotent_and_png_passthrough(tmp_path):
    fig = tmp_path / "fig1.pdf"
    _pdf_figure(fig)
    first = rasterize.rasterize(fig)
    stamp = first.stat().st_mtime_ns
    assert rasterize.rasterize(fig) == first          # existing PNG not re-rendered
    assert first.stat().st_mtime_ns == stamp
    assert rasterize.rasterize(first) == first        # .png input passes through


def test_rasterize_missing_file_fails_explicitly(tmp_path):
    with pytest.raises(rasterize.RasterizeError, match="no such figure"):
        rasterize.rasterize(tmp_path / "nope.pdf")


def test_rasterize_garbage_fails_explicitly(tmp_path):
    bad = tmp_path / "fig1.pdf"
    bad.write_bytes(b"not a pdf")
    with pytest.raises(rasterize.RasterizeError, match="cannot rasterize"):
        rasterize.rasterize(bad)
