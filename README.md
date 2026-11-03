# Patents Form No. 22 & No. 17 filler

A Streamlit app for QO Patent that fills the Malaysian **Patents Form No. 22** and **Patents Form No. 17**
from a foreign agent's information sheet or instruction letter.

1. Upload the sheet (PDF). Claude reads it and suggests the title, applicant, inventors, origin country,
   deadlines and anything that needs attention (address changes, title notes, rights basis…).
2. Check and edit every field. Enter the running number (never guessed).
3. Generate:
   - Form 22 (.docx) and Form 17 (.docx) from the firm's Word templates, or
   - Form 17 (.pdf) from a client-signed copy (e.g. CALB), adding only the file reference and title.

## Rules built in

- Everything filled in is **bold**; template text, agent details, ticks and signature image are kept.
- No underline or strikethrough in filled text; *Author* and *Last modified by* are blanked.
- Nationality as a country name; I.C./Passport No. keeps the template's "-".
- Form 22 Section IV: one block, inventors one per line, numbered when there is more than one;
  stray cells outside the table grid are removed.
- Form 22 Section VII date: e.g. 3<sup>rd</sup> November 2026 (Malaysia time, editable).
- Form 17: patent application number, signature, signatory, capacity and date stay blank.
- Form 17 page 2, "This patent is under opposition proceeding": **No** is ticked unless the
  sheet says otherwise (tick the option in the app to switch to Yes). Applies to the Word form and
  to client-signed PDFs.
- File reference `N1N2N3 A1 A2A3 A4 / N4N5N6`, e.g. `2611CFTN/128`;
  file names `2611CFTN128 - Patent Form No. 22.docx`.

## Project layout

```
app.py                     Streamlit UI
formfill/reference.py      file reference + ordinal date helpers
formfill/docx_fill.py      Form 22 / Form 17 Word filling
formfill/pdf17.py          overlay on a client-signed Form 17 PDF (profiles per client)
formfill/extract.py        Claude extraction (PDF sent as a document, so scans work)
templates/                 put the two .docx templates here (git-ignored)
fonts/                     optional timesbd.ttf for signed PDFs (git-ignored)
tests/                     pytest
```

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # add your Anthropic API key
streamlit run app.py
pytest -q
```

## Deploy on Streamlit Community Cloud

1. Push this repo to GitHub. **Use a private repository** – the templates contain the agent's
   signature image and client work is confidential.
2. On share.streamlit.io, create an app from the repo with `app.py` as the entry point.
3. In *App settings → Secrets* add:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   CLAUDE_MODEL = "claude-sonnet-4-5"
   ```
4. Either commit the templates to the private repo (remove `templates/*.docx` from `.gitignore`)
   or upload them in the sidebar each session.
5. `packages.txt` installs Liberation fonts as a fallback for signed-PDF text.

## Signed Form 17 PDFs and fonts

`formfill/pdf17.py` has a profile per client-signed form (positions in points from the top-left).
`CALB_PROFILE` matches `OP2626-MY-0834.Executed Form 17.pdf`. For a new client, measure the
positions of the reference box and the "Title:" line and add a profile.

Text is drawn with an **embedded** TrueType font. For real Times New Roman, upload `timesbd.ttf`
in the app or place it in `fonts/` (private repo only – it is a licensed Microsoft font).
Without it, Liberation Serif Bold (same metrics) is used.

Only use a signed copy where the client has confirmed it may be reused. The app never changes
the signature, signatory, capacity or signing date.

## Notes

- Claude's output is a suggestion; always review the fields before generating.
- The Word filling relies on the current template layout. If the templates change, update the
  lookups in `formfill/docx_fill.py` (the code raises a clear error if the layout differs).
