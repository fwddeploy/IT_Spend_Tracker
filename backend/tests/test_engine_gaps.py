"""Engine gap closures (REVIEW-v0.1 "still open" / product-gap review section 2). Today is fixed at 12-Sep-2026."""
import io
from datetime import date
from dateutil.relativedelta import relativedelta
import pytest

from app.engine.vendors import Catalog
from app.engine.normalize import clean_payee, detect_mode, instrument_no, same_instrument
from app.engine.dedupe import build_occurrences
from app.engine.recurrence import build_streams, fy_of
from tests.test_engine import row, run, one, monthly, TODAY


@pytest.fixture(scope="module")
def cat():
    return Catalog()


# --- 1. cheque-number matching (2.37) -------------------------------------------------------------
def test_clean_payee_keeps_bare_cheque_number():
    assert clean_payee("CHQ 000412") == "CHQ 000412"
    assert clean_payee("CHEQUE NO. 412") == "CHQ 412"
    assert clean_payee("CLG/000412") == "CHQ 000412"
    assert clean_payee("CHQ PAID-MICR CTS-ABC COMPUTERS-000412") == "ABC COMPUTERS"   # name present: unchanged
    assert detect_mode("CHQ 000412") == "cheque"


def test_instrument_no_from_narration():
    assert instrument_no("CHQ 000412") == "000412"
    assert instrument_no("CHQ PAID-MICR CTS-ABC COMPUTERS-000412") == "000412"
    assert instrument_no("ABC Computers | Chq No: 000412 AMC Q2") == "000412"
    assert instrument_no("ABC Computers | Ch. No 000412") == "000412"
    assert instrument_no("ABC Computers | Cheque 000412") == "000412"
    assert instrument_no("NEFT-N1-TALLY SOLUTIONS-TSS") is None
    assert same_instrument("000412", "412") and same_instrument("CHQ 1000412", "000412") and not same_instrument("412", "413")


def test_case37_cheque_resolved_via_tally_joins_amc_stream(cat):
    rows = [row(cat, "NEFT-N-ABC COMPUTERS-IT AMC", d, 8850) for d in (date(2025, 7, 6), date(2025, 10, 8), date(2026, 1, 6))]
    bank = row(cat, "CHQ 000412", date(2026, 4, 7), 8850)
    tally = row(cat, "ABC Computers | Chq No: 000412 AMC Q2", date(2026, 4, 5), 8850, source="tally")
    assert bank.payee_clean == "CHQ 000412" and bank.res.vendor_key is None
    occs, s = run(cat, rows + [bank, tally])
    chq = [o for o in occs if o.date == date(2026, 4, 7)]
    assert len(chq) == 1 and chq[0].payee_clean == "ABC COMPUTERS" and chq[0].vendor_key == "it_amc"
    assert set(chq[0].sources) == {"bank", "tally"} and "cheque_matched" in chq[0].flags
    st = one(s, "it_amc")
    assert st.cycle == "quarterly" and len(st.occurrences) == 4 and "cheque_matched" in st.flags
    # Row.instrument_no given explicitly (runner may fill it from the statement's ref column) wins over narration
    bank2 = row(cat, "CHQ PAID", date(2026, 4, 7), 8850, instrument_no="412")
    occs, _ = run(cat, [bank2, tally])
    assert len(occs) == 1 and occs[0].payee_clean == "ABC COMPUTERS"


def test_cheque_number_alone_never_matches_wrong_amount(cat):
    bank = row(cat, "CHQ 000412", date(2026, 4, 7), 8850)
    tally = row(cat, "ABC Computers | Chq No: 000412", date(2026, 4, 5), 50000, source="tally")
    occs, _ = run(cat, [bank, tally])
    assert len(occs) == 2   # cheque numbers repeat across cheque books; amount must still relate


