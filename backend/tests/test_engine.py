"""Engine tests — cases from research/3-engine-logic-and-test-cases.md (Part 5). Today is fixed at 12-Sep-2026."""
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
import pytest

from app.engine.vendors import Catalog
from app.engine.normalize import clean_payee, detect_mode
from app.engine.dedupe import Row, build_occurrences
from app.engine.recurrence import build_streams
from app.engine.status import compute_status, monthly_equivalent

TODAY = date(2026, 9, 12)


@pytest.fixture(scope="module")
def cat():
    return Catalog()


_id = [0]


def row(cat, desc, d, amt, source="bank", direction="debit", **kw):
    _id[0] += 1
    clean = clean_payee(desc)
    r = Row(id=_id[0], source=source, date=d, amount=amt, direction=direction, payee_clean=clean, raw_description=desc,
            payment_mode=detect_mode(desc) if source in ("bank", "card") else None, **kw)
    r.res = cat.resolve(clean, amt, desc, kw.get("ledger") or "")
    return r


def run(cat, rows):
    occs = build_occurrences(rows, cat)
    streams = build_streams(occs, cat, TODAY)
    return occs, streams


def one(streams, vendor_key=None, name_contains=None):
    hits = [s for s in streams if (vendor_key and s.vendor_key == vendor_key) or (name_contains and name_contains.lower() in s.vendor_name.lower())]
    assert len(hits) == 1, f"expected exactly one stream, got {[(s.vendor_name, s.product, s.cycle) for s in hits]}"
    return hits[0]


def monthly(cat, desc, amt, start, n, day_jitter=0):
    rows = []
    for i in range(n):
        d = start + relativedelta(months=i) + timedelta(days=(i % 2) * day_jitter)
        rows.append(row(cat, desc, d, amt))
    return rows


# --- normalisation -------------------------------------------------------------------------
def test_clean_payee_bank_prefixes():
    assert clean_payee("NEFT-N0000002-SHREE INFOTECH-TSS RENEWAL") == "SHREE INFOTECH"
    assert clean_payee("POS 4XXXXX MSFT * E0100ABCD REDMOND WA").startswith("MSFT")
    assert clean_payee("UPI/425511/tallysolutions.rzp@hdfcbank/TSS/HDFC") == "TALLYSOLUTIONS"
    assert clean_payee("VIN/AMAZON INTERNET SERVICES PVT LTD/20240104/ECOM") == "AMAZON INTERNET SERVICES"


def test_detect_mode():
    assert detect_mode("ACH D- AIRTEL") == "nach"
    assert detect_mode("POS 4XXXX ZOOM.US") == "card"
    assert detect_mode("NEFT-X-Y") == "neft"


# --- vendor recognition --------------------------------------------------------------------
def test_alias_and_fingerprint(cat):
    assert cat.resolve(clean_payee("POS MSFT * E0100ABCD")).vendor_key == "microsoft365"
    assert cat.resolve(clean_payee("GOOGLE *GSUITE_acme.in")).vendor_key == "google_workspace"
    r = cat.resolve("SHREE INFOTECH", 5310)
    assert r.vendor_key == "tally" and r.method == "fingerprint" and r.suggested_cycle == "yearly"


def test_gateway_and_reseller(cat):
    r = cat.resolve(clean_payee("PAYPAL *GODADDY"), 1100)
    assert r.vendor_key == "godaddy"
    r = cat.resolve("CADSPRO TECHNOLOGIES", 46400, "RTGS-CADSPRO TECHNOLOGIES-SW SUBSCRIPTION")
    assert r.is_reseller and "solidworks" in r.candidates
    assert cat.resolve("CONSOLIDATED CHARGES FOR A C").excluded
    assert cat.resolve("TIN NSDL TDS CHALLAN").excluded


