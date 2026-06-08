# Manual Rule-Safe Hackathon Setup Guide — No AI Assistance — Benefits Navigator for Families

A **self-contained**, rule-safe guide to **build and demo** the Benefits Navigator
app **manually** in a new hackathon Databricks environment — using only your
laptop and the Databricks / Lakebase UIs, **without** Claude, ChatGPT, or any AI
coding assistant during the event.

> **No real secrets in this document.** Everything sensitive is a `<PLACEHOLDER>`.
> Never paste real API keys, tokens, passwords, or private hostnames into GitHub.
>
> **Not legal advice.** This reflects the *safest interpretation* of the official
> rules. When uncertain, **confirm with the organizers.**

---

## 0. When to Use This Guide

- **Use this guide if AI coding help is NOT permitted** by the official rules.
- It can be used as a **checklist / reference only** if the rules allow referring
  to your own notes/templates — **confirm with organizers** if unsure.
- **Do not use Claude / ChatGPT during the Project Period if AI assistance is
  prohibited.**
- **Build the actual submission manually during the Project Period**
  (**Mon, June 15, 2026 8:00 AM PT → Tue, June 16, 2026 2:30 PM PT**).

---

## 1. Official Rule Checklist (read first)

These come from the official hackathon rules — plan your build around them:

- [ ] **Start a new repo during the Project Period** (do not submit an old repo as-is).
- [ ] Build a **Databricks App on Lakebase**.
- [ ] Use **at least one additional Databricks tool** (Unity Catalog, Databricks SQL).
- [ ] **Public** GitHub repo.
- [ ] **Open-source license** in the repo.
- [ ] **Demonstration video ≤ 3 minutes** (public).
- [ ] **Synthetic data only** — no real personal information.
- [ ] **No secrets** in GitHub.
- [ ] **No proprietary / employer / confidential code or data.** Original work,
      owned by your team, no third-party IP violations (open-source deps are fine
      if their licenses are followed).
- [ ] Repo history **shows the work was done during the Project Period**.

When unsure about prebuilt code, AI assistance, or external APIs (e.g., Anthropic
or OpenAI), **ask the organizers and get it in writing.**

---

## 2. What You Are Building

**Benefits Navigator** helps New Jersey families find benefits they likely
qualify for, starting from a plain-language description. Components:

- **Streamlit app** — friendly intake form, program cards, feedback widget.
- **Claude/LLM agent** *(only if an external API is permitted)* — extracts a
  structured profile, asks adaptive follow-up questions, writes the action plan.
- **Rules engine** — deterministic, explainable eligibility screening.
- **Databricks Unity Catalog trusted data** — source-labeled NJ programs
  (`benefits_navigator.trusted.benefit_programs`) read via a SQL Warehouse.
- **Lakebase Postgres app state** — `family_intake_events`, `program_matches`,
  `action_plans`, `user_feedback`.
- **Feedback and analytics** — ratings + SQL views for social-impact reporting.

> If the external LLM API is **not** permitted, the data/rules/state pieces still
> work; only the agent reasoning step is unavailable. Confirm with organizers.

---

## 3. Prerequisites Checklist

- [ ] **Git** installed (`git --version`)
- [ ] **Python** installed (`python --version`, 3.10+ recommended)
- [ ] **VS Code** (or any editor)
- [ ] Access to your **public GitHub repo**
- [ ] A **Databricks workspace** (the hackathon environment)
- [ ] Permission to **create/start a SQL Warehouse**
- [ ] Permission to **create a catalog / schema / table** (Unity Catalog)
- [ ] Permission to **create a Databricks App**
- [ ] Permission to **create a Lakebase database**
- [ ] **Anthropic API key** *(only if the rules allow an external LLM API)*
- [ ] Ability to **create Databricks secrets / app resources**

---

## 4. Create a Brand-New Repo During the Project Period (default)

