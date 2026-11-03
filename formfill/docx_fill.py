"""Fill the Malaysian Patents Form No. 22 and No. 17 Word templates.

The templates are edited in place: existing text, agent details, ticks and the
agent signature image are kept. Everything filled in is bold, with no underline
or strikethrough. Author / Last modified by metadata is blanked.

The code locates cells by the template's table layout (nested tables inside one
outer table). If the firm changes the templates, adjust the lookups below.
"""
from __future__ import annotations

import copy
import io
from dataclasses import dataclass, field
from datetime import date

import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

from .reference import date_parts


@dataclass
class FormData:
    reference: str
    title: str
    applicant_name: str
    applicant_address: str
    applicant_nationality: str
    inventors: list[str] = field(default_factory=list)
    inventor_nationality: str = ""
    inventor_address: str = ""
    sign_date: date | None = None  # Form 22 Section VII date
    under_opposition: bool = False  # Form 17: tick "No" unless told otherwise


class TemplateError(RuntimeError):
    pass


# --------------------------------------------------------------------------- helpers
def _run_props(p: Paragraph, superscript: bool = False):
    """Run properties copied from the paragraph mark, made bold, no underline/strike."""
    pPr = p._p.pPr
    if pPr is not None and pPr.find(qn("w:rPr")) is not None:
        rpr = copy.deepcopy(pPr.find(qn("w:rPr")))
    else:
        rpr = OxmlElement("w:rPr")
    for tag in ("w:u", "w:strike", "w:dstrike", "w:vertAlign"):
        for e in rpr.findall(qn(tag)):
            rpr.remove(e)
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        fonts.set(qn("w:ascii"), "Times New Roman")
        fonts.set(qn("w:hAnsi"), "Times New Roman")
        rpr.insert(0, fonts)
    if rpr.find(qn("w:b")) is None:
        fonts.addnext(OxmlElement("w:b"))
    if rpr.find(qn("w:bCs")) is None:
        rpr.find(qn("w:b")).addnext(OxmlElement("w:bCs"))
    if rpr.find(qn("w:sz")) is None:
        for tag in ("w:sz", "w:szCs"):
            e = OxmlElement(tag)
            e.set(qn("w:val"), "20")
            rpr.append(e)
    if superscript:
        v = OxmlElement("w:vertAlign")
        v.set(qn("w:val"), "superscript")
        lang = rpr.find(qn("w:lang"))
        if lang is not None:
            lang.addprevious(v)
        else:
            rpr.append(v)
    return rpr


def _clean_paragraph_mark(p: Paragraph):
    pPr = p._p.pPr
    if pPr is not None and pPr.find(qn("w:rPr")) is not None:
        rpr = pPr.find(qn("w:rPr"))
        for tag in ("w:u", "w:strike", "w:dstrike"):
            for e in rpr.findall(qn(tag)):
                rpr.remove(e)


def add_bold(p: Paragraph, text: str, superscript: bool = False):
    r = OxmlElement("w:r")
    r.append(_run_props(p, superscript))
    t = OxmlElement("w:t")
    t.text = text
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    r.append(t)
    p._p.append(r)
    _clean_paragraph_mark(p)


def add_lines_as_paragraphs(p: Paragraph, lines: list[str]):
    """First line into p, every further line into a copy of p (same formatting)."""
    prev = p._p
    for i, line in enumerate(lines):
        if i == 0:
            add_bold(p, line)
            continue
        new_p = copy.deepcopy(p._p)
        for r in new_p.findall(qn("w:r")):
            new_p.remove(r)
        prev.addnext(new_p)
        prev = new_p
        add_bold(Paragraph(new_p, p._parent), line)


def numbered(names: list[str]) -> list[str]:
    names = [n.strip() for n in names if n.strip()]
    if len(names) <= 1:
        return names
    return [f"{i}. {n}" for i, n in enumerate(names, 1)]


def raw_cell(table: Table, row: int, col: int) -> _Cell:
    """Cell by its position in the row XML (ignores grid spans)."""
    return _Cell(table._tbl.tr_lst[row].tc_lst[col], table)


def _finish(d: docx.document.Document) -> bytes:
    # no strikethrough anywhere (the template has a stray one on an empty paragraph mark)
    for tag in ("w:strike", "w:dstrike"):
        for e in list(d.element.body.iter(qn(tag))):
            e.getparent().remove(e)
    cp = d.core_properties
    cp.author = ""
    cp.last_modified_by = ""
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _check(cond: bool, msg: str):
    if not cond:
        raise TemplateError(f"Template layout not as expected: {msg}")


def _fix_inventor_table(tbl):
    """Delete stray cells outside the 3-column grid and make the table 3 columns wide."""
    grid = tbl.find(qn("w:tblGrid"))
    cols = grid.findall(qn("w:gridCol"))
    for tr in tbl.tr_lst:
        for tc in tr.tc_lst[3:]:
            tr.remove(tc)
        trPr = tr.find(qn("w:trPr"))
        if trPr is not None:
            for tag in ("w:gridAfter", "w:wAfter", "w:gridBefore", "w:wBefore"):
                for e in trPr.findall(qn(tag)):
                    trPr.remove(e)
    for gc in cols[3:]:
        grid.remove(gc)
    total = sum(int(gc.get(qn("w:w"))) for gc in grid.findall(qn("w:gridCol")))
    tblW = tbl.find(qn("w:tblPr")).find(qn("w:tblW"))
    if tblW is not None:
        tblW.set(qn("w:w"), str(total))
        tblW.set(qn("w:type"), "dxa")


