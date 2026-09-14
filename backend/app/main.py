"""CareReady AI — Phase 1 API (FastAPI)."""
import os
from datetime import date, datetime
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from .models import (SessionLocal, init_db, Organisation, Location, User, Staff,
                     ServiceUser, Incident, ComplianceAction, Evidence, TrendPoint,
                     Activity, Alert, KQ_NAMES, KQ_IDS)
from . import core
from .seed import seed

STORAGE = Path(os.environ.get("STORAGE_DIR", Path(__file__).resolve().parent.parent / "storage"))
STORAGE.mkdir(parents=True, exist_ok=True)
FRONTEND = Path(os.environ.get("FRONTEND_DIR", Path(__file__).resolve().parent.parent.parent / "frontend"))

app = FastAPI(title="CareReady AI API", version="1.0-phase1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def _startup():
    init_db(); seed()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def current_user(authorization: str = Header(default=""), token: str = Query(default=""), db=Depends(get_db)) -> User:
    raw = authorization.removeprefix("Bearer ").strip() or token
    if not raw:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = core.decode_token(raw)
    except Exception:
        raise HTTPException(401, "Invalid or expired token")
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(401, "User not found")
    return user

# ---------------- Auth ----------------
class LoginIn(BaseModel):
    email: str
    password: str

@app.post("/api/auth/login")
def login(body: LoginIn, db=Depends(get_db)):
    user = db.query(User).filter_by(email=body.email.strip().lower()).first()
    if not user or not core.verify_password(body.password, user.password_salt, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return {"token": core.make_token(user.id, user.org_id, user.role),
            "user": {"name": user.name, "role": user.role, "email": user.email}}

# ---------------- Bootstrap (everything the UI needs) ----------------
KQ_UI = {
    "safe":       {"icon": "shield", "bg": "#fffbeb"},
    "effective":  {"icon": "bars",   "bg": "#f0fdf4"},
    "caring":     {"icon": "heart",  "bg": "#eff6ff"},
    "responsive": {"icon": "people", "bg": "#f0fdf4"},
    "wellled":    {"icon": "cog",    "bg": "#fef2f2"},
}

@app.get("/api/bootstrap")
def bootstrap(user: User = Depends(current_user), db=Depends(get_db)):
    org = db.get(Organisation, user.org_id)
    scores, overall, _ = core.compute_readiness(db, org.id)
    kq = []
    for k in KQ_IDS:
        st, cls, colour = core.status_for(scores[k])
        kq.append({"id": k, "name": KQ_NAMES[k], "score": scores[k], "status": st,
                   "cls": cls, "color": colour, **KQ_UI[k]})

    ev = db.query(Evidence).filter_by(org_id=org.id).all()
    glance = {"items": len(ev),
              "present": sum(1 for e in ev if e.status != "missing"),
              "current": sum(1 for e in ev if e.status == "current"),
              "expiring": sum(1 for e in ev if e.status == "expiring"),
              "expired": sum(1 for e in ev if e.status == "expired"),
              "missing": sum(1 for e in ev if e.status == "missing")}

    locations = []
    for loc in db.query(Location).filter_by(org_id=org.id).all():
        ls, lo, _ = core.compute_readiness(db, org.id, loc.id)
        st = "Ready" if lo >= 85 else "Attention" if lo >= 75 else "Action"
        c = "green" if lo >= 85 else "amber" if lo >= 75 else "red"
        locations.append({"id": loc.id, "name": loc.name, "score": lo, "st": st, "c": c,
                          "users": db.query(ServiceUser).filter_by(location_id=loc.id).count(),
                          "staff": db.query(Staff).filter_by(location_id=loc.id).count()})

    named_evidence = [e for e in ev if not ("— item" in (e.title or ""))][:12]
    return {
        "org": org.name, "strapline": org.strapline, "plan": org.plan,
        "user": {"name": user.name, "role": user.role},
        "overall": overall, "kq": kq, "glance": glance, "locations": locations,
        "trend": [{"m": t.month, "v": t.value} for t in db.query(TrendPoint).filter_by(org_id=org.id)],
        "risks": _risks(db, org.id),
        "upcoming": [
            {"d": "8", "m": "SEP", "t": "2 staff supervisions due", "when": "Today"},
            {"d": "9", "m": "SEP", "t": "Medication audit — Mitcham House", "when": "Tomorrow"},
            {"d": "11", "m": "SEP", "t": "Fire drill — Croydon House", "when": "In 3 days"},
            {"d": "12", "m": "SEP", "t": "4 training certifications expiring", "when": "In 4 days"}],
        "activity": [{"t": a.text, "when": a.when, "c": a.colour}
                     for a in db.query(Activity).filter_by(org_id=org.id).order_by(Activity.id.desc()).limit(8)],
        "alerts": [{"id": a.id, "t": a.text, "when": a.when, "c": a.colour, "read": a.read}
                   for a in db.query(Alert).filter_by(org_id=org.id).order_by(Alert.id)],
        "unread": db.query(Alert).filter_by(org_id=org.id, read=False).count(),
        "staff": [{"id": s.id, "name": s.name, "role": s.role, "loc": s.location.name,
                   "dbs": s.dbs_status, "training": s.training_pct, "supervision": s.supervision_status,
                   "st": "green" if s.dbs_status == "Current" and s.training_pct >= 80
                         and s.supervision_status.startswith("Up") else
                         "red" if s.dbs_status != "Current" or s.supervision_status in ("Overdue", "Due today")
                         else "amber"}
                  for s in db.query(Staff).filter_by(org_id=org.id)],
        "people": [{"id": u.initials, "name": u.name, "loc": u.location.name,
                    "careplan": u.careplan_status, "risk": u.risk_note, "st": u.careplan_state}
                   for u in db.query(ServiceUser).filter_by(org_id=org.id)],
        "incidents": [{"id": i.ref, "dbid": i.id, "t": i.title, "loc": i.location.name,
                       "sev": i.severity, "date": i.occurred, "st": i.status,
                       "c": "green" if i.status == "Closed" else "blue" if i.status == "Under review" else "amber"}
                      for i in db.query(Incident).filter_by(org_id=org.id).order_by(Incident.id.desc())],
        "actions": [{"id": a.ref, "dbid": a.id, "t": a.title, "owner": a.owner, "due": a.due,
                     "pr": a.priority, "st": a.status,
                     "c": "red" if a.priority == "High" else "amber" if a.priority == "Medium" else "blue"}
                    for a in db.query(ComplianceAction).filter_by(org_id=org.id)],
        "evidence": [{"dbid": e.id, "t": e.title, "cat": e.category,
                      "kq": KQ_NAMES[e.kq], "exp": e.expiry.strftime("%d %b %Y") if e.expiry else "—",
                      "st": e.status.capitalize(),
                      "c": {"current": "green", "expiring": "amber", "expired": "red", "missing": "red"}[e.status]}
                     for e in named_evidence],
        "ai": {"engine": "llm" if core.llm_available() else "keyword"},
    }

def _risks(db, org_id):
    risks = []
    dbs_bad = db.query(Staff).filter(Staff.org_id == org_id, Staff.dbs_status != "Current").count()
    if dbs_bad:
        risks.append({"t": f"{dbs_bad} staff DBS records require review", "sev": "High", "when": "Today", "c": "red"})
    risks.append({"t": "Safeguarding refresher overdue — 1 employee", "sev": "High", "when": "Today", "c": "red"})
    exp_soon = db.query(Evidence).filter_by(org_id=org_id, status="expiring").count()
    if exp_soon:
        risks.append({"t": f"Fire risk assessment due in 18 days (+{exp_soon - 1} items expiring)", "sev": "Medium", "when": "18 Sep", "c": "amber"})
    for u in db.query(ServiceUser).filter_by(org_id=org_id, careplan_state="red"):
        risks.append({"t": f"{u.name} care-plan review overdue", "sev": "Medium", "when": "6 days ago", "c": "amber"})
    return risks[:5]

# ---------------- Actions ----------------
class StatusIn(BaseModel):
    status: str

@app.post("/api/actions/{action_id}/status")
def set_action_status(action_id: int, body: StatusIn, user: User = Depends(current_user), db=Depends(get_db)):
    a = db.get(ComplianceAction, action_id)
    if not a or a.org_id != user.org_id:
        raise HTTPException(404, "Action not found")
    if body.status not in ("Not started", "In progress", "Scheduled", "Done"):
        raise HTTPException(400, "Invalid status")
    a.status = body.status
    db.add(Activity(org_id=user.org_id, text=f"{a.ref} moved to {body.status} by {user.name}", when="Just now",
                    colour="green" if body.status == "Done" else "blue"))
    db.commit()
    return {"ok": True}

# ---------------- Evidence upload ----------------
@app.post("/api/evidence/upload")
async def upload_evidence(file: UploadFile = File(...), user: User = Depends(current_user), db=Depends(get_db)):
    data = await file.read()
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(413, "File too large (25 MB max)")
    safe_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{os.path.basename(file.filename)}"
    (STORAGE / safe_name).write_bytes(data)
    category, kq = core.classify_document(file.filename)
    ev = Evidence(org_id=user.org_id, title=os.path.splitext(file.filename)[0],
                  category=category, kq=kq, status="current", filename=safe_name)
    db.add(ev)
    db.add(Activity(org_id=user.org_id, text=f"Evidence uploaded: {ev.title} → {category}", when="Just now", colour="green"))
    db.commit()
    return {"ok": True, "title": ev.title, "category": category, "kq": KQ_NAMES[kq]}

# ---------------- Alerts ----------------
@app.post("/api/alerts/{alert_id}/read")
def mark_read(alert_id: int, user: User = Depends(current_user), db=Depends(get_db)):
    a = db.get(Alert, alert_id)
    if not a or a.org_id != user.org_id:
        raise HTTPException(404)
    a.read = True; db.commit()
    return {"ok": True}

# ---------------- Mock CQC inspection ----------------
MOCKQ = {
    "safe": [
        {"q": "How do you ensure all staff have current DBS checks, and what happens when a check flags an issue or requires renewal?",
         "keys": ["dbs", "renew", "risk assessment", "register", "check"],
         "model": "A strong answer covers: a live DBS register with renewal dates, a defined escalation route when checks lapse or flag concerns, interim risk assessments, and evidence the Registered Manager reviews the register monthly."},
        {"q": "Walk me through what happens when a safeguarding concern is raised about a person you support.",
         "keys": ["safeguard", "refer", "local authority", "record", "investigat", "learn"],
         "model": "Inspectors expect: immediate protection steps, referral to the local authority safeguarding team, notification to CQC where required, a recorded investigation, and evidence of learning shared with the team."},
        {"q": "How do you manage medication errors, and can you show me your last three medication audits?",
         "keys": ["audit", "error", "report", "mar", "competen", "learn"],
         "model": "Cover: incident reporting for every error, MAR chart audits, staff competency reassessment after errors, and trend analysis with actions."}],
    "effective": [
        {"q": "How do you make sure staff have the right skills and training for the people they support?",
         "keys": ["training", "induction", "care certificate", "competen", "supervis", "matrix"],
         "model": "Reference your training matrix, Care Certificate-aligned induction, role-specific competencies, refresher schedules, and how supervision checks skills in practice."},
        {"q": "How do you monitor whether the support you provide is actually achieving good outcomes?",
         "keys": ["outcome", "goal", "review", "measure", "feedback"],
         "model": "Show outcome-focused support plans with measurable goals, regular reviews with the person, and how outcome data feeds your quality reporting."}],
    "caring": [
        {"q": "How do you involve the people you support in decisions about their own care?",
         "keys": ["involve", "choice", "co-produc", "advoca", "consent", "person-centred"],
         "model": "Evidence co-produced care plans, capacity and consent records, advocacy access, and examples where a person's preference changed their support."},
        {"q": "Give me an example of how you protect people's dignity and privacy in day-to-day support.",
         "keys": ["dignity", "privacy", "respect", "confidential", "knock"],
         "model": "Concrete daily practices plus dignity audits, staff training on respect, and confidentiality safeguards in records handling."}],
    "responsive": [
        {"q": "A person's needs change suddenly. How quickly does their care plan reflect that, and who is responsible?",
         "keys": ["review", "update", "48", "responsib", "communicat", "risk"],
         "model": "Name the trigger-based review process, target timescale (e.g. within 48–72 hours), the accountable role, and how changes reach the whole team."},
        {"q": "How do you handle complaints, and what changed in your service as a result of one?",
         "keys": ["complaint", "respond", "timescale", "learn", "chang", "outcome"],
         "model": "Show your complaints log with response timescales, outcomes, and at least one concrete service change driven by a complaint."}],
    "wellled": [
        {"q": "As Registered Manager, how do you know — today — that your service is safe and compliant?",
         "keys": ["dashboard", "audit", "data", "kpi", "assurance", "oversight", "governance"],
         "model": "Real-time readiness data, audit schedules, action tracking, and governance meetings where that data is reviewed and acted on."},
        {"q": "Show me how learning from incidents, audits and complaints changes practice in your organisation.",
         "keys": ["learn", "action", "capa", "share", "team meeting", "chang", "embed"],
         "model": "Trace one item end-to-end: finding → CAPA action → team communication → practice change → follow-up audit confirming it stuck."}],
}
EVIDENCE_HINTS = {
    "safe": "Staff DBS Register · Safeguarding Policy v4.0 · Medication Administration SOP · Fire Risk Assessment",
    "effective": "Training Compliance Report — Aug · Staff Supervision Matrix · Induction records",
    "caring": "Service User Feedback Survey 2026 · Care plans (co-production evidence) · Dignity audit",
    "responsive": "Care Plan Audit — Q2 2026 · Complaints log · Review schedule",
    "wellled": "Live readiness dashboard · Business Continuity Plan · CAPA tracker · Governance meeting minutes",
}

@app.get("/api/mock/questions")
def mock_questions(kq: str, user: User = Depends(current_user)):
    if kq not in MOCKQ:
        raise HTTPException(404, "Unknown key question")
    return {"kq": kq, "name": KQ_NAMES[kq], "questions": [q["q"] for q in MOCKQ[kq]],
            "engine": "llm" if core.llm_available() else "keyword"}

class AnswerIn(BaseModel):
    kq: str
    index: int
    answer: str

@app.post("/api/mock/answer")
def mock_answer(body: AnswerIn, user: User = Depends(current_user)):
    bank = MOCKQ.get(body.kq)
    if not bank or not (0 <= body.index < len(bank)):
        raise HTTPException(400, "Invalid question reference")
    q = bank[body.index]
    result = core.llm_assess(q["q"], body.answer) or core.keyword_assess(body.answer, q["keys"])
    result.update({"model": q["model"], "evidence": EVIDENCE_HINTS[body.kq]})
    return result

# ---------------- Evidence pack (printable) ----------------
@app.get("/api/reports/evidence-pack", response_class=HTMLResponse)
def evidence_pack(user: User = Depends(current_user), db=Depends(get_db)):
    org = db.get(Organisation, user.org_id)
    scores, overall, _ = core.compute_readiness(db, org.id)
    ev = db.query(Evidence).filter_by(org_id=org.id).all()
    gaps = [e for e in ev if e.status in ("expired", "missing")][:40]
    rows_kq = "".join(
        f"<tr><td>{KQ_NAMES[k]}</td><td>{scores[k]}%</td>"
        f"<td>{sum(1 for e in ev if e.kq == k and e.status == 'current')} current / "
        f"{sum(1 for e in ev if e.kq == k)} required</td></tr>" for k in KQ_IDS)
    rows_gap = "".join(f"<tr><td>{e.title}</td><td>{e.category}</td><td>{KQ_NAMES[e.kq]}</td>"
                       f"<td>{e.status.capitalize()}</td></tr>" for e in gaps)
    return f"""<!DOCTYPE html><html><head><meta charset='utf-8'><title>Evidence Pack — {org.name}</title>
<style>body{{font-family:Inter,system-ui,sans-serif;margin:40px;color:#0f172a}}h1{{font-size:1.5rem}}
h2{{font-size:1.05rem;margin:26px 0 10px}}table{{border-collapse:collapse;width:100%;font-size:.85rem}}
td,th{{border:1px solid #e2e8f0;padding:7px 10px;text-align:left}}th{{background:#f1f5f9}}
.head{{display:flex;justify-content:space-between;align-items:center;border-bottom:3px solid #2563eb;padding-bottom:14px}}
.big{{font-size:2.2rem;font-weight:800;color:#16a34a}}@media print{{button{{display:none}}}}</style></head><body>
<div class='head'><div><h1>CareReady AI — Inspection-Ready Evidence Pack</h1>
<p>{org.name} · Generated {date.today().strftime('%d %B %Y')} by {user.name} ({user.role})</p></div>
<div class='big'>{overall}%</div></div>
<h2>Readiness by CQC key question</h2><table><tr><th>Key question</th><th>Score</th><th>Evidence coverage</th></tr>{rows_kq}</table>
<h2>Gaps requiring attention ({len(gaps)} shown)</h2><table><tr><th>Item</th><th>Category</th><th>Key question</th><th>Status</th></tr>{rows_gap}</table>
<p style='margin-top:26px;color:#64748b;font-size:.8rem'>Powered by Omfys Technologies · CareReady AI Phase 1</p>
<button onclick='print()' style='margin-top:14px;padding:10px 18px'>Print / Save as PDF</button></body></html>"""

@app.get("/api/health")
def health():
    return {"ok": True, "version": "1.0-phase1", "ai": "llm" if core.llm_available() else "keyword"}

# ---------------- Frontend (static) ----------------
if FRONTEND.exists():
    @app.get("/", response_class=HTMLResponse)
    def index():
        return FileResponse(FRONTEND / "index.html")
    app.mount("/", StaticFiles(directory=str(FRONTEND)), name="frontend")
