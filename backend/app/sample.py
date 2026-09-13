"""Realistic sample company so the app opens full on first run. Also writes the same files to backend/samples/
so users can see what an upload looks like. Dates are relative to today."""
from __future__ import annotations
import random
from datetime import date, timedelta
from pathlib import Path
from dateutil.relativedelta import relativedelta
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models as m
from app.engine import runner
from app.parsers.tabular import parse_rows

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def _bank_rows(today: date) -> list[dict]:
    rnd = random.Random(7)
    rows: list[dict] = []
    start = today - relativedelta(months=24)

    def add(d, desc, debit=None, credit=None, ref=""):
        if d > today:
            return
        rows.append({"Date": d.strftime("%d/%m/%Y"), "Narration": desc, "Chq/Ref No": ref,
                     "Withdrawal Amt": debit, "Deposit Amt": credit})

    # Microsoft 365 – card, 3rd of every month, seat change 8 months ago (1,450 -> 1,740)
    d = date(start.year, start.month, 3)
    while d <= today:
        amt = 1450 if d < today - relativedelta(months=8) else 1740
        add(d + timedelta(days=rnd.choice([0, 0, 1])), "POS 4XXXXX MSFT * E0100ABCD REDMOND WA", amt)
        d += relativedelta(months=1)
    # Google Workspace via Razorpay, 5th monthly
    d = date(start.year, start.month, 5)
    while d <= today:
        add(d, "UPI/425511/razorpay.google@icici/GOOGLE WORKSPACE/ICIC", 2360)
        d += relativedelta(months=1)
    # AWS variable, 4th monthly
    d = date(start.year, start.month, 4)
    while d <= today:
        add(d, "VIN/AMAZON INTERNET SERVICES PVT LTD/20240104/ECOM", round(rnd.uniform(7300, 15100), 2))
        d += relativedelta(months=1)
    # Adobe USD with forex markup, 8th monthly
    d = date(start.year, start.month, 8)
    while d <= today:
        inr = round(54.99 * rnd.uniform(83.5, 85.5), 2)
        add(d, "POS 4XXXXX ADOBE SYSTEMS SOFTWARE IRELAND LTD DUBLIN", inr)
        add(d + timedelta(days=1), "FOREIGN CURRENCY MARKUP FEE + GST", round(inr * 0.035, 2))
        d += relativedelta(months=1)
    # Tally: licence 2 years ago via reseller, then TSS Silver every April (a bit early/late)
    lic = date(start.year, start.month, 2)
    add(lic, "NEFT-N0000001-SHREE INFOTECH-TALLY PRIME SILVER", 26550, ref="N0000001")
    for yr in range(start.year, today.year + 1):
        t = date(yr, 4, rnd.choice([8, 10, 15]))
        if lic < t <= today:
            add(t, "NEFT-N0000002-SHREE INFOTECH-TSS RENEWAL", 5310, ref="N0000002")
    # SolidWorks subscription service via Cadspro, yearly in March, TDS 2% on 40,000 -> bank 46,400
    for yr in range(start.year, today.year + 1):
        t = date(yr, 3, 20)
        if start <= t <= today:
            add(t, "RTGS-CADSPRO TECHNOLOGIES PVT LTD-SW SUBSCRIPTION", 46400, ref=f"SW{yr}")
    # Seqrite 3-year key once, 14 months ago
    add(today - relativedelta(months=14), "NEFT-SHREE INFOTECH-SEQRITE EPS 30 USERS 3YR", 63720, ref="N0000003")
    # GoDaddy domain 2 years apart (last one 13 months ago) -> yearly
    add(today - relativedelta(months=25), "POS 4XXXXX DNH*GODADDY.COM", 1299)
    add(today - relativedelta(months=13), "POS 4XXXXX DNH*GODADDY.COM", 1499)
    add(today - relativedelta(months=1), "POS 4XXXXX DNH*GODADDY.COM", 1499)
    # Airtel broadband NACH, monthly variable
    d = date(start.year, start.month, 12)
    while d <= today:
        add(d, "ACH D- BHARTI AIRTEL LTD-AIRTELBB", rnd.choice([2065, 2140, 2065, 2183]))
        d += relativedelta(months=1)
    # MSG91 prepaid credits, irregular
    for k in (0, 49, 75, 138, 190, 251, 300, 366, 401, 470, 520, 600, 660):
        t = start + timedelta(days=k)
        if t <= today:
            add(t, "UPI/900123/walkoverwebsolutions@ybl/MSG91 CREDITS", rnd.choice([5000, 5000, 10000]))
    # IT support AMC quarterly, ABC Computers, sometimes late
    d = date(start.year, start.month, 6)
    while d <= today:
        add(d + timedelta(days=rnd.choice([0, 3, 12])), "NEFT-ABC COMPUTERS-IT AMC Q", 8850)
        d += relativedelta(months=3)
    # Zoom monthly, with one refund
    d = date(start.year, start.month, 15)
    i = 0
    while d <= today - relativedelta(months=5):
        add(d, "POS 4XXXXX ZOOM.US 888-799-9666 SAN JOSE", 1769)
        if i == 6:
            add(d + timedelta(days=4), "REFUND ZOOM.US", credit=1769)
        d += relativedelta(months=1)
        i += 1
    # Unknown yearly to a local firm (question)
    add(today - relativedelta(months=17), "NEFT-SRI BALAJI ENTERPRISES-BILL 118", 11800, ref="B118")
    add(today - relativedelta(months=5), "NEFT-SRI BALAJI ENTERPRISES-BILL 231", 11800, ref="B231")
    # Auth charge then subscription (Canva yearly) – 2 hits
    add(today - relativedelta(months=15), "POS 4XXXXX CANVA* I03X SYDNEY", 2)
    add(today - relativedelta(months=15) + timedelta(days=3), "POS 4XXXXX CANVA* I03X SYDNEY", 3999)
    add(today - relativedelta(months=3), "POS 4XXXXX CANVA* I03X SYDNEY", 3999)
    # Noise: salary, raw material, electricity, GST, bank charges, TDS challan, customer receipts
    d = start
    while d <= today:
        add(date(d.year, d.month, 1), "NEFT-SALARY BATCH-STAFF SALARY", 845000)
        add(date(d.year, d.month, 9), "RTGS-JINDAL STEEL-RAW MATERIAL", round(rnd.uniform(400000, 900000), 2))
        add(date(d.year, d.month, 11), "BIL/ONL/TSSPDCL ELECTRICITY", round(rnd.uniform(60000, 95000), 2))
        add(date(d.year, d.month, 20), "GST PMT-2400PAYMENT", round(rnd.uniform(120000, 220000), 2))
        add(date(d.year, d.month, 7), "TIN NSDL-TDS CHALLAN", 14200)
        add(date(d.year, d.month, 28), "CONSOLIDATED CHARGES FOR A/C", 590)
        add(date(d.year, d.month, 16), "NEFT-CUSTOMER RECEIPT-M/S KIRLOSKAR", credit=round(rnd.uniform(500000, 1500000), 2))
        d += relativedelta(months=1)
    rows.sort(key=lambda r: pd.to_datetime(r["Date"], dayfirst=True))
    return rows


