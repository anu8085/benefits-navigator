# Benefits Navigator From-Scratch Hackathon Build Guide with Claude — Rule-Safe Version

> **This is the recommended guide if the hackathon rules are interpreted
> strictly.** It assumes **no copying, forking, or reusing prior working repo
> code for the final submission.** You create a **brand-new public repo during
> the Project Period** and build everything in-window.

A phase-by-phase playbook to build the **Benefits Navigator** app **from scratch
during the Project Period**. Each phase has a **Goal**, a **copy-paste Claude
prompt** (use Claude only if AI assistance is permitted), **expected files**,
**commands/SQL**, **verification checks**, **common errors + fixes**, and a
**stop/go checkpoint**.

> **No real secrets in this document.** Everything sensitive is a `<PLACEHOLDER>`.
> Never paste real API keys, tokens, passwords, or private hostnames into GitHub.
>
> **Not legal advice.** This reflects the *safest interpretation* of the official
> rules. When uncertain, **confirm with the organizers.**

**Project Period:** Mon, June 15, 2026 **8:00 AM PT** → Tue, June 16, 2026
**2:30 PM PT.**  **Judging:** Tue, June 16, 2026 **2:30 PM PT → 6:00 PM PT.**

---

## 1. Hackathon Rule Safety First

**Read the official rules before you start.** This guide is structured to match
the kind of requirements this event imposes, but the official rules and the
organizers always win. Based on the official rules for this event, plan for:

- **New projects only — build during the Project Period.** Projects must be
  created during the official build window (for this event: **Mon Jun 15, 2026
  8:00am PT → Tue Jun 16, 2026 2:30pm PT**, per the official rules). This is
  exactly why a **from-scratch** build is the safe path: **do not fork/copy/reuse
  a prior repo** if the rules require in-window creation.
- **Use the required platform.** This event requires building on **Databricks
  (Free Edition)**, with a **Databricks App built on Lakebase** plus **one or
  more additional Databricks tools** (Unity Catalog, SQL Warehouse, etc.).
- **Public, open-source repo.** Your GitHub repo must be **public**, include an
  **open-source license**, and show that the work was **done during the Project
  Period** (clean, in-window commit history).
- **Original, solely-owned work.** Build your own implementation. **Do not use
  proprietary company code or private/confidential data.** Comply with any
  open-source licenses you depend on, and with any employer policies.
- **AI assistance:** outside models/tools are generally permitted by these rules
  (you may use external models), but **if you are unsure whether an AI coding
  assistant is allowed, ask the organizers and get it in writing.** If AI code
  generation is **not** allowed, use the manual guide
  (`docs/MANUAL_HACKATHON_SETUP_NO_AI.md`) and write the code yourself.
- **Synthetic demo data only.** No real personal information. Benefits data is
  sensitive — use fictional family scenarios.
- **No secrets in GitHub.** Keys/tokens/passwords live in Databricks
  secrets/app resources, never in the repo.
- **Transparency.** Keep commit history honest; do not misrepresent prebuilt work
  as built during the event.
- **Submission basics** (plan ahead): a working demo link (with login creds if
  private), a text description, and a **public demo video ≤ 3 minutes**, submitted
  via the event's Devpost.
- **When in doubt, ask.** Use the organizer contact in the official rules.

**Rule-safe statement (put this in your README/submission):**
> "I built this project during the hackathon using permitted tools, public
> documentation, synthetic demo data, and my own implementation."

---

## 1a. Before 8:00 AM PT (allowed prep only)

> ⚠️ **Nothing you build before the Project Period may be submitted as the
> project.** Prep is for *understanding*, not for pre-building the submission.

**Allowed before the window opens:**
- ✅ Read the official rules end-to-end.
- ✅ Practice **privately** (a separate, private scratch space) to build your own
  understanding.
- ✅ Prepare personal understanding of the architecture and steps.
- ✅ Prepare blank notes / checklists (if allowed by the rules).
- ✅ Confirm tools and accounts (Databricks Free Edition, GitHub, Devpost, conf pass).
- ✅ Ask the organizers any open questions and get answers in writing.

**Not for final submission:**
- ❌ Do **not** submit a previous repo as-is.
- ❌ Do **not** claim prebuilt code was created during the hackathon.
- ❌ Do **not** copy/paste prior-repo code into the submission (unless organizers
  explicitly allow reuse — see the appendix).

---

## 1b. At 8:00 AM PT (Project Period opens)

Do these **in order**, in-window:

1. **Create a new public GitHub repo** (`<NEW_PUBLIC_REPO_URL>`).
2. **Add an open-source license** (`LICENSE` — e.g., MIT or Apache-2.0).
3. **Make the initial commit** (timestamped inside the Project Period).
4. **Begin building** from Phase 0 onward.

```bash
mkdir benefits-navigator-hackathon
cd benefits-navigator-hackathon
git init
echo "# Benefits Navigator Hackathon" > README.md
git add .
git commit -m "Initial hackathon repo created during project period"
git branch -M main
git remote add origin <NEW_PUBLIC_REPO_URL>
git push -u origin main
```

> **Commit early and often** for the rest of the window so the public repo clearly
> shows the work was done **during** the Project Period.

---

## 2. Final Target Architecture

We are building, from scratch:

