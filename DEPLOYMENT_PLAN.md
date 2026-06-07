# Benefits Navigator V2 — Databricks App Deployment Plan

A practical, beginner-friendly guide to deploying this Streamlit app as a
**Databricks App**, wired to Unity Catalog (trusted data), Lakebase Postgres
(live app state), and the Claude/Anthropic API (agent reasoning).

---

## 1. How this Streamlit app is deployed as a Databricks App

**Databricks Apps** run a web app (Streamlit, Dash, Flask, etc.) directly inside
your Databricks workspace, on Databricks-managed compute. You give it your code,
a list of Python dependencies, and a start command — Databricks builds the
environment and serves the app at a private workspace URL.

At a high level:

1. You upload this project's files into a folder in the Databricks workspace
   (or sync them from Git via a Repo).
2. Databricks reads `requirements.txt` and installs the dependencies.
3. Databricks runs the start command, which launches Streamlit:
   ```
   streamlit run app.py
   ```
4. Secrets (API keys, DB passwords) are injected as **environment variables** —
   they are never committed to the repo.
5. Databricks serves the app behind workspace authentication (only authorized
   users can open it).

A minimal **`app.yaml`** (the Databricks Apps config file) describes the start
command and which env vars/secrets to expose. Example:

```yaml
command: ["streamlit", "run", "app.py", "--server.port", "8000", "--server.address", "0.0.0.0"]

env:
  - name: ANTHROPIC_API_KEY
    valueFrom: anthropic-api-key          # references a Databricks secret
  - name: DATABRICKS_SERVER_HOSTNAME
    valueFrom: databricks-server-hostname
  - name: DATABRICKS_HTTP_PATH
    valueFrom: databricks-http-path
  - name: DATABRICKS_TOKEN
    valueFrom: databricks-token
  - name: LAKEBASE_HOST
    valueFrom: lakebase-host
  - name: LAKEBASE_PORT
    valueFrom: lakebase-port
  - name: LAKEBASE_DATABASE
    valueFrom: lakebase-database
  - name: LAKEBASE_USER
    valueFrom: lakebase-user
  - name: LAKEBASE_PASSWORD
    valueFrom: lakebase-password
```

> Note: `app.yaml` is **not yet in this repo**. Create it at the project root
> when you deploy (this plan keeps `app.py` and existing files unchanged).

---

## 2. Required project files

All of these live at the project root unless noted:

| File | Purpose |
|------|---------|
| `app.py` | Streamlit UI + the 3-stage agent flow. **Entry point.** |
| `agent.py` | Claude/Anthropic reasoning (profile parsing, questions, action plan). |
| `benefits_rules.py` | Rules engine that screens programs against a family profile. |
| `databricks_client.py` | Reads the trusted `benefit_programs` table from Unity Catalog. |
| `lakebase_client.py` | Writes live app state (intake, matches, plans, feedback) to Lakebase. |
| `requirements.txt` | Python dependencies installed by the Databricks App. |
| `social_impact_analytics.sql` | Analytics queries to run against Lakebase (impact reporting). |
| `sample_data/programs.json` | **Local fallback** benefits data if Databricks is unavailable. |

Plus, **to be added at deploy time**: `app.yaml` (start command + env wiring).

`requirements.txt` already contains:

```
streamlit
anthropic
databricks-sql-connector
psycopg[binary]
python-dotenv
```

---

## 3. Required environment variables / secrets

Store all of these as **Databricks secrets** and expose them to the app as
environment variables (see `app.yaml` above). Never hard-code them in the repo.

| Variable | Used by | What it is |
|----------|---------|------------|
| `ANTHROPIC_API_KEY` | `agent.py` | Claude API key for agent reasoning. |
| `DATABRICKS_SERVER_HOSTNAME` | `databricks_client.py` | SQL Warehouse hostname. |
| `DATABRICKS_HTTP_PATH` | `databricks_client.py` | SQL Warehouse HTTP path. |
| `DATABRICKS_TOKEN` | `databricks_client.py` | Token to query Unity Catalog. |
| `LAKEBASE_HOST` | `lakebase_client.py` | Lakebase Postgres host. |
| `LAKEBASE_PORT` | `lakebase_client.py` | Postgres port (e.g. `5432`). |
| `LAKEBASE_DATABASE` | `lakebase_client.py` | Database name. |
| `LAKEBASE_USER` | `lakebase_client.py` | Postgres username. |
| `LAKEBASE_PASSWORD` | `lakebase_client.py` | Postgres password (secret). |

**Creating a secret (CLI example):**

```bash
databricks secrets create-scope benefits-navigator
databricks secrets put-secret benefits-navigator anthropic-api-key
# ...repeat for each value...
```

> The app code reads every one of these via `os.environ`. If a value is missing,
> the app logs only the **variable name** (never the value) and degrades safely.

---

## 4. How the Databricks App connects to each system

