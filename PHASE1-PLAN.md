# CareReady AI — Phase 1 Plan

From POC (validated with UltraWell) to a sellable product. This build is the
Phase 1 foundation; the plan below covers what is done, what remains, and the
suggested order.

## Delivered in this foundation build

Real authentication and roles, live readiness scoring engine, evidence library
with upload and auto-classification, action management wired to scoring, mock
CQC inspection with pluggable AI engine (Anthropic / Azure OpenAI / keyword
fallback), server-generated evidence pack, per-location scoring, activity and
alert trails, Docker deployment.

## Remaining Phase 1 workstreams (suggested order)

1. **Multi-tenancy & onboarding (weeks 1–2).** Organisation self-signup,
   tenant isolation on every query (org_id scoping is already in place),
   invite flows, password reset via email. This unlocks selling beyond
   UltraWell.

2. **Evidence lifecycle depth (weeks 2–4).** OCR text extraction on upload
   (PDF/images), LLM classification replacing the rule-based classifier,
   versioning, expiry reminder emails, CSV import for staff/training/incident
   registers — the concept note's data-sources list.

3. **Mock inspection v2 (weeks 3–5).** Multi-turn interviews (follow-up
   questions from the LLM), grounding in the tenant's own evidence library
   ("you say X — but your fire risk assessment expired in May"), full report
   at session end saved to the evidence library.

4. **Notifications & calendar (weeks 4–6).** Email digests, expiry and
   supervision reminders, the compliance calendar module with recurrence.

5. **Reports & exports (weeks 5–7).** True PDF/Excel exports (the printable
   pack exists), monthly board report generation, commissioner-ready packs.

6. **Hardening for sale (weeks 6–8).** PostgreSQL migration, backups,
   rate limiting, audit-log completeness, DPIA/UK GDPR documentation
   (special-category data — care records — so this is a gate, not a
   nice-to-have), Cyber Essentials alignment, penetration test.

Billing/subscriptions, mobile app and domiciliary-care-specific modules stay
in Phase 2 per the concept note.

## Commercial notes

- Target segment per your positioning: small providers (1–5 locations) where
  the Registered Manager is the single point of compliance knowledge.
- The scoring methodology (weighted evidence/staff/incidents/actions per key
  question) is now a defensible product asset — document it for sales
  conversations; it answers "how do you get to 82%?"
- Pricing hypothesis to validate with Kunle: per-location per-month, with the
  mock inspection metered or in a higher tier.

## Data protection gate before real customer data

The demo dataset is fictional. Before any provider loads real staff or
service-user records: signed DPA, UK data residency for DB and file storage,
encryption at rest, role-based access review, and an ICO-registration check
for the operating entity.
