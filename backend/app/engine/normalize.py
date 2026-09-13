"""Clean a raw statement narration into a comparable payee name and detect how it was paid."""
import re

# Bank prefixes and noise that carry no vendor information.
_PREFIX_RE = re.compile(
    r"^((?:TO|BY)\s+TRANSFER[- ]*|POS\s*\d*\s*|VIN/|IIN/|BIL/ONL/|BIL/|MMT/|NEFT[-/ ]|RTGS[-/ ]|IMPS[-/ ]|UPI[-/ ]|"
    r"N?ACH\s*D(?:R)?[-/ ]*|N?ACH/|SI\s+|ME\s+DC\s+SI\s*|DC\s+SI\s*|ECOM\s*PUR/?|ECOM/|ATM/|TPT/|INB/|FT/|IB\s+BILLPAY\s+DR[- ]*|IB\s+|"
    r"NET\s*BANKING\s*|PCD/|EDC/|ME\s+)",
    re.I,
)
_TXN_ID_RE = re.compile(r"\b[A-Z]{0,4}\d{6,}\b")  # long numeric / alnum references
_DATE_RE = re.compile(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b|\b\d{8}\b")
_CARD_FRAG_RE = re.compile(r"\b(?:XX+|\*+)\d{2,4}\b|\b\d{1,6}X{3,}\d{0,4}\b|\bX{4,}\b", re.I)
_FX_TAIL_RE = re.compile(r"\b(USD|EUR|GBP|SGD|AED|AUD|CAD|CHF|JPY)\s*[\d.,]+\b", re.I)
_SUFFIX_WORDS = [
    "PVT LTD", "PRIVATE LIMITED", "PVT. LTD.", "PVT.LTD", "PVT LTD.", "LIMITED", "LTD", "LLP", "INC", "INC.", "LLC",
    "CORPORATION", "CO.", "PLC", "SA", "S.A.", "GMBH", "PTE",
    "DUBLIN", "SINGAPORE", "REDMOND WA", "REDMOND", "IRELAND", "MOUNTAIN VIEW", "SAN FRANCISCO", "SAN JOSE", "SEATTLE",
    "USA", "US", "UK", "IN", "INDIA", "BANGALORE", "BENGALURU", "MUMBAI", "HYDERABAD", "CHENNAI", "PUNE", "DELHI",
    "NOIDA", "GURGAON", "GURUGRAM", "KOLKATA", "AHMEDABAD", "COIMBATORE",
]
# (?<![.\w]) keeps "ZOOM.US", "BUSY.IN", "GODADDY.COM": a dotted domain suffix is part of the name, not a country.
_SUFFIX_RE = re.compile(r"(?<![.\w])(" + "|".join(re.escape(w) for w in _SUFFIX_WORDS) + r")\b\.?", re.I)

MODE_PATTERNS = [
    ("upi", re.compile(r"\bUPI\b|@[a-z]+\b", re.I)),
    ("neft", re.compile(r"\bNEFT\b", re.I)),
    ("rtgs", re.compile(r"\bRTGS\b", re.I)),
    ("imps", re.compile(r"\bIMPS\b", re.I)),
    ("cheque", re.compile(r"\bCHQ\b|\bCHEQUE\b|\bCLG\b|\bMICR\b", re.I)),
    ("nach", re.compile(r"\bACH\b|\bNACH\b|\bECS\b|\bMANDATE\b", re.I)),
    ("si", re.compile(r"^SI\s|\bSTANDING INSTR|\bDC\s+SI\b", re.I)),
    ("card", re.compile(r"\bPOS\b|\bECOM\b|\bVIN/|\bIIN/|\bPCD/|\bEDC/|\bCARD\b|\bINTL\b|\bE-?COM\b", re.I)),
    ("netbanking", re.compile(r"\bBIL/ONL\b|\bBILLPAY\b|\bINB\b|\bTPT\b|\bNET\s*BANKING\b|\bIB\s", re.I)),
    ("cash", re.compile(r"\bCASH\b", re.I)),
]

AUTO_MODES = {"card", "si", "nach"}


def detect_mode(raw: str) -> str:
    for mode, rx in MODE_PATTERNS:
        if rx.search(raw or ""):
            return mode
    return "unknown"


_VPA_RE = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]{1,60})@([A-Za-z][A-Za-z0-9]*)")
_VPA_PSP_TAIL = re.compile(r"[._-]?(rzp|razorpay|payu|paytm|ybl|okaxis|oksbi|okicici|okhdfcbank|axl|ptaxis|ptsbi|ptyes|ibl|upi)$", re.I)


