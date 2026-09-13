"""Vendor recognition: alias dictionary -> reseller list -> amount fingerprint -> narration hints -> fuzzy -> unknown.

Everything is loaded from data/vendors.yaml plus company-scoped aliases learned from user answers.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path
import yaml
from rapidfuzz import fuzz

from app.engine.normalize import payee_tokens

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "vendors.yaml"

FILLER = {"INFOTECH", "TECHNOLOGIES", "TECHNOLOGY", "SOLUTIONS", "SYSTEMS", "SERVICES", "SOFTWARE", "SOFTWARES",
          "INDIA", "PVT", "LTD", "LIMITED", "PRIVATE", "THE", "AND", "OF", "ENTERPRISES", "TRADERS", "AGENCIES",
          "COMPUTERS", "COMPUTER", "DIGITAL", "TECH", "CORP", "CORPORATION", "GROUP"}


@dataclass
class VendorInfo:
    key: str
    name: str
    category: str
    default_cycle: str = "monthly"
    variable: bool = False
    prepaid: bool = False
    currency: str = "INR"
    entity_type: str = "domestic"
    is_reseller: bool = False
    sells: list[str] = field(default_factory=list)
    pay_url: str | None = None
    exclude: bool = False
    intro_pricing: bool = False
    aliases: list[str] = field(default_factory=list)


@dataclass
class Resolution:
    vendor_key: str | None = None
    product: str | None = None
    method: str = "none"          # alias | reseller | fingerprint | narration | fuzzy | user | gateway | none
    is_reseller: bool = False
    is_gateway: bool = False
    excluded: bool = False
    is_fee: bool = False
    looks_it: bool = False        # unknown payee but IT-ish words
    confidence: float = 0.0
    suggested_cycle: str | None = None
    term_months: int | None = None   # "3 years", "annual", "FY 26-27" found in the narration
    candidates: list[str] = field(default_factory=list)  # for reseller: product menu


_TERM_RX = [
    (re.compile(r"(\d+)\s*(?:YEARS?|YRS?)\b", re.I), lambda m: int(m.group(1)) * 12),
    (re.compile(r"(\d+)\s*(?:MONTHS?|MON)\b", re.I), lambda m: int(m.group(1))),
    (re.compile(r"\b(?:ANNUAL|YEARLY|PER YEAR|P\.?A\.?|FY\s*\d{2})", re.I), lambda m: 12),
    (re.compile(r"\bHALF[- ]?YEARLY\b", re.I), lambda m: 6),
    (re.compile(r"\bQUARTERLY\b|\bQTR\b|\bQ[1-4]\b", re.I), lambda m: 3),
    (re.compile(r"\bMONTHLY\b", re.I), lambda m: 1),
]


def term_months_from_text(text: str) -> int | None:
    for rx, fn in _TERM_RX:
        m = rx.search(text or "")
        if m:
            v = fn(m)
            if 1 <= v <= 120:
                return v
    return None


class Catalog:
    def __init__(self, path: Path = DATA_PATH):
        raw = yaml.safe_load(path.read_text())
        self.vendors: dict[str, VendorInfo] = {}
        self._alias_rx: list[tuple[re.Pattern, str, str | None]] = []
        for v in raw["vendors"]:
            info = VendorInfo(**{k: v[k] for k in v if k != "aliases"}, aliases=v.get("aliases", []))
            self.vendors[info.key] = info
            for a in info.aliases:
                self._alias_rx.append((re.compile(a, re.I), info.key, None))
        self.exclude_rx = [re.compile(p, re.I) for p in raw.get("exclude_patterns", [])]
        self.fee_rx = [re.compile(p, re.I) for p in raw.get("fee_patterns", [])]
        self.gateway_rx = [re.compile(p, re.I) for p in raw.get("gateway_patterns", [])]
        self.reseller_words = [w.upper() for w in raw.get("reseller_hint_words", [])]
        self.resellers = [(r["name"].upper(), r.get("sells", [])) for r in raw.get("resellers", [])]
        self.fingerprints = raw.get("fingerprints", [])
        self.narration_hints = [(re.compile(h["pattern"], re.I), h.get("vendor"), h.get("product")) for h in raw.get("narration_hints", [])]
        self.hardware_words = [w.upper() for w in raw.get("hardware_words", [])]
        # company-scoped learned aliases: {company_id: [(pattern_rx, vendor_key, product)]}
        self.learned: dict[int, list[tuple[re.Pattern, str, str | None]]] = {}

    # ---- learned aliases (from DB) ----
    def load_learned(self, rows):
        """rows: iterable of (company_id, pattern, kind, vendor_key, product)."""
        self.learned = {}
        for company_id, pattern, kind, vendor_key, product in rows:
            rx = re.compile(re.escape(pattern) if kind == "exact" else pattern, re.I)
            self.learned.setdefault(company_id, []).append((rx, vendor_key, product))

    def add_learned(self, company_id: int, pattern: str, vendor_key: str, product: str | None):
        self.learned.setdefault(company_id, []).append((re.compile(re.escape(pattern), re.I), vendor_key, product))

    # ---- helpers ----
    def vendor(self, key: str | None) -> VendorInfo | None:
        return self.vendors.get(key) if key else None

    def is_excluded(self, raw: str) -> bool:
        return any(rx.search(raw or "") for rx in self.exclude_rx)

    def is_fee(self, raw: str) -> bool:
        return any(rx.search(raw or "") for rx in self.fee_rx)

    def strip_gateway(self, clean: str) -> tuple[str, bool]:
        hit = False
        s = clean
        for rx in self.gateway_rx:
            if rx.search(s):
                hit = True
                s = rx.sub(" ", s)
        s = re.sub(r"\bSOFTWARE\b|\bPAYMENTS?\b|\bPVT\b|\bLTD\b", " ", s)
        return re.sub(r"\s+", " ", s).strip(" *-"), hit

    def looks_it(self, clean: str) -> bool:
        return any(w in clean for w in self.reseller_words)

    def is_hardware_text(self, text: str) -> bool:
        t = (text or "").upper()
        return any(w in t for w in self.hardware_words)

    # ---- main entry ----
    def resolve(self, clean: str, amount: float | None = None, narration: str = "", ledger: str = "",
                company_id: int | None = None) -> Resolution:
        res = Resolution()
        text = f"{clean} {narration or ''} {ledger or ''}"
        res.term_months = term_months_from_text(f"{narration or ''} {ledger or ''}")
        if self.is_fee(clean) or self.is_fee(narration or ""):
            res.is_fee = True
            return res
        if self.is_excluded(clean) or self.is_excluded(narration or ""):
            res.excluded = True
            return res

        # 0. company-learned aliases win
        for rx, key, product in self.learned.get(company_id or -1, []):
            if rx.search(clean):
                return self._fill(res, key, product, "user", 1.0)

        # 1. global alias dictionary
        for rx, key, _ in self._alias_rx:
            if rx.search(clean):
                self._fill(res, key, None, "alias", 0.95)
                # narration may refine the product
                for hrx, hv, hp in self.narration_hints:
                    if hp and hrx.search(text) and (hv in (None, key)):
                        res.product = hp
                        break
                return res

        # 2. payment gateway wrapper -> try the remainder
        remainder, gw = self.strip_gateway(clean)
        if gw:
            res.is_gateway = True
            if remainder:
                for rx, key, _ in self._alias_rx:
                    if rx.search(remainder):
                        return self._fill(res, key, None, "gateway", 0.85)
            # fall through with is_gateway=True

        # 3. known reseller
        for rname, sells in self.resellers:
            if rname in clean:
                res.is_reseller = True
                res.candidates = list(sells)
                res.method = "reseller"
                res.confidence = 0.6
                # narration/ledger may tell which product
                for hrx, hv, hp in self.narration_hints:
                    if hv and hrx.search(text):
                        self._fill(res, hv, hp, "reseller", 0.85)
                        res.is_reseller = True
                        return res
                if amount:
                    fp = self.fingerprint(amount)
                    if fp:
                        self._fill(res, fp["vendor"], fp["product"], "fingerprint", 0.8)
                        res.is_reseller = True
                        res.suggested_cycle = fp.get("cycle")
                        return res
                return res

        # 4. narration hints with a vendor (e.g. Tally purchase register line "SolidWorks subscription 2026")
        for hrx, hv, hp in self.narration_hints:
            if hv and hrx.search(narration or "") or (hv and ledger and hrx.search(ledger)):
                self._fill(res, hv, hp, "narration", 0.8)
                if self.looks_it(clean):
                    res.is_reseller = True
                return res

        # 5. amount fingerprint (exact list prices)
        if amount:
            fp = self.fingerprint(amount)
            if fp:
                self._fill(res, fp["vendor"], fp["product"], "fingerprint", 0.65)
                res.suggested_cycle = fp.get("cycle")
                res.is_reseller = self.looks_it(clean)
                return res

        # 6. fuzzy against vendor names / aliases (rare tokens only)
        best_key, best_score = None, 0.0
        toks = [t for t in payee_tokens(clean) if t not in FILLER and len(t) >= 4]
        if toks:
            probe = " ".join(toks)
            for key, info in self.vendors.items():
                names = [re.sub(r"[\\*^$?()|\[\]]", " ", a).upper() for a in info.aliases if len(a) >= 5]
                for n in names:
                    sc = fuzz.token_set_ratio(probe, n) / 100.0
                    if sc > best_score:
                        best_key, best_score = key, sc
        if best_key and best_score >= 0.9:
            return self._fill(res, best_key, None, "fuzzy", 0.7)

        # 7. unknown
        res.looks_it = self.looks_it(clean)
        res.is_reseller = res.looks_it
        return res

    def fingerprint(self, amount: float):
        for fp in self.fingerprints:
            if abs(amount - fp["amount"]) <= max(1.0, fp["amount"] * 0.01):
                return fp
        return None

    def _fill(self, res: Resolution, key: str, product: str | None, method: str, conf: float) -> Resolution:
        info = self.vendors.get(key)
        res.vendor_key = key
        res.product = product
        res.method = method
        res.confidence = conf
        if info:
            res.excluded = info.exclude
            res.suggested_cycle = res.suggested_cycle or info.default_cycle
            res.looks_it = True
        return res


_catalog: Catalog | None = None


def get_catalog() -> Catalog:
    global _catalog
    if _catalog is None:
        _catalog = Catalog()
    return _catalog
