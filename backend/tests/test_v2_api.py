"""v2 routes: auth + roles, settings, delete company, aliases undo, reminders, share text, export, FY view, audit,
bulk answers, bundle questions, upload additions."""
import io
import os
import tempfile
from datetime import date, timedelta

os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(tempfile.mkdtemp(), "test_v2.db"))
os.environ["SEED_SAMPLE"] = "0"
os.environ["SCHEDULER"] = "0"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["APP_ACCESS_KEY"] = "script-key"

import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from openpyxl import load_workbook  # noqa: E402

from app.main import app  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app import models as m  # noqa: E402
from app import reminders as R  # noqa: E402
from app.sample import write_sample_files  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def files():
    return write_sample_files()


def _xlsx(rows: list[dict]) -> io.BytesIO:
    buf = io.BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False)
    buf.seek(0)
    return buf


@pytest.fixture(scope="module")
def owner(client, files):
    """Registers the owner, uploads the sample files, returns (client, company_id)."""
    r = client.post("/api/auth/register", json={"name": "Owner", "email": "owner@example.com", "password": "secret123", "company_name": "Owner Co"})
    assert r.status_code == 200, r.text
    cid = r.json()["companies"][0]["id"]
    assert r.json()["companies"][0]["role"] == "owner"
    bank, tally = files
    with open(bank, "rb") as f:
        r = client.post(f"/api/companies/{cid}/upload", files={"file": (bank.name, f)}, data={"source_kind": "bank", "account_label": "HDFC Current"})
    assert r.status_code == 200, r.text
    assert r.json()["detected_bank"] is None or r.json()["detected_bank"] == "HDFC"
    with open(tally, "rb") as f:
        client.post(f"/api/companies/{cid}/upload", files={"file": (tally.name, f)}, data={"source_kind": "tally"})
    return cid


# ---------- auth ----------
def test_unauthenticated_is_401():
    with TestClient(app) as c:
        assert c.get("/api/companies").status_code == 401
        assert c.get("/api/auth/me").status_code == 401
        assert c.get("/api/health").status_code == 200


def test_access_key_header_still_works(owner):
    with TestClient(app, headers={"X-Access-Key": "script-key"}) as c:
        r = c.get("/api/companies")
        assert r.status_code == 200 and any(co["id"] == owner for co in r.json())
        assert c.get(f"/api/companies/{owner}/streams").status_code == 200
    with TestClient(app, headers={"X-Access-Key": "wrong"}) as c:
        assert c.get("/api/companies").status_code == 401


def test_login_logout_me(client, owner):
    me = client.get("/api/auth/me").json()
    assert me["user"]["email"] == "owner@example.com" and me["companies"][0]["role"] == "owner"
    with TestClient(app) as c2:
        assert c2.post("/api/auth/login", json={"email": "owner@example.com", "password": "nope"}).status_code == 401
        r = c2.post("/api/auth/login", json={"email": "Owner@Example.com", "password": "secret123"})
        assert r.status_code == 200 and c2.get("/api/auth/me").status_code == 200
        assert c2.post("/api/auth/logout").status_code == 204
        assert c2.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/register", json={"name": "x", "email": "owner@example.com", "password": "secret123", "company_name": "y"}).status_code == 400


def test_invite_and_roles(client, owner):
    r = client.post("/api/auth/invite", json={"company_id": owner, "email": "viewer@example.com", "role": "viewer"})
    assert r.status_code == 200 and r.json()["temp_password"]
    pw = r.json()["temp_password"]
    r = client.post("/api/auth/invite", json={"company_id": owner, "email": "acct@example.com", "role": "accountant"})
    pw2 = r.json()["temp_password"]
    with TestClient(app) as v:
        assert v.post("/api/auth/login", json={"email": "viewer@example.com", "password": pw}).status_code == 200
        assert v.get(f"/api/companies/{owner}/streams").status_code == 200
        assert v.get(f"/api/companies/{owner}/settings").status_code == 200
        sid = v.get(f"/api/companies/{owner}/streams").json()[0]["id"]
        assert v.patch(f"/api/companies/{owner}/streams/{sid}", json={"notes": "x"}).status_code == 403
        assert v.patch(f"/api/companies/{owner}/settings", json={"short_name": "x"}).status_code == 403
        assert v.delete(f"/api/companies/{owner}").status_code == 403
        # a viewer creating their own company becomes its owner, but still can't invite into ours
        other = v.post("/api/companies", json={"name": "Viewer's own"}).json()["id"]
        assert v.get(f"/api/companies/{other}").json()["role"] == "owner"
        assert v.post("/api/auth/invite", json={"company_id": owner, "email": "z@example.com", "role": "owner"}).status_code == 403
        assert client.get(f"/api/companies/{other}").status_code == 403   # not a member
        assert {c["id"] for c in v.get("/api/companies").json()} == {owner, other}
    with TestClient(app) as a:
        a.post("/api/auth/login", json={"email": "acct@example.com", "password": pw2})
        sid = a.get(f"/api/companies/{owner}/streams").json()[0]["id"]
        assert a.patch(f"/api/companies/{owner}/streams/{sid}", json={"notes": "acct note"}).status_code == 200
        assert a.patch(f"/api/companies/{owner}/settings", json={"short_name": "x"}).status_code == 403
    # re-inviting an existing user changes the role, no new password
    r = client.post("/api/auth/invite", json={"company_id": owner, "email": "viewer@example.com", "role": "accountant"})
    assert r.json()["temp_password"] is None and r.json()["role"] == "accountant"