# --- cycles ----------------------------------------------------------------------------------
def test_case1_monthly_card(cat):
    rows = monthly(cat, "POS 4XXXXX MSFT * E0100ABCD", 1450, date(2026, 1, 3), 9, day_jitter=1)
    _, s = run(cat, rows)
    st = one(s, "microsoft365")
    assert st.cycle == "monthly" and st.expected_amount == 1450 and st.auto_renew
    assert st.next_due.month == 10 and st.next_due.day in (3, 4)
    assert st.confidence >= 75


def test_case2_seat_change_same_stream(cat):
    rows = monthly(cat, "POS MSFT * E0100ABCD", 1450, date(2026, 1, 3), 3) + monthly(cat, "POS MSFT * E0100ABCD", 1740, date(2026, 4, 3), 3)
    _, s = run(cat, rows)
    st = one(s, "microsoft365")
    assert st.expected_amount == 1740 and "price_changed" in st.flags and len(st.occurrences) == 6


def test_case3_catch_up_two_months(cat):
    rows = monthly(cat, "POS MSFT * E0100ABCD", 1450, date(2026, 1, 3), 4)
    rows.append(row(cat, "POS MSFT * E0100ABCD", date(2026, 6, 5), 2900))
    _, s = run(cat, rows)
    st = one(s, "microsoft365")
    assert "catch_up_2_cycles" in st.flags and st.expected_amount == 1450 and "price_changed" not in st.flags


def test_case4_5_tally_tss_yearly(cat):
    rows = [row(cat, "NEFT-N1-TALLY SOLUTIONS PVT LTD-TSS", date(2024, 4, 10), 5310),
            row(cat, "NEFT-N2-TALLY SOLUTIONS PVT LTD-TSS", date(2025, 4, 8), 5310),
            row(cat, "NEFT-N3-TALLY SOLUTIONS PVT LTD-TSS", date(2026, 4, 15), 5310)]
    _, s = run(cat, rows)
    st = one(s, "tally")
    assert st.cycle == "yearly" and st.next_due == date(2027, 4, 15) and st.confidence >= 75
    # single hit with fingerprint -> yearly candidate, no vendor question
    _, s2 = run(cat, [row(cat, "NEFT-N3-TALLY SOLUTIONS-TSS", date(2026, 4, 15), 5310)])
    st2 = one(s2, "tally")
    assert st2.cycle == "yearly" and st2.next_due == date(2027, 4, 15) and not st2.needs_vendor


def test_case6_licence_then_amc(cat):
    rows = [row(cat, "NEFT-N1-SHREE INFOTECH-TALLY LICENCE", date(2024, 6, 2), 22500),
            row(cat, "NEFT-N2-SHREE INFOTECH-TSS", date(2025, 6, 1), 5310),
            row(cat, "NEFT-N3-SHREE INFOTECH-TSS", date(2026, 6, 3), 5310)]
    _, s = run(cat, rows)
    types = sorted((x.stream_type, x.expected_amount) for x in s if x.vendor_key == "tally")
    assert ("one_time", 22500.0) in types and ("subscription", 5310.0) in types


def test_case10_12_tds_matching(cat):
    inv = dict(taxable=40000.0, gst=7200.0, invoice_no="SW2026")
    bill = row(cat, "Cadspro Technologies Pvt Ltd | SolidWorks Subscription Service 1 seat", date(2026, 3, 1), 47200, source="tally", **inv)
    for paid, tds in ((46400, 800), (43200, 4000), (47200, None)):
        pay = row(cat, "RTGS-CADSPRO TECHNOLOGIES PVT LTD-SW SUBSCRIPTION", date(2026, 3, 20), paid)
        occs, s = run(cat, [bill, pay])
        assert len(occs) == 1, "bill and payment must merge into one occurrence"
        o = occs[0]
        assert o.tds == tds and o.amount_paid == paid and o.amount_gross == 47200 and o.vendor_key == "solidworks"