def _upi_payee(raw: str) -> str | None:
    """UPI narrations look like UPI/123456/tallysolutions.rzp@hdfcbank/remark/bank. The VPA carries the merchant."""
    if not re.search(r"\bUPI\b", raw, re.I) and "@" not in raw:
        return None
    for m in _VPA_RE.finditer(raw):
        handle = _VPA_PSP_TAIL.sub("", m.group(1))
        # phone-number / QR-id handles ("9876543210@ybl", "paytmqr2810...") say nothing about the merchant
        if re.fullmatch(r"[\d.\-_]+", handle) or re.match(r"(paytmqr|q\d{6,}|bharatpe\d)", handle, re.I):
            continue
        if len(re.sub(r"[^A-Za-z]", "", handle)) < 3:
            continue
        return handle.replace(".", " ").replace("_", " ").replace("-", " ").upper()
    m = re.search(r"UPI[/-]([^/]*)[/-]([^/]*)[/-]?([^/]*)", raw, re.I)
    if not m:
        return None
    for p in [p for p in m.groups() if p]:
        if "@" in p or sum(ch.isdigit() for ch in p) > len(p) / 2:
            continue
        if re.search(r"[A-Za-z]{3,}", p) and p.strip().upper() not in _SKIP_SEGMENTS:
            return p.upper()
    return None


_SEGMENT_MODES = re.compile(r"^(?:(?:TO|BY)\s+TRANSFER[- ]*)?(NEFT|RTGS|IMPS|BIL|MMT|TPT|INB|FT|IB|CLG|CHQ|N?ACH|NACH|PCD|EDC)\b", re.I)
_ID_LIKE = re.compile(r"^[A-Z]{0,5}\d{5,}[A-Z0-9]*$|^\d+$|^[A-Z]\d+$", re.I)
# Bank short codes / IFSC prefixes that sit between the mode and the beneficiary in NEFT/IMPS narrations.
_BANK_CODE = re.compile(
    r"^(?:[A-Z]{4}0[A-Z0-9]{6}"                                                   # IFSC: HDFC0000001
    r"|HDFC|ICIC|ICICI|SBIN|SBI|UTIB|AXIS|KKBK|KOTAK|YESB|IDIB|PUNB|BARB|CNRB|UBIN|IOBA|INDB|FDRL|HSBC|CITI|SCBL|DBSS|"
    r"BKID|MAHB|CBIN|IBKL|RATN|KVBL|SIBL|TMBL|CIUB|AUBL|BDBL|ESFB|UCBA|PSIB|IDFB|PYTM|FINO)$",
    re.I,
)
_SKIP_SEGMENTS = {
    "ONL", "OFF", "DR", "CR", "P2A", "P2M", "MB", "IB", "NB", "SI", "N", "R", "MICR CTS", "CTS", "MICR", "PAID", "PAYMENT",
    "BILLPAY", "TRANSFER", "TO", "BY", "NEFT", "RTGS", "IMPS", "UPI", "INB IMPS", "INB", "MMT", "TPT", "ACH", "NACH", "ECS",
    "PCD", "EDC", "PAY", "PYMT", "PMT", "TRF", "OTH", "COLLECT", "PPI", "INTERNET", "MOBILE", "BANKING", "CARD", "BILL",
}


def _segment_payee(raw: str) -> str | None:
    """'NEFT-N000123-SHREE INFOTECH-TSS RENEWAL' -> 'SHREE INFOTECH'. Segments are split on - / | *,
    the mode word, bank codes and id-like segments are dropped, and the first real name segment is the payee."""
    if not _SEGMENT_MODES.match(raw.strip()):
        return None
    segs = [s.strip() for s in re.split(r"[-/|*]", raw) if s.strip()]
    segs = segs[1:]  # drop the mode
    for s in segs:
        su = s.upper()
        if su in _SKIP_SEGMENTS or re.fullmatch(r"(INB|IB|MB)\s+(IMPS|NEFT|RTGS|UPI)", su):
            continue
        if _ID_LIKE.match(s) or len(s) < 3:
            continue
        if re.fullmatch(r"[\d\s.,]+", s) or re.fullmatch(r"[\dX*]{6,}", su):   # masked card "4123XXXXXXXX5678"
            continue
        if _BANK_CODE.match(su) or re.fullmatch(r"[A-Z]{3,5}X{2,}", su):   # HDFC, KKBK0000001, HDFCXX
            continue
        # a segment that is mostly digits is an id, not a name
        if sum(ch.isdigit() for ch in s) > len(s) / 2:
            continue
        return su
    return None


