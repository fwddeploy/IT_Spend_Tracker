"""Tally XML export (Day Book / Purchase Register exported with Ctrl+E -> XML)."""
from __future__ import annotations
import re
import xml.etree.ElementTree as ET
from datetime import datetime


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
            "taxable": taxable, "gst": gst or None, "fx_amount": None,
        })
    return rows, "tally_xml", skipped
