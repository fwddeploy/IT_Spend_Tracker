"""Tally XML export (Day Book / Purchase Register exported with Ctrl+E -> XML)."""
from __future__ import annotations
import re
import xml.etree.ElementTree as ET
from datetime import datetime

from app.engine.normalize import instrument_no as _instrument_from_text


_BOOK_LEDGER_RE = re.compile(r"\bBANK\b|\bCASH\b|\bA/C\b|\bCASH CREDIT\b|\bCURRENT ACCOUNT\b|\bPETTY CASH\b", re.I)


def _text(el, tag):
    x = el.find(tag)
    return (x.text or "").strip() if x is not None and x.text else ""


def parse_tally_xml(content: bytes) -> tuple[list[dict], str, int]:
    text = content.decode("utf-8", errors="replace")
    # Tally XML often contains control chars / bare ampersands
    text = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;|#)", "&amp;", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    root = ET.fromstring(text)
    rows, skipped = [], 0
    for v in root.iter("VOUCHER"):
        vtype = (v.get("VCHTYPE") or _text(v, "VOUCHERTYPENAME")).lower()
        if not any(k in vtype for k in ("purchase", "payment", "journal", "debit note", "credit note")):
            skipped += 1
            continue
        d = _text(v, "DATE")
        try:
            dt = datetime.strptime(d, "%Y%m%d").date()
        except ValueError:
            skipped += 1
            continue
        party = _text(v, "PARTYLEDGERNAME") or _text(v, "PARTYNAME")
        narration = _text(v, "NARRATION")
        vno = _text(v, "VOUCHERNUMBER")
        # cheque number: Bank Allocations (<BANKALLOCATIONS.LIST><INSTRUMENTNUMBER>) or the narration ("Chq No: 000412")
        instrument = None
        for ba in v.iter("BANKALLOCATIONS.LIST"):
            n = _text(ba, "INSTRUMENTNUMBER") or _text(ba, "CHEQUENUMBER")
            if n and re.search(r"\d{3,}", n):
                instrument = re.sub(r"\D", "", n)
                break
        instrument = instrument or _instrument_from_text(narration)
        ledgers, amount, expense_ledger = [], 0.0, None
        for le in list(v.iter("ALLLEDGERENTRIES.LIST")) + list(v.iter("LEDGERENTRIES.LIST")):
            name = _text(le, "LEDGERNAME")
            amt = _text(le, "AMOUNT")
            try:
                a = float(amt.replace(",", ""))
            except ValueError:
                a = 0.0
            ledgers.append((name, a))
            if name and name != party and not re.search(r"gst|igst|cgst|sgst|round|tds|bank|cash", name, re.I):
                expense_ledger = expense_ledger or name
            if name == party:
                amount = abs(a)
        # Payment / receipt vouchers name the bank or cash ledger as "party"; the real party is the other ledger.
        if _BOOK_LEDGER_RE.search(party or "") and expense_ledger:
            party, expense_ledger = expense_ledger, None
            amount = next((abs(a) for n, a in ledgers if n == party), 0.0)
        if not amount:
            amount = max((abs(a) for _, a in ledgers), default=0.0)
        if not amount:
            skipped += 1
            continue
        taxable = None
        gst = 0.0
        for name, a in ledgers:
            if re.search(r"igst|cgst|sgst|gst", name, re.I) and not re.search(r"round", name, re.I):
                gst += abs(a)
        if gst:
            taxable = round(amount - gst, 2)
        rows.append({
            "date": dt, "amount": round(amount, 2), "direction": "credit" if "credit note" in vtype else "debit",
            "raw_description": f"{party} | {narration}".strip(" |"), "ref": vno or None, "ledger": expense_ledger,
            "taxable": taxable, "gst": gst or None, "fx_amount": None, "instrument_no": instrument,
            "_vtype": vtype, "_party": party.upper(),
        })
    # A payment voucher that settles a purchase voucher is the same bill twice: the purchase carries the invoice
    # (amount, GST, narration); the bank statement carries the cash. Keep payment vouchers only for parties
    # with no purchase voucher (cash / cheque payments booked straight to the party, rule 2.37).
    purchase_parties = {r["_party"] for r in rows if "purchase" in r["_vtype"]}
    rows = [r for r in rows if not ("payment" in r["_vtype"] and r["_party"] in purchase_parties)]
    for r in rows:
        r.pop("_vtype"), r.pop("_party")
    return rows, "tally_xml", skipped
