"""Read bank / card statements and Tally exports from Excel, CSV or (best effort) PDF into common rows.

Common row: {date, amount, direction, raw_description, ref, ledger?, invoice_no?, taxable?, gst?, currency?, fx_amount?}
Column names are auto-detected from a synonym list, and the header row is searched for in the first 40 lines
(bank statements start with account details, not the table).
"""
from __future__ import annotations
import csv
import io
import re
from datetime import date, datetime
import pandas as pd
from dateutil import parser as dparser

from app.engine.normalize import instrument_no as _instrument_from_text, detect_mode as _detect_mode

# Bank names as they appear in the statement preamble ("HDFC BANK LTD", "ICICI Bank Limited", "State Bank of India").
BANK_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("hdfc", re.compile(r"\bHDFC\b", re.I)),
    ("icici", re.compile(r"\bICICI\b", re.I)),
    ("sbi", re.compile(r"STATE BANK OF INDIA|\bSBI\b|\bSBIN\b", re.I)),
    ("axis", re.compile(r"\bAXIS BANK\b|\bUTIB\b", re.I)),
    ("kotak", re.compile(r"\bKOTAK\b|\bKKBK\b", re.I)),
    ("yes", re.compile(r"\bYES BANK\b|\bYESB\b", re.I)),
    ("idfc", re.compile(r"\bIDFC\b", re.I)),
    ("indusind", re.compile(r"\bINDUSIND\b|\bINDB\b", re.I)),
    ("bob", re.compile(r"BANK OF BARODA|\bBARB\b", re.I)),
    ("pnb", re.compile(r"PUNJAB NATIONAL BANK|\bPNB\b|\bPUNB\b", re.I)),
    ("canara", re.compile(r"\bCANARA\b|\bCNRB\b", re.I)),
    ("union", re.compile(r"UNION BANK OF INDIA|\bUBIN\b", re.I)),
    ("boi", re.compile(r"BANK OF INDIA|\bBKID\b", re.I)),
    ("indian", re.compile(r"\bINDIAN BANK\b|\bIDIB\b", re.I)),
    ("iob", re.compile(r"INDIAN OVERSEAS BANK|\bIOBA\b", re.I)),
    ("central", re.compile(r"CENTRAL BANK OF INDIA|\bCBIN\b", re.I)),
    ("federal", re.compile(r"\bFEDERAL BANK\b|\bFDRL\b", re.I)),
    ("hsbc", re.compile(r"\bHSBC\b", re.I)),
    ("citi", re.compile(r"\bCITIBANK\b|\bCITI BANK\b", re.I)),
    ("sc", re.compile(r"STANDARD CHARTERED|\bSCBL\b", re.I)),
    ("dbs", re.compile(r"\bDBS\b", re.I)),
    ("rbl", re.compile(r"\bRBL BANK\b|\bRATN\b", re.I)),
    ("idbi", re.compile(r"\bIDBI\b|\bIBKL\b", re.I)),
    ("au", re.compile(r"AU SMALL FINANCE|\bAUBL\b", re.I)),
    ("bandhan", re.compile(r"\bBANDHAN\b|\bBDBL\b", re.I)),
    ("karnataka", re.compile(r"KARNATAKA BANK|\bKARB\b", re.I)),
    ("kvb", re.compile(r"KARUR VYSYA|\bKVBL\b", re.I)),
    ("sib", re.compile(r"SOUTH INDIAN BANK|\bSIBL\b", re.I)),
    ("tmb", re.compile(r"TAMILNAD MERCANTILE|\bTMBL\b", re.I)),
    ("cub", re.compile(r"CITY UNION BANK|\bCIUB\b", re.I)),
    ("saraswat", re.compile(r"\bSARASWAT\b", re.I)),
]

PDF_PASSWORD_HELP = ("This PDF needs a password — for HDFC it is your Customer ID, for ICICI/Axis your date of birth (DDMMYYYY)")


def detect_bank(df: pd.DataFrame) -> str | None:
    """Scan the first 40 rows (the statement preamble) for a bank name; returns a short key or None."""
    lines = []
    for i in range(min(40, len(df))):
        lines.append(" ".join(str(v) for v in df.iloc[i].tolist() if not _is_blank(v)))
    text = "\n".join(lines)
    for key, rx in BANK_PATTERNS:
        if rx.search(text):
            return key
    return None

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


def _loose(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s)