- **Streamlit UI** deployed as a **Databricks App**.
- **Claude/LLM agent** for profile extraction, follow-up questions, and action
  plan generation *(external model — use only if permitted)*.
- **Python rules engine** for explainable program matching.
- **Unity Catalog / Delta** table for trusted benefits reference data.
- **Databricks SQL Warehouse + SQL Connector** to read trusted data.
- **Lakebase Postgres** for transactional app state:
  `family_intake_events`, `program_matches`, `action_plans`, `user_feedback`.
- **Social impact analytics** queries/views.
- **Local JSON fallback** for demo safety.

```
            ┌──────────────────────────────────────────────────────────┐
            │                    USER (NJ family)                       │
            │  describes situation → answers follow-ups → gets a plan   │
            └───────────────┬──────────────────────────────────────────┘
                            │
                    ┌───────▼────────┐
                    │  Streamlit UI  │  (Databricks App)
                    │ app.py         │
                    └───┬────────┬───┘
            profile/    │        │   matches + plan
            questions   │        │
                ┌───────▼──┐  ┌──▼──────────┐
                │  Claude  │  │ Rules Engine│  benefits_rules.py
                │ agent.py │  │ explainable │
                └──────────┘  └──┬──────────┘
                                 │ needs trusted data
                       ┌─────────▼───────────┐        ┌──────────────────────┐
                       │ Databricks SQL       │  read  │ Unity Catalog/Delta  │
                       │ Warehouse + connector│───────▶│ benefit_programs     │
                       │ databricks_client.py │        │ (8 curated programs) │
                       └─────────┬───────────┘         └──────────────────────┘
                                 │  (fallback)                ▲
                                 ▼                            │ if Databricks down
                       sample_data/programs.json ─────────────┘
                                 │
                    writes app state ▼
                       ┌──────────────────────┐        ┌──────────────────────┐
                       │ Lakebase Postgres     │ aggreg │ Social Impact        │
                       │ lakebase_client.py    │───────▶│ Analytics (SQL views)│
                       │ intake/matches/plan/fb│        └──────────────────────┘
                       └──────────────────────┘
```

---

## 3. Phase 0 — Create Empty GitHub Repo

**Goal:** Start a clean, in-window, public repo with no prior code.

**Prompt to Claude:**
```
Help me start a new hackathon repo from scratch for a Streamlit + Databricks +
Lakebase + Claude app called benefits-navigator-hackathon. Do not copy any prior
repo code. Generate a clean project structure and README only.
```

**Files expected:** `README.md`, `docs/`, `sample_data/` (empty), plus a
`LICENSE` (open-source license is required by the rules — e.g., MIT or Apache-2.0).

**Commands:**
```bash
mkdir benefits-navigator-hackathon
cd benefits-navigator-hackathon
git init
echo "# Benefits Navigator Hackathon" > README.md
mkdir docs sample_data
# Add an OSS license (required). Pick MIT or Apache-2.0 and save it as LICENSE.
git add .
git commit -m "Initial empty hackathon repo (built during Project Period)"

# Remote
git remote add origin <NEW_EMPTY_REPO_URL>
git branch -M main
git push -u origin main
```

**Verification:**
- Repo exists and is **public**.
- `README.md` and a `LICENSE` exist.
- No prior app code copied in.
- Commit history starts clean and **inside the Project Period**.

**Common errors and fixes:**
- *`remote origin already exists`* → `git remote set-url origin <NEW_EMPTY_REPO_URL>`.
- *Push rejected (non-empty remote)* → create the remote with **no** README, or
  `git pull --rebase origin main` then push.
- *Repo private* → make it public (rules require a public repo).

**Checkpoint (stop/go):** ✅ Public repo + license + clean first commit before
moving on.

---

## 4. Phase 1 — Create Project Skeleton

**Goal:** Minimal runnable skeleton that opens locally before any cloud setup.

**Prompt to Claude:**
```
Create a from-scratch Streamlit app project skeleton for Benefits Navigator.
Create app.py, agent.py, benefits_rules.py, databricks_client.py,
lakebase_client.py, sample_data/programs.json, requirements.txt, app.yaml,
.gitignore, and README.md. Keep implementation minimal first. Do not use secrets
in code.
```

**Files expected:** `app.py`, `agent.py`, `benefits_rules.py`,
`databricks_client.py`, `lakebase_client.py`, `sample_data/programs.json`,
`requirements.txt`, `app.yaml`, `.gitignore`, `README.md`.

**`requirements.txt`:**
```
streamlit
anthropic
databricks-sql-connector
databricks-sdk>=0.89.0
psycopg[binary]
python-dotenv
```

**`.gitignore`:**
```
.env
.venv/
__pycache__/
*.pyc
```

**Commands (verification):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

**Common errors and fixes:**
- *`streamlit: command not found`* → venv not activated / deps not installed.
- *`ModuleNotFoundError`* → re-run `pip install -r requirements.txt` in the venv.
- *App crashes on import of cloud libs* → keep cloud imports lazy; skeleton must
  run without Databricks/Lakebase.

**Checkpoint:** ✅ App opens locally even before Databricks/Lakebase exist.

---

## 5. Phase 2 — Create Local Fallback Data

**Goal:** 8 curated synthetic NJ programs so the app works offline/in demos.

