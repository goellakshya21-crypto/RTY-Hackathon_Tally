"""Talks to TallyPrime's built-in XML server and turns replies into plain Python data."""
from __future__ import annotations

import os
import re
import socket
import threading
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime
from xml.sax.saxutils import escape

TALLY_URL = os.environ.get("TALLY_URL", "http://localhost:9000")
TIMEOUT = float(os.environ.get("TALLY_TIMEOUT", "30"))

# TallyPrime serves one request at a time on its UI thread; queue ours instead of piling them up.
_one_at_a_time = threading.Lock()


class TallyError(RuntimeError):
    pass


# ---------- transport ----------

def _post(xml: str) -> str:
    req = urllib.request.Request(
        TALLY_URL, data=xml.encode("utf-8"),
        headers={"Content-Type": "text/xml; charset=utf-8"}, method="POST")
    try:
        with _one_at_a_time, urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
    except (socket.timeout, TimeoutError) as e:
        raise TallyError(
            f"TallyPrime at {TALLY_URL} accepted the request but didn't answer within {TIMEOUT:.0f}s. "
            "If its window shows 'Not Responding', close and reopen TallyPrime. If it is just a very "
            "large company, raise TALLY_TIMEOUT.") from e
    except OSError as e:
        raise TallyError(
            f"Could not reach TallyPrime at {TALLY_URL} ({e}). Make sure TallyPrime is open with a "
            "company loaded, and that F1 > Settings > Connectivity has 'TallyPrime acts as' = Both/Server "
            "on this port.") from e
    for enc in ("utf-8", "utf-16"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


# Swappable for tests / offline demo
transport = _post

_BAD_REF = re.compile(r"&#(?:x0*[0-8bcef]|x0*1[0-9a-f]|0*[0-8]|0*1[1-2]|0*1[4-9]|0*2[0-9]|0*3[01]);", re.I)
_PREFIX = re.compile(r"(</?)([A-Za-z]\w*):(?=\w)")
_BAD_CHR = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def parse_xml(text: str) -> ET.Element:
    """Tally emits control-character refs like &#4; that break normal XML parsers."""
    text = _BAD_CHR.sub("", _BAD_REF.sub("", text)).lstrip("﻿")
    # Tally uses undeclared prefixes (<UDF:HSNCODE>); make them plain tag names (UDF_HSNCODE).
    text = _PREFIX.sub(r"\1\2_", text)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise TallyError(f"Tally returned unreadable XML: {e}. First 300 chars: {text[:300]!r}") from e
    err = root.findtext(".//LINEERROR")
    if err:
        raise TallyError(f"Tally error: {err.strip()}")
    return root


# ---------- values ----------

def to_tally_date(d: str | date | None) -> str | None:
    if d is None or d == "":
        return None
    if isinstance(d, date):
        return d.strftime("%Y%m%d")
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y%m%d", "%d-%b-%Y"):
        try:
            return datetime.strptime(d.strip(), fmt).strftime("%Y%m%d")
        except ValueError:
            pass
    raise TallyError(f"Don't understand the date {d!r}; use YYYY-MM-DD")


def from_tally_date(s: str | None) -> str:
    if not s:
        return ""
    s = s.strip()
    try:
        return datetime.strptime(s, "%Y%m%d").strftime("%d %b %Y")
    except ValueError:
        return s


_NUM = re.compile(r"-?\(?-?[\d,]*\.?\d+\)?")


def to_number(s: str | None) -> float:
    """'-1,500.00', '(-)1500', '10 Nos', '₹ 25.00/Nos' -> float. Empty -> 0."""
    if not s:
        return 0.0
    s = s.strip().replace("(-)", "-")
    m = _NUM.search(s)
    if not m:
        return 0.0
    t = m.group(0).replace(",", "").replace("(", "").replace(")", "")
    try:
        return float(t)
    except ValueError:
        return 0.0


def unit_of(s: str | None) -> str:
    if not s:
        return ""
    m = re.search(r"[\d.,]+\s*([A-Za-z][A-Za-z.]*)", s)
    return m.group(1) if m else ""


def yes(s: str | None) -> bool:
    return (s or "").strip().lower() == "yes"


def text(el: ET.Element, tag: str) -> str:
    v = el.findtext(tag)
    return v.strip() if v else ""


# ---------- requests ----------

def _static_vars(company: str | None, from_date: str | None, to_date: str | None) -> str:
    parts = ["<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>"]
    if company:
        parts.append(f"<SVCURRENTCOMPANY>{escape(company)}</SVCURRENTCOMPANY>")
    # Dates MUST go as typed dates in d-Mon-yyyy form. Sending SVFROMDATE + SVTODATE as plain
    # YYYYMMDD (e.g. 20250401) sends TallyPrime into an endless loop: its window freezes at 100% CPU
    # and only a restart recovers it (found with diagnose.py on TallyPrime's integration sandbox).
    if from_date:
        parts.append(f'<SVFROMDATE TYPE="Date">{tdl_date(from_date)}</SVFROMDATE>')
    if to_date:
        parts.append(f'<SVTODATE TYPE="Date">{tdl_date(to_date)}</SVTODATE>')
    return "".join(parts)


def collection(obj_type: str, fetch: list[str], *, company=None, from_date=None, to_date=None,
               filters: dict[str, str] | None = None, child_of: str | None = None) -> list[ET.Element]:
    """Export a TDL collection and return the object elements (LEDGER, VOUCHER, ...)."""
    cid = "MCP" + re.sub(r"\W", "", obj_type)
    filt_names = ",".join(filters) if filters else ""
    formulae = "".join(
        f'<SYSTEM TYPE="Formulae" NAME="{n}">{escape(f)}</SYSTEM>' for n, f in (filters or {}).items())
    xml = (
        "<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST>"
        f"<TYPE>Collection</TYPE><ID>{cid}</ID></HEADER><BODY><DESC>"
        f"<STATICVARIABLES>{_static_vars(company, from_date, to_date)}</STATICVARIABLES>"
        f'<TDL><TDLMESSAGE><COLLECTION NAME="{cid}" ISMODIFY="No"><TYPE>{obj_type}</TYPE>'
        + (f"<CHILDOF>{escape(child_of)}</CHILDOF>" if child_of else "")
        + f"<FETCH>{','.join(fetch)}</FETCH>"
        + (f"<FILTERS>{filt_names}</FILTERS>" if filt_names else "")
        + f"</COLLECTION>{formulae}</TDLMESSAGE></TDL></DESC></BODY></ENVELOPE>"
    )
    root = parse_xml(send(xml))
    coll = root.find(".//COLLECTION")
    items = list(coll) if coll is not None else []
    # An empty answer can mean "nothing matched" or "no company is open" - Tally replies the same way
    # (its CMPINFO block is all zeros in every reply, so it can't tell us). Ask which one it is.
    if not items and obj_type != "Company" and not collection("Company", ["Name"]):
        raise TallyError("TallyPrime is running but no company is open. Open (load) a company in Tally "
                         "with Alt+F3 / 'Select Company', then ask again.")
    return items


def raw(xml: str) -> ET.Element:
    return parse_xml(send(xml))


def report(name: str, *, company=None, from_date=None, to_date=None, explode=False) -> ET.Element:
    """Export one of Tally's built-in reports ('Trial Balance', 'Profit and Loss', 'Balance Sheet')."""
    sv = _static_vars(company, from_date, to_date) + ("<EXPLODEFLAG>Yes</EXPLODEFLAG>" if explode else "")
    xml = ("<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Data</TYPE>"
           f"<ID>{escape(name)}</ID></HEADER><BODY><DESC><STATICVARIABLES>{sv}</STATICVARIABLES>"
           "</DESC></BODY></ENVELOPE>")
    root = parse_xml(send(xml))
    if len(root) == 0 and not collection("Company", ["Name"]):
        raise TallyError("TallyPrime is running but no company is open. Open (load) a company in Tally "
                         "with Alt+F3 / 'Select Company', then ask again.")
    return root


_PLAIN_SV_DATE = re.compile(r"<(SV(?:FROM|TO)DATE)(?:\s[^>]*)?>\s*(\d{8})\s*</\1>", re.I)


def make_dates_safe(xml: str) -> str:
    """Rewrite <SVFROMDATE>20250401</SVFROMDATE> as <SVFROMDATE TYPE="Date">1-Apr-2025</SVFROMDATE>.
    The plain form freezes TallyPrime, and raw_request lets an agent write its own XML."""
    return _PLAIN_SV_DATE.sub(lambda m: f'<{m.group(1)} TYPE="Date">{tdl_date(m.group(2))}</{m.group(1)}>', xml)


def send(xml: str) -> str:
    return transport(make_dates_safe(xml))


_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def tdl_date(d: str) -> str:
    """YYYY-MM-DD (or YYYYMMDD) -> '1-Apr-2026', the form Tally documents for dates.
    Month names are spelled out here so a non-English Windows locale can't change them."""
    dt = datetime.strptime(to_tally_date(d), "%Y%m%d")
    return f"{dt.day}-{_MONTHS[dt.month - 1]}-{dt.year}"
