"""
lakebase_client.py

Writes Benefits Navigator LIVE APP-STATE data to Lakebase (Postgres).

Lakebase is the TRANSACTIONAL app-state layer for this app. Unlike the
Databricks/Unity Catalog "trusted" layer (which is read-only reference data
about benefit programs), Lakebase stores the dynamic, per-user records the app
generates as people use it:

    * family intake events   - what the user told us (raw text + parsed profile)
    * program matches         - which programs the rules engine surfaced
    * action plans            - the generated step-by-step plan
    * user feedback           - ratings / comments on the experience

This module only WRITES. It connects to Lakebase Postgres using the `psycopg`
(v3) driver and credentials supplied through environment variables. Secrets
(especially LAKEBASE_PASSWORD) are NEVER logged or printed.

    LAKEBASE_HOST       - Lakebase Postgres host
    LAKEBASE_PORT       - Postgres port (e.g. 5432)
    LAKEBASE_DATABASE   - database name
    LAKEBASE_USER       - username
    LAKEBASE_PASSWORD   - password (secret - never logged)

Every record is keyed by a server-generated UUID so writes are idempotent to
generate and easy to correlate across tables (intake_id ties matches, plans,
and feedback back to a single intake event).
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

# psycopg (v3) is imported lazily inside the connection helper so that simply
# importing this module stays cheap and does not hard-require the driver to be
# installed in every environment.

logger = logging.getLogger(__name__)

# Required environment variables for connecting to Lakebase Postgres.
_REQUIRED_ENV_VARS = (
    "LAKEBASE_HOST",
    "LAKEBASE_PORT",
    "LAKEBASE_DATABASE",
    "LAKEBASE_USER",
    "LAKEBASE_PASSWORD",
)


def _connect():
    """Open a psycopg connection to Lakebase using env-var credentials.

    Returns a live connection on success, or None if configuration is missing,
    the driver is unavailable, or the connection cannot be established. Secrets
    are never logged - on missing config we report only the variable NAMES.
    """
    missing = [name for name in _REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        logger.error(
            "Cannot connect to Lakebase: missing environment variable(s): %s",
            ", ".join(missing),
        )
        return None

    try:
        import psycopg  # lazy import - driver only needed when actually writing
    except ImportError:
        logger.error(
            "The 'psycopg' package is not installed. "
            "Install it with: pip install \"psycopg[binary]\""
        )
        return None

    try:
        # Note: psycopg uses `dbname` (mapped from LAKEBASE_DATABASE). The
        # password is passed straight to the driver and never logged.
        connection = psycopg.connect(
            host=os.environ["LAKEBASE_HOST"],
            port=os.environ["LAKEBASE_PORT"],
            dbname=os.environ["LAKEBASE_DATABASE"],
            user=os.environ["LAKEBASE_USER"],
            password=os.environ["LAKEBASE_PASSWORD"],
        )
        return connection
    except Exception as exc:  # noqa: BLE001 - degrade gracefully on any failure
        # The exception text does not contain the password, so this is safe.
        logger.error("Failed to connect to Lakebase Postgres: %s", exc)
        return None


def write_family_intake_event(
    profile: Dict[str, Any], raw_user_text: str
) -> Optional[str]:
    """Persist a family intake event (raw text + parsed profile).

    This is the root record for a user's session: the matches, action plan, and
    feedback all reference the returned intake_id.

    Args:
        profile: The structured profile dict parsed from the user's description.
        raw_user_text: The original free-text the user typed.

    Returns:
        The generated intake_id (UUID string) on success, or None if the write
        failed for any reason.
    """
    intake_id = str(uuid.uuid4())

    # Parameterized INSERT - values are bound by the driver, never concatenated.
    # profile is stored as JSON; the %s::jsonb cast lets Postgres store it in a
    # jsonb column.
    sql = """
        INSERT INTO family_intake_events (intake_id, raw_user_text, profile)
        VALUES (%s, %s, %s::jsonb)
    """
    params = (intake_id, raw_user_text, json.dumps(profile or {}))

    conn = _connect()
    if conn is None:
        return None
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
        logger.info("Wrote family intake event %s to Lakebase.", intake_id)
        return intake_id
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to write family intake event to Lakebase: %s", exc)
        return None
    finally:
        conn.close()


def write_program_matches(intake_id: str, matches: List[Dict[str, Any]]) -> bool:
    """Persist the program matches surfaced for an intake event.

    Args:
        intake_id: The intake event these matches belong to.
        matches: List of matched-program dicts (as produced by the rules engine).

    Returns:
        True if the matches were written (or there were none to write), False if
        the write failed.
    """
    if not matches:
        # Nothing to persist is not an error.
        return True

    # Build one parameter tuple per match, each with its own UUID. match_reasons
    # is stored as JSON. All values are bound parameters - no string building.
    sql = """
        INSERT INTO program_matches
            (match_id, intake_id, program_id, program_name, category, match_reasons)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
    """
    rows = [
        (
            str(uuid.uuid4()),
            intake_id,
            m.get("id"),
            m.get("name"),
            m.get("category"),
            json.dumps(m.get("match_reasons", [])),
        )
        for m in matches
    ]

    conn = _connect()
    if conn is None:
        return False
    try:
        with conn:
            with conn.cursor() as cur:
                cur.executemany(sql, rows)
        logger.info(
            "Wrote %d program match(es) for intake %s to Lakebase.",
            len(rows),
            intake_id,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to write program matches to Lakebase: %s", exc)
        return False
    finally:
        conn.close()


def write_action_plan(
    intake_id: str, action_plan_text: str, generated_by_model: str
) -> Optional[str]:
    """Persist the generated action plan for an intake event.

    Args:
        intake_id: The intake event this plan belongs to.
        action_plan_text: The generated plan text shown to the user.
        generated_by_model: Identifier of the model that produced the plan.

    Returns:
        The generated plan_id (UUID string) on success, or None on failure.
    """
    plan_id = str(uuid.uuid4())

    sql = """
        INSERT INTO action_plans
            (plan_id, intake_id, action_plan_text, generated_by_model)
        VALUES (%s, %s, %s, %s)
    """
    params = (plan_id, intake_id, action_plan_text, generated_by_model)

    conn = _connect()
    if conn is None:
        return None
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
        logger.info("Wrote action plan %s for intake %s to Lakebase.", plan_id, intake_id)
        return plan_id
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to write action plan to Lakebase: %s", exc)
        return None
    finally:
        conn.close()


def write_user_feedback(
    intake_id: str, rating: Any, feedback_text: str
) -> Optional[str]:
    """Persist user feedback (rating + optional comment) for an intake event.

    Args:
        intake_id: The intake event this feedback relates to.
        rating: The user's rating (e.g. an int score or thumbs value).
        feedback_text: Optional free-text feedback.

    Returns:
        The generated feedback_id (UUID string) on success, or None on failure.
    """
    feedback_id = str(uuid.uuid4())

    sql = """
        INSERT INTO user_feedback
            (feedback_id, intake_id, rating, feedback_text)
        VALUES (%s, %s, %s, %s)
    """
    params = (feedback_id, intake_id, rating, feedback_text)

    conn = _connect()
    if conn is None:
        return None
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
        logger.info(
            "Wrote user feedback %s for intake %s to Lakebase.",
            feedback_id,
            intake_id,
        )
        return feedback_id
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to write user feedback to Lakebase: %s", exc)
        return None
    finally:
        conn.close()