**Prompt to Claude:**
```
Create sample_data/programs.json with 8 curated synthetic/source-labeled New
Jersey benefit program records: NJ SNAP, WIC, NJ FamilyCare, NJ FamilyCare CHIP,
NJ Child Care Assistance Program, NJ Preschool Education Aid, LIHEAP, and NJ
2-1-1. Include fields needed by the rules engine: program_id, program_name,
category, description, eligibility_summary, apply_url, apply_phone, source_name,
source_url, source_type, state, active_flag, rule_key, income_limit_pct_fpl,
accepts_undocumented, min_child_age, max_child_age, requires_work_or_school. Use
public program names and URLs, but do not scrape. Keep language as 'may qualify'
not final eligibility.
```

**Files expected:** `sample_data/programs.json` (8 records).

**Command (verification):**
```bash
python -m json.tool sample_data/programs.json
```

**Verification:**
- JSON is valid (the command prints it without error).
- App loads local programs.
- Program count is **8**.

**Common errors and fixes:**
- *`json.decoder.JSONDecodeError`* → trailing comma / unescaped quote; fix and
  re-run.
- *Wrong field names* → make keys exactly match what the rules engine reads.

**Checkpoint:** ✅ Valid 8-program JSON the app can load offline.

---

## 6. Phase 3 — Build Rules Engine

**Goal:** Deterministic, explainable screening (no AI in this layer).

**Prompt to Claude:**
```
Create benefits_rules.py from scratch. It should expose screen_programs(profile,
programs). It must apply deterministic explainable screening rules using
household size, monthly income, child ages, pregnancy, work/school status,
healthcare need, food need, childcare need, utility/basic support need,
documentation/citizenship sensitivity, and county. Return matched programs with
program_id, program_name, category, rule_key, qualification_reason,
confidence_label. Do not make official eligibility decisions; use 'may qualify'
language.
```

**Expected rules:**
- SNAP — low income + food need
- WIC — pregnancy or child under 5
- FamilyCare — healthcare need
- CHIP — children under 19 needing coverage
- CCAP — working/in-school parent with child under 13 needing childcare
- Preschool — child age 3–4
- LIHEAP — utility/bill pressure
- NJ 211 — local resource navigation

**Files expected:** `benefits_rules.py` (+ optional `tests/manual_rule_test.py`).

**Verification prompt to Claude:**
```
Add simple unit-style test examples at the bottom under
if __name__ == '__main__' or create tests/manual_rule_test.py to validate that
the single-mom scenario returns multiple matches.
```

**Command (verification):**
```bash
python benefits_rules.py
```

**Common errors and fixes:**
- *No matches for main scenario* → check thresholds (income %FPL, child ages) and
  that needs are read from the profile keys you defined.
- *KeyError on profile fields* → use `profile.get(...)` with safe defaults.

**Checkpoint:** ✅ Rules return expected matches for the main scenario.

---

## 7. Phase 4 — Build Claude Agent Layer

**Goal:** Profile extraction, follow-ups, and plan generation (external model —
only if permitted).

**Prompt to Claude:**
```
Create agent.py from scratch using the Anthropic Python SDK. Add functions:
- extract_profile_from_text(user_text)
- generate_clarifying_questions(profile)
- merge_profile_with_answers(profile, answers)
- generate_action_plan(profile, matches)
Use safe prompts. The profile should be structured JSON. The agent should ask
only 2–3 missing follow-up questions. The action plan should be warm, concise,
and grounded only in matched programs. Do not claim guaranteed eligibility.
```

**Files expected:** `agent.py`.

**Environment (local only — never commit):**
```
ANTHROPIC_API_KEY=<your-key>
```

**Verification (manual):** run extraction on the main scenario:
> "I am a single mom in New Jersey with two kids ages 3 and 7. I work part-time
> and make about $1,800 per month. I do not have health insurance right now. I
> need help with food, childcare, and paying bills."

Expected: household size inferred, children ages extracted, needs detected,
follow-up questions generated.

**Fallback:** if the Anthropic key is missing, the app should show a friendly
message or use basic local parsing — it must not crash.

**Common errors and fixes:**
- *`anthropic.AuthenticationError`* → bad/missing `ANTHROPIC_API_KEY`.
- *JSON parse error from model output* → instruct the model to return JSON only;
  wrap parsing in try/except with a safe fallback.
- *Too many questions* → cap follow-ups at 2–3 in the prompt.

**Checkpoint:** ✅ Agent extracts a profile and asks sensible follow-ups (or
degrades gracefully without a key).

---

## 8. Phase 5 — Build Streamlit UI

**Goal:** Polished end-to-end UX wiring agent + rules + data + write-back.

**Prompt to Claude:**
```
Create app.py from scratch as a polished Streamlit UI for Benefits Navigator.
Flow:
1. Landing header and short privacy note
2. Free-text family situation input
3. Extract profile with Claude
4. Ask follow-up questions
5. Merge answers
6. Load programs from Databricks first, fallback to sample_data/programs.json
7. Run rules engine
8. Generate Claude action plan
9. Display action plan and program cards
10. Write intake/matches/action plan to Lakebase if available
11. Feedback widget writes feedback to Lakebase if available
12. Gracefully continue if Lakebase fails
Use session_state carefully.
```

**UI wording:**
- "Using trusted Databricks benefits data" — when Databricks read succeeds
- "Using local fallback data" — when fallback is used
- "Plan generated successfully, but saving app state failed" — only if Lakebase fails
- "Thanks for your feedback!" — when feedback saves