> ⚠️ **"New Projects Only."** The rule-safe default is to **create a brand-new
> public repo during the Project Period** and build manually in-window. **Do not
> paste from your old repo** into the submission **unless organizers explicitly
> allow reuse** (and even then, disclose it — see the warning below).

At/after **June 15, 2026 8:00 AM PT**, create a new **public** repo:

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

Add an **open-source license** (`LICENSE`, e.g., MIT or Apache-2.0).

> ⚠️ **Do not paste from your old repo unless approved.** Your prior working repo
> may be used only as **private practice/reference before the event**. Copying it
> into the final submission is **not** assumed to be allowed. If organizers
> confirm reuse is permitted, **disclose in your README** what existed before vs.
> what was built during the Project Period, and still commit your meaningful work
> in-window.

### 4a. Manual rebuild checklist (build each file by hand)

- [ ] Create the **blank repo** (above) + `LICENSE`.
- [ ] Manually create the **project files**: `app.py`, `agent.py`,
      `benefits_rules.py`, `databricks_client.py`, `lakebase_client.py`.
- [ ] Manually create **`requirements.txt`** and **`app.yaml`** and `.gitignore`.
- [ ] Manually create the **SQL files** (trusted table, Lakebase tables, grants,
      analytics).
- [ ] Manually create **`sample_data/programs.json`** (synthetic, 8 programs).
- [ ] **Run local tests** (rules engine, JSON validity, app launch with fallback).
- [ ] Manually create **Databricks tables, Lakebase tables, app resources, and
      service-principal grants** via the UIs / SQL editors.
- [ ] **Manually deploy and validate** the Databricks App.

> The code blocks later in this guide are **allowed reference / template
> material** to type or adapt **by hand**. If you are unsure whether using a
> template counts as permitted, **confirm with the organizers** first.

---

## 5. Local Setup (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

> If `.env.example` does not exist in the repo, create `.env` by hand using the
> keys below. **Never commit `.env`** (confirm `.gitignore` contains `.env`).

Fill in `.env` (local/dev only):

| Variable | What to put |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic key (**only if the LLM API is permitted**). Used by `agent.py`. |
| `DATABRICKS_SERVER_HOSTNAME` | Workspace host, e.g. `dbc-xxxx.cloud.databricks.com` (no `https://`). |
| `DATABRICKS_HTTP_PATH` | SQL Warehouse HTTP path, e.g. `/sql/1.0/warehouses/<WAREHOUSE_ID>`. |
| `DATABRICKS_TOKEN` | A personal access token (**local/dev only** — never commit). |

> **Do not** add a Lakebase password unless you specifically need to test
> Lakebase **writes locally**. The deployed app uses managed credentials instead.

Run locally:

```powershell
streamlit run app.py
```

> The app falls back to `sample_data/programs.json` if Databricks is unreachable,
> and still generates a plan if Lakebase writes fail — so local dev works even
> before the cloud pieces exist.

---

## 6. Databricks SQL Warehouse Setup (UI)

1. Open **Databricks** (the hackathon workspace).
2. Go to **SQL → SQL Warehouses**.
3. **Create** a new warehouse (small/serverless is fine) or **Start** an existing
   one.
4. Open the warehouse → **Connection details**:
   - **Copy the HTTP path** → use for `DATABRICKS_HTTP_PATH`.
   - **Copy the Server hostname** → use for `DATABRICKS_SERVER_HOSTNAME`.
5. In the **SQL Editor**, test connectivity:
   ```sql
   SELECT 1;
   ```
   You should get a single row with `1`.

---

## 7. Unity Catalog Trusted Data Setup (SQL Editor)

Run this in the Databricks **SQL Editor**. It creates the catalog/schema/table
(including the **rule columns** the app reads) and loads **8 curated NJ
programs**.

