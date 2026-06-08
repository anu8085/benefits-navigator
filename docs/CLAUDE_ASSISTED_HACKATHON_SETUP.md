# Claude-Assisted Hackathon Setup — Benefits Navigator for Families

A complete, end-to-end guide for rebuilding the **Benefits Navigator** app in a
**new, empty hackathon Databricks environment**, starting only from your public
GitHub repo and your existing laptop. Claude can help you at every step (code,
SQL, commands, troubleshooting).

> **No real secrets in this document.** Everything sensitive is a `<PLACEHOLDER>`.
> Never paste real API keys, tokens, or passwords into source control.

---

## 0. Hackathon Rule Safety (read first)

Before anything technical, make sure your build is **eligible** under the
official rules:

- **Use only permitted tools and resources** per the official hackathon rules
  (allowed cloud accounts, APIs, datasets, and AI assistants).
- **Do not submit private/proprietary company code.** Only use code you are
  allowed to use publicly (e.g., your own public repo or an approved template).
- **Do not use confidential or real personal data.** Benefits data is sensitive
  by nature.
- **Use synthetic / demo family scenarios only** (see §13). No real PII.
- **If rules require code to be written during the hackathon window**, start from
  an **allowed public repo/template** and make the **final, eligible changes
  during the event** so your meaningful work happens in-window.
- **Keep commit history transparent** — clear, honest commits with timestamps.
- **Ask organizers if uncertain** about using prebuilt code, AI assistance, or
  external APIs (e.g., Anthropic). Get it in writing if you can.
- **Do not misrepresent** what was built *before* vs. *during* the event. Be
  explicit in your README/submission about what pre-existed and what you added.

When in doubt: **disclose and ask.** Transparency protects your submission.

---

## 1. Overview

This guide takes you from "empty hackathon Databricks workspace + my public
GitHub repo" to a **fully deployed, demo-ready Benefits Navigator**:

1. Get the code into a hackathon-eligible GitHub repo.
2. Set up your laptop to run it locally.
3. Stand up the **trusted data** (Unity Catalog / Delta) and a **SQL Warehouse**.
4. Stand up **Lakebase Postgres** app-state tables.
5. Configure the **Databricks App** (resources, secrets, `app.yaml`).
6. Grant the App's **service principal** access to Lakebase.
7. Deploy, validate, and rehearse the demo.

Each phase includes **copy-paste Claude prompts** (§11) and a **troubleshooting
FAQ** (§14).

---

## 2. Target Final Architecture

| Layer | Component | Role |
|---|---|---|
| UX | **Databricks App + Streamlit UI** | Friendly intake form, program cards, feedback widget |
| Reasoning | **Claude agent** | Extract profile, ask adaptive questions, write action plan |
| Reasoning | **Rules engine** | Deterministic, explainable eligibility screening |
| Trusted data | **Unity Catalog / Delta** `benefits_navigator.trusted.benefit_programs` | Source-labeled NJ programs + rule columns |
| Trusted data | **Databricks SQL Warehouse** | Secure, governed read access via SQL connector |
| App state | **Lakebase Postgres** | `family_intake_events`, `program_matches`, `action_plans`, `user_feedback` |
| Impact | **Feedback + analytics** | County needs, program demand, feedback trends |

Repo files involved: `app.py`, `agent.py`, `benefits_rules.py`,
`databricks_client.py`, `lakebase_client.py`, `requirements.txt`, `app.yaml`,
`sample_data/programs.json` (local fallback), `social_impact_analytics.sql`.

---

## 3. GitHub Setup Options

Use placeholders:
- `<OLD_REPO_URL>` — your current public repo (e.g., `https://github.com/<you>/benefits-navigator.git`)
- `<NEW_HACKATHON_REPO_URL>` — the hackathon repo you will push to

### Option A — Fork the existing public repo

Fork `<OLD_REPO_URL>` in the GitHub UI, then:

```bash
git clone <NEW_HACKATHON_REPO_URL>
cd benefits_navigator
git remote -v
# origin  <NEW_HACKATHON_REPO_URL> (fetch)
# origin  <NEW_HACKATHON_REPO_URL> (push)
```

(Optional) keep a link back to the original to pull updates:

```bash
git remote add upstream <OLD_REPO_URL>
git remote -v
```

### Option B — Create a new repo and copy code from your current repo