**Files expected:** `app.py` (full flow).

**Command (verification):**
```powershell
streamlit run app.py
```

**Common errors and fixes:**
- *Widgets reset / state lost* → store values in `st.session_state`, not locals.
- *App crashes when Lakebase down* → wrap write-back in try/except; never block
  the plan on persistence.
- *Blank screen* → check terminal traceback; confirm `streamlit run app.py`.

**Checkpoint:** ✅ App works locally via JSON fallback even without
Databricks/Lakebase.

---

## 9. Phase 6 — Databricks Unity Catalog Trusted Data Setup

**Goal:** Create governed trusted table + load 8 programs.

**Prompt to Claude:**
```
Create docs/sql/01_create_trusted_benefit_programs.sql with SQL to create catalog
benefits_navigator, schema trusted, and table benefit_programs with all current
app columns including rule columns. Insert 8 curated NJ programs. Add validation
queries.
```

**Files expected:** `docs/sql/01_create_trusted_benefit_programs.sql`.

**SQL (run in Databricks SQL Editor):**
```sql
CREATE CATALOG IF NOT EXISTS benefits_navigator;
CREATE SCHEMA  IF NOT EXISTS benefits_navigator.trusted;

CREATE OR REPLACE TABLE benefits_navigator.trusted.benefit_programs (
    program_id              STRING,
    program_name            STRING,
    category                STRING,
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
    rule_key                STRING,
    income_limit_pct_fpl    INT,
    accepts_undocumented    BOOLEAN,
    min_child_age           INT,
    max_child_age           INT,
    requires_work_or_school BOOLEAN
);
-- INSERT the 8 curated programs (snap, wic, nj_familycare, chip, ccdf/ccap,
-- preschool, liheap, nj_211) with rule columns. Use 'may qualify' language in
-- descriptions. (Claude can generate the INSERT to match sample_data/programs.json.)
```

**Validation:**
```sql
SELECT COUNT(*) FROM benefits_navigator.trusted.benefit_programs;
SELECT category, COUNT(*) FROM benefits_navigator.trusted.benefit_programs GROUP BY category;
SELECT program_id, program_name, rule_key FROM benefits_navigator.trusted.benefit_programs ORDER BY program_id;
```

**Manual steps:** open Databricks SQL Editor → select SQL Warehouse → run SQL →
confirm 8 rows.

**Common errors and fixes:**
- *`PARSE_SYNTAX_ERROR`* → check column list vs values count.
- *No permission to create catalog* → confirm Unity Catalog privileges (Free
  Edition); use an allowed catalog/schema if restricted.

**Checkpoint:** ✅ Trusted table exists with 8 rows and rule columns.

---

## 10. Phase 7 — Databricks SQL Connector

**Goal:** Read the trusted table from the app; fall back to JSON on failure.

**Prompt to Claude:**
```
Create databricks_client.py from scratch. It should load benefit programs from
benefits_navigator.trusted.benefit_programs using databricks-sql-connector.
Required env vars: DATABRICKS_SERVER_HOSTNAME, DATABRICKS_HTTP_PATH,
DATABRICKS_TOKEN. Return list of dicts. Log safe errors only. Do not print token.
App should fallback to JSON if this fails.
```

**Files expected:** `databricks_client.py`.

**Local env example (PowerShell):**
```powershell
$env:DATABRICKS_SERVER_HOSTNAME="<workspace-host>"
$env:DATABRICKS_HTTP_PATH="<warehouse-http-path>"
$env:DATABRICKS_TOKEN="<token>"
```

**Verification:**
```bash
python -c "from databricks_client import load_benefit_programs_from_databricks; print(len(load_benefit_programs_from_databricks()))"
```
Expected: `8`.

**Common errors and fixes:**
- *`ENDPOINT_NOT_FOUND`* → wrong warehouse HTTP path.
- *`401 Unauthorized`* → bad token.
- *`table not found`* → SQL not run, or wrong catalog/schema.
- *App shows fallback message* → env vars missing or connector failed (check
  logs).

**Checkpoint:** ✅ Connector returns 8 rows; app shows the "trusted Databricks
data" message.

---

## 11. Phase 8 — Lakebase Tables

**Goal:** Create the four app-state tables.

**Prompt to Claude:**
```
Create docs/sql/02_create_lakebase_tables.sql with SQL to create app-state tables
for Lakebase Postgres: family_intake_events, program_matches, action_plans,
user_feedback. Use JSONB profile in family_intake_events and JSONB match_reasons
in program_matches if supported. Include validation queries.
```

**Files expected:** `docs/sql/02_create_lakebase_tables.sql`.

**SQL (Lakebase SQL Editor on `databricks_postgres`):**
```sql
CREATE TABLE IF NOT EXISTS family_intake_events (
  intake_id TEXT PRIMARY KEY,
  event_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  raw_user_text TEXT,
  profile JSONB
);

CREATE TABLE IF NOT EXISTS program_matches (
  match_id TEXT PRIMARY KEY,
  intake_id TEXT REFERENCES family_intake_events(intake_id),
  event_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  program_id TEXT,
  program_name TEXT,
  category TEXT,
  match_reasons JSONB
);

CREATE TABLE IF NOT EXISTS action_plans (
  plan_id TEXT PRIMARY KEY,
  intake_id TEXT REFERENCES family_intake_events(intake_id),
  event_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  action_plan_text TEXT,
  generated_by_model TEXT
);

CREATE TABLE IF NOT EXISTS user_feedback (
  feedback_id TEXT PRIMARY KEY,
  intake_id TEXT REFERENCES family_intake_events(intake_id),
  event_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  rating INTEGER,
  feedback_text TEXT
);
```

