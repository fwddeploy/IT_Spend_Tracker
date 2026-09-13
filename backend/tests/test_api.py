"""End-to-end: create company -> upload bank + tally files -> dashboard -> answer a question -> confirm / edit / mark paid."""
import os
import tempfile
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(tempfile.mkdtemp(), "test.db"))
os.environ["SEED_SAMPLE"] = "0"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.sample import write_sample_files  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def files():
    return write_sample_files()


def test_full_flow(client, files):
    bank, tally = files
    r = client.post("/api/companies", json={"name": "Test Factory", "gstin": "36AAAAA0000A1Z5"})
    assert r.status_code == 200
    cid = r.json()["id"]

    with open(bank, "rb") as f:
        r = client.post(f"/api/companies/{cid}/upload", files={"file": (bank.name, f)}, data={"source_kind": "bank", "account_label": "HDFC Current"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["batch"]["rows_imported"] > 100 and body["engine"]["streams"] >= 10

    with open(tally, "rb") as f:
        r = client.post(f"/api/companies/{cid}/upload", files={"file": (tally.name, f)}, data={"source_kind": "tally"})
    assert r.status_code == 200, r.text
    assert r.json()["batch"]["detected_format"] == "tally_register"

    # re-upload the same file -> nothing new (dedupe)
    with open(bank, "rb") as f:
        r = client.post(f"/api/companies/{cid}/upload", files={"file": (bank.name, f)}, data={"source_kind": "bank", "account_label": "HDFC Current"})
    assert r.json()["batch"]["rows_imported"] == 0

    d = client.get(f"/api/companies/{cid}/dashboard").json()
    assert d["monthly_equivalent"] > 0 and d["cash_out_month"] > 0 and len(d["calendar"]) == 12
    assert any(c["category"] == "cad" for c in d["by_category"])

    streams = client.get(f"/api/companies/{cid}/streams").json()
    names = {s["vendor_name"] for s in streams}
    assert {"Microsoft 365", "SolidWorks (Dassault)", "Tally (TSS / licence)"} <= names
    sw = next(s for s in streams if s["vendor_name"].startswith("SolidWorks"))
    assert sw["cycle"] == "yearly" and sw["expected_amount"] == 47200 and "tally" in sw["sources"]

    # questions: answer the unknown vendor one
    qs = client.get(f"/api/companies/{cid}/questions").json()
    vq = next(q for q in qs if q["kind"] == "vendor")
    r = client.post(f"/api/companies/{cid}/questions/{vq['id']}/answer", json={"choice": "v:it_amc:Website AMC"})
    assert r.status_code == 200
    streams = client.get(f"/api/companies/{cid}/streams").json()
    balaji = [s for s in streams if s["payee_name"] == "SRI BALAJI ENTERPRISES"]
    assert balaji and balaji[0]["vendor_name"].startswith("IT support AMC") and balaji[0]["status"] != "needs_confirm"
    assert not any(q["kind"] == "vendor" for q in client.get(f"/api/companies/{cid}/questions").json())

    # stopped question -> cancelled
    sq = next(q for q in client.get(f"/api/companies/{cid}/questions").json() if q["kind"] == "stopped")
    r = client.post(f"/api/companies/{cid}/questions/{sq['id']}/answer", json={"choice": "cancelled"})
    assert r.json()["stream"]["status"] == "cancelled"

    # edit a line: cycle change sticks across a re-run
    m365 = next(s for s in streams if s["vendor_name"] == "Microsoft 365")
    r = client.patch(f"/api/companies/{cid}/streams/{m365['id']}", json={"owner_name": "Ravi", "cycle": "monthly", "pay_url": "https://admin.microsoft.com"})
    assert r.json()["owner_name"] == "Ravi" and r.json()["is_user_modified"]
    client.post(f"/api/companies/{cid}/run")
    m365b = client.get(f"/api/companies/{cid}/streams/{m365['id']}").json()
    assert m365b["owner_name"] == "Ravi" and len(m365b["occurrences"]) >= 20

    # mark paid on an engine stream rolls the due date
    tss = next(s for s in streams if s["product"] == "TSS renewal")
    r = client.post(f"/api/companies/{cid}/streams/{tss['id']}/mark-paid", json={"date": "2027-04-09"})
    assert r.status_code == 200 and r.json()["next_due"] == "2028-04-09"

    # manual add
    r = client.post(f"/api/companies/{cid}/streams", json={"vendor_name": "Keka HR", "category": "hr", "cycle": "monthly", "expected_amount": 4500, "last_paid_date": "2026-09-01"})
    assert r.status_code == 200 and r.json()["next_due"] == "2026-10-01" and r.json()["status"] in ("active", "due_soon")
    client.post(f"/api/companies/{cid}/run")
    assert any(s["vendor_name"] == "Keka HR" for s in client.get(f"/api/companies/{cid}/streams").json())

    up = client.get(f"/api/companies/{cid}/upcoming?days=120").json()
    assert up and all("total" in mth for mth in up)

    # bad file
    r = client.post(f"/api/companies/{cid}/upload", files={"file": ("x.xlsx", b"not an excel")}, data={"source_kind": "bank"})
    assert r.status_code == 400 and "detail" in r.json()


def test_mark_paid_keeps_cycle_and_later_payment_moves_due(client, files):
    bank, tally = files
    cid = client.post("/api/companies", json={"name": "Mark Paid Co"}).json()["id"]
    with open(bank, "rb") as f:
        client.post(f"/api/companies/{cid}/upload", files={"file": (bank.name, f)}, data={"source_kind": "bank", "account_label": "HDFC"})
    with open(tally, "rb") as f:
        client.post(f"/api/companies/{cid}/upload", files={"file": (tally.name, f)}, data={"source_kind": "tally"})
    sw = next(s for s in client.get(f"/api/companies/{cid}/streams").json() if s["vendor_name"].startswith("SolidWorks"))
    before_meq = sw["monthly_equivalent"]
    r = client.post(f"/api/companies/{cid}/streams/{sw['id']}/mark-paid", json={"date": "2026-09-13"}).json()
    assert r["cycle"] == "yearly" and r["monthly_equivalent"] == before_meq and r["next_due"] == "2027-09-13"
    assert r["paid_from"], "paid_from must survive a mark-paid re-run"
    # a note edit must not silently confirm / change anything else
    r2 = client.patch(f"/api/companies/{cid}/streams/{sw['id']}", json={"notes": "check with Cadspro"}).json()
    assert r2["cycle"] == "yearly" and r2["notes"] == "check with Cadspro"
    # a user-typed next_due is respected until a newer real payment arrives, then the engine takes over again
    client.patch(f"/api/companies/{cid}/streams/{sw['id']}", json={"next_due": "2027-10-01"})
    assert client.get(f"/api/companies/{cid}/streams/{sw['id']}").json()["next_due"] == "2027-10-01"
    import io, pandas as pd
    df = pd.DataFrame([{"Date": "20/03/2028", "Narration": "RTGS-CADSPRO TECHNOLOGIES PVT LTD-SW SUBSCRIPTION", "Chq/Ref No": "SW2028", "Withdrawal Amt": 46400, "Deposit Amt": None}])
    buf = io.BytesIO(); df.to_excel(buf, index=False); buf.seek(0)
    client.post(f"/api/companies/{cid}/upload", files={"file": ("later.xlsx", buf)}, data={"source_kind": "bank", "account_label": "HDFC"})
    sw2 = client.get(f"/api/companies/{cid}/streams/{sw['id']}").json()
    assert sw2["last_paid_date"] == "2028-03-20" and sw2["next_due"] == "2029-03-20"
    d = client.get(f"/api/companies/{cid}/dashboard").json()
    assert "cash_breakdown" in d and d["cash_out_month"] >= d["cash_breakdown"]["paid"]


def test_same_day_identical_rows_both_imported(client):
    import io, pandas as pd
    cid = client.post("/api/companies", json={"name": "Dup Co"}).json()["id"]
    rows = [{"Date": "05/06/2026", "Narration": "POS 4XXXX ZOOM.US 888-799-9666", "Withdrawal Amt": 1769, "Deposit Amt": None}] * 2
    df = pd.DataFrame(rows)
    buf = io.BytesIO(); df.to_excel(buf, index=False); buf.seek(0)
    r = client.post(f"/api/companies/{cid}/upload", files={"file": ("two.xlsx", buf)}, data={"source_kind": "bank"}).json()
    assert r["batch"]["rows_imported"] == 2
    buf.seek(0)
    r = client.post(f"/api/companies/{cid}/upload", files={"file": ("two.xlsx", buf)}, data={"source_kind": "bank"}).json()
    assert r["batch"]["rows_imported"] == 0


def test_upload_guards(client):
    cid = client.post("/api/companies", json={"name": "Guard Co"}).json()["id"]
    r = client.post(f"/api/companies/{cid}/upload", files={"file": ("fake.xlsx", b"hello world")}, data={"source_kind": "bank"})
    assert r.status_code == 400 and "not a real Excel" in r.json()["detail"]
    r = client.post(f"/api/companies/{cid}/upload", files={"file": ("x.exe", b"MZ")}, data={"source_kind": "bank"})
    assert r.status_code == 400
