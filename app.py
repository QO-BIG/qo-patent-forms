"""QO Patent – Patents Form No. 22 / No. 17 filler (Streamlit).

Run locally:  streamlit run app.py
"""
from __future__ import annotations

import io
import os
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

from formfill.docx_fill import FormData, TemplateError, fill_form17, fill_form22
from formfill.pdf17 import PROFILES, overlay_signed_form17
from formfill.reference import build_reference, file_stem

TZ = ZoneInfo("Asia/Kuala_Lumpur")
TEMPLATE_DIR = Path(__file__).parent / "templates"
FONT_DIR = Path(__file__).parent / "fonts"
DEFAULT_MODEL = "claude-sonnet-4-5"

st.set_page_config(page_title="Patent Forms 17 & 22", page_icon="📄", layout="wide")


def secret(name: str, default: str = "") -> str:
    try:
        return st.secrets.get(name, os.environ.get(name, default))
    except Exception:  # no secrets.toml
        return os.environ.get(name, default)


def load_bytes(uploaded, fallback: Path) -> bytes | None:
    if uploaded is not None:
        return uploaded.getvalue()
    return fallback.read_bytes() if fallback.exists() else None


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("Settings")
    initials = st.text_input("Person in charge (initials)", value="FT", max_chars=2).upper()
    patent_digit = st.text_input("N2 (1 = Patent)", value="1", max_chars=1)
    incoming_digit = st.text_input("N3 (1 = Incoming)", value="1", max_chars=1)

    st.subheader("Templates")
    up22 = st.file_uploader("Form 22 template (.docx)", type="docx", key="t22")
    up17 = st.file_uploader("Form 17 template (.docx)", type="docx", key="t17")
    tpl22 = load_bytes(up22, TEMPLATE_DIR / "Patents Form No. 22.docx")
    tpl17 = load_bytes(up17, TEMPLATE_DIR / "Patents Form No. 17.docx")
    st.caption(f"Form 22: {'ready' if tpl22 else 'missing'} · Form 17: {'ready' if tpl17 else 'missing'}")

    st.subheader("Claude")
    configured_key = secret("ANTHROPIC_API_KEY")
    key_override = st.text_input(
        "Anthropic API key override (leave blank to use the one configured in Secrets)",
        value="", type="password",
    )
    api_key = key_override or configured_key
    st.caption("Using key from Secrets" if (configured_key and not key_override) else
               ("Using key entered above" if api_key else "No key configured"))
    model = st.text_input("Model", value=secret("CLAUDE_MODEL", DEFAULT_MODEL))

st.title("Patents Form No. 22 & No. 17")

# ------------------------------------------------------------------ 1. sheet
st.subheader("1. Information sheet / instruction letter")
sheet = st.file_uploader("Upload the PDF", type="pdf", key="sheet")
if sheet and st.button("Read with Claude", disabled=not api_key):
    from formfill.extract import extract_details

    with st.spinner("Reading the sheet…"):
        try:
            st.session_state["x"] = extract_details(sheet.getvalue(), api_key, model,
                                                    today=datetime.now(TZ).date())
        except Exception as e:  # show API / parsing errors to the user
            st.error(f"Extraction failed: {e}")
if sheet and not api_key:
    st.info("Add an Anthropic API key in the sidebar to read the sheet automatically, "
            "or fill in the fields below by hand.")

x = st.session_state.get("x", {})

if x.get("flags") or x.get("deadlines"):
    with st.container(border=True):
        st.markdown("**Check before filing**")
        for d in x.get("deadlines", []):
            st.markdown(f"- Deadline **{d.get('date')}** – {d.get('what')}")
        for f in x.get("flags", []):
            st.markdown(f"- {f}")
        if x.get("inventor_addresses_differ"):
            st.warning("Inventors have different addresses – Form 22 has one address field.")
        rb = x.get("rights_basis")
        if rb and rb != "employment":
            st.warning(f"Rights basis on the sheet: **{rb}**. The template ticks 'by virtue of employment'.")

# ------------------------------------------------------------------ 2. details
st.subheader("2. Details (check and edit)")
c1, c2 = st.columns(2)
with c1:
    title = st.text_area("Title (exactly as on the sheet)", value=x.get("title") or "", height=80)
    applicant_name = st.text_input("Applicant name", value=x.get("applicant_name") or "")
    applicant_address = st.text_area("Applicant address", value=x.get("applicant_address") or "", height=80)
    applicant_nat = st.text_input("Applicant nationality (country name)",
                                  value=x.get("applicant_nationality") or "")
with c2:
    inventors_txt = st.text_area("Inventors (one per line, in sheet order)",
                                 value="\n".join(x.get("inventors") or []), height=120)
    inventor_nat = st.text_input("Inventor nationality (country name)",
                                 value=x.get("inventor_nationality") or "")
    inventor_address = st.text_area("Inventors' address", value=x.get("inventor_address") or "", height=80)