**Validation:**
```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema='public' ORDER BY table_name;
```

**Manual steps:** create Lakebase project → create/use **production** branch →
open SQL Editor → run SQL → verify tables.

**Common errors and fixes:**
- *`syntax error near JSONB`* → ensure you're on Postgres (Lakebase), not the
  Databricks SQL editor.
- *Tables missing later* → you created them on a different branch/database.

**Checkpoint:** ✅ Four tables exist on the `production` branch /
`databricks_postgres`.

---

## 12. Phase 9 — Lakebase Client

**Goal:** Dual-mode Lakebase writer (local manual + Databricks App managed).

**Prompt to Claude:**
```
Create lakebase_client.py from scratch. It must support:
A. Local/manual mode using LAKEBASE_HOST, LAKEBASE_PORT, LAKEBASE_DATABASE,
   LAKEBASE_USER, LAKEBASE_PASSWORD.
B. Databricks App managed mode using PGHOST, PGDATABASE, PGUSER, PGPORT,
   PGSSLMODE and Databricks SDK OAuth to call
   w.postgres.generate_database_credential(endpoint=ENDPOINT_NAME or
   LAKEBASE_RESOURCE).
It should expose:
- write_intake_event(raw_user_text, profile)
- write_program_matches(intake_id, matches)
- write_action_plan(intake_id, action_plan_text, model_name)
- write_feedback(intake_id, rating, feedback_text)
It must never log secrets/tokens/passwords/full DSNs. Add safe diagnostic
logging. If connection fails, return None or skip gracefully so app demo does not
crash.
```

**Files expected:** `lakebase_client.py`.

**Verification:**
- Local mode optional (set `LAKEBASE_*` to test writes locally).
- Deployed mode verified after App resource setup (Phase 11).
- No secrets in logs.
- Writes create rows.

**Common errors and fixes (known):**
- *PAT/OAuth conflict* (`more than one authorization method configured: oauth and
  pat`) → explicitly init `WorkspaceClient(auth_type="oauth-m2m", ...)` and ignore
  `DATABRICKS_TOKEN` for Lakebase.
- *Missing PG vars* → Lakebase app resource not attached.
- *`permission denied`* → grant table privileges to the app service principal
  (Phase 12).
- *`WorkspaceClient has no attribute postgres`* → pin `databricks-sdk>=0.89.0`.

**Checkpoint:** ✅ Client imports cleanly and degrades gracefully with no secrets
in logs.

---

## 13. Phase 10 — Databricks App app.yaml

**Goal:** Declare the start command + env wiring (no secrets inline).

**Prompt to Claude:**
```
Create app.yaml for Databricks Apps deployment. Use Streamlit command. Use env
vars for Anthropic key, Databricks SQL connection, and Lakebase endpoint
resource. Do not include real secrets.
```

**Files expected:** `app.yaml`.

**Example:**
```yaml
command:
  - streamlit
  - run
  - app.py

env:
  - name: STREAMLIT_GATHER_USAGE_STATS
    value: "false"
  - name: DATABRICKS_SERVER_HOSTNAME
    value: "<workspace-host>"
  - name: DATABRICKS_HTTP_PATH
    value: "<sql-warehouse-http-path>"
  - name: ANTHROPIC_API_KEY
    valueFrom: "<anthropic-secret-resource-key>"
  - name: DATABRICKS_TOKEN
    valueFrom: "<databricks-token-secret-resource-key>"
  - name: ENDPOINT_NAME
    valueFrom: "<lakebase-resource-key>"
```

> Depending on the hackathon Databricks Apps behavior, the Lakebase resource may
> also inject `PGHOST`, `PGDATABASE`, `PGUSER`, `PGPORT`, `PGSSLMODE`.

**Verification:**
- `app.yaml` committed.
- No secrets hardcoded.
- Source path blank if app is at repo root.

**Common errors and fixes:**
- *Secret not resolving* → the `valueFrom` key must match the app resource/secret
  name exactly.
- *App can't find app.py* → wrong source path; leave blank for repo root.

**Checkpoint:** ✅ `app.yaml` committed with placeholders, no secrets.

---

## 14. Phase 11 — Databricks App Resources and Secrets

**Goal:** Wire the deployed app to the warehouse, Anthropic key, and Lakebase.

**Manual steps:**
- Create the **Databricks App**.
- Connect the **GitHub repo**; branch **main**; **source path blank**.
- Add **SQL Warehouse** resource.
- Add **Anthropic API key** secret/resource.
- Add **Databricks token** secret/resource *(only if the SQL connector needs a
  PAT)*.
- Add the **Lakebase database** resource.
- **Note the App service principal / client ID** (needed for Phase 12).

**Prompt to Claude:**
```
Create docs/APP_RESOURCE_SETUP_CHECKLIST.md documenting all Databricks App
resources required and how to validate them. Include placeholders only.
```

**Files expected:** `docs/APP_RESOURCE_SETUP_CHECKLIST.md`.