Create an **empty** `<NEW_HACKATHON_REPO_URL>` in GitHub (no README), then:

```bash
# 1) Clone your current working repo
git clone <OLD_REPO_URL>
cd benefits_navigator

# 2) Point origin at the new hackathon repo
git remote -v
git remote set-url origin <NEW_HACKATHON_REPO_URL>
git remote -v

# 3) Push everything to the new repo
git push -u origin main
```

If you want a clean history that starts in-window (sometimes preferred for rule
clarity), re-initialize:

```bash
rm -rf .git
git init
git add .
git commit -m "Initial hackathon import from public template"
git branch -M main
git remote add origin <NEW_HACKATHON_REPO_URL>
git push -u origin main
```

> **Rule-safety tie-in:** whichever option you choose, make your **substantive
> changes during the event** and keep commits transparent (§0).

---

## 4. Local Laptop Setup (same laptop, PowerShell)

```powershell
# Into the repo
cd benefits_navigator

# Create and activate a virtual environment (Windows PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

Create a local `.env` (for local/dev only — **never commit it**):

```dotenv
# .env  (LOCAL ONLY — do NOT commit. Use placeholders; fill with your own values.)
ANTHROPIC_API_KEY=<YOUR_ANTHROPIC_API_KEY>

# Databricks SQL connector (trusted-data read)
DATABRICKS_SERVER_HOSTNAME=<YOUR_WORKSPACE_HOST>      # e.g. dbc-xxxx.cloud.databricks.com
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/<WAREHOUSE_ID>
DATABRICKS_TOKEN=<YOUR_PERSONAL_ACCESS_TOKEN>          # local/dev only

# Local Lakebase (manual mode) — optional for local testing
LAKEBASE_HOST=<YOUR_PG_HOST>
LAKEBASE_PORT=5432
LAKEBASE_DATABASE=databricks_postgres
LAKEBASE_USER=<YOUR_PG_USER>
LAKEBASE_PASSWORD=<YOUR_PG_PASSWORD>
```

Confirm `.env` is ignored:

```powershell
# .gitignore should contain a line: .env
Select-String -Path .gitignore -Pattern "^\.env$"
```

Run locally:

```powershell
streamlit run app.py
```

> The app **gracefully falls back** to `sample_data/programs.json` if Databricks
> isn't reachable, and still generates a plan if Lakebase writes fail — so you
> can develop locally even before the cloud pieces exist.

---

## 5. Databricks Workspace Setup

1. **Create or identify a SQL Warehouse**
   - In the new workspace: **SQL → SQL Warehouses → Create** (a small/serverless
     warehouse is fine for a demo). Start it.
2. **Capture the server hostname**
   - Warehouse → **Connection details** → **Server hostname**
     (e.g., `dbc-xxxx.cloud.databricks.com`).
3. **Capture the HTTP path**
   - Same panel → **HTTP path** (e.g., `/sql/1.0/warehouses/<WAREHOUSE_ID>`).
4. **Create a token only if needed for local/dev**
   - **User Settings → Developer → Access tokens → Generate**. Use this only in
     your local `.env`. **Do not** commit it.
5. **In the deployed app, prefer Databricks App resources/secrets**
   - The deployed App should get the warehouse via an **app resource** and the
     Anthropic key via a **secret** — not a hard-coded token (§8).

---

## 6. Unity Catalog Trusted Data Setup

Run this in a Databricks **SQL editor** (or a notebook). It creates the trusted
catalog/schema/table with the **rule columns the current code reads** and loads
8 curated NJ programs.

```sql
-- Catalog + schema
CREATE CATALOG IF NOT EXISTS benefits_navigator;
CREATE SCHEMA  IF NOT EXISTS benefits_navigator.trusted;

-- Trusted, source-labeled benefit programs (+ rule columns used by the app)
CREATE TABLE IF NOT EXISTS benefits_navigator.trusted.benefit_programs (
    program_id              STRING,
    program_name            STRING,
    category                STRING,   -- food | healthcare | childcare | cash | family
    description             STRING,
    eligibility_summary     STRING,
    apply_url               STRING,
    apply_phone             STRING,
    source_name             STRING,
    source_url              STRING,
    source_type             STRING,
    state                   STRING,
    active_flag             BOOLEAN,
    last_verified_date      DATE,
    -- Rule columns consumed by benefits_rules.py via the adapter:
    rule_key                STRING,   -- maps to the engine's program id (snap, wic, ...)
    income_limit_pct_fpl    INT,
    accepts_undocumented    BOOLEAN,
    min_child_age           INT,
    max_child_age           INT,
    requires_work_or_school BOOLEAN
);

