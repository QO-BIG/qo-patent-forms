"""File reference and date helpers.

File reference rule: N1N2N3 A1 A2A3 A4 / N4N5N6   e.g. 2611JFTP/116
  N1     last two digits of the year
  N2     1 = Patent
  N3     1 = Incoming
  A1, A4 first and second letter of the ORIGIN country code (JP, US, CN, DE ...)
  A2A3   initials of the person in charge (e.g. FT)
  N4-N6  running number (always supplied by the user, never guessed)
"""
from __future__ import annotations

from datetime import date


def build_reference(
    country_code: str,
    initials: str,
    running_no: str | int,
    year: int | None = None,
    patent: int = 1,
    incoming: int = 1,
) -> str:
    cc = (country_code or "").strip().upper()
    ini = (initials or "").strip().upper()
    rn = str(running_no or "").strip()
    if len(cc) != 2 or not cc.isalpha():
        raise ValueError("Origin country code must be two letters, e.g. CN, JP, US.")
    if len(ini) != 2 or not ini.isalpha():
        raise ValueError("Initials of the person in charge must be two letters, e.g. FT.")
    if not rn.isdigit():
        raise ValueError("Running number is required and must be digits only, e.g. 118.")
    yy = f"{(year or date.today().year) % 100:02d}"
    return f"{yy}{patent}{incoming}{cc[0]}{ini}{cc[1]}/{rn.zfill(3)}"


def file_stem(reference: str) -> str:
    """Reference without the slash, used in file names (2611CFTN/118 -> 2611CFTN118)."""
    return reference.replace("/", "")


def ordinal_suffix(day: int) -> str:
    if 11 <= day % 100 <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def date_parts(d: date) -> tuple[str, str, str]:
    """('23', 'rd', ' October 2026') -> rendered as 23rd October 2026 with superscript suffix."""
    return str(d.day), ordinal_suffix(d.day), f" {d.strftime('%B %Y')}"