**Verification:**
- App overview shows the attached resources.
- Deployment succeeds.
- Logs show packages installed and the app started.

**Common errors and fixes:**
- *App starts but trusted read fails* → warehouse resource not attached or
  hostname/path wrong.
- *Anthropic step fails* → secret not attached / wrong key name.

**Checkpoint:** ✅ All resources attached; app boots in the workspace.

---

## 15. Phase 12 — Lakebase Service Principal Grants

**Goal:** Let the App (service principal) write to the app-state tables.

**Prompt to Claude:**
```
Create docs/sql/03_lakebase_service_principal_grants.sql with placeholder SQL to
find the app service principal role and grant permissions to app-state tables.
```

**Files expected:** `docs/sql/03_lakebase_service_principal_grants.sql`.

**SQL:**
```sql
SELECT rolname
FROM pg_roles
WHERE rolname ILIKE '%<APP_CLIENT_ID_PREFIX>%'
   OR rolname ILIKE '%benefits%'
   OR rolname ILIKE '%app%';

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

**Explain:** the Databricks App writes as a **service principal**, not as your
human user — so your personal access does not grant the app access.

**Verification:** run one app journey and confirm Lakebase rows inserted.

**Common errors and fixes:**
- *`role "..." does not exist`* → re-run the `pg_roles` lookup; use the exact
  `rolname`.
- *`permission denied for table ...`* → grants not applied / wrong role.

**Checkpoint:** ✅ App journey writes rows as the service principal.

---

## 16. Phase 13 — Deployment

**Goal:** Deploy from `main` and confirm it runs.

**Commands:**
```bash
git status
git add .
git commit -m "Build Benefits Navigator hackathon app"
git push
```

**Manual steps:**
- In Databricks **Apps**: create app → add GitHub source → branch **main** →
  source path **blank** (unless in a subfolder) → **Deploy**.
- Watch logs: source downloaded → packages installed → app built → app started.
- Open the app URL.

**Verification:**
- App loads.
- "trusted Databricks data" (or fallback) message appears.
- Main scenario works.
- Feedback saves.

**Common errors and fixes:**
- *Deploy used old commit* → push to `main`, redeploy, confirm commit hash.
- *Wrong source path* → leave blank for repo root.
- *Build fails on deps* → check `requirements.txt` and the deploy log.

**Checkpoint:** ✅ Live URL runs the full journey.

---

## 17. Phase 14 — Demo Analytics SQL

**Goal:** Impact views/queries over Lakebase state.

**Prompt to Claude:**
```
Create docs/sql/04_demo_analytics.sql with clean demo queries and views for
Lakebase analytics.
```

**Files expected:** `docs/sql/04_demo_analytics.sql`.

**SQL:**
```sql
CREATE OR REPLACE VIEW demo_journey_summary AS
SELECT
  f.event_ts,
  f.intake_id,
  f.profile ->> 'county' AS county,
  f.profile ->> 'household_size' AS household_size,
  f.profile ->> 'monthly_income' AS monthly_income,
  f.profile ->> 'free_text_summary' AS family_summary,
  COUNT(DISTINCT pm.program_id) AS matched_program_count,
  MAX(uf.rating) AS feedback_rating
FROM family_intake_events f
LEFT JOIN program_matches pm ON f.intake_id = pm.intake_id
LEFT JOIN user_feedback uf ON f.intake_id = uf.intake_id
GROUP BY f.event_ts, f.intake_id, f.profile
ORDER BY f.event_ts DESC;

SELECT * FROM demo_journey_summary ORDER BY event_ts DESC;

SELECT program_name, category, COUNT(*) AS times_recommended
FROM program_matches
GROUP BY program_name, category
ORDER BY times_recommended DESC;

SELECT ROUND(AVG(rating), 2) AS average_rating, COUNT(*) AS total_feedback
FROM user_feedback;