def test_case14_usd_with_markup(cat):
    rows = []
    for i, inr in enumerate((4612, 4701, 4655)):
        d = date(2026, 1, 8) + relativedelta(months=i)
        rows.append(row(cat, "POS ADOBE SYSTEMS SOFTWARE IRELAND LTD DUBLIN", d, inr))
        rows.append(row(cat, "FOREIGN CURRENCY MARKUP FEE", d + timedelta(days=1), round(inr * 0.035, 2)))
    occs, s = run(cat, rows)
    st = one(s, "adobe")
    assert st.cycle == "monthly" and len(st.occurrences) == 3 and all(o.fees > 0 for o in st.occurrences)


def test_case16_aws_variable(cat):
    rows = [row(cat, "VIN/AMAZON INTERNET SERVICES/ECOM", date(2026, 1, 4) + relativedelta(months=i), a) for i, a in enumerate((8240, 11900, 7300, 15100))]
    _, s = run(cat, rows)
    st = one(s, "aws")
    assert st.cycle == "monthly" and "price_changed" not in st.flags and 7300 <= st.expected_amount <= 15100


def test_case17_prepaid_credits(cat):
    rows = [row(cat, "UPI/1/walkoverwebsolutions@ybl/MSG91", date(2026, 1, 12) + timedelta(days=k), 5000) for k in (0, 49, 75, 138)]
    _, s = run(cat, rows)
    st = one(s, "sms_gateway")
    assert st.stream_type == "prepaid" and st.next_due is None


def test_case18_19_domain_biennial(cat):
    _, s = run(cat, [row(cat, "POS GODADDY.COM", date(2023, 8, 14), 1299), row(cat, "POS GODADDY.COM", date(2025, 8, 12), 1499)])
    st = one(s, "godaddy")
    assert st.cycle == "biennial" and st.next_due == date(2027, 8, 12)
    _, s2 = run(cat, [row(cat, "GoDaddy | Domain renewal 2 years", date(2025, 8, 14), 1299, source="tally", invoice_no="G1")])
    st2 = one(s2, "godaddy")
    assert st2.cycle == "biennial" and "cycle_from_invoice" in st2.flags and st2.next_due == date(2027, 8, 14)


def test_case20_seqrite_3yr_from_invoice(cat):
    bill = row(cat, "Shree Infotech | Seqrite Endpoint Security 30 users 3 years", date(2025, 7, 13), 63720, source="tally", taxable=54000.0, gst=9720.0, invoice_no="SI118")
    pay = row(cat, "NEFT-N3-SHREE INFOTECH-SEQRITE", date(2025, 7, 13), 63720)
    _, s = run(cat, [bill, pay])
    st = one(s, "quickheal")
    assert st.cycle == "triennial" and st.next_due == date(2028, 7, 13) and round(monthly_equivalent(st.expected_amount, st.cycle_months, st.stream_type)) == 1770


def test_case21_22_quarterly_late_and_yearly_late(cat):
    rows = [row(cat, "NEFT-N-ABC COMPUTERS-IT AMC", d, 8850) for d in (date(2025, 4, 5), date(2025, 7, 6), date(2025, 10, 8), date(2026, 1, 6))]
    _, s = run(cat, rows)
    st = one(s, "it_amc")
    assert st.cycle == "quarterly"
    _, s2 = run(cat, [row(cat, "NEFT-N-PIXEL WEB STUDIO-WEBSITE AMC", date(2025, 4, 1), 11800), row(cat, "NEFT-N-PIXEL WEB STUDIO-WEBSITE AMC", date(2026, 4, 22), 11800)])
    st2 = one(s2, "web_amc")
    assert st2.cycle == "yearly"