def _pick(cols: list[str], names: list[str], exclude: set[str] = frozenset()) -> str | None:
    lc = {_norm(c): c for c in cols}
    for n in names:
        if n in lc and lc[n] not in exclude:
            return lc[n]
    for n in names:  # punctuation-insensitive: "Chq./Ref.No." == "chq/ref no", "Withdrawal Amt." == "withdrawal amt"
        for k, c in lc.items():
            if c not in exclude and _loose(k) == _loose(n):
                return c
    for n in names:  # startswith / contains fallback
        for k, c in lc.items():
            if c in exclude:
                continue
            if k.startswith(n) or (len(n) > 4 and n in k):
                return c
    return None


def _is_blank(v) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and pd.isna(v):
        return True
    return str(v).strip().lower() in ("", "nan", "none", "nat")


def _str(v) -> str | None:
    """Cell as a stripped string, or None for empty / NaN (never the string 'nan')."""
    return None if _is_blank(v) else str(v).strip()


def _drcr_in_cell(v) -> str | None:
    """Credit-card statements put the side inside the amount cell: '1,769.00 Dr', 'Cr 12,000.00'."""
    if v is None or isinstance(v, (int, float)):
        return None
    m = re.search(r"(?<![A-Za-z])(dr|cr|debit|credit)(?![A-Za-z])", str(v), re.I)
    if not m:
        return None
    return "credit" if m.group(1).lower().startswith("cr") else "debit"


def _money(v) -> float | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    if not s or s.lower() in ("nan", "none", "-", "--"):
        return None
    # "(500.00)", "-500", "500.00-" (trailing minus, SAP / some bank exports) are negatives
    neg = (s.startswith("(") and s.endswith(")")) or s.endswith("-") or s.startswith("-")
    s = s.replace(",", "")
    m = re.search(r"\d+(?:\.\d+)?", s)   # skip "Rs.", "INR", "₹", "Dr"/"Cr"
    if not m:
        return None
    val = float(m.group(0))
    return -val if neg else val


_DATE_SHAPES = re.compile(
    r"^\d{4}-\d{1,2}-\d{1,2}"                        # ISO 2026-04-01[ 00:00:00]
    r"|^\d{1,2}[-/. ]\d{1,2}[-/. ]\d{2,4}$"           # 01/04/2026, 1-4-26
    r"|^\d{1,2}[-/. ]?[A-Za-z]{3,9}[-/. ,]*\d{2,4}$"  # 01-Apr-26, 1 Apr 2026, 01Apr2026
    r"|^[A-Za-z]{3,9}[-/. ]\d{1,2},?[-/. ]\d{2,4}$"   # Apr 1, 2026
    r"|^\d{8}$"                                       # 20260401 (Tally)
)


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
    s = re.sub(r"\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?$", "", s, flags=re.I)  # drop a time part
    if not _DATE_SHAPES.match(s):
        return None   # "1", "Page 1 of 3", "MARCH 2026" are not transaction dates
    if re.fullmatch(r"\d{8}", s):
        try:
            return datetime.strptime(s, "%Y%m%d").date()
        except ValueError:
            return None
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:  # ISO: never day-first
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    try:
        return dparser.parse(s, dayfirst=True).date()
    except Exception:
        return None


def load_table(content: bytes, filename: str, pdf_password: str | None = None) -> pd.DataFrame:
    name = filename.lower()
    if not content or not content.strip():
        raise ValueError("The file is empty.")
    if name.endswith((".xlsx", ".xlsm", ".xls")):
        try:
            xls = pd.ExcelFile(io.BytesIO(content))
        except Exception as e:  # noqa: BLE001 — openpyxl/xlrd raise many different types
            raise ValueError(f"Could not open this Excel file: {e}") from e
        best = None
        for sheet in xls.sheet_names:
            df = xls.parse(sheet, header=None, dtype=object)
            if _find_header(df) is not None and (best is None or len(df) > len(best)):
                best = df
        return best if best is not None else xls.parse(xls.sheet_names[0], header=None, dtype=object)
    if name.endswith((".csv", ".txt", ".tsv")):
        text = content.decode("utf-8-sig", errors="replace")
        sep = "\t" if name.endswith(".tsv") or text.count("\t") > text.count(",") else ","
        # Bank CSVs start with a narrow preamble ("Kotak Mahindra Bank,,,") followed by a wider table.
        # pandas would treat the first line as the column count and drop every wider row, so read
        # with the csv module and pad every row to the widest one.
        rows = list(csv.reader(io.StringIO(text), delimiter=sep))
        rows = [r for r in rows if any(c.strip() for c in r)]
        if not rows:
            raise ValueError("The file is empty.")
        width = max(len(r) for r in rows)
        rows = [[c if c.strip() != "" else None for c in r] + [None] * (width - len(r)) for r in rows]
        return pd.DataFrame(rows, dtype=object)
    if name.endswith(".pdf"):
        return _pdf_table(content, pdf_password)
    raise ValueError("Unsupported file type. Upload Excel (.xlsx/.xls), CSV, or PDF.")