# Cheque / instrument numbers (rule 2.37): "CHQ 000412", "CHEQUE NO. 412", "Chq No: 000412", "Ch. No 000412",
# "MICR 000412", Tally "Cheque 000412". The number is 3-8 digits (banks pad to 6).
_INSTRUMENT_RE = re.compile(
    r"\b(?:CHQ|CHEQUE|CHECK|CH|MICR|INSTRUMENT|INST)\b\.?\s*(?:NO|NUM|NUMBER|#)?\.?\s*[:#\-]?\s*(\d{3,8})\b", re.I)
_BARE_CHEQUE_RE = re.compile(r"^\s*(?:CHQ|CHEQUE|CLG|MICR)(?:\s+(?:PAID|NO\.?|NUMBER|#))?\s*[:#\-]?\s*(\d{3,8})\s*$", re.I)


def instrument_no(raw: str) -> str | None:
    """Cheque / instrument number from a narration, or None. For cheque-mode bank lines that carry the number
    only as a trailing token ("CHQ PAID-MICR CTS-ABC COMPUTERS-000412") the last 6-digit token is taken."""
    if not raw:
        return None
    m = _INSTRUMENT_RE.search(raw)
    if m:
        return m.group(1)
    if detect_mode(raw) == "cheque":
        toks = re.findall(r"(?<![\dX])\d{6}(?![\dX])", raw)
        if toks:
            return toks[-1]
    return None


def same_instrument(a: str | None, b: str | None) -> bool:
    """Compare the last 6 digits, leading zeros ignored ("000412" == "412" == "CHQ412")."""
    if not a or not b:
        return False
    da = re.sub(r"\D", "", a)[-6:].lstrip("0")
    db = re.sub(r"\D", "", b)[-6:].lstrip("0")
    return bool(da) and da == db


def clean_payee(raw: str) -> str:
    """Uppercase, strip prefixes, ids, dates, card fragments, legal/city suffixes, collapse spaces."""
    if not raw:
        return ""
    s = raw.strip()
    # a bare cheque line has no payee: keep the instrument number so Tally can supply the party (2.37)
    m = _BARE_CHEQUE_RE.match(s)
    if m:
        return f"CHQ {m.group(1)}"
    # Tally-style "Party | narration": the party is the payee
    if "|" in s and not _SEGMENT_MODES.match(s):
        s = s.split("|", 1)[0].strip()
    upi = _upi_payee(s)
    seg = _segment_payee(s)
    if upi:
        s = upi
    elif seg:
        s = seg
    s = s.upper()
    s = _PREFIX_RE.sub("", s)
    s = _PREFIX_RE.sub("", s)  # twice: "NEFT-UTR-NAME" then leading junk
    s = _FX_TAIL_RE.sub(" ", s)
    s = re.sub(r"\b\d{3}[- ]\d{3}[- ]\d{4}\b", " ", s)   # US-style phone numbers in card descriptors (ZOOM.US 888-799-9666)
    s = _CARD_FRAG_RE.sub(" ", s)
    s = _DATE_RE.sub(" ", s)
    s = _TXN_ID_RE.sub(" ", s)
    s = re.sub(r"[/\\|,;:_]+", " ", s)
    s = re.sub(r"\bUTR\b|\bREF\b|\bTXN\b|\bTRF\b|\bTRANSFER\b|\bPAYMENT\b|\bPMT\b|\bTO\b|\bECOM\b|\bPOS\b|\bINTL\b|\bPUR\b", " ", s)
    s = _SUFFIX_RE.sub(" ", s)
    s = re.sub(r"[^A-Z0-9*.&@ ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" .-")
    if s in ("", "CHQ", "CHEQUE", "CLG", "MICR", "CHQ PAID", "MICR CTS", "CTS", "CHQ PAID MICR CTS"):
        n = instrument_no(raw)
        if n:
            return f"CHQ {n}"
    return s


def payee_tokens(clean: str) -> list[str]:
    return [t for t in re.split(r"[^A-Z0-9]+", clean) if t]