def _tally_rows(today: date) -> list[dict]:
    """Purchase register: shows the SolidWorks invoice (so TDS matches) and a reseller bill with line items."""
    rows = []
    for yr in range(today.year - 2, today.year + 1):
        t = date(yr, 3, 1)
        if t <= today and t >= today - relativedelta(months=24):
            rows.append({"Date": t.strftime("%d-%b-%y"), "Particulars": "Cadspro Technologies Pvt Ltd", "Vch Type": "Purchase",
                         "Vch No.": f"SW{yr}", "GSTIN/UIN": "36AAACC1234A1Z5", "Taxable Value": 40000, "GST": 7200, "Gross Total": 47200,
                         "Narration": "SolidWorks Subscription Service 1 seat 01-Apr to 31-Mar"})
    rows.append({"Date": (today - relativedelta(months=14)).strftime("%d-%b-%y"), "Particulars": "Shree Infotech", "Vch Type": "Purchase",
                 "Vch No.": "SI/2025/118", "GSTIN/UIN": "36AABCS9876B1Z2", "Taxable Value": 54000, "GST": 9720, "Gross Total": 63720,
                 "Narration": "Seqrite Endpoint Security 30 users 3 years"})
    # a bill booked but not yet paid (shows as "booked, not paid")
    rows.append({"Date": (today - timedelta(days=6)).strftime("%d-%b-%y"), "Particulars": "Uneecops Technologies", "Vch Type": "Purchase",
                 "Vch No.": "UT/26/0912", "GSTIN/UIN": "07AAACU1111C1Z9", "Taxable Value": 180000, "GST": 32400, "Gross Total": 212400,
                 "Narration": "SAP B1 AMC FY 26-27, 10 users"})
    return rows


def write_sample_files(today: date | None = None) -> tuple[Path, Path]:
    today = today or date.today()
    SAMPLES.mkdir(exist_ok=True)
    bank = SAMPLES / "sample_hdfc_current_account.xlsx"
    tally = SAMPLES / "sample_tally_purchase_register.xlsx"
    bdf = pd.DataFrame(_bank_rows(today))
    with pd.ExcelWriter(bank) as xw:
        # mimic a real statement: 5 lines of account details, then the table
        head = pd.DataFrame([["Sri Venkateswara Precision Engineering Pvt Ltd"], ["Account No: XXXXXXXX4521  Current Account"],
                             ["Statement of account"], [""], [""]])
        head.to_excel(xw, index=False, header=False, startrow=0)
        bdf.to_excel(xw, index=False, startrow=5)
    pd.DataFrame(_tally_rows(today)).to_excel(tally, index=False)
    return bank, tally


def seed_sample_if_empty(db: Session, today: date | None = None):
    if db.execute(select(m.Company.id)).first():
        return
    today = today or date.today()
    bank, tally = write_sample_files(today)
    c = m.Company(name="Sri Venkateswara Precision Engineering Pvt Ltd (sample)", gstin="36AAACS1234A1Z5")
    db.add(c)
    db.flush()
    for path, kind, label in ((bank, "bank", "HDFC Current A/c"), (tally, "tally", "Tally purchase register")):
        acc = m.Account(company_id=c.id, label=label, kind="bank" if kind == "bank" else "tally", bank_name="HDFC" if kind == "bank" else None)
        db.add(acc)
        db.flush()
        batch = m.ImportBatch(company_id=c.id, account_id=acc.id, filename=path.name, source_kind=kind)
        db.add(batch)
        db.flush()
        rows, fmt, skipped = parse_rows(path.read_bytes(), path.name, kind)
        added, dup = runner.ingest_rows(db, c, acc, batch, rows, kind)
        batch.rows_imported, batch.rows_skipped, batch.detected_format = added, skipped + dup, fmt
    db.commit()
    runner.run_engine(db, c.id, today)
