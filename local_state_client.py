"""
local_state_client.py

LOCAL SQLite fallback for Benefits Navigator app-state.

Lakebase (Postgres) remains the PRIMARY transactional app-state store. This
module is a *fallback only*: when a Lakebase write fails (e.g. local laptop
testing with no Lakebase configured, or the Lakebase project was deleted), the
app persists the same records into a local SQLite database so a demo journey is
never lost and the user never sees a dead-end error.

Durability note:
  * On a laptop, the SQLite file (.local_state/benefits_navigator_state.db) is
    durable across runs.
  * Inside a DEPLOYED Databricks App, local disk is EPHEMERAL - SQLite data does
    NOT survive app restarts/redeploys. In that environment SQLite is only an
    emergency fallback and the logs say so clearly.

This module mirrors the public write-function names/signatures of
lakebase_client.py so it can be used as a drop-in fallback. It uses only the
Python standard library (sqlite3) - no new dependency. It NEVER logs secrets,
tokens, passwords, or raw user text.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Local fallback storage location (kept out of git via .gitignore).
_LOCAL_DIR = Path(".local_state")
_DB_PATH = _LOCAL_DIR / "benefits_navigator_state.db"

# Marker stored on every row so it's clear the record came from the SQLite
# fallback path (not Lakebase).
_STORAGE_MODE = "sqlite_fallback"


def get_db_path() -> str:
    """Return the SQLite database path as a string."""
    return str(_DB_PATH)


def _now_iso() -> str:
    """UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    """Generate a new id (uuid4 hex)."""
    return uuid.uuid4().hex


def _is_deployed_app() -> bool:
    """Best-effort check for a deployed Databricks App environment.

    Used only to warn that SQLite storage is ephemeral when deployed. We look
    for env markers that a deployed App / Lakebase resource would expose. No
    secret values are read or logged - presence only.
    """
    return bool(
        os.environ.get("LAKEBASE_RESOURCE")
        or os.environ.get("DATABRICKS_CLIENT_ID")
        or os.environ.get("DATABRICKS_APP_NAME")
    )


def _warn_if_deployed() -> None:
    if _is_deployed_app():
        logger.warning(
            "Local SQLite fallback is being used inside what looks like a "
            "DEPLOYED Databricks App. This storage is EPHEMERAL and NOT durable "
            "across app restarts/redeploys - use it only as an emergency fallback."
        )