SELECT COUNT(*) AS intake_count   FROM family_intake_events;
SELECT COUNT(*) AS match_count    FROM program_matches;
SELECT COUNT(*) AS plan_count     FROM action_plans;
SELECT COUNT(*) AS feedback_count FROM user_feedback;
```

**Verification:** queries run and show demo data after a few journeys.

**Common errors and fixes:**
- *`column profile ->> 'county' does not exist`* → ensure `profile` is JSONB and
  the key exists in your stored profile.
- *Empty results* → run a journey first.

**Checkpoint:** ✅ Analytics queries return live demo data.

---

## 18. Phase 15 — Test Scenarios

**Goal:** Repeatable synthetic scenarios for demo validation.

**Prompt to Claude:**
```
Create docs/TEST_SCENARIOS.md with test scenarios for demo validation. Include
input, follow-up answers, expected matches, and what the scenario proves.
```

**Files expected:** `docs/TEST_SCENARIOS.md`.

**Scenario 1 — Single mom with two kids**
- **Input:** "I am a single mom in New Jersey with two kids ages 3 and 7. I work
  part-time and make about $1,800 per month. I do not have health insurance right
  now. I need help with food, childcare, and paying bills."
- **Answers:** Middlesex County · 7-year-old in school, 3-year-old needs
  daycare/preschool · Not currently receiving benefits.
- **Expected:** SNAP, WIC, FamilyCare, CHIP, CCAP, Preschool, LIHEAP, NJ 211.

Also include (Claude generates details for each):
- **Scenario 2 — Pregnant mother** (expects WIC, FamilyCare).
- **Scenario 3 — Higher-income child health coverage** (expects CHIP).
- **Scenario 4 — Utility bill emergency** (expects LIHEAP, maybe SNAP).
- **Scenario 5 — Childcare-focused working parent** (expects CCAP, Preschool).
- **Scenario 6 — Immigration-sensitive family** (expects WIC/Preschool; correctly
  excludes restricted programs).
- **Scenario 7 — State retention demo** (below).

**State retention steps:** check counts → run app journey → submit feedback →
check counts increased → redeploy app → check counts retained.

**Verification:** each scenario yields the expected categories; retention counts
persist across redeploy.

**Common errors and fixes:**
- *Unexpected matches* → tune rule thresholds; verify follow-up answers update
  the profile.

**Checkpoint:** ✅ Main scenario + retention proof pass.

---

## 19. Phase 16 — Troubleshooting Guide

**Goal:** A single reference for fast fixes.

**Prompt to Claude:**
```
Create docs/TROUBLESHOOTING.md with a detailed issue/fix table for this
from-scratch build.
```

**Files expected:** `docs/TROUBLESHOOTING.md`.

| Symptom | Likely cause | Fix | Verify |
|---|---|---|---|
| App deploy fails | Build/config error | Check deploy logs, `app.yaml`, branch/source path | Redeploy succeeds |
| requirements install fails | Version conflict | Recreate venv; check failing line | `pip install` clean |
| Streamlit command wrong | Bad `command:` | Use `streamlit run app.py` | App starts |
| GitHub branch mismatch | App on wrong branch | Set branch `main` | Deploy uses main |
| Source path wrong | Subfolder set | Blank for repo root | App found |
| App starts blank | Runtime traceback | Read logs; fix import/error | UI renders |
| Anthropic key missing | Secret unset | Attach secret + `valueFrom` | Agent works |
| Claude API failure | Bad key / quota / not allowed | Verify key; confirm API allowed | Calls succeed |
| JSON parsing failure | Model returned non-JSON | Force JSON-only; try/except | Profile parses |
| SQL `ENDPOINT_NOT_FOUND` | Wrong HTTP path | Recopy path; start warehouse | `SELECT 1` works |
| `DATABRICKS_TOKEN` missing | Secret unset | Add token secret (if needed) | Read succeeds |
| table not found | SQL not run | Run Phase 6 SQL | 8 rows |
| App using fallback JSON | Read failed | Check creds/warehouse/table | "trusted" caption |
| SQL Warehouse stopped | Idle/stopped | Start warehouse | Connects |
| Lakebase PG vars missing | Resource not attached | Attach Lakebase resource | PG vars present |
| PAT/OAuth conflict | SDK saw both | Explicit OAuth M2M init | Token mints |
| `WorkspaceClient` has no `postgres` | Old SDK | Pin `databricks-sdk>=0.89.0` | Attr exists |
| `generate_database_credential` error | Wrong endpoint/SDK surface | Pass endpoint; fallback to manual | Token mints |
| Lakebase permission denied | Missing grants | Run Phase 12 grants | Rows insert |
| service principal role not found | Wrong role name | `pg_roles` lookup | Exact role |
| relation does not exist | Tables not created here | Run Phase 8 on correct branch | Tables exist |
| feedback not saving | No intake_id / grants | Check intake write + grants | Feedback row |
| state not retained | Wrong DB/branch | Use `production`/`databricks_postgres` | Counts persist |
| old commit deployed | Stale deploy | Push + redeploy; confirm hash | New code live |
| secrets accidentally committed | `.env` not ignored | Rotate secret; add `.gitignore`; purge | No secrets in repo |
| raw user text privacy | Storing free text | Synthetic only; never log raw text | Safe logs |

**Checkpoint:** ✅ You can resolve any red-path issue quickly.

---

## 20. Phase 17 — Final Demo Script

**Goal:** Tight, rehearsed scripts at three lengths.

**Prompt to Claude:**
```
Create docs/FINAL_DEMO_SCRIPT.md with 1-minute, 3-minute, and 5-minute hackathon
demo scripts. Include exact live demo steps, SQL queries to show, timing, vocal
delivery, gestures, and strong opening/closing. Do not mention my employer unless
required by organizers. Focus on the product, architecture, social impact, and
Databricks value.
```

**Files expected:** `docs/FINAL_DEMO_SCRIPT.md`.

**The ≤ 3-minute OFFICIAL video is the version that counts.** Make it your
strongest asset. The 5-minute version is only a **backup for live judging if
allowed**.

### ⭐ 3-minute official video script (primary)

| Time | Segment | Say / show |
|---|---|---|
| **0:00–0:20** | **Problem** | "Millions of families miss benefits they qualify for — the system is confusing and full of acronyms." |
| **0:20–0:45** | **Solution / architecture** | "Benefits Navigator: a **Databricks App on Lakebase**. Plain-language intake → agent + explainable rules → governed NJ program data → personalized plan → saved to Lakebase." |
| **0:45–1:50** | **Live app demo** | Run Scenario 1. Show the "trusted Databricks data" caption, follow-up questions, the action plan, and a *reason* on each match. |
| **1:50–2:30** | **Lakebase proof + analytics** | Show the four table counts and one analytics query (program demand + avg rating). |
| **2:30–3:00** | **Impact closing** | "Agentic AI + governed trusted data + durable Lakebase state + social impact — built to scale additively. Behind every number is a family that found help faster." |

### 60-second pitch (elevator)
Problem → "Databricks App on Lakebase that matches families to benefits with
explainable reasons" → one-line impact close.

### 5-minute backup (live judging only, if allowed)
Same arc as the 3-minute, with extra time for a second scenario (e.g.,
immigration-sensitive family) and a deeper architecture/Well-Architected walk.

> Keep the recorded submission video **≤ 3 minutes** and **public** (a submission
> requirement). Do not include third-party IP you don't have rights to.

**Checkpoint:** ✅ The ≤3-minute official video is recorded, public, and tight.

---

## 20a. Devpost Submission Readiness

Confirm every required submission artifact (per the official rules):

- [ ] **Public GitHub repo URL** (open-source license; history shows in-window work).
- [ ] **Working Databricks App URL** (or accessible test build).
- [ ] **Testing instructions** (include login credentials **only** if the app is
      private — but prefer a publicly accessible demo).
- [ ] **Text description** of features and functionality.
- [ ] **Demonstration video ≤ 3 minutes**, public (YouTube/Vimeo/etc.), linked on Devpost.
- [ ] **Open-source license** present in the repo.
- [ ] **Team members / collaborators** added on Devpost (if a team).
- [ ] **Synthetic data only**; **no secrets** committed.

---

## 20b. Judge Criteria Mapping

Map your project to the official judging criteria (equally weighted) so the demo
and README speak directly to them:

| Criterion | How Benefits Navigator addresses it |
|---|---|
| **Business Applicability** | Solves a real social problem — families miss benefits they qualify for; the app delivers an explainable, actionable plan. |
| **Data Relevance** | Combines **Databricks tools**: Unity Catalog/Delta trusted data, Databricks SQL read, and **Lakebase** transactional state + analytics. |
| **Creativity** | Agentic intake + adaptive questions + explainable rules + grounded trusted data + social-impact analytics — a fresh combination. |
| **Thoroughness** | Easy for end users (plain-language input, clear plan, reasons per match); end-to-end journey with feedback. |
| **Well-Architected** | Clean separation (trusted reference data vs. transactional app state); graceful fallbacks; scaling the program catalog and features is **additive**, not a rewrite. |

---

## 20c. Rule-Safe Disclosure Statement

Put a short, honest statement in your README/submission, e.g.:

> "Built during the Project Period using a **new public repo**, **permitted
> tools**, **synthetic data**, a **Databricks App**, **Lakebase**, **Unity
> Catalog / Databricks SQL**, and an **external LLM API if permitted**. The
> submission is the team's original work."

---

## 21. Final From-Scratch Build Checklist

- [ ] Empty **public** repo created **during the Project Period** (+ OSS LICENSE)
- [ ] Project skeleton created
- [ ] Local fallback works (8-program JSON)
- [ ] Rules engine works (explainable matches)
- [ ] Claude agent works (or degrades gracefully)
- [ ] Databricks trusted table created (8 rows)
- [ ] SQL connector works (returns 8)
- [ ] Lakebase tables created (production / databricks_postgres)
- [ ] Lakebase client works (no secrets in logs)
- [ ] App resources configured (warehouse, Anthropic, Lakebase)
- [ ] Service principal grants applied
- [ ] App deployed from `main`
- [ ] Test scenarios pass
- [ ] Lakebase rows saved (all four tables)
- [ ] Analytics queries run
- [ ] State retention proven across redeploy
- [ ] Final demo rehearsed; **public demo video ≤ 3 min** recorded
- [ ] **Devpost submission** complete (repo link, description, demo link, video)

---

## 22. Final Rule-Safe Reminder

If the hackathon does **not** allow prior repo reuse, **do not copy the old repo**
— use this guide to recreate the idea **from scratch during the permitted time
window**. If **AI coding help is not allowed**, use
`docs/MANUAL_HACKATHON_SETUP_NO_AI.md` and write the code yourself. Keep the repo
**public** with an **open-source license**, keep commit history **transparent and
in-window**, use **synthetic data only**, keep **secrets out of GitHub**, and
ensure your submission is your **original work**. **When in doubt, ask the
organizers and disclose your approach honestly.**

---

## Appendix — If Organizers Say Repo Reuse IS Allowed

Only if the organizers **explicitly confirm** (ideally in writing) that reusing a
prior repo is permitted:

- It is then acceptable to **fork/copy/reference your existing public repo** —
  **only with that permission**.
- **Still commit your meaningful hackathon work during the Project Period** so the
  repo shows in-window effort.
- **Still disclose prior work** clearly in your README (what existed before vs.
  what was built during the event).
- **Still ensure** the final submission is **original, owned by your team, and
  compliant** (open-source licenses respected; no proprietary/confidential code or
  data; synthetic demo data; no secrets in GitHub).
- If there is **any** ambiguity, default to the **strict path** (brand-new repo)
  in the main guide above — it is the safest interpretation.

> This appendix does not override the official rules or the organizers'
> decisions. **When uncertain, ask and disclose honestly.**

---

> **Claude note:** This guide is **documentation-only**. It does not modify
> `app.py` or any working application code, and contains **no real secrets** —
> only placeholders.