# --------------------------------------------------------------------------- Form 22
def fill_form22(template: bytes, data: FormData) -> bytes:
    d = docx.Document(io.BytesIO(template))
    outer = d.tables[0]
    _check("Form No. 22" in outer.rows[0].cells[0].text, "first cell is not Patents Form No. 22")

    # file reference (top right box, empty paragraph under the label)
    ref_cell = outer.rows[1].cells[1]
    _check("file reference" in ref_cell.text, "file reference box")
    add_bold(ref_cell.paragraphs[1], data.reference)

    # II. title
    _check("TITLE OF INVENTION" in outer.rows[3].cells[0].text, "Section II")
    add_bold(outer.rows[3].cells[0].tables[0].rows[0].cells[0].paragraphs[0], data.title)

    # III. applicant
    t3 = outer.rows[4].cells[0].tables[0]
    _check(t3.rows[0].cells[0].text.strip() == "Name", "Section III table")
    add_bold(t3.rows[0].cells[2].paragraphs[0], data.applicant_name)
    add_bold(t3.rows[2].cells[2].paragraphs[0], data.applicant_nationality)
    add_bold(t3.rows[3].cells[2].paragraphs[0], data.applicant_address)

    # IV. inventors - one block, names one per line
    t4 = outer.rows[5].cells[0].tables[0]
    _check(t4.rows[0].cells[0].text.strip() == "Name", "Section IV table")
    _fix_inventor_table(t4._tbl)
    add_lines_as_paragraphs(t4.rows[0].cells[2].paragraphs[0], numbered(data.inventors))
    add_bold(t4.rows[2].cells[2].paragraphs[0], data.inventor_nationality)
    add_bold(t4.rows[3].cells[2].paragraphs[0], data.inventor_address)

    # VII. date
    t7 = outer.rows[8].cells[0].tables[0]
    date_row = next(
        (i for i, tr in enumerate(t7._tbl.tr_lst) if raw_cell(t7, i, 0).text.strip().startswith("Date")),
        None,
    )
    _check(date_row is not None, "Section VII Date row")
    if data.sign_date:
        p = raw_cell(t7, date_row, 1).paragraphs[0]
        day, suffix, rest = date_parts(data.sign_date)
        add_bold(p, day)
        add_bold(p, suffix, superscript=True)
        add_bold(p, rest)

    return _finish(d)


# --------------------------------------------------------------------------- Form 17
def fill_form17(template: bytes, data: FormData) -> bytes:
    d = docx.Document(io.BytesIO(template))
    outer = d.tables[0]
    _check("Form No. 17" in outer.rows[0].cells[0].text, "first cell is not Patents Form No. 17")

    ref_cell = outer.rows[1].cells[1]
    _check("file reference" in ref_cell.text, "file reference box")
    add_bold(ref_cell.paragraphs[1], data.reference)

    body = outer.rows[2].cells[0]
    t_app = body.tables[0]
    _check(t_app.rows[0].cells[0].text.strip() == "Name", "applicant table")
    add_bold(t_app.rows[0].cells[2].paragraphs[0], data.applicant_name)
    add_bold(t_app.rows[1].cells[2].paragraphs[0], data.applicant_address)

    # Title under "*patent application/patent no." (number stays blank)
    t_pat = next(
        (t for t in body.tables
         if any("*patent application/patent no." in raw_cell(t, 0, i).text
                for i in range(len(t._tbl.tr_lst[0].tc_lst)))),
        None,
    )
    _check(t_pat is not None, "patent application table")
    title_cell = raw_cell(t_pat, 1, 1)
    _check(title_cell.paragraphs[0].text.strip().startswith("Title"), "Title line under patent application")
    add_bold(title_cell.paragraphs[0], data.title)

    # "This patent is under opposition proceeding": tick No (default) or Yes
    _set_opposition(title_cell._tc, data.under_opposition)

    return _finish(d)


W14 = "http://schemas.microsoft.com/office/word/2010/wordml"


def _set_box(tc, checked: bool):
    for t in tc.iter(qn("w:t")):
        if t.text in ("\u2610", "\u2612"):
            t.text = "\u2612" if checked else "\u2610"
    for e in tc.iter(f"{{{W14}}}checked"):
        e.set(f"{{{W14}}}val", "1" if checked else "0")


def _set_opposition(container, yes: bool):
    """Find the 'This patent is under opposition proceeding' row and set Yes/No."""
    for tr in container.iter(qn("w:tr")):
        cells = list(tr.iter(qn("w:tc")))
        texts = ["".join(t.text or "" for t in c.iter(qn("w:t"))).strip() for c in cells]
        if texts and texts[0].startswith("This patent is under opposition"):
            try:
                yes_i, no_i = texts.index("Yes"), texts.index("No")
            except ValueError:
                break
            _set_box(cells[yes_i - 1], yes)
            _set_box(cells[no_i - 1], not yes)
            return
    raise TemplateError("Template layout not as expected: opposition Yes/No row")