### a) Unity Catalog — trusted `benefit_programs` table (READ)
- **Module:** `databricks_client.py` → `get_benefit_programs_from_databricks()`
- **How:** uses `databricks-sql-connector` to connect to a **SQL Warehouse**
  with `DATABRICKS_SERVER_HOSTNAME` + `DATABRICKS_HTTP_PATH` + `DATABRICKS_TOKEN`.
- **Query:** selects active rows (incl. rule columns) from
  `benefits_navigator.trusted.benefit_programs`.
- **Role:** this is the **trusted, source-labeled reference data** about benefit
  programs. `app.py` loads it first and adapts it into the rules-engine schema.

### b) Lakebase Postgres — app-state tables (WRITE)
- **Module:** `lakebase_client.py` → `write_family_intake_event`,
  `write_program_matches`, `write_action_plan`, `write_user_feedback`.
- **Driver:** `psycopg` (v3).
- **Tables:** `family_intake_events`, `program_matches`, `action_plans`,
  `user_feedback` (keyed/correlated by `intake_id`).
- **Role:** the **transactional app-state layer** — every user journey is
  recorded here so it can power `social_impact_analytics.sql`.

`lakebase_client.py` supports **two authentication modes** and picks one
automatically at runtime:

#### Mode A — Local / manual (development)
- **When:** chosen whenever `LAKEBASE_PASSWORD` is set.
- **Uses:** `LAKEBASE_HOST`, `LAKEBASE_PORT`, `LAKEBASE_DATABASE`,
  `LAKEBASE_USER`, `LAKEBASE_PASSWORD`.
- **How:** connects directly with those static credentials. Simple, good for
  running on your laptop.
- **⚠️ Known issue:** a static password can fail with
  **`External authorization failed`** if it has expired/rotated or your IP isn't
  allow-listed. That's expected locally — use Mode B in production.

#### Mode B — Databricks App / managed credentials (production)
- **When:** chosen when there is **no** `LAKEBASE_PASSWORD` and the Databricks
  App database resource is present as `LAKEBASE_RESOURCE`.
- **Wiring (`app.yaml`):**
  ```yaml
  - name: LAKEBASE_RESOURCE
    valueFrom: lakebase-db        # the attached Lakebase database resource
  ```
  Inside Databricks Apps, `valueFrom: lakebase-db` resolves to the Lakebase
  database **instance name** (`databricks_postgres`, branch `production`).
- **How:** the app authenticates as its **service principal** and uses the
  Databricks SDK to (1) look up the instance host and (2) mint a **short-lived
  OAuth token** used as the Postgres password. A fresh token is generated on
  every connection, so credentials **rotate automatically** — no static
  password is ever stored, which is what fixes `External authorization failed`.
- **Optional overrides:** `LAKEBASE_DATABASE`, `LAKEBASE_PORT`, `LAKEBASE_HOST`,
  and `LAKEBASE_USER` may still be set to override the auto-derived values; if
  omitted, sensible defaults (`databricks_postgres` / `5432`) and the instance's
  DNS / current identity are used.

> Mode selection in one line: **`LAKEBASE_PASSWORD` set → Mode A; else
> `LAKEBASE_RESOURCE` set → Mode B; else writes are skipped gracefully.**

#### Service principal needs Lakebase / Postgres privileges
In Mode B the OAuth token authenticates as the **Databricks App service
principal**, so that principal must exist as a Postgres role in Lakebase **and**
be granted privileges on the app-state tables — otherwise connections succeed
but `INSERT`s are rejected.

- **App service principal id:**
  ```
  DATABRICKS_CLIENT_ID=8455768b-1140-43a8-89b3-04ec91d565ad
  ```
- **One-time grant (run as a Lakebase Postgres admin):**
  ```sql
  -- Create a role for the App service principal (Databricks may auto-provision
  -- this; create it explicitly if it does not already exist).
  CREATE ROLE "8455768b-1140-43a8-89b3-04ec91d565ad" LOGIN;

  -- Allow it to use the schema and write to the four app-state tables.
  GRANT USAGE ON SCHEMA public TO "8455768b-1140-43a8-89b3-04ec91d565ad";
  GRANT SELECT, INSERT ON
      family_intake_events,
      program_matches,
      action_plans,
      user_feedback
  TO "8455768b-1140-43a8-89b3-04ec91d565ad";
  ```
- After granting, redeploy/restart the App and run one journey to confirm rows
  land in the tables.

See §7 for what happens if Lakebase auth still fails (the app degrades safely).

### c) Claude / Anthropic API — agent reasoning
- **Module:** `agent.py` (`client = anthropic.Anthropic(api_key=...)`,
  model `claude-sonnet-4-5-20250929`).
- **How:** reads `ANTHROPIC_API_KEY` from the environment; calls Claude to parse
  the family's free text, generate clarifying questions, and produce the plan.
- **Role:** the **intelligence layer** that turns plain-language situations into
  a structured profile and a personalized action plan.

**Data flow in one line:**
`User text → Claude (agent.py) → profile → rules engine screens it against Unity
Catalog data (databricks_client.py) → action plan → written to Lakebase
(lakebase_client.py) → analytics (social_impact_analytics.sql).`

---

## 5. Deployment checklist