def _is_password_error(e: BaseException) -> bool:
    """pdfplumber wraps pdfminer's PDFPasswordIncorrect in PdfminerException(inner) — look at the wrapper, its
    message, its args and its cause."""
    seen = []
    stack: list[BaseException] = [e]
    while stack:
        x = stack.pop()
        if x in seen:
            continue
        seen.append(x)
        for txt in (type(x).__name__, str(x), repr(x)):
            t = txt.lower()
            if "password" in t or "encrypt" in t or "decrypt" in t:
                return True
        stack += [a for a in getattr(x, "args", ()) if isinstance(a, BaseException)]
        for link in (x.__cause__, x.__context__):
            if link:
                stack.append(link)
    return False


def _pdf_table(content: bytes, pdf_password: str | None = None) -> pd.DataFrame:
    try:
        import pdfplumber  # optional
    except ImportError as e:
        raise ValueError("PDF reading needs pdfplumber; upload the Excel/CSV version of the statement instead.") from e
    rows = []
    try:
        with pdfplumber.open(io.BytesIO(content), password=pdf_password or None) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    rows.extend(table)
    except ValueError:
        raise
    except Exception as e:  # noqa: BLE001 — pdfminer raises PDFPasswordIncorrect / PDFEncryptionError, pypdfium its own types
        if _is_password_error(e):
            raise ValueError(PDF_PASSWORD_HELP) from e
        raise ValueError(f"Could not read this PDF ({type(e).__name__}). Upload the Excel/CSV version instead.") from e
    if not rows:
        raise ValueError("Could not find a table in this PDF. Upload the Excel/CSV version instead.")
    width = max(len(r) for r in rows)
    rows = [list(r) + [None] * (width - len(r)) for r in rows]
    return pd.DataFrame(rows, dtype=object)


def parse_rows(content: bytes, filename: str, source_kind: str, pdf_password: str | None = None) -> tuple[list[dict], str, int]:
    """Returns (rows, detected_format, skipped)."""
    rows, fmt, skipped, _bank = parse_rows_ex(content, filename, source_kind, pdf_password)
    return rows, fmt, skipped