# --- 2. hardware exclusion (2.29) ------------------------------------------------------------------
def test_case7_hardware_only_bill_is_one_time(cat):
    bill = row(cat, "Shree Infotech | 2 Dell laptops", date(2026, 7, 5), 100000, source="tally", invoice_no="S1")
    occs, s = run(cat, [bill])
    assert occs[0].vendor_key == "hardware" and occs[0].resolution == "hardware"
    assert len(s) == 1 and s[0].stream_type == "one_time" and s[0].vendor_key == "hardware"


def test_mixed_hardware_software_bill_keeps_vendor_and_flags(cat):
    bill = row(cat, "Shree Infotech | Seqrite EPS 25 users 1 yr + 1 HP printer", date(2026, 7, 5), 35400, source="tally", invoice_no="S2")
    pay = row(cat, "NEFT-N-SHREE INFOTECH-BILL", date(2026, 7, 6), 35400)
    occs, s = run(cat, [bill, pay])
    assert len(occs) == 1 and occs[0].vendor_key == "quickheal" and "mixed_hardware_bill" in occs[0].flags
    st = one(s, "quickheal")
    assert "mixed_hardware_bill" in st.flags and st.stream_type == "subscription"


def test_unknown_bank_payee_with_hardware_words_is_hardware(cat):
    occs, s = run(cat, [row(cat, "NEFT-N-RAMESH ENTERPRISES-LAPTOP PURCHASE", date(2026, 7, 5), 60000)])
    assert occs[0].vendor_key == "hardware" and s[0].stream_type == "one_time" and not s[0].needs_vendor


def test_hardware_words_are_whole_words(cat):
    assert not cat.is_hardware_text("PROGRAMME UPSTREAM CABLEWAY")
    assert cat.is_hardware_text("8GB RAM upgrade") and cat.is_hardware_text("Toner cartridges")


# --- 3. reseller bundle (2.28) ---------------------------------------------------------------------
def test_case9_reseller_bundle_stream_asks_to_split(cat):
    r = cat.resolve("SHREE INFOTECH", 35400, "NEFT-N-SHREE INFOTECH-BILL")   # not a known reseller: plain unknown
    assert not r.bundle
    r = cat.resolve("REDINGTON", 35400, "NEFT-N-REDINGTON-BILL")
    assert r.method == "reseller" and r.bundle and r.candidates and r.vendor_key is None and r.looks_it
    assert not cat.resolve("REDINGTON", 2000, "NEFT-N-REDINGTON").bundle          # too small to be a bundle
    _, s = run(cat, [row(cat, "NEFT-N-REDINGTON-BILL", date(2026, 7, 5), 35400)])
    assert len(s) == 1
    st = s[0]
    assert st.needs_bundle and not st.needs_vendor and "bundle_unknown_product" in st.flags
    assert st.vendor_key is None and st.vendor_name == "Redington"


def test_reseller_with_product_hint_is_not_a_bundle(cat):
    r = cat.resolve("CADSPRO TECHNOLOGIES", 46400, "RTGS-CADSPRO TECHNOLOGIES-SOLIDWORKS SUBSCRIPTION")
    assert r.vendor_key == "solidworks" and not r.bundle
    r = cat.resolve("SHWETA COMPUTERS", 5310)     # fingerprint gives the product
    assert r.vendor_key == "tally" and not r.bundle


# --- 4. supplier switch (2.27 / TC31) --------------------------------------------------------------
def test_supplier_switch_not_merged_when_far_apart_or_different_price(cat):
    # old reseller stream stopped 2 years before the direct one began -> two streams
    rows = [row(cat, "NEFT-N-ABC INFOTECH-M365 RENEWAL", date(2021, 3, 1), 17700), row(cat, "NEFT-N-ABC INFOTECH-M365 RENEWAL", date(2022, 3, 1), 17700)]
    rows += monthly(cat, "POS MSFT * E0100ABCD", 1475, date(2025, 3, 3), 6)
    _, s = run(cat, rows)
    assert len([x for x in s if x.vendor_key == "microsoft365"]) == 2
    # monthly-equivalent differs by more than 25% -> two streams
    rows = [row(cat, "NEFT-N-ABC INFOTECH-M365 RENEWAL", date(2023, 3, 1), 17700), row(cat, "NEFT-N-ABC INFOTECH-M365 RENEWAL", date(2024, 3, 1), 17700)]
    rows += monthly(cat, "POS MSFT * E0100ABCD", 2900, date(2025, 3, 3), 6)
    _, s = run(cat, rows)
    assert len([x for x in s if x.vendor_key == "microsoft365"]) == 2


