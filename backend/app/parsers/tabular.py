"""Read bank / card statements and Tally exports from Excel, CSV or (best effort) PDF into common rows.

Common row: {date, amount, direction, raw_description, ref, ledger?, invoice_no?, taxable?, gst?, currency?, fx_amount?}
Column names are auto-detected from a synonym list, and the header row is searched for in the first 40 lines
(bank statements start with account details, not the table).
"""
from __future__ import annotations
import io
import re
from datetime import date, datetime
import pandas as pd
from dateutil import parser as dparser

SYN = {
    "date": ["txn date", "transaction date", "tran date", "value date", "date", "posting date", "voucher date", "vch date", "bill date", "invoice date"],
    "desc": ["narration", "description", "transaction details", "transaction remarks", "remarks", "details", "particulars", "merchant", "party", "party name", "supplier", "vendor", "account name", "beneficiary", "name"],
    "party": ["particulars", "party name", "party", "supplier", "supplier name", "vendor", "vendor name", "account name", "beneficiary", "name", "merchant"],
    "debit": ["withdrawal amt", "withdrawal amount", "withdrawal", "withdrawals", "debit amount", "debit amt", "debit", "dr amount", "dr", "paid", "amount paid", "withdrawal (dr)", "debit (dr)"],
    "credit": ["deposit amt", "deposit amount", "deposit", "deposits", "credit amount", "credit amt", "credit", "cr amount", "cr", "received", "deposit (cr)", "credit (cr)"],
    "amount": ["amount", "transaction amount", "txn amount", "amount (inr)", "amount inr", "gross total", "grand total", "invoice value", "value", "total", "bill amount", "net amount", "amount (rs.)"],
    "drcr": ["dr/cr", "cr/dr", "type", "transaction type", "dr / cr", "debit/credit"],
    "ref": ["chq/ref no", "chq / ref no", "cheque no", "ref no", "reference", "ref", "utr", "chq no", "instrument no", "voucher no", "vch no", "vch no.", "voucher no.", "invoice no", "bill no", "invoice number", "bill no."],
    "ledger": ["ledger", "expense head", "account", "head", "ledger name", "purchase ledger", "under"],
    "taxable": ["taxable value", "taxable", "taxable amount", "assessable value"],
    "gst": ["gst", "total tax", "tax amount", "igst", "cgst", "sgst", "tax"],
    "narr2": ["narration", "remarks", "description"],
    "fx": ["foreign amount", "transaction currency amount", "original amount", "fx amount"],
    "vtype": ["vch type", "voucher type", "vch type."],
}


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower().replace("\n", " ")) if s is not None else ""


def _find_header(df: pd.DataFrame) -> int | None:
    for i in range(min(40, len(df))):
        vals = [_norm(v) for v in df.iloc[i].tolist()]
        has_date = any(v in SYN["date"] or v.startswith("date") for v in vals)
        has_desc = any(v in SYN["desc"] for v in vals)
        has_amt = any(v in SYN["debit"] or v in SYN["amount"] or v in SYN["credit"] or "amount" in v or "withdrawal" in v or "debit" in v for v in vals)
        if has_date and (has_desc or has_amt) and has_amt:
            return i
    return None


def _pick(cols: list[str], names: list[str], exclude: set[str] = frozenset()) -> str | None:
    lc = {_norm(c): c for c in cols}
    for n in names:
        if n in lc and lc[n] not in exclude:
            return lc[n]
    for n in names:  # startswith / contains fallback
        for k, c in lc.items():
            if c in exclude:
                continue
            if k.startswith(n) or (len(n) > 4 and n in k):
                return c
    return None


def _money(v) -> float | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    if not s or s.lower() in ("nan", "none", "-", "--"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = re.sub(r"[^\d.\-]", "", s.replace(",", ""))
    if s in ("", "-", "."):
        return None
    try:
        val = float(s)
    except ValueError:
        return None
    return -val if neg else val


def _date(v) -> date | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (datetime, pd.Timestamp)):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    if not s:
        return None
    # Tally exports sometimes use "1-Apr-26"; banks "01/04/2026"; Excel serials
    if re.fullmatch(r"\d{5}", s):
        try:
            return (pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(s))).date()
        except Exception:
            return None
    try:
        return dparser.parse(s, dayfirst=True, fuzzy=True).date()
    except Exception:
        return None


def load_table(content: bytes, filename: str) -> pd.DataFrame:
    name = filename.lower()
    if name.endswith((".xlsx", ".xlsm", ".xls")):
        xls = pd.ExcelFile(io.BytesIO(content))
        best = None
        for sheet in xls.sheet_names:
            df = xls.parse(sheet, header=None, dtype=object)
            if _find_header(df) is not None and (best is None or len(df) > len(best)):
                best = df
        return best if best is not None else xls.parse(xls.sheet_names[0], header=None, dtype=object)
    if name.endswith((".csv", ".txt", ".tsv")):
        text = content.decode("utf-8-sig", errors="replace")
        sep = "\t" if name.endswith(".tsv") or text.count("\t") > text.count(",") else ","
        return pd.read_csv(io.StringIO(text), header=None, dtype=object, sep=sep, engine="python", on_bad_lines="skip")
    if name.endswith(".pdf"):
        return _pdf_table(content)
    raise ValueError("Unsupported file type. Upload Excel (.xlsx/.xls), CSV, or PDF.")