# ---------- settings / delete ----------
def test_settings_roundtrip(client, owner):
    s = client.get(f"/api/companies/{owner}/settings").json()
    assert s["reminder_days_before"] == {"monthly": 5, "quarterly": 10, "yearly": 30} and s["fy_start_month"] == 4
    r = client.patch(f"/api/companies/{owner}/settings", json={"short_name": "OwnerCo", "owner_phone": "+919876543210", "owner_email": "md@example.com",
                                                              "whatsapp_enabled": True, "email_enabled": True,
                                                              "reminder_days_before": {"yearly": 45}, "weekly_digest_day": "mon"})
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["short_name"] == "OwnerCo" and s["reminder_days_before"]["yearly"] == 45 and s["reminder_days_before"]["monthly"] == 5
    assert client.patch(f"/api/companies/{owner}/settings", json={"weekly_digest_day": "xyz"}).status_code == 400
    assert client.patch(f"/api/companies/{owner}/settings", json={"fy_start_month": 13}).status_code == 400
    ev = client.get(f"/api/companies/{owner}/events").json()
    assert ev and ev[0]["action"] == "settings" and ev[0]["user"] == "owner@example.com"


def test_delete_company_cascades(client, files):
    bank, _ = files
    cid = client.post("/api/companies", json={"name": "Throwaway"}).json()["id"]
    with open(bank, "rb") as f:
        client.post(f"/api/companies/{cid}/upload", files={"file": (bank.name, f)}, data={"source_kind": "bank"})
    assert client.get(f"/api/companies/{cid}/streams").json()
    assert client.delete(f"/api/companies/{cid}").status_code == 204
    assert client.get(f"/api/companies/{cid}").status_code == 404
    with SessionLocal() as db:
        for model in (m.Stream, m.Occurrence, m.RawRow, m.ImportBatch, m.Account, m.Question, m.Membership, m.Event):
            assert db.query(model).filter_by(company_id=cid).count() == 0, model.__name__


# ---------- aliases ----------
def test_alias_list_and_undo(client, owner):
    qs = client.get(f"/api/companies/{owner}/questions").json()
    vq = next(q for q in qs if q["kind"] == "vendor")
    payee = vq["context"]["payee"]
    client.post(f"/api/companies/{owner}/questions/{vq['id']}/answer", json={"choice": "not_it"})
    assert not any(s["payee_name"] == payee for s in client.get(f"/api/companies/{owner}/streams").json())
    al = client.get(f"/api/companies/{owner}/aliases").json()
    hidden = [a for a in al if a["hidden"]]
    assert hidden and hidden[0]["pattern"] == payee and hidden[0]["vendor_name"] == "Not IT"
    assert client.delete(f"/api/companies/{owner}/aliases/{hidden[0]['id']}").status_code == 204
    assert not any(a["id"] == hidden[0]["id"] for a in client.get(f"/api/companies/{owner}/aliases").json())
    # engine re-ran: the payee is back as a line / question
    assert any(s["payee_name"] == payee for s in client.get(f"/api/companies/{owner}/streams").json()) or \
        any(q["context"].get("payee") == payee for q in client.get(f"/api/companies/{owner}/questions").json())
    assert client.delete(f"/api/companies/{owner}/aliases/999999").status_code == 404
    assert any(e["action"] == "alias_delete" for e in client.get(f"/api/companies/{owner}/events").json())