-- Refresh: clear and load the 8 curated programs (idempotent for demos)
DELETE FROM benefits_navigator.trusted.benefit_programs;

INSERT INTO benefits_navigator.trusted.benefit_programs VALUES
('snap','NJ SNAP (Supplemental Nutrition Assistance Program)','food',
 'Monthly food benefits on an EBT card to buy groceries.',
 'Based on household size and gross income (about 130% FPL).',
 'https://www.njhelps.org','1-800-687-9512',
 'NJ DHS','https://www.nj.gov/humanservices/','official','NJ',true, DATE'2025-01-01',
 'snap',130,false,NULL,NULL,false),

('wic','WIC (Women, Infants & Children)','food',
 'Food, nutrition support, and referrals for pregnant women and young children.',
 'Income up to 185% FPL; pregnant or child under 5.',
 'https://www.nj.gov/health/fhs/wic/','1-800-328-3838',
 'NJ DOH','https://www.nj.gov/health/','official','NJ',true, DATE'2025-01-01',
 'wic',185,true,0,5,false),

('nj_familycare','NJ FamilyCare (Medicaid)','healthcare',
 'Free or low-cost health coverage for eligible NJ residents.',
 'Children up to 350% FPL; adults up to 138% FPL.',
 'https://www.njfamilycare.org','1-800-701-0710',
 'NJ DHS','https://www.nj.gov/humanservices/','official','NJ',true, DATE'2025-01-01',
 'nj_familycare',350,false,NULL,NULL,false),

('chip','NJ FamilyCare - CHIP (Children''s Health Insurance)','healthcare',
 'Low-cost health coverage for children who do not qualify for Medicaid.',
 'Children up to age 19; household income up to 350% FPL.',
 'https://getcovered.nj.gov','1-800-701-0710',
 'NJ DHS','https://getcovered.nj.gov','official','NJ',true, DATE'2025-01-01',
 'chip',350,false,0,18,false),

('ccdf','NJ Child Care Assistance (CCDF / Child Care Subsidy)','childcare',
 'Subsidizes child care so parents can work or attend school.',
 'Working/in-school families, children under 13, income up to 200% FPL.',
 'https://www.childcarenj.gov','1-800-332-9227',
 'NJ DHS','https://www.childcarenj.gov','official','NJ',true, DATE'2025-01-01',
 'ccdf',200,false,0,12,true),

('preschool','NJ Preschool Education Aid (PEA)','childcare',
 'Free, high-quality preschool for 3- and 4-year-olds in eligible districts.',
 'Children ages 3-4 in participating districts; no income requirement.',
 'https://www.nj.gov/education/ece/','609-376-3600',
 'NJ DOE','https://www.nj.gov/education/','official','NJ',true, DATE'2025-01-01',
 'preschool',999,true,3,4,false),

('tanf','NJ WorkFirst (TANF)','cash',
 'Cash assistance and employment support for families with children.',
 'Families with children under 18; very low income; time-limited.',
 'https://www.njhelps.org','1-800-687-9512',
 'NJ DHS','https://www.nj.gov/humanservices/','official','NJ',true, DATE'2025-01-01',
 'tanf',50,false,NULL,NULL,false),

('liheap','Low Income Home Energy Assistance (LIHEAP)','cash',
 'Helps eligible households pay heating/cooling bills and energy emergencies.',
 'Income up to ~60% of state median income; seasonal enrollment.',
 'https://www.njhelps.org','1-800-510-3102',
 'NJ DCA','https://www.nj.gov/dca/','official','NJ',true, DATE'2025-01-01',
 'liheap',150,false,NULL,NULL,false);
```

**Validation queries:**

```sql
-- Count rows (expect 8)
SELECT COUNT(*) AS total_programs
FROM benefits_navigator.trusted.benefit_programs;

-- Count by category
SELECT category, COUNT(*) AS n
FROM benefits_navigator.trusted.benefit_programs
GROUP BY category
ORDER BY n DESC;

-- Select all programs
SELECT program_id, program_name, category, rule_key,
       income_limit_pct_fpl, accepts_undocumented,
       min_child_age, max_child_age, requires_work_or_school
