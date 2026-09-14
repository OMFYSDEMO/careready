"""Seed the CareReady AI database with UltraWell Supported Living demo data."""
import random
from datetime import date, timedelta
from .models import (SessionLocal, init_db, Organisation, Location, User, Staff,
                     ServiceUser, Incident, ComplianceAction, Evidence, TrendPoint,
                     Activity, Alert)
from .core import hash_password

random.seed(11)

def seed():
    init_db()
    db = SessionLocal()
    if db.query(Organisation).first():
        db.close()
        return False

    org = Organisation(name="UltraWell Supported Living",
                       strapline="Safe People • Brighter Futures", plan="Phase 1")
    db.add(org); db.flush()

    locs = {}
    for n in ["Mitcham House", "Croydon House", "Sutton House", "Purley House"]:
        l = Location(org_id=org.id, name=n); db.add(l); db.flush(); locs[n] = l

    for email, name, role in [
        ("kunle.adeyemi@ultrawell.co.uk", "Kunle Adeyemi", "Registered Manager"),
        ("admin@ultrawell.co.uk", "UltraWell Admin", "Super Admin"),
        ("compliance@ultrawell.co.uk", "Compliance Lead", "Compliance Lead"),
        ("viewer@ultrawell.co.uk", "Executive Viewer", "Viewer"),
    ]:
        h, s = hash_password("demo1234")
        db.add(User(org_id=org.id, email=email, name=name, role=role,
                    password_hash=h, password_salt=s))

    staff_rows = [
        ("Amara Okoye", "Senior Support Worker", "Mitcham House", "Current", 96, "Up to date"),
        ("James Whitfield", "Support Worker", "Croydon House", "Review required", 88, "Due today"),
        ("Priya Nair", "Team Leader", "Croydon House", "Current", 100, "Up to date"),
        ("Daniel Mensah", "Support Worker", "Sutton House", "Review required", 74, "Overdue"),
        ("Sophie Turner", "Support Worker", "Purley House", "Current", 91, "Up to date"),
        ("Mohammed Farah", "Night Support Worker", "Mitcham House", "Current", 82, "Due 14 Sep"),
        ("Grace Adebayo", "Support Worker", "Sutton House", "Current", 69, "Up to date"),
        ("Liam O'Connor", "Deputy Manager", "Purley House", "Current", 98, "Up to date"),
    ]
    for name, role, loc, dbs, tr, sup in staff_rows:
        db.add(Staff(org_id=org.id, location_id=locs[loc].id, name=name, role=role,
                     dbs_status=dbs, training_pct=tr, supervision_status=sup,
                     dbs_renewal=date.today() + timedelta(days=random.randint(60, 900))))

    su_rows = [
        ("JM", "Service User JM", "Croydon House", "Review overdue (6 days)", "red", "Updated Aug 2026"),
        ("KT", "Service User KT", "Mitcham House", "Current", "green", "Updated Sep 2026"),
        ("RB", "Service User RB", "Sutton House", "Review due 20 Sep", "amber", "Updated Jul 2026"),
        ("AL", "Service User AL", "Purley House", "Current", "green", "Updated Sep 2026"),
        ("DN", "Service User DN", "Mitcham House", "Current", "green", "Updated Aug 2026"),
        ("SP", "Service User SP", "Croydon House", "Current", "amber", "Review due 25 Sep"),
    ]
    for init, name, loc, cp, st, risk in su_rows:
        db.add(ServiceUser(org_id=org.id, location_id=locs[loc].id, initials=init,
                           name=name, careplan_status=cp, careplan_state=st, risk_note=risk))

    inc_rows = [
        ("INC-1044", "Medication administration delay", "Sutton House", "Medium", "Open", "Yesterday"),
        ("INC-1043", "Slip in communal kitchen — no injury", "Croydon House", "Low", "Under review", "3 days ago"),
        ("INC-1042", "Safeguarding concern raised — resolved", "Mitcham House", "High", "Closed", "5 days ago"),
        ("INC-1041", "Missing person protocol activated (returned safe)", "Sutton House", "High", "Closed", "1 week ago"),
        ("INC-1040", "Verbal altercation between service users", "Purley House", "Medium", "Closed", "2 weeks ago"),
    ]
    for ref, t, loc, sev, st, when in inc_rows:
        db.add(Incident(org_id=org.id, location_id=locs[loc].id, ref=ref, title=t,
                        severity=sev, status=st, occurred=when))

    act_rows = [
        ("CA-217", "Review and refresh 2 staff DBS records", "HR / Training Lead", "Today", "High", "In progress", "safe"),
        ("CA-216", "Book safeguarding refresher — J. Whitfield", "HR / Training Lead", "Today", "High", "Not started", "safe"),
        ("CA-215", "Complete Service User JM care-plan review", "Support Coordinator", "Overdue", "High", "In progress", "responsive"),
        ("CA-214", "Schedule fire risk assessment — all locations", "Operations Manager", "18 Sep", "Medium", "Scheduled", "safe"),
        ("CA-213", "Upload Q3 team meeting minutes to evidence library", "Registered Manager", "22 Sep", "Low", "Not started", "wellled"),
        ("CA-212", "CAPA: medication audit findings — Mitcham", "Compliance Lead", "26 Sep", "Medium", "In progress", "wellled"),
        ("CA-211", "Close 3 supervision gaps — schedule sessions", "Registered Manager", "Overdue", "High", "Not started", "wellled"),
    ]
    for ref, t, own, due, pr, st, kq in act_rows:
        db.add(ComplianceAction(org_id=org.id, ref=ref, title=t, owner=own, due=due,
                                priority=pr, status=st, kq=kq))

    # ----- Evidence library: 493 required items, 447 present -----
    # Distribution engineered to land the reference position:
    # 421 current · 26 expiring · 11 expired · 35 missing
    cats = {
        "safe": ["Staff Compliance", "Policies & Governance", "Medication",
                 "Property & Environment", "Incidents & Safeguarding"],
        "effective": ["Staff Compliance", "Care Planning", "Quality Assurance"],
        "caring": ["Quality Assurance", "Care Planning"],
        "responsive": ["Care Planning", "Quality Assurance"],
        "wellled": ["Policies & Governance", "Audit Centre", "Staff Compliance"],
    }
    per_kq = {"safe": 140, "effective": 100, "caring": 75, "responsive": 88, "wellled": 90}
    bad = {"safe": (12, 8, 24), "effective": (5, 2, 4), "caring": (2, 0, 2),
           "responsive": (5, 2, 6), "wellled": (10, 6, 30)}  # (expiring, expired, missing)
    named = [
        ("Safeguarding Policy v4.0", "Policies & Governance", "safe", "current", 540),
        ("Staff DBS Register", "Staff Compliance", "safe", "expiring", 20),
        ("Fire Risk Assessment 2025", "Property & Environment", "safe", "expiring", 18),
        ("Medication Administration SOP", "Medication", "safe", "current", 480),
        ("Care Plan Audit — Q2 2026", "Audit Centre", "responsive", "current", None),
        ("Staff Supervision Matrix", "Staff Compliance", "wellled", "expiring", 30),
        ("Business Continuity Plan", "Policies & Governance", "wellled", "current", 420),
        ("Infection Control Audit", "Audit Centre", "safe", "missing", None),
        ("Service User Feedback Survey 2026", "Quality Assurance", "caring", "current", None),
        ("Training Compliance Report — Aug", "Staff Compliance", "effective", "current", None),
    ]
    for t, cat, kq, st, days in named:
        db.add(Evidence(org_id=org.id, title=t, category=cat, kq=kq, status=st,
                        expiry=date.today() + timedelta(days=days) if days else None))
        per_kq[kq] -= 1
        if st != "current":
            i = {"expiring": 0, "expired": 1, "missing": 2}[st]
            lst = list(bad[kq]); lst[i] = max(0, lst[i] - 1); bad[kq] = tuple(lst)

    for kq, total in per_kq.items():
        exp, expd, miss = bad[kq]
        statuses = (["expiring"] * exp + ["expired"] * expd + ["missing"] * miss
                    + ["current"] * (total - exp - expd - miss))
        random.shuffle(statuses)
        for i, st in enumerate(statuses, 1):
            cat = cats[kq][i % len(cats[kq])]
            days = (random.randint(5, 28) if st == "expiring"
                    else -random.randint(5, 120) if st == "expired"
                    else random.randint(90, 720) if st == "current" else None)
            db.add(Evidence(org_id=org.id, title=f"{cat} — item {kq[:2].upper()}{i:03d}",
                            category=cat, kq=kq, status=st,
                            expiry=date.today() + timedelta(days=days) if days else None))

    for m, v in [("Apr", 62), ("May", 68), ("Jun", 72), ("Jul", 78), ("Aug", 80), ("Sep", 82)]:
        db.add(TrendPoint(org_id=org.id, month=m, value=v))

    for t, when, c in [
        ("New staff training certificate uploaded", "2 hours ago", "green"),
        ("Care plan updated — Service User JM", "3 hours ago", "blue"),
        ("Incident INC-1042 marked as closed", "5 hours ago", "red"),
        ("Policy version updated — Safeguarding v4", "1 day ago", "green"),
        ("Internal audit completed — Medication", "1 day ago", "green"),
    ]:
        db.add(Activity(org_id=org.id, text=t, when=when, colour=c))

    for t, when, c in [
        ("Urgent: 2 DBS records require review", "Today", "red"),
        ("Safeguarding training overdue", "Today", "red"),
        ("Fire risk assessment due soon", "Today", "amber"),
        ("New CQC guidance released — Aug 2026", "2 days ago", "blue"),
        ("Monthly compliance report is ready", "3 days ago", "blue"),
    ]:
        db.add(Alert(org_id=org.id, text=t, when=when, colour=c))

    db.commit(); db.close()
    return True

if __name__ == "__main__":
    print("Seeded." if seed() else "Database already seeded — skipped.")