# ---------- reminders ----------
def test_reminders_preview_send_now_log(client, owner, monkeypatch):
    streams = client.get(f"/api/companies/{owner}/streams").json()
    live = next(s for s in streams if s["status"] in ("active", "due_soon", "overdue") and s["next_due"])
    pv = client.get(f"/api/companies/{owner}/reminders?days=400").json()
    assert any(p["stream_id"] == live["id"] for p in pv)
    row = next(p for p in pv if p["stream_id"] == live["id"])
    assert set(row["channel"]) == {"whatsapp", "email"} and row["will_send_on"] <= row["due"]
    # env not configured -> skipped_not_configured, logged
    r = client.post(f"/api/companies/{owner}/reminders/send-now", json={"stream_id": live["id"]})
    assert r.status_code == 200, r.text
    sent = r.json()["sent"]
    assert {s["channel"] for s in sent} == {"whatsapp", "email"} and all(s["status"] == "skipped_not_configured" for s in sent)
    lg = client.get(f"/api/companies/{owner}/reminders/log").json()
    assert lg and lg[0]["status"] == "skipped_not_configured" and "IT Tracker · OwnerCo" in lg[0]["message"] and "Reply PAID when done." in lg[0]["message"]
    # configured + fake transport -> sent
    monkeypatch.setenv("WA_PHONE_NUMBER_ID", "123")
    monkeypatch.setenv("WA_TOKEN", "tok")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    calls = []

    class FakeResp:
        status_code = 200
        text = "ok"
    monkeypatch.setattr(R.httpx, "post", lambda url, **kw: (calls.append(("wa", kw["json"]["to"])), FakeResp())[1])

    class FakeSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def ehlo(self): pass
        def starttls(self): pass
        def login(self, u, p): pass
        def send_message(self, msg): calls.append(("email", msg["To"]))
    monkeypatch.setattr(R.smtplib, "SMTP", FakeSMTP)
    r = client.post(f"/api/companies/{owner}/reminders/send-now", json={"stream_id": live["id"]}).json()
    assert all(s["ok"] for s in r["sent"]) and ("wa", "919876543210") in calls and ("email", "md@example.com") in calls


def test_compute_due_reminders_and_dedupe(owner):
    with SessionLocal() as db:
        company = db.get(m.Company, owner)
        today = date(2030, 1, 1)
        st = m.Stream(company_id=owner, stream_key="manual|rem", vendor_name="Remind Me", cycle="monthly", cycle_months=1, expected_amount=999,
                      status="active", reminder_on=True, next_due=today + timedelta(days=5), confidence=100, is_user_modified=True)
        db.add(st)
        db.commit()
        due = R.compute_due_reminders(db, company, today)
        assert {(s.id, ch) for s, ch, _ in due} >= {(st.id, "whatsapp"), (st.id, "email")}
        assert not [x for x in R.compute_due_reminders(db, company, today + timedelta(days=1)) if x[0].id == st.id]  # 4 days: not a trigger day
        res = R.run_reminders(db, today)
        assert res["skipped"] >= 2 or res["sent"] >= 2
        assert not [x for x in R.compute_due_reminders(db, company, today) if x[0].id == st.id]   # deduped on stream+due+channel
        # overdue: reminded again only after 7 days
        st.next_due = today - timedelta(days=3)
        db.commit()
        assert not [x for x in R.compute_due_reminders(db, company, today) if x[0].id == st.id]
        for row in db.query(m.ReminderLog).filter_by(stream_id=st.id):
            row.sent_at = row.sent_at - timedelta(days=8)
        db.commit()
        assert [x for x in R.compute_due_reminders(db, company, today) if x[0].id == st.id]
        db.delete(st)
        db.execute(m.ReminderLog.__table__.delete().where(m.ReminderLog.stream_id == st.id))
        db.commit()


def test_internal_reminder_run(client, owner):
    r = client.post("/api/internal/reminders/run")
    assert r.status_code == 200 and set(r.json()) >= {"sent", "skipped", "failed"}
    with TestClient(app, headers={"X-Access-Key": "script-key"}) as c:
        assert c.post("/api/internal/reminders/run").status_code == 200


# ---------- share / export / FY / audit ----------
def test_share_text(client, owner):
    t = client.get(f"/api/companies/{owner}/share-text").json()["text"]
    lines = t.split("\n")
    assert lines[0] == "IT Tracker · OwnerCo" and 4 <= len(lines) <= 12 and "Monthly-equivalent" in t


def test_export_xlsx(client, owner):
    r = client.get(f"/api/companies/{owner}/export.xlsx")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"] and r.headers["content-disposition"].endswith('.xlsx"')
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Lines", "Upcoming", "Payments", "Questions"]
    assert wb["Lines"].max_row > 5 and wb["Payments"].max_row > 50 and wb["Lines"]["A1"].value == "Vendor"


