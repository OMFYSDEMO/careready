"""CareReady AI — auth, readiness scoring engine, AI service."""
import hashlib, hmac, os, secrets, time
import jwt
import httpx
from .models import (Staff, ServiceUser, Incident, ComplianceAction, Evidence,
                     KQ_IDS, KQ_NAMES)

JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production")
JWT_HOURS = int(os.environ.get("JWT_HOURS", "12"))

# ---------------- Auth ----------------
def hash_password(password: str, salt: str | None = None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
    return h, salt

def verify_password(password: str, salt: str, expected: str) -> bool:
    h, _ = hash_password(password, salt)
    return hmac.compare_digest(h, expected)

def make_token(user_id: int, org_id: int, role: str) -> str:
    return jwt.encode({"sub": str(user_id), "org": org_id, "role": role,
                       "exp": int(time.time()) + JWT_HOURS * 3600}, JWT_SECRET, algorithm="HS256")

def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])

# ---------------- Readiness scoring engine ----------------
# Weights per concept note methodology:
#   evidence currency & coverage 40% · staff compliance 25% ·
#   incidents & learning 15% · audits & open actions 20%
# Each CQC key question weighs the same factors differently.
KQ_FACTOR_WEIGHTS = {
    #            evidence staff incidents actions
    "safe":       (0.35, 0.35, 0.20, 0.10),
    "effective":  (0.30, 0.50, 0.05, 0.15),
    "caring":     (0.55, 0.25, 0.10, 0.10),
    "responsive": (0.45, 0.15, 0.20, 0.20),
    "wellled":    (0.30, 0.20, 0.10, 0.40),
}

def _evidence_score(rows):
    if not rows:
        return 100.0
    pts = {"current": 1.0, "expiring": 0.7, "expired": 0.25, "missing": 0.0}
    return 100.0 * sum(pts.get(e.status, 0.5) for e in rows) / len(rows)

def _staff_score(rows):
    if not rows:
        return 100.0
    dbs = 100.0 * sum(1 for s in rows if s.dbs_status == "Current") / len(rows)
    training = sum(s.training_pct for s in rows) / len(rows)
    sup_pts = {"Up to date": 1.0, "Overdue": 0.0, "Due today": 0.3}
    sup = 100.0 * sum(sup_pts.get(s.supervision_status, 0.7) for s in rows) / len(rows)
    return 0.4 * dbs + 0.35 * training + 0.25 * sup

def _incident_score(rows):
    score = 100.0
    for i in rows:
        if i.status in ("Open", "Under review"):
            score -= {"High": 18, "Medium": 9, "Low": 4}.get(i.severity, 5)
    return max(0.0, score)

def _action_score(rows):
    open_rows = [a for a in rows if a.status not in ("Done",)]
    score = 100.0
    for a in open_rows:
        overdue = a.due in ("Today", "Overdue")
        score -= {"High": 14 if overdue else 8, "Medium": 6, "Low": 2}.get(a.priority, 4)
    return max(0.0, score)

def compute_readiness(db, org_id: int, location_id: int | None = None):
    """Returns {kq_id: score}, overall, and factor breakdown."""
    ev = db.query(Evidence).filter_by(org_id=org_id).all()
    staff_q = db.query(Staff).filter_by(org_id=org_id)
    su_q = db.query(ServiceUser).filter_by(org_id=org_id)
    inc_q = db.query(Incident).filter_by(org_id=org_id)
    if location_id:
        staff_q = staff_q.filter_by(location_id=location_id)
        su_q = su_q.filter_by(location_id=location_id)
        inc_q = inc_q.filter_by(location_id=location_id)
    staff, sus, incidents = staff_q.all(), su_q.all(), inc_q.all()
    actions = db.query(ComplianceAction).filter_by(org_id=org_id).all()

    factors_by_kq = {}
    for kq in KQ_IDS:
        f_ev = _evidence_score([e for e in ev if e.kq == kq])
        f_st = _staff_score(staff)
        f_in = _incident_score(incidents)
        kq_actions = [a for a in actions if a.kq == kq]
        f_ac = _action_score(kq_actions) if kq_actions else 95.0
        # Responsive additionally reflects care-plan currency
        if kq == "responsive" and sus:
            cp = 100.0 * sum({"green": 1.0, "amber": 0.6, "red": 0.1}[u.careplan_state] for u in sus) / len(sus)
            f_ev = 0.6 * f_ev + 0.4 * cp
        factors_by_kq[kq] = (f_ev, f_st, f_in, f_ac)

    scores = {}
    for kq, (w_ev, w_st, w_in, w_ac) in KQ_FACTOR_WEIGHTS.items():
        f_ev, f_st, f_in, f_ac = factors_by_kq[kq]
        scores[kq] = round(w_ev * f_ev + w_st * f_st + w_in * f_in + w_ac * f_ac)
    overall = round(sum(scores.values()) / len(scores))
    return scores, overall, factors_by_kq

