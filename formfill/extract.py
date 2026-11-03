"""Read an information sheet / instruction letter (PDF) with Claude and return
structured filing details. The PDF is sent as a document, so scanned letters work too.

Everything returned is a suggestion: the app shows it in an editable form and the
user checks it before any form is generated.
"""
from __future__ import annotations

import base64
from datetime import date

import anthropic

SYSTEM_PROMPT = """You read information sheets and instruction letters sent to a Malaysian patent
agent by foreign law firms, clients or agents (PCT national phase entries, divisionals,
Paris Convention / direct filings). Senders and layouts vary; read the whole document.

Rules:
- If the sheet has an original-language version (e.g. Chinese) and an English translation,
  use the English translation.
- Applicant: name and address. If the sheet says the applicant's name changed or rights were
  transferred, use the CURRENT applicant and mention it in flags.
- Inventors: names exactly as written, in the order on the sheet; one shared address if they
  share one. Set inventor_addresses_differ=true if inventors have different addresses.
- Title: exactly as on the sheet. Do not change it, even if a note says to amend it
  (mention such a note in flags).
- Nationality: country name only (China, Japan, United States, Germany), never adjectives or
  codes. If the sheet does not state the applicant's nationality, leave it null and add a flag.
- origin_country_code: ISO 3166-1 alpha-2 code of the country the application comes from
  (normally the applicant's country / priority country). Explain in flags if unclear.
- Ignore any reference numbers on the sheet ("Your Ref.", "Our Ref.", QO Ref., etc.).
- rights_basis: "employment", "assignment", "other" or null, based on what the sheet says.
- deadlines: every deadline or requested filing / reply date, with what it is for (ISO dates).
- flags: short notes the agent must see before filing: missing or unclear items, pending
  address or name changes, title notes, numbers or dates that don't match, unusual instructions.
- Never guess or invent details. Use null when something is not on the sheet.
Record the result with the record_filing_details tool."""

TOOL = {
    "name": "record_filing_details",
    "description": "Record the filing details read from the information sheet.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": ["string", "null"]},
            "applicant_name": {"type": ["string", "null"]},
            "applicant_address": {"type": ["string", "null"]},
            "applicant_nationality": {"type": ["string", "null"]},
            "inventors": {"type": "array", "items": {"type": "string"}},
            "inventor_address": {"type": ["string", "null"]},
            "inventor_addresses_differ": {"type": "boolean"},
            "inventor_nationality": {"type": ["string", "null"]},
            "origin_country_code": {"type": ["string", "null"]},
            "application_type": {"type": ["string", "null"],
                                  "description": "e.g. PCT national phase, Paris Convention, divisional"},
            "rights_basis": {"type": ["string", "null"], "enum": ["employment", "assignment", "other", None]},
            "deadlines": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"date": {"type": "string"}, "what": {"type": "string"}},
                    "required": ["date", "what"],
                },
            },
            "flags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["title", "applicant_name", "applicant_address", "inventors", "flags"],
    },
}


def extract_details(pdf_bytes: bytes, api_key: str, model: str, today: date | None = None) -> dict:
    client = anthropic.Anthropic(api_key=api_key)
    today = today or date.today()
    resp = client.messages.create(
        model=model,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        tools=[TOOL],
        tool_choice={"type": "tool", "name": TOOL["name"]},
        messages=[{
            "role": "user",
            "content": [
                {"type": "document",
                 "source": {"type": "base64", "media_type": "application/pdf",
                            "data": base64.standard_b64encode(pdf_bytes).decode()}},
                {"type": "text",
                 "text": f"Today is {today.isoformat()}. Extract the filing details. "
                         "Flag any deadline that is already past or within 14 days."},
            ],
        }],
    )
    for block in resp.content:
        if block.type == "tool_use":
            return dict(block.input)
    raise RuntimeError("Claude did not return filing details.")