def test_fy_dashboard(client, owner):
    d = client.get(f"/api/companies/{owner}/dashboard?fy=2026").json()
    assert d["period"] == "FY 2026-27" and d["calendar"][0]["month"] == "2026-04" and d["calendar"][-1]["month"] == "2027-03"
    assert d["cash_out_period"] == round(sum(c["cash_out"] for c in d["calendar"]), 2) and d["cash_out_period"] > 0
    # past months are actuals (items carry paid=True), future months are dues
    past = [c for c in d["calendar"] if c["month"] < date.today().strftime("%Y-%m")]
    assert past and all(it.get("paid") for it in past[0]["items"])
    mo = client.get(f"/api/companies/{owner}/dashboard").json()
    assert mo["period"] and "cash_out_month" in mo and len(mo["calendar"]) == 12
    client.patch(f"/api/companies/{owner}/settings", json={"fy_start_month": 1})
    assert client.get(f"/api/companies/{owner}/dashboard?fy=2026").json()["period"] == "FY 2026"
    client.patch(f"/api/companies/{owner}/settings", json={"fy_start_month": 4})


def test_stream_out_v2_fields(client, owner):
    streams = client.get(f"/api/companies/{owner}/streams").json()
    m365 = next(s for s in streams if s["vendor_name"] == "Microsoft 365")
    assert m365["quantity"] == 12 and m365["unit_price"] == 145 and m365["fy"] and "-" in m365["fy"]
    assert all(isinstance(f, str) and "_" not in f for s in streams for f in s["flags_human"])
    assert all(len(s["flags_human"]) == len(s["flags"]) for s in streams)
    adobe = next((s for s in streams if s["vendor_name"].startswith("Adobe")), None)
    if adobe and "rcm_gst_payable" in adobe["flags"]:
        assert adobe["rcm_gst"] == round(adobe["expected_amount"] * 0.18, 2)
    assert all(s["supplier_history"] == [] or len(s["supplier_history"]) > 1 for s in streams)


def test_events_written(client, owner):
    streams = client.get(f"/api/companies/{owner}/streams").json()
    sid = streams[0]["id"]
    client.patch(f"/api/companies/{owner}/streams/{sid}", json={"notes": "audit me"})
    client.post(f"/api/companies/{owner}/streams/{sid}/confirm", json={"accept": True})
    client.post(f"/api/companies/{owner}/streams/{sid}/mark-paid", json={"date": "2026-09-01", "amount": 10})
    ev = client.get(f"/api/companies/{owner}/events?limit=10").json()
    actions = [e["action"] for e in ev]
    assert actions[:3] == ["mark_paid", "confirm", "patch"] and ev[2]["detail"]["notes"] == "audit me"
    assert {"upload", "answer", "settings"} <= set(e["action"] for e in client.get(f"/api/companies/{owner}/events?limit=1000").json())


# ---------- questions: bulk + bundle ----------
def test_bulk_answer(client, files):
    bank, _ = files
    cid = client.post("/api/companies", json={"name": "Bulk Co"}).json()["id"]
    with open(bank, "rb") as f:
        client.post(f"/api/companies/{cid}/upload", files={"file": (bank.name, f)}, data={"source_kind": "bank"})
    qs = client.get(f"/api/companies/{cid}/questions").json()
    assert len(qs) >= 2
    answers = []
    for q in qs:
        if q["kind"] == "vendor":
            answers.append({"question_id": q["id"], "choice": "v:it_amc:Website AMC"})
        elif q["kind"] == "stopped":
            answers.append({"question_id": q["id"], "choice": "cancelled"})
        elif q["kind"] == "cycle":
            answers.append({"question_id": q["id"], "choice": "yearly"})
    answers.append({"question_id": 999999, "choice": "x"})
    r = client.post(f"/api/companies/{cid}/questions/answer-bulk", json={"answers": answers})
    assert r.status_code == 200, r.text
    assert r.json()["answered"] == len(answers) - 1 and r.json()["engine"]["streams"] > 0
    assert not any(q["id"] in {a["question_id"] for a in answers} for q in client.get(f"/api/companies/{cid}/questions").json())