```sql
CREATE CATALOG IF NOT EXISTS benefits_navigator;
CREATE SCHEMA  IF NOT EXISTS benefits_navigator.trusted;

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
    -- Rule columns consumed by the app's rules engine:
    rule_key                STRING,
    income_limit_pct_fpl    INT,
    accepts_undocumented    BOOLEAN,
    min_child_age           INT,
    max_child_age           INT,
    requires_work_or_school BOOLEAN
);

-- Idempotent refresh for demos
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
-- Expect 8
SELECT COUNT(*) AS total_programs
FROM benefits_navigator.trusted.benefit_programs;

-- By category
SELECT category, COUNT(*) AS n
FROM benefits_navigator.trusted.benefit_programs
GROUP BY category
ORDER BY n DESC;

-- All programs
SELECT program_id, program_name, category, rule_key,
       income_limit_pct_fpl, accepts_undocumented,
       min_child_age, max_child_age, requires_work_or_school
FROM benefits_navigator.trusted.benefit_programs
ORDER BY category, program_name;
```

---

## 8. Lakebase Setup (UI + SQL Editor)

**UI steps:**
1. Create a **Lakebase project** (e.g., `benefits-navigator-lakebase`).
2. Create / use the **`production`** branch.
3. Use the **`databricks_postgres`** database.
4. Open the Lakebase **SQL Editor** for that database.

**Create the four app-state tables** (compatible with the current app; `event_ts`
defaults to `now()`):

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

**List tables (validation):**

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
-- expect: action_plans, family_intake_events, program_matches, user_feedback
```

---

## 9. App Resources and Secrets (UI)

1. **Create a secret scope** (or use Databricks App **resources**).
2. **Add the Anthropic API key secret** (only if the LLM API is permitted) →
   surfaced as `ANTHROPIC_API_KEY`.
3. **Add the Databricks token secret** → only if the SQL connector still needs a
   PAT (`DATABRICKS_TOKEN`).
4. **Attach the SQL Warehouse resource** to the app.
5. **Attach the Lakebase database resource** (injects the Lakebase endpoint and,
   on Autoscaling, the `PG*` connection env vars).
6. **Note the app's service principal / client ID** — you'll need it for Lakebase
   grants (§12). Record it as `<APP_CLIENT_ID_PREFIX>` / `<APP_SERVICE_PRINCIPAL_ROLE>`.

> Secrets live **only** in Databricks — never in GitHub.

---

## 10. app.yaml Checklist

Expected shape (placeholders only — no secrets inline):

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

> Notes:
> - Non-secret values (`DATABRICKS_SERVER_HOSTNAME`, `DATABRICKS_HTTP_PATH`) are
>   inline; secrets/resources use `valueFrom`.
> - The Lakebase resource key (here `ENDPOINT_NAME`) maps to your app's Lakebase
>   variable. If your build uses `LAKEBASE_RESOURCE`, name it accordingly and
>   keep `LAKEBASE_DATABASE` / `LAKEBASE_PORT` set; the `PG*` vars are injected by
>   the Lakebase resource.

---

## 11. Deploy Manually (UI)

1. **Commit changes:**
   ```bash
   git add .
   git commit -m "Configure for hackathon Databricks workspace"
   ```
2. **Push to GitHub:**
   ```bash
   git push origin main
   ```
3. In Databricks, go to **Compute → Apps** (or the **Apps** section).
4. **Create app.**
5. **Connect the GitHub source** (`<NEW_HACKATHON_REPO_URL>` or your public repo).
6. **Branch:** `main`.
7. **Source path:** leave **blank** (this repo's `app.py` is at the root); set a
   subfolder only if your app lives in one.
8. **Deploy.**
9. **Watch the deployment logs** — confirm dependencies install, the data-source
   selection is logged, and (after a journey) you see connection success + write
   commits. Logs show only safe status, never secrets.

---

## 12. Grant Lakebase Table Permissions Manually

**Why:** the deployed app writes as its **service principal** (machine identity),
not as your human user. Without explicit grants you'll get `permission denied`.

**Find the role** (Lakebase SQL Editor on `databricks_postgres`):

```sql
SELECT rolname
FROM pg_roles
WHERE rolname ILIKE '%<APP_CLIENT_ID_PREFIX>%'
   OR rolname ILIKE '%benefits%'
   OR rolname ILIKE '%app%';