FROM benefits_navigator.trusted.benefit_programs
ORDER BY category, program_name;
```

---

## 7. Lakebase Setup

1. **Create a Lakebase project** in the workspace (e.g.,
   `benefits-navigator-lakebase`).
2. **Branch:** use **`production`**.
3. **Database:** **`databricks_postgres`**.
4. **Create the four app-state tables** (run in the Lakebase SQL editor /
   psql against `databricks_postgres`). These match what `lakebase_client.py`
   writes; `event_ts` defaults to `now()`.

```sql
CREATE TABLE IF NOT EXISTS family_intake_events (
    intake_id      TEXT PRIMARY KEY,
    event_ts       TIMESTAMPTZ NOT NULL DEFAULT now(),
    raw_user_text  TEXT,
    profile        JSONB
);

CREATE TABLE IF NOT EXISTS program_matches (
    match_id       TEXT PRIMARY KEY,
    intake_id      TEXT REFERENCES family_intake_events(intake_id),
    event_ts       TIMESTAMPTZ NOT NULL DEFAULT now(),
    program_id     TEXT,
    program_name   TEXT,
    category       TEXT,
    match_reasons  JSONB
);

CREATE TABLE IF NOT EXISTS action_plans (
    plan_id            TEXT PRIMARY KEY,
    intake_id          TEXT REFERENCES family_intake_events(intake_id),
    event_ts           TIMESTAMPTZ NOT NULL DEFAULT now(),
    action_plan_text   TEXT,
    generated_by_model TEXT
);

CREATE TABLE IF NOT EXISTS user_feedback (
    feedback_id    TEXT PRIMARY KEY,
    intake_id      TEXT REFERENCES family_intake_events(intake_id),
    event_ts       TIMESTAMPTZ NOT NULL DEFAULT now(),
    rating         INTEGER,
    feedback_text  TEXT
);
```

**Validation query (list tables):**

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
-- expect: action_plans, family_intake_events, program_matches, user_feedback
```

---

## 8. Databricks App Resources

In the Databricks App configuration, add:

- **SQL Warehouse resource** → exposes the warehouse to the app (used for the
  trusted-data read).
- **Anthropic API key secret** → a secret-scope entry surfaced as
  `ANTHROPIC_API_KEY`.
- **Databricks token secret** → only if your SQL connector path still needs a
  PAT (`DATABRICKS_TOKEN`). Prefer warehouse-resource auth where possible.
- **Lakebase database resource** → exposes the Lakebase endpoint and, on
  Autoscaling, injects the `PG*` connection env vars.

**`app.yaml` pattern** (non-secret values inline; secrets via `valueFrom`):

```yaml
command:
  - streamlit
  - run
  - app.py

env:
  - name: STREAMLIT_GATHER_USAGE_STATS
    value: "false"

  # Trusted-data read (SQL connector)
  - name: DATABRICKS_SERVER_HOSTNAME
    value: "<YOUR_WORKSPACE_HOST>"
  - name: DATABRICKS_HTTP_PATH
    value: "/sql/1.0/warehouses/<WAREHOUSE_ID>"

  # Secrets (never inline)
  - name: ANTHROPIC_API_KEY
    valueFrom: anthropic-api-key
  - name: DATABRICKS_TOKEN          # only if the SQL connector still needs a PAT
    valueFrom: databricks-token

  # Lakebase (managed): resource + PG* injected by the database resource
  - name: LAKEBASE_RESOURCE
    valueFrom: lakebase-db          # e.g. projects/<p>/branches/production/endpoints/primary
  - name: LAKEBASE_DATABASE
    value: "databricks_postgres"
  - name: LAKEBASE_PORT
    value: "5432"
  # PGHOST / PGDATABASE / PGUSER / PGPORT / PGSSLMODE are expected to be injected
  # by the Lakebase database resource when available (Autoscaling). The app reads
  # them in managed mode and mints a short-lived OAuth token for the password.
```

> The current `lakebase_client.py` selects mode automatically: **manual** when
> `LAKEBASE_PASSWORD` is set (local), otherwise **managed** using `PG*` +
> `LAKEBASE_RESOURCE` and a minted OAuth credential.

---

## 9. Lakebase Service Principal Grants

**Why:** In a deployed Databricks App, writes happen as the **App's service
principal** (machine identity), **not** as your human user. So your human
ability to query Lakebase does **not** automatically let the App write — the
service-principal role needs explicit grants, or you'll see `permission denied`.