def test_bundle_question_choice_and_split(client):
    rows = [{"Date": "10/04/2026", "Narration": "NEFT-DESIGNTECH SYSTEMS-INV 4471", "Withdrawal Amt": 118000, "Deposit Amt": None}]
    for choice in ("vendor", "split"):
        cid = client.post("/api/companies", json={"name": f"Bundle {choice}"}).json()["id"]
        r = client.post(f"/api/companies/{cid}/upload", files={"file": ("b.xlsx", _xlsx(rows))}, data={"source_kind": "bank"})
        assert r.status_code == 200, r.text
        qs = client.get(f"/api/companies/{cid}/questions").json()
        bq = next((q for q in qs if q["kind"] == "bundle"), None)
        assert bq, qs
        keys = [o["key"] for o in bq["options"]]
        assert "split" in keys and any(k.startswith("v:solidworks:") for k in keys)
        if choice == "vendor":
            r = client.post(f"/api/companies/{cid}/questions/{bq['id']}/answer", json={"choice": "v:solidworks:SolidWorks subscription"})
            assert r.status_code == 200
            st = next(s for s in client.get(f"/api/companies/{cid}/streams").json() if s["payee_name"] == "DESIGNTECH SYSTEMS")
            assert st["vendor_name"].startswith("SolidWorks") and st["product"] == "SolidWorks subscription"
            assert not any(q["kind"] == "bundle" for q in client.get(f"/api/companies/{cid}/questions").json())
        else:
            assert client.post(f"/api/companies/{cid}/questions/{bq['id']}/answer", json={"choice": "split"}).status_code == 400
            r = client.post(f"/api/companies/{cid}/questions/{bq['id']}/answer",
                            json={"choice": "split", "items": [{"vendor_key": "solidworks", "product": "SolidWorks 2 seats", "amount": 94400},
                                                                {"vendor_key": "quickheal", "product": "Seqrite 20 users", "amount": 23600}]})
            assert r.status_code == 200, r.text
            streams = client.get(f"/api/companies/{cid}/streams").json()
            names = {(s["vendor_name"], s["product"], s["expected_amount"]) for s in streams}
            assert any(n[1] == "SolidWorks 2 seats" and n[2] == 94400 for n in names) and any(n[1] == "Seqrite 20 users" for n in names)
            assert not any(s["payee_name"] == "DESIGNTECH SYSTEMS" and s["product"] is None for s in streams)  # original dismissed
            assert all("Split out of a reseller bill" in s["flags_human"] for s in streams if s["product"] in ("SolidWorks 2 seats", "Seqrite 20 users"))
            client.post(f"/api/companies/{cid}/run")
            assert len(client.get(f"/api/companies/{cid}/streams").json()) == 2   # survive a re-run, original stays hidden


# ---------- upload additions ----------
def test_upload_detected_bank_hint_and_pdf_password(client, monkeypatch):
    cid = client.post("/api/companies", json={"name": "Upload Co"}).json()["id"]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf) as xw:
        pd.DataFrame([["ICICI Bank Ltd"], ["Statement of account"], [""]]).to_excel(xw, index=False, header=False)
        pd.DataFrame([{"Date": "05/06/2026", "Narration": "POS ZOOM.US", "Withdrawal Amt": 1769, "Deposit Amt": None}]).to_excel(xw, index=False, startrow=4)
    buf.seek(0)
    r = client.post(f"/api/companies/{cid}/upload", files={"file": ("stmt.xlsx", buf)}, data={"source_kind": "bank", "account_label": "Main"}).json()
    assert r["detected_bank"] == "ICICI" and r["hint"] is None
    assert next(a for a in client.get(f"/api/companies/{cid}/accounts").json() if a["label"] == "Main")["bank_name"] == "ICICI"
    buf.seek(0)
    r = client.post(f"/api/companies/{cid}/upload", files={"file": ("stmt.xlsx", buf)}, data={"source_kind": "bank", "account_label": "Main"}).json()
    assert r["batch"]["rows_imported"] == 0 and r["hint"] == "This statement was already uploaded"
    # pdf_password is passed through to the parser when it accepts it
    from app.api import routes
    seen = {}

    def fake_parse(content, filename, source_kind, pdf_password=None):
        seen["pw"] = pdf_password
        return [{"date": date(2026, 6, 5), "amount": 500.0, "direction": "debit", "raw_description": "POS ZOOM.US"}], "pdf", 0
    monkeypatch.setattr(routes, "parse_rows", fake_parse)
    r = client.post(f"/api/companies/{cid}/upload", files={"file": ("s.pdf", b"%PDF-1.4 fake")}, data={"source_kind": "bank", "pdf_password": "ABCD1234"})
    assert r.status_code == 200, r.text
    assert seen["pw"] == "ABCD1234"