c3, c4, c5 = st.columns(3)
with c3:
    origin = st.text_input("Origin country code (A1/A4)", value=(x.get("origin_country_code") or "").upper(),
                           max_chars=2)
with c4:
    running = st.text_input("Running number (N4N5N6) – required", value="")
with c5:
    sign_date = st.date_input("Form 22 Section VII date", value=datetime.now(TZ).date(), format="DD/MM/YYYY")

reference = ""
try:
    reference = build_reference(origin, initials, running, year=datetime.now(TZ).year,
                                patent=int(patent_digit or 1), incoming=int(incoming_digit or 1))
    st.success(f"File reference: **{reference}**")
except ValueError as e:
    st.caption(str(e))

# ------------------------------------------------------------------ 3. output
st.subheader("3. Forms")
o1, o2, o3 = st.columns(3)
want22 = o1.checkbox("Form 22 (Word)", value=True)
want17 = o2.checkbox("Form 17 (Word template)", value=True)
want17s = o3.checkbox("Form 17 from client-signed PDF", value=False)
under_opposition = st.checkbox(
    "Form 17: patent IS under opposition proceeding (tick 'Yes')", value=False,
    help="Leave unticked unless the sheet says so – Form 17 then ticks 'No'.")

signed_pdf = font_file = None
profile_name = None
if want17s:
    st.caption("Only for clients who confirmed their signed Form 17 may be reused. "
               "Signature, signatory and date are left untouched.")
    profile_name = st.selectbox("Signed-copy profile", list(PROFILES))
    signed_pdf = st.file_uploader("Signed Form 17 (PDF)", type="pdf", key="signed")
    font_file = st.file_uploader("Times New Roman Bold (timesbd.ttf) – optional if in ./fonts", type="ttf")

inventors = [l.strip() for l in inventors_txt.splitlines() if l.strip()]
missing = [n for n, v in [("title", title), ("applicant name", applicant_name),
                          ("applicant address", applicant_address), ("applicant nationality", applicant_nat),
                          ("reference", reference)] if not v.strip()]
if want22:
    missing += [n for n, v in [("inventors", "x" if inventors else ""), ("inventor nationality", inventor_nat),
                               ("inventor address", inventor_address)] if not v.strip()]
if want22 and not tpl22:
    missing.append("Form 22 template")
if want17 and not tpl17:
    missing.append("Form 17 template")
if want17s and not signed_pdf:
    missing.append("signed Form 17 PDF")

if missing:
    st.warning("Missing: " + ", ".join(missing))

if st.button("Generate", type="primary", disabled=bool(missing)):
    data = FormData(
        reference=reference, title=title.strip(), applicant_name=applicant_name.strip(),
        applicant_address=" ".join(applicant_address.split()), applicant_nationality=applicant_nat.strip(),
        inventors=inventors, inventor_nationality=inventor_nat.strip(),
        inventor_address=" ".join(inventor_address.split()), sign_date=sign_date,
        under_opposition=under_opposition,
    )
    stem = file_stem(reference)
    files: dict[str, bytes] = {}
    try:
        if want22:
            files[f"{stem} - Patent Form No. 22.docx"] = fill_form22(tpl22, data)
        if want17:
            files[f"{stem} - Patent Form No. 17.docx"] = fill_form17(tpl17, data)
        if want17s:
            font_bytes = font_file.getvalue() if font_file else None
            if font_bytes is None and (FONT_DIR / "timesbd.ttf").exists():
                font_bytes = (FONT_DIR / "timesbd.ttf").read_bytes()
            pdf, font_desc = overlay_signed_form17(signed_pdf.getvalue(), reference, data.title,
                                                   PROFILES[profile_name], font_bytes,
                                                   under_opposition=under_opposition)
            files[f"{stem} - Patent Form No. 17.pdf"] = pdf
            if "timesbd" not in font_desc and font_desc != "uploaded font":
                st.info(f"Signed PDF text used {font_desc}. Upload timesbd.ttf for real Times New Roman.")
    except (TemplateError, ValueError) as e:
        st.error(str(e))
    else:
        st.session_state["files"] = files

for name, blob in st.session_state.get("files", {}).items():
    mime = ("application/pdf" if name.endswith(".pdf")
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    st.download_button(f"Download {name}", blob, file_name=name, mime=mime, key=f"dl-{name}")

if len(st.session_state.get("files", {})) > 1:
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w") as z:
        for name, blob in st.session_state["files"].items():
            z.writestr(name, blob)
    st.download_button("Download all (.zip)", zbuf.getvalue(), file_name=f"{file_stem(reference)}.zip")
