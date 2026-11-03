"""Add the file reference and title onto a client-signed Form 17 PDF.

Use only where the client has confirmed the signed copy may be reused for other
applications. The signature, signatory, capacity and date are never touched.

Text is drawn with an EMBEDDED TrueType font (Times New Roman Bold by default).
Times New Roman is licensed by Microsoft, so do not commit timesbd.ttf to a public
repository: put it in ./fonts/ in a private repo, or upload it in the app.
If no font file is given, Liberation Serif Bold (metric-compatible, free) is used
when installed; the PDF base-14 "Times-Bold" is the last resort (not embedded, so
viewers substitute their own font and it can look off).
"""
from __future__ import annotations

import io
import os
from dataclasses import dataclass

import pikepdf
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


@dataclass
class SignedForm17Profile:
    """Positions in PDF points, measured from the TOP-LEFT of the page."""
    name: str
    ref_xy: tuple[float, float]          # page 1, file reference box
    title_xy: tuple[float, float]        # page 2, after "Title:" under *patent application
    title_max_x: float                   # wrap title before this x
    title_line_gap: float = 11.0
    whiteout: tuple[float, float, float, float] | None = None  # page 2 dotted leader x, y_top, w, h
    font_size: float = 10.0
    # page 2 "This patent is under opposition proceeding" -> "No" box (x0, y_top, x1, y_bottom)
    opposition_no_box: tuple[float, float, float, float] | None = None
    opposition_yes_box: tuple[float, float, float, float] | None = None


# Profile for "OP2626-MY-0834.Executed Form 17.pdf" (CALB GROUP CO., LTD., signed 2026.7.28)
CALB_PROFILE = SignedForm17Profile(
    name="CALB GROUP CO., LTD.",
    ref_xy=(302.5, 248.5),
    title_xy=(138.0, 115.0),
    title_max_x=500.0,
    whiteout=(136.0, 113.5, 263.0, 10.0),
    opposition_no_box=(359.0, 130.1, 366.2, 137.5),
    opposition_yes_box=(309.6, 129.4, 316.8, 136.6),
)

PROFILES = {CALB_PROFILE.name: CALB_PROFILE}

_FALLBACK_TTFS = [
    "fonts/timesbd.ttf",
    "C:/Windows/Fonts/timesbd.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Times_New_Roman_Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
]


def _register_font(font_bytes: bytes | None) -> tuple[str, str]:
    """Return (reportlab font name, human description)."""
    if font_bytes:
        pdfmetrics.registerFont(TTFont("FormBold", io.BytesIO(font_bytes)))
        return "FormBold", "uploaded font"
    for path in _FALLBACK_TTFS:
        if os.path.exists(path):
            name = "FormBold_" + os.path.basename(path).split(".")[0]
            pdfmetrics.registerFont(TTFont(name, path))
            return name, os.path.basename(path)
    return "Times-Bold", "base-14 Times-Bold (not embedded)"


def _wrap(text: str, font: str, size: float, width: float) -> list[str]:
    lines = [""]
    for word in text.split():
        trial = f"{lines[-1]} {word}".strip()
        if stringWidth(trial, font, size) <= width or not lines[-1]:
            lines[-1] = trial
        else:
            lines.append(word)
    return lines


def _tick(c: canvas.Canvas, page_h: float, box: tuple[float, float, float, float]):
    """Draw an X inside a printed checkbox, matching the form's other ticked boxes."""
    x0, y_top, x1, y_bot = box
    inset = 0.9
    c.setLineWidth(0.7)
    c.setStrokeColorRGB(0, 0, 0)
    c.line(x0 + inset, page_h - y_top - inset, x1 - inset, page_h - y_bot + inset)
    c.line(x0 + inset, page_h - y_bot + inset, x1 - inset, page_h - y_top - inset)


def overlay_signed_form17(
    signed_pdf: bytes,
    reference: str,
    title: str,
    profile: SignedForm17Profile = CALB_PROFILE,
    font_bytes: bytes | None = None,
    under_opposition: bool = False,
) -> tuple[bytes, str]:
    """Return (new PDF bytes, font description)."""
    pdf = pikepdf.open(io.BytesIO(signed_pdf))
    if len(pdf.pages) < 2:
        raise ValueError("Expected a 2-page signed Form 17.")
    w, h = (float(v) for v in pdf.pages[0].mediabox[2:4])

    font, font_desc = _register_font(font_bytes)
    size = profile.font_size

    ov_buf = io.BytesIO()
    c = canvas.Canvas(ov_buf, pagesize=(w, h))
    # page 1: reference
    c.setFont(font, size)
    c.drawString(profile.ref_xy[0], h - profile.ref_xy[1], reference)
    c.showPage()
    # page 2: title
    if profile.whiteout:
        x, y_top, ww, hh = profile.whiteout
        c.setFillColorRGB(1, 1, 1)
        c.rect(x, h - y_top - hh, ww, hh, stroke=0, fill=1)
        c.setFillColorRGB(0, 0, 0)
    c.setFont(font, size)
    lines = _wrap(title, font, size, profile.title_max_x - profile.title_xy[0])
    if len(lines) > 2:
        raise ValueError("Title is too long for two lines on this signed form.")
    for i, line in enumerate(lines):
        c.drawString(profile.title_xy[0], h - profile.title_xy[1] - i * profile.title_line_gap, line)
    # opposition proceeding: tick "No" unless told otherwise
    box = profile.opposition_yes_box if under_opposition else profile.opposition_no_box
    if box is None and under_opposition:
        raise ValueError("This profile has no position for the 'Yes' box.")
    if box:
        _tick(c, h, box)
    c.showPage()
    c.save()

    ov = pikepdf.open(io.BytesIO(ov_buf.getvalue()))
    pdf.pages[0].add_overlay(ov.pages[0])
    pdf.pages[1].add_overlay(ov.pages[1])

    # strip author / creator metadata
    pdf.docinfo = pdf.make_indirect(pikepdf.Dictionary())
    if "/Metadata" in pdf.Root:
        del pdf.Root["/Metadata"]

    out = io.BytesIO()
    pdf.save(out)
    return out.getvalue(), font_desc