def init_local_db() -> None:
    """Create the SQLite database and tables if they do not already exist."""
    _LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(_DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS family_intake_events (
                intake_id     TEXT PRIMARY KEY,
                event_ts      TEXT,
                raw_user_text TEXT,
                profile_json  TEXT,
                storage_mode  TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS program_matches (
                match_id           TEXT PRIMARY KEY,
                intake_id          TEXT,
                event_ts           TEXT,
                program_id         TEXT,
                program_name       TEXT,
                category           TEXT,
                match_reasons_json TEXT,
                storage_mode       TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS action_plans (
                plan_id            TEXT PRIMARY KEY,
                intake_id          TEXT,
                event_ts           TEXT,
                action_plan_text   TEXT,
                generated_by_model TEXT,
                storage_mode       TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_feedback (
                feedback_id   TEXT PRIMARY KEY,
                intake_id     TEXT,
                event_ts      TEXT,
                rating        INTEGER,
                feedback_text TEXT,
                storage_mode  TEXT
            )
            """
        )
        conn.commit()


def _match_reasons_json(match: Dict[str, Any]) -> str:
    """Serialize a matched program's reasons to JSON text.

    Supports both shapes:
      * rules-engine output with a `match_reasons` list, and
      * an explainable shape with `qualification_reason` / `confidence_label`.
    """
    if (
        match.get("qualification_reason") is not None
        or match.get("confidence_label") is not None
    ):
        payload: Dict[str, Any] = {
            "qualification_reason": match.get("qualification_reason"),
            "confidence_label": match.get("confidence_label"),
            "rule_key": match.get("rule_key"),
        }
    else:
        payload = {
            "match_reasons": match.get("match_reasons", []),
            "rule_key": match.get("rule_key"),
        }
    return json.dumps(payload, ensure_ascii=False)


# ── Write functions (mirror lakebase_client.py names + signatures) ────────────
def write_family_intake_event(
    profile: Dict[str, Any], raw_user_text: str
) -> Optional[str]:
    """Persist a family intake event locally. Returns intake_id or None.

    Mirrors lakebase_client.write_family_intake_event(profile, raw_user_text).
    NOTE: raw_user_text is stored in the local DB (that is the point of the
    fallback) but is NEVER written to logs.
    """
    _warn_if_deployed()
    intake_id = _new_id()
    try:
        init_local_db()
        with sqlite3.connect(_DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO family_intake_events
                    (intake_id, event_ts, raw_user_text, profile_json, storage_mode)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    intake_id,
                    _now_iso(),
                    raw_user_text,
                    json.dumps(profile or {}, ensure_ascii=False),
                    _STORAGE_MODE,
                ),
            )
            conn.commit()
        logger.info("Local SQLite fallback: wrote intake event %s.", intake_id)
        return intake_id
    except Exception as exc:  # noqa: BLE001 - never crash the app
        logger.error(
            "Local SQLite fallback: failed to write intake event: %s: %s",
            type(exc).__name__,
            exc,
        )
        return None


def write_program_matches(intake_id: str, matches: List[Dict[str, Any]]) -> bool:
    """Persist program matches locally (one row per match). Returns True/False.

    Mirrors lakebase_client.write_program_matches(intake_id, matches).
    """
    if not matches:
        return True
    try:
        init_local_db()
        ts = _now_iso()
        rows = [
            (
                _new_id(),
                intake_id,
                ts,
                m.get("id") or m.get("program_id"),
                m.get("name") or m.get("program_name"),
                m.get("category"),
                _match_reasons_json(m),
                _STORAGE_MODE,
            )
            for m in matches
        ]
        with sqlite3.connect(_DB_PATH) as conn:
            conn.executemany(
                """
                INSERT INTO program_matches
                    (match_id, intake_id, event_ts, program_id, program_name,
                     category, match_reasons_json, storage_mode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()
        logger.info(
            "Local SQLite fallback: wrote %d program match(es) for intake %s.",
            len(rows),
            intake_id,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Local SQLite fallback: failed to write program matches: %s: %s",
            type(exc).__name__,
            exc,
        )
        return False


def write_action_plan(
    intake_id: str, action_plan_text: str, generated_by_model: str
) -> Optional[str]:
    """Persist the action plan locally. Returns plan_id or None.

    Mirrors lakebase_client.write_action_plan(intake_id, action_plan_text,
    generated_by_model).
    """
    plan_id = _new_id()
    try:
        init_local_db()
        with sqlite3.connect(_DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO action_plans
                    (plan_id, intake_id, event_ts, action_plan_text,
                     generated_by_model, storage_mode)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    intake_id,
                    _now_iso(),
                    action_plan_text,
                    generated_by_model,
                    _STORAGE_MODE,
                ),
            )
            conn.commit()
        logger.info(
            "Local SQLite fallback: wrote action plan %s for intake %s.",
            plan_id,
            intake_id,
        )
        return plan_id
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Local SQLite fallback: failed to write action plan: %s: %s",
            type(exc).__name__,
            exc,
        )
        return None


def write_user_feedback(
    intake_id: str, rating: Any, feedback_text: str
) -> Optional[str]:
    """Persist user feedback locally. Returns feedback_id or None.

    Mirrors lakebase_client.write_user_feedback(intake_id, rating, feedback_text).
    """
    feedback_id = _new_id()
    try:
        init_local_db()
        with sqlite3.connect(_DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO user_feedback
                    (feedback_id, intake_id, event_ts, rating, feedback_text,
                     storage_mode)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    feedback_id,
                    intake_id,
                    _now_iso(),
                    rating,
                    feedback_text,
                    _STORAGE_MODE,
                ),
            )
            conn.commit()
        logger.info(
            "Local SQLite fallback: wrote user feedback %s for intake %s.",
            feedback_id,
            intake_id,
        )
        return feedback_id
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Local SQLite fallback: failed to write user feedback: %s: %s",
            type(exc).__name__,
            exc,
        )
        return None


# ── Convenience aliases (names requested for compatibility) ───────────────────
def write_intake_event(raw_user_text: str, profile: Dict[str, Any]) -> Optional[str]:
    """Alias with (raw_user_text, profile) ordering -> write_family_intake_event."""
    return write_family_intake_event(profile, raw_user_text)


def write_feedback(
    intake_id: str, rating: Any, feedback_text: str
) -> Optional[str]:
    """Alias -> write_user_feedback."""
    return write_user_feedback(intake_id, rating, feedback_text)


# ── Helpers for inspection / debug ────────────────────────────────────────────
def get_local_state_counts() -> Dict[str, int]:
    """Return row counts for each app-state table (empty/zero on any error)."""
    tables = [
        "family_intake_events",
        "program_matches",
        "action_plans",
        "user_feedback",
    ]
    counts: Dict[str, int] = {t: 0 for t in tables}
    try:
        init_local_db()
        with sqlite3.connect(_DB_PATH) as conn:
            for t in tables:
                counts[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Local SQLite fallback: failed to read counts: %s: %s",
            type(exc).__name__,
            exc,
        )
    return counts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_local_db()
    print("Local SQLite state DB:", get_db_path())
    print("Counts:", get_local_state_counts())