# --- 6. yearly anchor (2.19) and paid-early (2.20) ------------------------------------------------
def test_yearly_anchor_snaps_to_median_day(cat):
    rows = [row(cat, "NEFT-N-TALLY SOLUTIONS-TSS", d, 5310) for d in (date(2024, 4, 10), date(2025, 4, 25), date(2026, 4, 2))]
    st = one(run(cat, rows)[1], "tally")
    assert st.next_due == date(2027, 4, 10)    # median of 10 Apr / 25 Apr / 2 Apr
    # two payments only: no snap
    rows = [row(cat, "NEFT-N-TALLY SOLUTIONS-TSS", d, 5310) for d in (date(2025, 4, 2), date(2026, 4, 25))]
    assert one(run(cat, rows)[1], "tally").next_due == date(2027, 4, 25)


def test_quarterly_anchor_day_of_month(cat):
    rows = [row(cat, "NEFT-N-ABC COMPUTERS-IT AMC", d, 8850) for d in (date(2025, 4, 5), date(2025, 7, 6), date(2025, 10, 8), date(2026, 1, 20))]
    st = one(run(cat, rows)[1], "it_amc")
    assert st.cycle == "quarterly" and st.next_due == date(2026, 4, 8) and st.anchor_day == 8   # median day of 6, 8, 20


def test_paid_early_keeps_previous_expected_due(cat):
    # yearly TSS: 10-Apr-24, 12-Apr-25, then renewed early on 1-Mar-26 (offer) -> due 12-Apr-27, not 1-Mar-27
    rows = [row(cat, "NEFT-N-TALLY SOLUTIONS-TSS", d, 5310) for d in (date(2024, 4, 10), date(2025, 4, 12), date(2026, 3, 1))]
    st = one(run(cat, rows)[1], "tally")
    assert "paid_early" in st.flags and st.cycle == "yearly" and st.next_due == date(2027, 4, 10)  # anchor snap on top (10/12 Apr -> 10 Apr, moved <= 45 d)
    # with an invoice period the period wins and there is no paid_early flag
    rows = [row(cat, "NEFT-N-TALLY SOLUTIONS-TSS", d, 5310) for d in (date(2024, 4, 10), date(2025, 4, 12))]
    rows.append(row(cat, "Tally Solutions | TSS renewal", date(2026, 3, 1), 5310, source="tally", invoice_no="T9",
                    period_from=date(2026, 4, 13), period_to=date(2027, 4, 12)))
    rows.append(row(cat, "NEFT-N-TALLY SOLUTIONS-TSS", date(2026, 3, 1), 5310))
    st = one(run(cat, rows)[1], "tally")
    assert "paid_early" not in st.flags and st.next_due == date(2027, 4, 13)


# --- 7. catch-up mid-history (2.21) -----------------------------------------------------------------
def test_catch_up_in_the_middle_of_the_history(cat):
    rows = [row(cat, "POS MSFT * E0100ABCD", date(2026, 1, 3), 1450), row(cat, "POS MSFT * E0100ABCD", date(2026, 3, 5), 2900)]
    rows += monthly(cat, "POS MSFT * E0100ABCD", 1450, date(2026, 4, 3), 3)
    st = one(run(cat, rows)[1], "microsoft365")
    assert st.cycle == "monthly" and "catch_up_2_cycles" in st.flags and "price_changed" not in st.flags
    assert st.expected_amount == 1450 and st.next_due == date(2026, 7, 3) and st.confidence >= 75 and st.missed_cycles == 0
    assert not any("change" in h for h in st.amount_history)