```

**Grant** (replace `<APP_SERVICE_PRINCIPAL_ROLE>` with the exact `rolname` found):

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

Then **redeploy/restart** the app and run a journey to confirm writes succeed.

---

## 13. End-to-End Test

**Main scenario (synthetic):**

> *"I am a single mom in New Jersey with two kids ages 3 and 7. I work part-time
> and make about $1,800 per month. I do not have health insurance right now. I
> need help with food, childcare, and paying bills."*

**Follow-up answers:**
- Middlesex County
- My 7-year-old is in school. My 3-year-old needs daycare or preschool.
- No, I am not currently receiving any government assistance or benefits.

**Expected:**
- The **"Using trusted Databricks benefits data"** caption appears.
- The agent generates **follow-up questions**.
- Matched programs are surfaced from the **8-program** catalog (e.g., SNAP, WIC,
  NJ FamilyCare, CHIP, CCDF, Preschool, plus cash/energy help).
- A **personalized action plan** is generated.
- Submitting the feedback widget shows **"Thanks for your feedback!"** (feedback
  saved).

---

## 14. Lakebase Validation Queries

```sql
SELECT COUNT(*) FROM family_intake_events;
SELECT COUNT(*) FROM program_matches;
SELECT COUNT(*) FROM action_plans;
SELECT COUNT(*) FROM user_feedback;
```

```sql
SELECT * FROM family_intake_events ORDER BY event_ts DESC;
SELECT * FROM action_plans         ORDER BY event_ts DESC;
SELECT * FROM user_feedback         ORDER BY event_ts DESC;
```

---

## 15. Demo Analytics Views

**Journey summary view** (one row per journey, stitched by `intake_id`):

```sql
CREATE OR REPLACE VIEW demo_journey_summary AS
SELECT
    fie.intake_id,
    fie.event_ts                AS intake_time,
    fie.raw_user_text,
    ap.action_plan_text,
    ap.generated_by_model,
    COUNT(pm.match_id)          AS programs_matched,
    uf.rating                   AS feedback_rating,
    uf.feedback_text
FROM family_intake_events fie
LEFT JOIN action_plans    ap ON ap.intake_id = fie.intake_id
LEFT JOIN program_matches pm ON pm.intake_id = fie.intake_id
LEFT JOIN user_feedback   uf ON uf.intake_id = fie.intake_id
GROUP BY fie.intake_id, fie.event_ts, fie.raw_user_text,
         ap.action_plan_text, ap.generated_by_model, uf.rating, uf.feedback_text
ORDER BY fie.event_ts DESC;
```

**Program demand** (most recommended programs):

```sql
SELECT program_id, program_name,
       COUNT(*)                 AS times_recommended,
       COUNT(DISTINCT intake_id) AS families_reached
FROM program_matches
GROUP BY program_id, program_name
ORDER BY times_recommended DESC;
```

**Feedback average**:

```sql
SELECT ROUND(AVG(rating), 2) AS average_rating,
       COUNT(*)              AS ratings_count