def parse_rows_ex(content: bytes, filename: str, source_kind: str, pdf_password: str | None = None) -> tuple[list[dict], str, int, str | None]:
    """Returns (rows, detected_format, skipped, bank) — bank is a short key ("hdfc", "icici", ...) found in the
    statement preamble, or None."""
    df = load_table(content, filename, pdf_password)
    bank = detect_bank(df) if source_kind != "tally" else None
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
    for r in body.to_dict("records"):
        d = _date(r.get(c_date))
        if not d:
            # Tally Day Book: the voucher's ledger lines follow the party line with a blank date.
            if fmt == "tally_register" and rows and c_desc and _str(r.get(c_desc)) and rows[-1].get("_vtype"):
                _daybook_ledger_line(rows[-1], _str(r.get(c_desc)), _money(r.get(c_debit)) if c_debit else None,
                                     _money(r.get(c_credit)) if c_credit else None)
                continue
            skipped += 1
            continue
        desc = (_str(r.get(c_desc)) or "") if c_desc else ""
        n2 = _str(r.get(c_narr2)) if c_narr2 else None
        if n2:
            desc = f"{desc} | {n2}" if desc else n2
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
                in_cell = _drcr_in_cell(r.get(c_amount))
                if typ.startswith("cr") or typ.startswith("credit") or typ.startswith("deposit"):
                    direction = "credit"
                elif typ.startswith("dr") or typ.startswith("debit") or typ.startswith("withdraw"):
                    direction = "debit"
                elif in_cell:
                    direction = in_cell
                else:
                    direction = "credit" if av < 0 and source_kind != "tally" else "debit"
                amount = abs(av)
        if amount is None or not desc and not c_ref:
            skipped += 1
            continue
        if not desc:
            desc = _str(r.get(c_ref)) or ""
        vtype = _norm(r.get(c_vtype)) if c_vtype else ""
        if fmt == "tally_register" and vtype and not any(k in vtype for k in ("purchase", "payment", "journal", "debit note", "credit note", "receipt")):
            skipped += 1
            continue
        if fmt == "tally_register" and vtype:
            # In a Tally register the Debit/Credit columns are the ledger side (party is credited on a purchase),
            # not the cash direction. Money-in vouchers are credits; everything else is money out.
            direction = "credit" if ("credit note" in vtype or "receipt" in vtype) else "debit"
        ref = _str(r.get(c_ref)) if c_ref else None
        instrument = _instrument_from_text(desc)
        if not instrument and ref and fmt != "tally_register" and _detect_mode(desc) == "cheque" and re.fullmatch(r"\d{3,8}", ref):
            instrument = ref   # bank statements put the cheque number in the Chq/Ref column
        rows.append({
            "date": d, "amount": round(amount, 2), "direction": direction, "raw_description": desc[:1000],
            "ref": ref, "instrument_no": instrument,
            "ledger": _str(r.get(c_ledger)) if c_ledger else None,
            "taxable": _money(r.get(c_tax)) if c_tax else None,
            "gst": _money(r.get(c_gst)) if c_gst else None,
            "fx_amount": _money(r.get(c_fx)) if c_fx else None,
            "_vtype": vtype, "_party": desc,
        })
    if fmt == "tally_register":
        rows = _finish_daybook(rows)
    for r in rows:
        for k in ("_vtype", "_party", "_ledgers", "_gst"):
            r.pop(k, None)
        if fmt == "tally_register" and not r.get("instrument_no"):
            r["instrument_no"] = _instrument_from_text(r["raw_description"])   # ledger lines may carry "Chq No: 000412"
    return rows, fmt, skipped, bank


_BOOK_LEDGER_RE = re.compile(r"\bBANK\b|\bCASH\b|\bA/C\b|\bCASH CREDIT\b|\bCURRENT ACCOUNT\b|\bPETTY CASH\b", re.I)
_GST_LEDGER_RE = re.compile(r"\b[ICS]GST\b|\bGST\b|\bCESS\b", re.I)
_SKIP_LEDGER_RE = re.compile(r"\bTDS\b|ROUND", re.I)


def _daybook_ledger_line(voucher: dict, name: str, dv: float | None, cv: float | None) -> None:
    """Attach one ledger line (row without a date) to the voucher above it."""
    amt = abs(dv or cv or 0.0)
    voucher.setdefault("_ledgers", []).append((name, amt))
    if _GST_LEDGER_RE.search(name) and not re.search(r"ROUND", name, re.I):
        voucher["_gst"] = round(voucher.get("_gst", 0.0) + amt, 2)
        return
    if _SKIP_LEDGER_RE.search(name):
        return
    # Payment / receipt vouchers head with the bank or cash ledger; the party is the first other ledger.
    if _BOOK_LEDGER_RE.search(voucher["_party"]) and not _BOOK_LEDGER_RE.search(name):
        voucher["_party"] = name
        voucher["raw_description"] = name
        return
    if _BOOK_LEDGER_RE.search(name):
        return
    if not voucher.get("ledger"):
        voucher["ledger"] = name
    narr = voucher["raw_description"]
    voucher["raw_description"] = (f"{narr} | {name}" if "|" not in narr else f"{narr}, {name}")[:1000]


def _finish_daybook(rows: list[dict]) -> list[dict]:
    """Day Book clean-up: derive taxable/GST from ledger lines, and drop Payment vouchers for parties that also
    have a Purchase voucher (the purchase carries the invoice; the bank statement carries the cash)."""
    any_ledgers = any(r.get("_ledgers") for r in rows)
    if not any_ledgers:
        return rows
    for r in rows:
        if r.get("_gst") and r.get("gst") is None:
            r["gst"] = r["_gst"]
            if r.get("taxable") is None:
                r["taxable"] = round(r["amount"] - r["_gst"], 2)
    purchase_parties = {r["_party"].strip().upper() for r in rows if "purchase" in r.get("_vtype", "")}
    return [r for r in rows if not ("payment" in r.get("_vtype", "") and r["_party"].strip().upper() in purchase_parties)]