# --- 8. FY tag -----------------------------------------------------------------------------------------
def test_case42_fy_tag_uses_service_period(cat):
    assert fy_of(date(2026, 3, 20)) == "2025-26" and fy_of(date(2026, 4, 1)) == "2026-27" and fy_of(date(2026, 3, 20), 1) == "2026-27"
    bill = row(cat, "Cadspro Technologies | SolidWorks subscription", date(2026, 3, 20), 47200, source="tally", invoice_no="S1",
               period_from=date(2026, 4, 1), period_to=date(2027, 3, 31))
    pay = row(cat, "RTGS-CADSPRO TECHNOLOGIES-SW", date(2026, 3, 20), 47200)
    occs, s = run(cat, [bill, pay])
    assert occs[0].fy == "2026-27" and one(s, "solidworks").fy == "2026-27"
    # no period: FY of the payment date; fy_start_month is a build_streams parameter
    occs = build_occurrences([row(cat, "POS MSFT * E0100ABCD", date(2026, 3, 3), 1450)], cat, TODAY)
    assert build_streams(occs, cat, TODAY)[0].fy == "2025-26"
    assert build_streams(occs, cat, TODAY, fy_start_month=1)[0].fy == "2026-27"


# --- 9. RCM ---------------------------------------------------------------------------------------------
def test_case15_rcm_gst_amount(cat):
    rows = [row(cat, "INTL POS NOTION LABS INC USD 96.00", date(2025, 1, 10) + relativedelta(months=i), 8000, fx_amount=96.0) for i in range(3)]
    st = one(run(cat, rows)[1], "notion")
    assert st.rcm_gst == 1440.0 and "rcm_gst_payable" in st.flags
    assert one(run(cat, monthly(cat, "POS MSFT * E0100ABCD", 1450, date(2026, 1, 3), 3))[1], "microsoft365").rcm_gst is None


# --- 10. personal account (2.36) --------------------------------------------------------------------
def test_case36_personal_card_not_in_company_books(cat):
    rows = [row(cat, "POS CANVA* I03", date(2025, 8, 14), 4000, is_personal=True), row(cat, "POS CANVA* I03", date(2026, 8, 14), 4000, is_personal=True)]
    st = one(run(cat, rows)[1], "canva")
    assert "paid_from_personal" in st.flags and "not_in_company_books" in st.flags
    # a Tally journal for the same charge -> it IS in the books
    rows.append(row(cat, "Canva | paid by director", date(2026, 8, 20), 4000, source="tally", invoice_no="J1"))
    st = one(run(cat, rows)[1], "canva")
    assert "paid_from_personal" in st.flags and "not_in_company_books" not in st.flags


# --- 11. price-change note (TC2) -------------------------------------------------------------------
def test_case2_price_change_note(cat):
    rows = monthly(cat, "POS MSFT * E0100ABCD", 1450, date(2026, 1, 3), 3) + monthly(cat, "POS MSFT * E0100ABCD", 1740, date(2026, 4, 3), 3)
    st = one(run(cat, rows)[1], "microsoft365")
    assert "price_changed" in st.flags and st.change_note == "1,450 → 1,740 on 3 Apr 2026"
    changed = [h for h in st.amount_history if "change" in h]
    assert changed == [{"date": "2026-04-03", "amount": 1740, "change": "+20%"}]
    # 2.16: 1,740 = 12 seats x Rs 145
    assert st.quantity == 12 and st.unit_price == 145
    # AWS (variable) never gets change notes
    rows = [row(cat, "VIN/AMAZON INTERNET SERVICES/ECOM", date(2026, 1, 4) + relativedelta(months=i), a) for i, a in enumerate((8240, 11900, 7300))]
    st = one(run(cat, rows)[1], "aws")
    assert st.change_note is None and not any("change" in h for h in st.amount_history)