- [ ] Create a SQL Warehouse and confirm the
      `benefits_navigator.trusted.benefit_programs` table exists and has rows.
- [ ] Create the Lakebase Postgres tables (`family_intake_events`,
      `program_matches`, `action_plans`, `user_feedback`).
- [ ] For Lakebase auth, prefer **Databricks-managed credentials / OAuth token
      rotation** (Mode B, `LAKEBASE_RESOURCE` → `valueFrom: lakebase-db`) over a
      static `LAKEBASE_PASSWORD` (avoids the "External authorization failed"
      error in production). See §4b.
- [ ] Grant the App **service principal**
      (`DATABRICKS_CLIENT_ID=8455768b-1140-43a8-89b3-04ec91d565ad`) Postgres
      privileges (`USAGE` + `SELECT, INSERT`) on the four Lakebase app-state
      tables — see the SQL grant in §4b.
- [ ] Attach the **Lakebase database resource** (`lakebase-db`) to the App and
      confirm `app.yaml` exposes it as `LAKEBASE_RESOURCE`.
- [ ] Create a Databricks **secret scope** and add the remaining secrets
      (`ANTHROPIC_API_KEY`, `DATABRICKS_TOKEN`).
- [ ] Add an `app.yaml` at the project root (start command + env wiring).
- [ ] Upload the project to the workspace (or connect a Git Repo).
- [ ] Verify `requirements.txt` is present and complete.
- [ ] Create the Databricks App and point it at this folder.
- [ ] Deploy; watch the build logs for dependency-install errors.
- [ ] Open the app URL and confirm it loads (no crash on the intake screen).
- [ ] Confirm the data-source caption shows **"Using trusted Databricks
      benefits data"** (not the local fallback).
- [ ] Run one full journey and confirm rows appear in the Lakebase tables.

---

## 6. Hackathon demo checklist

- [ ] App opens fast and shows the NJ Benefits Navigator hero screen.
- [ ] Caption reads **"Using trusted Databricks benefits data"** (proves the
      Unity Catalog connection is live).
- [ ] Paste a sample story (e.g. *"single mom, two kids ages 3 and 7,
      ~$1,800/month, no health insurance, need childcare"*).
- [ ] Claude generates clarifying questions → answer or skip.
- [ ] Action plan renders with matched programs and "how to apply" links.
- [ ] Submit a 1–5 rating + comment → "Thanks for your feedback!"
- [ ] In a SQL editor, run `social_impact_analytics.sql` queries 1–8 to show
      the live impact dashboard (intakes, matches, top categories, avg rating,
      recent journeys).
- [ ] Backup plan: have the local-fallback flow ready to show resilience (see §7).

---

## 7. Rollback / fallback notes

The app is designed to **never hard-fail** during a demo:

- **If the Databricks/Unity Catalog read fails or returns no rows:**
  `app.py` automatically falls back to `sample_data/programs.json` and shows
  **"Using local fallback benefits data."** The full flow still works — only the
  data source changes. (Implemented in `load_benefit_programs()`.)

- **If a Lakebase write fails:**
  The action plan is **still generated and shown**. The app displays a friendly
  **"Plan generated successfully, but saving app state failed."** and continues.
  Feedback save failures show **"Feedback could not be saved right now."** No
  exception reaches the user. (Writers in `lakebase_client.py` return
  `None`/`False`; `app.py` guards with try/except.)

- **If the Anthropic API is unavailable:**
  This is the one hard dependency for reasoning. Mitigations: confirm
  `ANTHROPIC_API_KEY` is valid before the demo, and keep a pre-recorded run or
  screenshots as a backup.

- **Lakebase "External authorization failed" (local vs. deployed):**
  Locally, Lakebase auth often fails with **`External authorization failed`**
  because a static `LAKEBASE_PASSWORD` has expired/rotated or the host isn't
  reachable from your machine. Thanks to the graceful write-back above, the app
  **keeps working** — plans still generate; only the save is skipped (with the
  friendly warning). For the **deployed Databricks App**, fix this at the source
  by using **Databricks-managed credentials** or **OAuth token rotation** for
  Lakebase rather than a long-lived password, so writes succeed reliably in
  production. During a hackathon demo, it is fine to run with Lakebase writes
  disabled and still show the full user journey.

- **Fast rollback:** Databricks Apps keep previous deployments. If a new deploy
  breaks, redeploy the last known-good version (or revert the Git commit and
  redeploy). Because secrets live outside the code, rolling back code does not
  require re-entering credentials.

---

## 8. Quick reference

| Concern | Where it lives |
|---------|----------------|
| Start command | `app.yaml` → `streamlit run app.py` |
| Dependencies | `requirements.txt` |
| Trusted data (read) | Unity Catalog via `databricks_client.py` |
| App state (write) | Lakebase via `lakebase_client.py` |
| Reasoning | Claude via `agent.py` |
| Local safety net | `sample_data/programs.json` |
| Impact reporting | `social_impact_analytics.sql` |

Keep secrets in Databricks secret scopes, deploy, run one journey end-to-end,
and you're hackathon-ready. 🚀