def status_for(score: int):
    if score >= 84: return "On track", "green", "#16a34a"
    if score >= 75: return "Attention needed", "amber", "#d97706"
    return "Action required", "red", "#dc2626"

# ---------------- AI service (mock inspection, classification) ----------------
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
AZURE_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
AZURE_KEY = os.environ.get("AZURE_OPENAI_KEY", "")
AZURE_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

INSPECTOR_SYSTEM = (
    "You are a CQC inspector conducting a mock inspection interview for a UK "
    "supported-living provider under the CQC single assessment framework. "
    "Assess the manager's answer to the question. Respond in strict JSON with keys: "
    "pct (0-100 integer, how inspection-ready the answer is), verdict (short phrase), "
    "feedback (2-3 sentences, specific and constructive, referencing what was strong "
    "and what was missing against CQC expectations)."
)

def llm_available() -> bool:
    return bool(ANTHROPIC_KEY or (AZURE_ENDPOINT and AZURE_KEY))

def llm_assess(question: str, answer: str) -> dict | None:
    """Live LLM assessment of a mock-inspection answer. Returns None on any failure."""
    prompt = f"Question: {question}\n\nManager's answer: {answer}\n\nAssess now. JSON only."
    try:
        if ANTHROPIC_KEY:
            r = httpx.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
                      "max_tokens": 400, "system": INSPECTOR_SYSTEM,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=30)
            r.raise_for_status()
            text = "".join(b.get("text", "") for b in r.json()["content"])
        elif AZURE_ENDPOINT and AZURE_KEY:
            url = f"{AZURE_ENDPOINT.rstrip('/')}/openai/deployments/{AZURE_DEPLOYMENT}/chat/completions?api-version=2024-06-01"
            r = httpx.post(url, headers={"api-key": AZURE_KEY},
                json={"messages": [{"role": "system", "content": INSPECTOR_SYSTEM},
                                   {"role": "user", "content": prompt}],
                      "max_tokens": 400, "response_format": {"type": "json_object"}},
                timeout=30)
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
        else:
            return None
        import json as _json, re as _re
        m = _re.search(r"\{.*\}", text, _re.S)
        data = _json.loads(m.group(0)) if m else None
        if data and all(k in data for k in ("pct", "verdict", "feedback")):
            data["pct"] = max(0, min(100, int(data["pct"])))
            data["engine"] = "llm"
            return data
    except Exception:
        return None
    return None

def keyword_assess(answer: str, keys: list[str]) -> dict:
    """Deterministic fallback when no LLM key is configured."""
    hits = sum(1 for k in keys if k in answer.lower())
    pct = min(100, round(hits / max(1, min(len(keys), 4)) * 100))
    verdict = "Strong answer" if pct >= 75 else "Partially there" if pct >= 40 else "Needs development"
    return {"pct": pct, "verdict": verdict,
            "feedback": "Assessed against expected themes for this question (keyword engine — "
                        "configure an AI key for full analysis).", "engine": "keyword"}

def classify_document(filename: str) -> tuple[str, str]:
    """Rule-based classification (category, kq). LLM/OCR classification lands later in Phase 1."""
    f = filename.lower()
    rules = [
        (("dbs",), ("Staff Compliance", "safe")),
        (("safeguard",), ("Policies & Governance", "safe")),
        (("fire", "risk assessment", "premises", "health and safety"), ("Property & Environment", "safe")),
        (("medic", "mar "), ("Medication", "safe")),
        (("training", "induction", "competen", "certificate"), ("Staff Compliance", "effective")),
        (("supervis", "appraisal"), ("Staff Compliance", "wellled")),
        (("care plan", "careplan", "support plan", "review"), ("Care Planning", "responsive")),
        (("complaint",), ("Quality Assurance", "responsive")),
        (("feedback", "survey", "dignity"), ("Quality Assurance", "caring")),
        (("audit",), ("Audit Centre", "wellled")),
        (("policy", "governance", "continuity", "minutes"), ("Policies & Governance", "wellled")),
        (("incident", "accident"), ("Incidents & Safeguarding", "safe")),
    ]
    for keys, out in rules:
        if any(k in f for k in keys):
            return out
    return ("Evidence Library", "wellled")