# --- 12. seat prices + reseller directory ------------------------------------------------------------
def test_infer_quantity(cat):
    assert cat.infer_quantity("microsoft365", 1740) == (12, 145)
    assert cat.infer_quantity("google_workspace", 2360) == (10, 236)
    assert cat.infer_quantity("quickheal", 17700) == (30, 590)
    assert cat.infer_quantity("microsoft365", 1475) is None          # not a multiple
    assert cat.infer_quantity("quickheal", 590 * 600) is None        # > 500 seats
    assert cat.infer_quantity("adobe", 1740) is None and cat.infer_quantity(None, 1740) is None
    st = one(run(cat, monthly(cat, "GOOGLE *WORKSPACE", 2360, date(2026, 1, 5), 3))[1], "google_workspace")
    assert st.quantity == 10 and st.unit_price == 236


def test_reseller_directory_grew(cat):
    assert len(cat.resellers) >= 60
    for payee, prod in (("SAVEX TECHNOLOGIES", "microsoft365"), ("RASHI PERIPHERALS", "quickheal"), ("ENCAPTECHNO", "zoho"),
                        ("DESIGNTECH SYSTEMS", "solidworks"), ("SILVER TOUCH TECHNOLOGIES", "sap_b1"), ("EMBEE SOFTWARE", "microsoft365")):
        r = cat.resolve(payee, 30000, f"NEFT-N-{payee}-BILL")
        assert r.method == "reseller" and prod in r.candidates, (payee, r)


# --- 13. parsers ----------------------------------------------------------------------------------------
def _xlsx(data):
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active
    for r in data:
        ws.append(r)
    b = io.BytesIO(); wb.save(b)
    return b.getvalue()


def test_detect_bank_and_parse_rows_ex():
    from app.parsers.tabular import parse_rows, parse_rows_ex, detect_bank, load_table
    csv = b"HDFC BANK LTD,,,\nStatement of account,,,\nDate,Narration,Chq./Ref.No.,Withdrawal Amt.,Deposit Amt.\n01/04/2026,CHQ PAID 000412,000412,\"8,850.00\",\n"
    rows, fmt, skipped, bank = parse_rows_ex(csv, "stmt.csv", "bank")
    assert bank == "hdfc" and rows[0]["instrument_no"] == "000412"
    assert parse_rows(csv, "stmt.csv", "bank") == (rows, fmt, skipped)   # old 3-tuple unchanged
    assert detect_bank(load_table(b"ICICI Bank Limited,,\nDate,Narration,Withdrawal Amt.\n", "a.csv")) == "icici"
    assert detect_bank(load_table(b"Date,Narration,Withdrawal Amt.\n01/04/2026,X,1\n", "a.csv")) is None
    # cheque number from the ref column when the narration only says CHQ
    csv = b"Date,Narration,Chq/Ref No,Withdrawal Amt.,Deposit Amt.\n01/04/2026,CHQ PAID,412,\"8,850.00\",\n"
    rows, _, _ = parse_rows(csv, "s.csv", "bank")
    assert rows[0]["instrument_no"] == "412"