def _pdf_table(content: bytes) -> pd.DataFrame:
    try:
        import pdfplumber  # optional
    except ImportError as e:
        raise ValueError("PDF reading needs pdfplumber; upload the Excel/CSV version of the statement instead.") from e
    rows = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                rows.extend(table)
    if not rows:
        raise ValueError("Could not find a table in this PDF. Upload the Excel/CSV version instead.")
    width = max(len(r) for r in rows)
    rows = [list(r) + [None] * (width - len(r)) for r in rows]
    return pd.DataFrame(rows, dtype=object)


def parse_rows(content: bytes, filename: str, source_kind: str) -> tuple[list[dict], str, int]:
    """Returns (rows, detected_format, skipped)."""
    df = load_table(content, filename)
    h = _find_header(df)
    if h is None:
        raise ValueError("Could not find the header row (Date / Narration / Withdrawal or Amount). "
                         "Export the statement as Excel from net banking and upload that.")
    header = [_norm(v) for v in df.iloc[h].tolist()]
    body = df.iloc[h + 1:].copy()
    body.columns = [c if c else f"col{i}" for i, c in enumerate(header)]
    cols = list(body.columns)

    c_date = _pick(cols, SYN["date"])
    c_vtype = _pick(cols, SYN["vtype"])
    if source_kind == "tally" or c_vtype:
        c_desc = _pick(cols, SYN["party"]) or _pick(cols, SYN["desc"])
    else:
        c_desc = _pick(cols, SYN["desc"])
    c_debit = _pick(cols, SYN["debit"])
    c_credit = _pick(cols, SYN["credit"], exclude={c_debit} if c_debit else set())
    c_amount = _pick(cols, SYN["amount"], exclude={c for c in (c_debit, c_credit) if c})
    c_drcr = _pick(cols, SYN["drcr"])
    c_ref = _pick(cols, SYN["ref"])
    c_ledger = _pick(cols, SYN["ledger"], exclude={c_desc} if c_desc else set())
    c_tax = _pick(cols, SYN["taxable"])
    c_gst = _pick(cols, SYN["gst"], exclude={c for c in (c_tax, c_amount) if c})
    c_narr2 = _pick(cols, SYN["narr2"], exclude={c_desc} if c_desc else set())
    c_fx = _pick(cols, SYN["fx"])

    if not c_date or not (c_debit or c_amount):
        raise ValueError("Found a table but not a Date plus Withdrawal/Debit/Amount column.")

    fmt = "tally_register" if (c_vtype or source_kind == "tally") else ("bank_debit_credit" if c_debit else "bank_single_amount")
    rows, skipped = [], 0
    for _, r in body.iterrows():
        d = _date(r.get(c_date))
        if not d:
            skipped += 1
            continue
        desc = str(r.get(c_desc) or "").strip() if c_desc else ""
        if c_narr2 and r.get(c_narr2) is not None and str(r.get(c_narr2)).strip() not in ("", "nan"):
            desc = f"{desc} | {str(r.get(c_narr2)).strip()}" if desc else str(r.get(c_narr2)).strip()
        amount, direction = None, None
        if c_debit:
            dv = _money(r.get(c_debit))
            cv = _money(r.get(c_credit)) if c_credit else None
            if dv and dv > 0:
                amount, direction = dv, "debit"
            elif cv and cv > 0:
                amount, direction = cv, "credit"
        if amount is None and c_amount:
            av = _money(r.get(c_amount))
            if av is not None and av != 0:
                typ = _norm(r.get(c_drcr)) if c_drcr else ""
                if typ.startswith("cr") or typ.startswith("credit") or typ.startswith("deposit"):
                    direction = "credit"
                elif typ.startswith("dr") or typ.startswith("debit") or typ.startswith("withdraw"):
                    direction = "debit"
                else:
                    direction = "credit" if av < 0 and source_kind != "tally" else "debit"
                amount = abs(av)
        if amount is None or not desc and not c_ref:
            skipped += 1
            continue
        if not desc:
            desc = str(r.get(c_ref) or "")
        vtype = _norm(r.get(c_vtype)) if c_vtype else ""
        if fmt == "tally_register" and vtype and not any(k in vtype for k in ("purchase", "payment", "journal", "debit note", "credit note", "receipt")):
            skipped += 1
            continue
        if fmt == "tally_register" and "credit note" in vtype:
            direction = "credit"
        rows.append({
            "date": d, "amount": round(amount, 2), "direction": direction, "raw_description": desc[:1000],
            "ref": (str(r.get(c_ref)).strip() if c_ref and r.get(c_ref) is not None else None),
            "ledger": (str(r.get(c_ledger)).strip() if c_ledger and r.get(c_ledger) is not None else None),
            "taxable": _money(r.get(c_tax)) if c_tax else None,
            "gst": _money(r.get(c_gst)) if c_gst else None,
            "fx_amount": _money(r.get(c_fx)) if c_fx else None,
        })
    return rows, fmt, skipped