**Find the role** (run in Lakebase `databricks_postgres`):

```sql
SELECT rolname
FROM pg_roles
WHERE rolname ILIKE '%<APP_CLIENT_ID_PREFIX>%'
   OR rolname ILIKE '%benefits%'
   OR rolname ILIKE '%app%';
```

**Grant template** (replace `<APP_SERVICE_PRINCIPAL_ROLE>` with the role you
found — often the App's client id / service-principal application id):

```sql
GRANT USAGE ON SCHEMA public TO "<APP_SERVICE_PRINCIPAL_ROLE>";

GRANT SELECT, INSERT, UPDATE, DELETE
ON TABLE family_intake_events,
         program_matches,
         action_plans,
         user_feedback
TO "<APP_SERVICE_PRINCIPAL_ROLE>";

GRANT USAGE, SELECT
ON ALL SEQUENCES IN SCHEMA public
TO "<APP_SERVICE_PRINCIPAL_ROLE>";
```

After granting, **redeploy/restart** the App and run one journey to confirm rows
land in the tables.

---

## 10. Deployment Steps

1. **Push to GitHub**
   ```bash
   git add .
   git commit -m "Configure for hackathon Databricks workspace"
   git push origin main
   ```
2. **Create a Databricks App** in the new workspace (**Compute → Apps → Create**,
   or the Apps section).
3. **Connect the GitHub repo** (link `<NEW_HACKATHON_REPO_URL>`).
4. **Branch:** `main`.
5. **Source path:** leave **blank** unless the app lives in a subfolder (this
   repo's `app.py` is at the root).
6. **Add resources & secrets** (§8): SQL warehouse, Anthropic secret, optional
   Databricks token secret, Lakebase database resource.
7. **Deploy.**
8. **Check logs** — confirm: data-source selection, `psycopg.connect() succeeded`,
   and write-back commits (the app logs only safe status, never secrets).
9. **Open the app URL** and run a scenario (§13).

---

## 11. Claude Prompts for Each Phase

Copy-paste these into Claude as you go. (Adjust file names if yours differ.)

**Inspect repo**
```
Inspect this repo and summarize each file's responsibility: app.py, agent.py,
benefits_rules.py, databricks_client.py, lakebase_client.py, requirements.txt,
app.yaml, sample_data/programs.json, social_impact_analytics.sql. Flag anything
that reads environment variables or external services.
```

**Verify requirements.txt**
```
Check requirements.txt against the imports in this repo. Confirm streamlit,
anthropic, databricks-sql-connector, psycopg[binary], python-dotenv, and
databricks-sdk are present and version-compatible. Suggest minimal pins if a
deployed environment might install incompatible versions.
```

**Update app.yaml for a new workspace**
```
Update app.yaml for a new Databricks workspace. Inline only non-secret values
(DATABRICKS_SERVER_HOSTNAME, DATABRICKS_HTTP_PATH, LAKEBASE_DATABASE,
LAKEBASE_PORT). Use valueFrom for ANTHROPIC_API_KEY, DATABRICKS_TOKEN, and the
Lakebase resource. Do not put secrets in the file. Here are my non-secret values:
host=<...>, http_path=<...>.
```

**Update databricks_client.py env names if needed**
```
Review databricks_client.py. Confirm it reads DATABRICKS_SERVER_HOSTNAME,
DATABRICKS_HTTP_PATH, and DATABRICKS_TOKEN, queries
benefits_navigator.trusted.benefit_programs, and falls back to local JSON on
failure. If the new workspace uses different env names, adapt safely without
breaking local fallback.
```

**Update lakebase_client.py for new Lakebase variables**
```
Review lakebase_client.py. It supports manual mode (LAKEBASE_* incl.
LAKEBASE_PASSWORD) and managed Databricks App mode (PG* env vars +
LAKEBASE_RESOURCE + minted OAuth token). If the new Lakebase resource injects
different variable names, adapt the managed path without breaking local/manual
mode, and keep logs free of secrets.
```

**Add safe diagnostic logging**
```
Add INFO-level diagnostic logging to lakebase_client.py covering startup, mode
selection, managed credential generation, connection (sanitized params), and
each write (started/execute/commit/closed). Never log secrets, tokens,
passwords, full hosts, or raw user text. Log only present/missing status and
exception type/message.
```

**Troubleshoot SQL Warehouse connection**
```
My trusted-data read fails. Here is the exact error/log: <PASTE>. Help me
diagnose whether it's the hostname, HTTP path, token/permissions, a stopped
warehouse, or a missing table — and how to confirm the app fell back to local
JSON.
```

**Troubleshoot Lakebase connection**
```
Lakebase writes are failing. Here are the safe logs: <PASTE>. Tell me whether
this is mode selection, PG* vars, OAuth token generation, SSL, or permissions,
and the next concrete step.
```

**Troubleshoot service principal grants**
```
I get 'permission denied for table ...' when the deployed app writes to
Lakebase. Walk me through finding the App service-principal role in pg_roles and
the exact GRANT statements for the four app-state tables and sequences.
```

**Create impact analytics SQL**
```
Using my Lakebase schema (family_intake_events, program_matches, action_plans,
user_feedback with event_ts), write read-only analytics queries for: total
intakes, matches, plans, feedback; most common categories; most recommended
programs; average rating; and recent end-to-end journeys.
```

**Prepare final demo script**
```
Write a 60-second spoken demo script for judges that frames this as agentic AI +
governed trusted Databricks data + Lakebase app state + social impact analytics,
and a step-by-step click path for a 'single mom with two kids' scenario.
```

---

## 12. Final Demo Readiness Checklist

- [ ] App loads without errors at its URL.
- [ ] Caption shows **"Using trusted Databricks benefits data"** (not local fallback).
- [ ] A scenario generates **adaptive follow-up questions**.
- [ ] The main scenario surfaces the expected programs from the **8-program** catalog.
- [ ] An **action plan** is generated and rendered.
- [ ] Submitting the feedback widget shows **"Thanks for your feedback!"**
- [ ] **Lakebase tables populate** (rows appear in all four tables).
- [ ] **Summary analytics queries** (`social_impact_analytics.sql`) return data.
- [ ] App **survives a redeploy** and previously written Lakebase data remains.

---

## 13. Testing Scenarios (synthetic only)

> All inputs are **fictional/synthetic**. No real personal data.

### A. Single mom with two kids
- **Input:** "I'm a single mom with two kids ages 3 and 7. I work part-time and
  make about $1,800 a month. We don't have health insurance and I need childcare
  help."
- **Follow-up answers:** household size 3; working; needs childcare; documented.
- **Expected programs:** SNAP, NJ FamilyCare, CHIP, CCDF (child care), Preschool
  (age 3), possibly WIC if a child is under 5.
- **Proves:** end-to-end agentic flow with multiple grounded matches + reasons.

### B. Pregnant mother
- **Input:** "I'm pregnant with my first child and not working right now. Money
  is very tight."
- **Follow-up answers:** pregnant yes; household size 1-2; low income.
- **Expected programs:** WIC, NJ FamilyCare; possibly SNAP/TANF depending on
  income.
- **Proves:** pregnancy-aware rules and prenatal support matching.

### C. Higher-income family needing child coverage
- **Input:** "We make a decent income but can't afford private health insurance
  for our two school-age kids."
- **Follow-up answers:** income near upper threshold; children under 19.
- **Expected programs:** CHIP (higher FPL ceiling), maybe NJ FamilyCare.
- **Proves:** income thresholds work — not everyone matches everything.

### D. Utility bill emergency
- **Input:** "I'm behind on my heating bill and worried about a shutoff this
  winter."
- **Follow-up answers:** low/moderate income; household with dependents.
- **Expected programs:** LIHEAP (energy assistance); possibly SNAP.
- **Proves:** needs-based matching beyond just income.

### E. Childcare-focused working parent
- **Input:** "I just started a full-time job and need affordable daycare for my
  4-year-old."
- **Follow-up answers:** working full-time; child age 4; needs childcare.
- **Expected programs:** CCDF (requires work/school), Preschool (age 3-4).
- **Proves:** `requires_work_or_school` and child-age rule columns in action.

### F. Immigration-sensitive family
- **Input:** "We need food and prenatal help, but we're worried about
  immigration status."
- **Follow-up answers:** undocumented; pregnant or child under 5.
- **Expected programs:** WIC and Preschool (which accept undocumented in our
  data); restricted programs correctly excluded.
- **Proves:** `accepts_undocumented` handling — inclusive and accurate.

### G. State retention demo
- **Input:** Run scenario A, submit feedback, then **redeploy** the app.
- **Check:** previously written rows still in Lakebase; new journey appends.
- **Proves:** Lakebase persistence + the social-impact data is durable.

---

## 14. FAQ and Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| **SQL warehouse `ENDPOINT_NOT_FOUND` / not found** | Wrong `DATABRICKS_HTTP_PATH` or stopped warehouse | Recopy HTTP path from warehouse connection details; start the warehouse |
| **Missing `DATABRICKS_TOKEN`** | Secret not set / not referenced | Add the token secret and `valueFrom: databricks-token` in `app.yaml` (only if the connector needs a PAT) |
| **`Table or view not found`** | Trusted table not created in this workspace | Re-run §6 catalog/schema/table + insert |
| **App uses fallback JSON instead of Databricks** | Connector failed and fell back silently | Check logs for the read error; verify host/path/token/warehouse + table; caption will read "local fallback" |
| **Anthropic key missing** | `ANTHROPIC_API_KEY` not set | Add the secret and `valueFrom: anthropic-api-key`; verify the agent step |
| **Lakebase env vars missing** | Neither manual nor managed config present | Set `LAKEBASE_PASSWORD` (local) **or** attach the Lakebase resource so `PG*` + `LAKEBASE_RESOURCE` are injected |
| **PAT/OAuth conflict** (`more than one authorization method configured: oauth and pat`) | SDK auto-detected both PAT and OAuth | Use the client's explicit OAuth M2M init (current code pins `auth_type="oauth-m2m"`) |
| **`WorkspaceClient has no attribute postgres/database`** | Old `databricks-sdk` | Pin `databricks-sdk>=0.89.0` in `requirements.txt`; redeploy |
| **`generate_database_credential` errors** | Wrong endpoint shape / SDK surface | Ensure `LAKEBASE_RESOURCE` is the endpoint path; current code passes it as `endpoint=...` and falls back to manual on failure |
| **`permission denied` on Lakebase tables** | Service principal lacks grants | Run §9 GRANTs for the role |
| **`role "..." does not exist`** | Wrong role name in GRANT | Re-run the `pg_roles` lookup (§9) and use the exact `rolname` |
| **`relation "..." does not exist`** | Tables not created in this Lakebase DB/branch | Re-run §7 table creation on the `production` branch / `databricks_postgres` |
| **Feedback not saving** | No `intake_id` (intake write failed) or grants missing | Check intake write succeeded; verify grants; the UI shows "Feedback could not be saved right now" on failure |
| **Deploy used an old commit** | App pointed at stale commit/branch | Push to `main`, redeploy, confirm the commit hash in the deploy view |
| **Source path wrong** | App configured with a subfolder path | Leave source path blank (app.py is at repo root) |
| **App starts but blank screen** | Streamlit start command/port issue | Confirm `command: streamlit run app.py`; check app logs for tracebacks |
| **Works locally but not in Databricks App** | Local uses `.env`/manual mode; deployed uses resources/secrets | Verify each `app.yaml` env entry resolves; check resource attachment + grants |

---

## 15. Closing — How to Present It

Frame the submission as four crisp pillars:

1. **Agentic AI** — a Claude agent that understands free text, asks adaptive
   follow-ups, and writes a personalized plan (not a scripted chatbot).
2. **Governed trusted data** — eligibility grounded in source-labeled NJ programs
   in **Unity Catalog / Delta**, read through a **SQL Warehouse**, with an
   **explainable rules engine** giving a reason for every match.
3. **Lakebase application state** — every journey (intake, matches, plan,
   feedback) persisted transactionally, authenticated via the App's **service
   principal** with rotating credentials.
4. **Social impact analytics** — individual journeys roll up into county needs,
   program demand, and feedback trends.

Be honest about scope (8 curated programs, synthetic inputs) and emphasize that
the architecture makes scaling **additive**, not a rewrite. Keep the demo tight
(scenario A), show the trusted-data caption, the explainable matches, the plan,
the feedback save, and one analytics query.

> **Reminder:** Follow **§0 Hackathon Rule Safety** throughout — permitted tools
> only, synthetic data only, transparent commits, and disclose AI assistance and
> any pre-existing code. When unsure, **ask the organizers.**

---

> **Claude note:** This guide is **documentation-only**. It does not modify
> `app.py` or any working application code, and contains **no real secrets** —
> only placeholders.