def test_case23_25_status_rules():
    kw = dict(stream_type="subscription", auto_renew=False, confidence=90, is_user_modified=False, dismissed=False, cancelled=False)
    assert compute_status(cycle="yearly", cycle_months=12, next_due=date(2026, 4, 10), last_paid_date=date(2025, 4, 10), today=TODAY, **kw) == "overdue"
    assert compute_status(cycle="monthly", cycle_months=1, next_due=date(2026, 7, 3), last_paid_date=date(2026, 6, 3), today=TODAY, **kw) == "stopped"
    kw["auto_renew"] = True
    assert compute_status(cycle="monthly", cycle_months=1, next_due=date(2026, 9, 3), last_paid_date=date(2026, 8, 3), today=TODAY, **kw) == "charge_missed"
    assert compute_status(cycle="yearly", cycle_months=12, next_due=date(2026, 9, 30), last_paid_date=date(2025, 9, 30), today=TODAY, **kw) == "due_soon"


def test_case26_refund_cancels(cat):
    rows = [row(cat, "POS ZOOM.US", date(2026, 6, 5), 1769), row(cat, "REFUND ZOOM.US", date(2026, 6, 9), 1769, direction="credit")]
    occs, s = run(cat, rows)
    assert occs == []


def test_case27_auth_charge_ignored(cat):
    rows = [row(cat, "POS ADOBE", date(2026, 1, 1), 2)] + monthly(cat, "POS ADOBE", 1675, date(2026, 1, 8), 3)
    _, s = run(cat, rows)
    st = one(s, "adobe")
    assert len(st.occurrences) == 3


def test_case28_gateway_resolved_via_bill(cat):
    bill = row(cat, "Google India Pvt Ltd | Google Workspace Business Starter 10 users", date(2026, 5, 4), 2360, source="tally", invoice_no="GW1")
    pay = row(cat, "UPI/1/razorpay@icici/PAYMENT", date(2026, 5, 5), 2360)
    occs, s = run(cat, [bill, pay])
    assert len(occs) == 1 and occs[0].vendor_key == "google_workspace"


def test_case29_gateway_unknown_becomes_question(cat):
    rows = monthly(cat, "POS PAYU*SOMETHING", 2360, date(2026, 1, 5), 4)
    _, s = run(cat, rows)
    assert len(s) == 1 and s[0].needs_vendor and s[0].cycle == "monthly"


def test_case31_supplier_switch_merges(cat):
    rows = [row(cat, "NEFT-N-ABC INFOTECH-M365 RENEWAL", date(2023, 3, 1), 17700), row(cat, "NEFT-N-ABC INFOTECH-M365 RENEWAL", date(2024, 3, 1), 17700)]
    rows += monthly(cat, "POS MSFT * E0100ABCD", 1475, date(2025, 3, 3), 6)
    _, s = run(cat, rows)
    m365 = [x for x in s if x.vendor_key == "microsoft365"]
    assert len(m365) == 2  # two products/cycles: yearly via reseller (old) + monthly direct — both attributed to M365


def test_case32_33_three_sources_one_occurrence(cat):
    email = row(cat, "Amazon Web Services | Invoice April", date(2026, 4, 3), 9440, source="email", invoice_no="AWS-APR")
    bank = row(cat, "VIN/AMAZON INTERNET SERVICES/ECOM", date(2026, 4, 4), 9440)
    tally = row(cat, "Amazon Internet Services | AWS April bill", date(2026, 4, 30), 9440, source="tally", invoice_no="AWS-APR")
    occs, _ = run(cat, [email, bank, tally])
    assert len(occs) == 1 and set(occs[0].sources) == {"email", "bank", "tally"} and occs[0].date == date(2026, 4, 4)
    occs2, _ = run(cat, [row(cat, "Amazon Internet Services | AWS Aug bill", date(2026, 8, 30), 9440, source="tally", invoice_no="AWS-AUG")])
    assert occs2[0].unpaid


