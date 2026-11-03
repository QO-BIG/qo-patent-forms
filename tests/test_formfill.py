from datetime import date
from pathlib import Path

import docx
import pytest

from formfill.docx_fill import FormData, fill_form17, fill_form22
from formfill.reference import build_reference, date_parts, file_stem

TPL = Path(__file__).parents[1] / "templates"


def test_reference():
    assert build_reference("jp", "ft", "116", year=2026) == "2611JFTP/116"
    assert build_reference("CN", "AI", 94, year=2026) == "2611CAIN/094"
    assert file_stem("2611CFTN/128") == "2611CFTN128"
    with pytest.raises(ValueError):
        build_reference("CN", "FT", "", year=2026)


def test_ordinals():
    assert date_parts(date(2026, 11, 3)) == ("3", "rd", " November 2026")
    assert date_parts(date(2026, 11, 12))[1] == "th"
    assert date_parts(date(2026, 10, 22))[1] == "nd"


DATA = FormData(
    reference="2611CFTN/128", title="BATTERY APPARATUS", applicant_name="CALB GROUP CO., LTD.",
    applicant_address="No. 1 Jiangdong Road, Jintan District, Changzhou, Jiangsu 213000, P.R. China",
    applicant_nationality="China", inventors=["WU, Binjie", "YANG, Liu", "ZHANG, Yongjie"],
    inventor_nationality="China",
    inventor_address="No. 1 Jiangdong Road, Jintan District, Changzhou, Jiangsu 213000, P.R. China",
    sign_date=date(2026, 11, 3),
)


@pytest.mark.skipif(not (TPL / "Patents Form No. 22.docx").exists(), reason="template not present")
def test_form22(tmp_path):
    out = fill_form22((TPL / "Patents Form No. 22.docx").read_bytes(), DATA)
    p = tmp_path / "f22.docx"; p.write_bytes(out)
    d = docx.Document(p)
    text = "\n".join(c.text for t in d.tables for r in t.rows for c in r.cells)
    for s in ("2611CFTN/128", "BATTERY APPARATUS", "1. WU, Binjie", "3. ZHANG, Yongjie", " November 2026", "superscript"):
        assert s in d.element.body.xml or s in text
    assert d.core_properties.author == "" and d.core_properties.last_modified_by == ""


@pytest.mark.skipif(not (TPL / "Patents Form No. 17.docx").exists(), reason="template not present")
def test_form17(tmp_path):
    out = fill_form17((TPL / "Patents Form No. 17.docx").read_bytes(), DATA)
    p = tmp_path / "f17.docx"; p.write_bytes(out)
    xml = docx.Document(p).element.body.xml
    assert "2611CFTN/128" in xml and "BATTERY APPARATUS" in xml


@pytest.mark.skipif(not (TPL / "Patents Form No. 17.docx").exists(), reason="template not present")
@pytest.mark.parametrize("yes", [False, True])
def test_form17_opposition(tmp_path, yes):
    from dataclasses import replace
    out = fill_form17((TPL / "Patents Form No. 17.docx").read_bytes(), replace(DATA, under_opposition=yes))
    p = tmp_path / "f.docx"; p.write_bytes(out)
    xml = docx.Document(p).element.body.xml
    i = xml.index("This patent is under opposition")
    seg = xml[i:i + 20000]
    boxes = [c for c in seg if c in "\u2610\u2612"][:2]
    assert boxes == (["\u2612", "\u2610"] if yes else ["\u2610", "\u2612"])
