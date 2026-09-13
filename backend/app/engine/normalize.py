"""Clean a raw statement narration into a comparable payee name and detect how it was paid."""
import re

# Bank prefixes and noise that carry no vendor information.
_PREFIX_RE = re.compile(
    r"^(POS\s*\d*\s*|VIN/|IIN/|BIL/ONL/|BIL/|MMT/|NEFT[-/ ]|RTGS[-/ ]|IMPS[-/ ]|UPI[-/ ]|ACH\s*D-?\s*|SI\s+|ECOM\s*PUR/?|ECOM/|ATM/|TPT/|INB/|FT/|IB\s+|NET\s*BANKING\s*)",
    re.I,
)
_TXN_ID_RE = re.compile(r"\b[A-Z]{0,4}\d{6,}\b")  # long numeric / alnum references
_DATE_RE = re.compile(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b|\b\d{8}\b")
_CARD_FRAG_RE = re.compile(r"\b(?:XX+|\*+)\d{2,4}\b|\b\d{1,6}X{3,}\d{0,4}\b|\bX{4,}\b", re.I)
_SUFFIX_WORDS = [
    "PVT LTD", "PRIVATE LIMITED", "PVT. LTD.", "PVT.LTD", "PVT LTD.", "LIMITED", "LTD", "LLP", "INC", "INC.", "LLC",
    "CORPORATION", "CO.", "PLC", "SA", "S.A.", "GMBH", "PTE",
    "DUBLIN", "SINGAPORE", "REDMOND WA", "REDMOND", "IRELAND", "MOUNTAIN VIEW", "SAN FRANCISCO", "SAN JOSE", "SEATTLE",
    "USA", "US", "UK", "IN", "INDIA", "BANGALORE", "BENGALURU", "MUMBAI", "HYDERABAD", "CHENNAI", "PUNE", "DELHI",
    "NOIDA", "GURGAON", "GURUGRAM", "KOLKATA", "AHMEDABAD", "COIMBATORE",
]
_SUFFIX_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in _SUFFIX_WORDS) + r")\b\.?", re.I)

MODE_PATTERNS = [
    ("upi", re.compile(r"\bUPI\b|@[a-z]+\b", re.I)),
    ("neft", re.compile(r"\bNEFT\b", re.I)),
    ("rtgs", re.compile(r"\bRTGS\b", re.I)),
    ("imps", re.compile(r"\bIMPS\b", re.I)),
    ("cheque", re.compile(r"\bCHQ\b|\bCHEQUE\b|\bCLG\b", re.I)),
    ("nach", re.compile(r"\bACH\s*D|\bNACH\b|\bECS\b|\bMANDATE\b", re.I)),
    ("si", re.compile(r"^SI\s|\bSTANDING INSTR", re.I)),
    ("card", re.compile(r"\bPOS\b|\bECOM\b|\bVIN/|\bIIN/|\bCARD\b|\bINTL\b|\bE-?COM\b", re.I)),
    ("cash", re.compile(r"\bCASH\b", re.I)),
]

AUTO_MODES = {"card", "si", "nach"}


def detect_mode(raw: str) -> str:
    for mode, rx in MODE_PATTERNS:
        if rx.search(raw or ""):
            return mode
    return "unknown"


def _upi_payee(raw: str) -> str | None:
    """UPI narrations look like UPI/123456/tallysolutions.rzp@hdfcbank/remark/bank. The VPA carries the merchant."""
    m = re.search(r"UPI[/-]([^/]*)[/-]([^/]*)[/-]?([^/]*)", raw, re.I)
    if not m:
        return None
    parts = [p for p in m.groups() if p]
    # Prefer a part that looks like a VPA (has @) else the first alphabetic part.
    for p in parts:
        if "@" in p:
            handle = p.split("@")[0]
            handle = re.sub(r"[._-]?(rzp|razorpay|payu|paytm|ybl|okaxis|oksbi|okicici|okhdfcbank|axl|ptaxis|ptsbi|ptyes)$", "", handle, flags=re.I)
            return handle.replace(".", " ").replace("_", " ").upper()
    for p in parts:
        if re.search(r"[A-Za-z]{3,}", p) and not re.fullmatch(r"\d+", p):
            return p.upper()
    return None


_SEGMENT_MODES = re.compile(r"^(NEFT|RTGS|IMPS|BIL|MMT|TPT|INB|FT|IB|CLG|CHQ)\b", re.I)
_ID_LIKE = re.compile(r"^[A-Z]{0,5}\d{5,}[A-Z0-9]*$|^\d+$|^[A-Z]\d+$", re.I)


def _segment_payee(raw: str) -> str | None:
    """'NEFT-N000123-SHREE INFOTECH-TSS RENEWAL' -> 'SHREE INFOTECH'. Segments are split on - or /,
    the mode word and id-like segments are dropped, and the first real name segment is the payee."""
    if not _SEGMENT_MODES.match(raw.strip()):
        return None
    segs = [s.strip() for s in re.split(r"[-/|]", raw) if s.strip()]
    segs = segs[1:]  # drop the mode
    for s in segs:
        if s.upper() in ("ONL", "OFF", "DR", "CR", "P2A", "P2M", "MB", "IB", "NB", "SI", "N", "R"):
            continue
        if _ID_LIKE.match(s) or len(s) < 3:
            continue
        if re.fullmatch(r"[\d\s.,]+", s):
            continue
        # a segment that is mostly digits is an id, not a name
        if sum(ch.isdigit() for ch in s) > len(s) / 2:
            continue
        return s.upper()
    return None


def clean_payee(raw: str) -> str:
    """Uppercase, strip prefixes, ids, dates, card fragments, legal/city suffixes, collapse spaces."""
    if not raw:
        return ""
    s = raw.strip()
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
    s = _CARD_FRAG_RE.sub(" ", s)
    s = _DATE_RE.sub(" ", s)
    s = _TXN_ID_RE.sub(" ", s)
    s = re.sub(r"[/\\|,;:_]+", " ", s)
    s = re.sub(r"\bUTR\b|\bREF\b|\bTXN\b|\bTRF\b|\bTRANSFER\b|\bPAYMENT\b|\bPMT\b|\bTO\b|\bECOM\b|\bPOS\b|\bINTL\b|\bPUR\b", " ", s)
    s = _SUFFIX_RE.sub(" ", s)
    s = re.sub(r"[^A-Z0-9*.&@ ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" .-")
    return s


def payee_tokens(clean: str) -> list[str]:
    return [t for t in re.split(r"[^A-Z0-9]+", clean) if t]