def test_case34_35_split_payments(cat):
    bill = row(cat, "Cadspro Technologies | SolidWorks", date(2026, 3, 1), 236000, source="tally", taxable=200000.0, gst=36000.0, invoice_no="C1")
    occs, _ = run(cat, [bill, row(cat, "RTGS-CADSPRO TECHNOLOGIES-SW", date(2026, 3, 20), 200000), row(cat, "RTGS-CADSPRO TECHNOLOGIES-SW", date(2026, 3, 20), 36000)])
    assert len(occs) == 1 and occs[0].amount_paid == 236000 and "paid_in_2_parts" in occs[0].flags


def test_case39_40_amount_bands_and_vendor_keying(cat):
    rows = monthly(cat, "POS ZOHO CORPORATION", 2360, date(2026, 1, 5), 4) + [row(cat, "POS ZOHO CORPORATION", date(2026, 2, 1), 11800), row(cat, "POS ZOHO CORPORATION", date(2025, 2, 1), 11800)]
    rows += monthly(cat, "POS CANVA*", 2360, date(2026, 1, 5), 4)
    _, s = run(cat, rows)
    zoho = [x for x in s if x.vendor_key == "zoho"]
    assert len(zoho) == 2 and {x.cycle for x in zoho} == {"monthly", "yearly"}
    assert len([x for x in s if x.vendor_key == "canva"]) == 1


def test_case44_45_bank_fees_and_government_excluded(cat):
    rows = monthly(cat, "CONSOLIDATED CHARGES FOR A/C", 590, date(2026, 1, 28), 4) + monthly(cat, "TIN NSDL TDS CHALLAN", 2000, date(2026, 1, 7), 4)
    occs, s = run(cat, rows)
    assert occs == [] and s == []


def test_case46_airtel_nach_variable(cat):
    rows = [row(cat, "ACH D- BHARTI AIRTEL LTD", date(2026, 1, 12) + relativedelta(months=i), a) for i, a in enumerate((2065, 2140, 2065, 2183))]
    _, s = run(cat, rows)
    st = one(s, "airtel")
    assert st.cycle == "monthly" and st.auto_renew and "price_changed" not in st.flags


def test_case48_rounded_upi_matches_invoice(cat):
    bill = row(cat, "Tally Solutions | TSS Silver", date(2026, 4, 10), 5310, source="tally", invoice_no="T1")
    pay = row(cat, "UPI/1/tallysolutions.rzp@hdfcbank/TSS", date(2026, 4, 11), 5300)
    occs, _ = run(cat, [bill, pay])
    assert len(occs) == 1 and occs[0].vendor_key == "tally"


def test_case49_tds_starts_midyear_no_price_cut(cat):
    rows = []
    for i in range(8):
        d = date(2026, 1, 5) + relativedelta(months=i)
        rows.append(row(cat, f"Cloud Telephony Co | Monthly plan {i}", d, 11800, source="tally", taxable=10000.0, gst=1800.0, invoice_no=f"CT{i}"))
        rows.append(row(cat, "NEFT-N-CLOUD TELEPHONY CO-PLAN", d + timedelta(days=2), 11800 if i < 5 else 11600))
    occs, s = run(cat, rows)
    assert len(occs) == 8 and all(o.amount_gross == 11800 for o in occs)
    assert len(s) == 1 and s[0].cycle == "monthly" and "price_changed" not in s[0].flags


def test_unknown_raw_material_supplier_dropped(cat):
    rows = [row(cat, "RTGS-JINDAL STEEL-RAW MATERIAL", date(2026, 1, 9) + relativedelta(months=i), a) for i, a in enumerate((412000, 799000, 473000, 850000))]
    _, s = run(cat, rows)
    assert s == []


def test_unknown_regular_yearly_kept_as_question(cat):
    _, s = run(cat, [row(cat, "NEFT-N-SRI BALAJI ENTERPRISES-BILL", date(2025, 4, 13), 11800), row(cat, "NEFT-N-SRI BALAJI ENTERPRISES-BILL", date(2026, 4, 13), 11800)])
    assert len(s) == 1 and s[0].needs_vendor and s[0].cycle == "yearly"