def test_tally_parsers_surface_cheque_number():
    from app.parsers.tabular import parse_rows
    from app.parsers.tally_xml import parse_tally_xml
    data = [["Date", "Particulars", "Vch Type", "Vch No.", "Debit", "Credit"],
            ["5-Apr-26", "Cash", "Payment", "46", None, "8,850.00"],
            [None, "ABC Computers", None, None, "8,850.00", None],
            ["6-Apr-26", "HDFC Bank", "Payment", "47", None, "5,310.00"],
            [None, "Shree Infotech", None, None, "5,310.00", None]]
    data2 = [["Date", "Particulars", "Vch Type", "Vch No.", "Narration", "Amount"],
             ["5-Apr-26", "ABC Computers", "Payment", "46", "Chq No: 000412 AMC Q2", "8,850.00"]]
    rows, _, _ = parse_rows(_xlsx(data2), "reg.xlsx", "tally")
    assert rows[0]["instrument_no"] == "000412"
    rows, _, _ = parse_rows(_xlsx(data), "daybook.xlsx", "tally")
    assert all(r["instrument_no"] is None for r in rows)
    xml = b"""<ENVELOPE><BODY><DATA><TALLYMESSAGE>
<VOUCHER VCHTYPE="Payment"><DATE>20260405</DATE><PARTYLEDGERNAME>HDFC Bank</PARTYLEDGERNAME><VOUCHERNUMBER>46</VOUCHERNUMBER><NARRATION>AMC Q2</NARRATION>
<ALLLEDGERENTRIES.LIST><LEDGERNAME>ABC Computers</LEDGERNAME><AMOUNT>-8850.00</AMOUNT></ALLLEDGERENTRIES.LIST>
<ALLLEDGERENTRIES.LIST><LEDGERNAME>HDFC Bank</LEDGERNAME><AMOUNT>8850.00</AMOUNT>
<BANKALLOCATIONS.LIST><INSTRUMENTNUMBER>000412</INSTRUMENTNUMBER><TRANSACTIONTYPE>Cheque</TRANSACTIONTYPE></BANKALLOCATIONS.LIST></ALLLEDGERENTRIES.LIST>
</VOUCHER>
<VOUCHER VCHTYPE="Payment"><DATE>20260406</DATE><PARTYLEDGERNAME>Cash</PARTYLEDGERNAME><VOUCHERNUMBER>47</VOUCHERNUMBER><NARRATION>Ch. No 000413 TSS</NARRATION>
<ALLLEDGERENTRIES.LIST><LEDGERNAME>Shree Infotech</LEDGERNAME><AMOUNT>-5310.00</AMOUNT></ALLLEDGERENTRIES.LIST>
<ALLLEDGERENTRIES.LIST><LEDGERNAME>Cash</LEDGERNAME><AMOUNT>5310.00</AMOUNT></ALLLEDGERENTRIES.LIST>
</VOUCHER></TALLYMESSAGE></DATA></BODY></ENVELOPE>"""
    rows, _, _ = parse_tally_xml(xml)
    assert [r["instrument_no"] for r in rows] == ["000412", "000413"]
    assert rows[0]["raw_description"] == "ABC Computers | AMC Q2"


def test_pdf_password():
    pytest.importorskip("pdfplumber")
    pytest.importorskip("reportlab")
    pypdf = pytest.importorskip("pypdf")
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
    from reportlab.lib import colors
    from app.parsers.tabular import parse_rows, parse_rows_ex
    b = io.BytesIO()
    t = Table([["Date", "Narration", "Withdrawal", "Deposit", "Balance"], ["01/04/2026", "CHQ 000412", "8,850.00", "", "1,00,000.00"]])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
    SimpleDocTemplate(b, pagesize=A4).build([t])
    w = pypdf.PdfWriter(); w.append(pypdf.PdfReader(io.BytesIO(b.getvalue()))); w.encrypt("12345678")
    enc = io.BytesIO(); w.write(enc); enc = enc.getvalue()
    for pw in (None, "wrong"):
        with pytest.raises(ValueError, match="needs a password"):
            parse_rows(enc, "stmt.pdf", "bank", pdf_password=pw)
    rows, _, _, _ = parse_rows_ex(enc, "stmt.pdf", "bank", pdf_password="12345678")
    assert len(rows) == 1 and rows[0]["amount"] == 8850 and rows[0]["instrument_no"] == "000412"
    # unencrypted PDFs still open without a password
    assert parse_rows(b.getvalue(), "stmt.pdf", "bank")[0][0]["amount"] == 8850