FROM user_feedback
WHERE rating IS NOT NULL;
```

---

## 16. State Retention Proof

1. **Run a full app journey** (scenario in §13).
2. **Check counts** (§14) — note the numbers.
3. **Redeploy / restart** the Databricks App.
4. **Check counts again** — they are **unchanged or higher**, never reset.
5. **Explain:** Lakebase is a managed Postgres store **independent of the app
   process**. Restarting or redeploying the app does **not** wipe data — the
   transactional state persists, which is exactly why app state lives in Lakebase
   and not in app memory.

---

## 17. Troubleshooting FAQ

| Symptom | Likely cause | Fix |
|---|---|---|
| **App deploy fails** | Build/config error | Read deploy logs; verify `app.yaml`, `requirements.txt`, and branch/source path |
| **`pip install` / requirements install fails** | Version conflict or missing wheel | Recreate venv; ensure Python 3.10+; check the failing package line |
| **Databricks SQL connector missing** | `databricks-sql-connector` not installed | Confirm it's in `requirements.txt`; reinstall |
| **SQL warehouse endpoint not found** | Wrong/expired `DATABRICKS_HTTP_PATH` or stopped warehouse | Recopy HTTP path; start the warehouse |
| **`benefit_programs` table not found** | Trusted table not created here | Re-run §7 catalog/schema/table + insert |
| **App uses fallback JSON** | Databricks read failed and fell back | Check logs; verify host/path/token/warehouse + table; caption reads "local fallback" |
| **Anthropic key missing** | `ANTHROPIC_API_KEY` unset | Add secret + `valueFrom`; confirm the agent step (only if LLM API permitted) |
| **Claude API fails** | Key invalid / rate limit / API not allowed | Verify key; check quota; confirm external API is permitted by rules |
| **Lakebase `PG*` vars missing** | Lakebase resource not attached | Attach the Lakebase database resource; confirm `PGHOST/PGUSER/PGDATABASE` injected |
| **Lakebase token generation fails** | SDK/auth issue | Ensure `databricks-sdk` is recent (`>=0.89.0`); check explicit OAuth init; app falls back gracefully |
| **Service principal `permission denied`** | Missing grants | Run §12 GRANTs for the role |
| **Role not found** | Wrong role name | Re-run the `pg_roles` lookup; use the exact `rolname` |
| **Feedback not saving** | Intake write failed (no `intake_id`) or grants missing | Confirm intake wrote; verify grants; UI shows "Feedback could not be saved right now" |
| **Records not retained** | Looking at wrong DB/branch, or app stored in memory | Confirm `production` branch + `databricks_postgres`; data persists across restarts |
| **Old code deployed** | App on a stale commit | Push to `main`, redeploy, confirm the commit hash in the deploy view |
| **GitHub branch mismatch** | App points to a different branch | Set the app source branch to `main` |
| **Wrong source path** | Subfolder path set incorrectly | Leave source path blank (app.py is at repo root) |
| **App works locally but not deployed** | Local uses `.env`; deployed uses resources/secrets | Verify each `app.yaml` env entry resolves; check resource attachment + grants |
| **Privacy concern with raw text** | Storing free-text input | Use synthetic data only; raw text is never logged; for production add consent/redaction/retention |

---

## 18. Official Submission Video (≤ 3 minutes)

> The official rules require the demonstration video to be **no longer than 3
> minutes** and **public**. Use this exact structure to stay under 3:00.

| Time | Segment | What to say / show |
|---|---|---|
| **0:00–0:20** | **Problem** | "Millions of families miss benefits they qualify for — the system is confusing and full of acronyms. A working parent doesn't have time to decode a dozen programs." |
| **0:20–0:45** | **Solution / architecture** | "Benefits Navigator: a Databricks App on Lakebase. A family describes their situation in plain language; an agent + an explainable rules engine match them against governed NJ program data; a personalized plan is generated; and every journey is saved in Lakebase." |
| **0:45–1:50** | **Live app demo** | Run the §13 scenario. Show the "trusted Databricks data" caption, the follow-up questions, the action plan, and the *reasons* on each match. |
| **1:50–2:30** | **Lakebase state + analytics** | Run the §14 counts and a §15 analytics query — show journeys persisting and rolling up into community insight. |
| **2:30–3:00** | **Impact closing** | "Agentic AI, grounded in governed trusted data, with durable Lakebase state and social-impact analytics — built to scale additively. Behind every number is a family that found help faster." |

> Optionally prepare a **60-second pitch** and a **5-minute backup** for live
> Q&A/judging **if the organizers allow it** — but the **≤ 3-minute video is the
> version that counts** for submission.

---

> **Note:** This guide is **documentation-only**. It does not modify `app.py` or
> any working application code, and contains **no real secrets** — only
> placeholders.
