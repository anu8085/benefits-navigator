# Local SQLite Fallback — Benefits Navigator

## Why this exists

Benefits Navigator persists its live app-state (intake events, program matches,
action plans, feedback) to **Lakebase Postgres**. During **local laptop testing**
— or if a **Lakebase project is deleted/unavailable** — those writes fail and the
user would otherwise just see *"saving app state failed."*

To keep demos resilient, the app now has a **local SQLite fallback**
(`local_state_client.py`, standard-library `sqlite3`, **no new dependency**). If a
Lakebase write fails, the **same records** are written into a local SQLite
database so the journey is never lost.

## When it is used

The write path is **Lakebase-first**:

1. The app tries **Lakebase** (unchanged primary behavior).
2. Only if the Lakebase write fails/returns nothing does it write to **local
   SQLite** at `.local_state/benefits_navigator_state.db`.
3. The session's storage mode is tracked in `st.session_state["state_storage_mode"]`:
   `"lakebase"`, `"sqlite_fallback"`, or `"none"`.

UI messages reflect the outcome:

| Outcome | Message |
|---|---|
| Lakebase saved | "Plan saved to Lakebase app-state tables." |
| Lakebase failed, SQLite saved | "Plan generated successfully. Lakebase is unavailable, so this session was saved locally in SQLite for demo fallback." |
| Both failed | "Plan generated successfully, but app-state saving failed." |
| Feedback (Lakebase) | "Thanks for your feedback! Saved to Lakebase." |
| Feedback (SQLite) | "Thanks for your feedback! Saved locally in SQLite for demo fallback." |

## Why Lakebase is still the primary architecture

Lakebase remains the real transactional app-state layer for the hackathon: it is
durable, governed, queryable for analytics (`social_impact_analytics.sql`), and
authenticated via the App's service principal. **SQLite is a fallback for
resilience, not a replacement.** The Lakebase-first behavior, the Unity Catalog
trusted-data read, and the deployed Databricks App flow are **unchanged**.

## ⚠️ Durability warning (deployed Databricks App)

On a **laptop**, the SQLite file is durable across runs. Inside a **deployed
Databricks App**, local disk is **ephemeral** — SQLite data does **not** survive
app restarts/redeploys. There, SQLite is only an **emergency fallback**, and the
logs say so:

> `Local SQLite fallback is being used inside what looks like a DEPLOYED
> Databricks App. This storage is EPHEMERAL and NOT durable across app
> restarts/redeploys ...`

For durable state in production, **fix Lakebase** (resource attachment +
service-principal grants) — do not rely on SQLite.

## Inspect the local SQLite database

**Row counts (PowerShell):**
```powershell
python - <<'PY'
import sqlite3
from pathlib import Path

db = Path(".local_state/benefits_navigator_state.db")
print("DB:", db.resolve())
conn = sqlite3.connect(db)
for table in ["family_intake_events", "program_matches", "action_plans", "user_feedback"]:
    print(table, conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
conn.close()
PY
```

**Latest intakes (PowerShell):**
```powershell
python - <<'PY'
import sqlite3
conn = sqlite3.connect(".local_state/benefits_navigator_state.db")
for row in conn.execute("SELECT intake_id, event_ts, substr(raw_user_text,1,80) FROM family_intake_events ORDER BY event_ts DESC LIMIT 5"):
    print(row)
conn.close()
PY
```

You can also enable an in-app debug panel: set `SHOW_LOCAL_STATE_DEBUG=true`
before launching, and the results page shows a "Local SQLite fallback state
counts" expander (off by default so the deployed app stays clean).

## Clean the local fallback database

```powershell
Remove-Item -Recurse -Force .local_state
```

The `.local_state/` folder and `*.db` / `*.sqlite` / `*.sqlite3` files are
git-ignored, so they are never committed.

## Schema (SQLite)

Each table carries a `storage_mode` column (set to `sqlite_fallback`) and a
`*_json` text column for JSON fields:

- `family_intake_events(intake_id, event_ts, raw_user_text, profile_json, storage_mode)`
- `program_matches(match_id, intake_id, event_ts, program_id, program_name, category, match_reasons_json, storage_mode)`
- `action_plans(plan_id, intake_id, event_ts, action_plan_text, generated_by_model, storage_mode)`
- `user_feedback(feedback_id, intake_id, event_ts, rating, feedback_text, storage_mode)`

Ids use `uuid.uuid4().hex`; timestamps use UTC ISO-8601.
