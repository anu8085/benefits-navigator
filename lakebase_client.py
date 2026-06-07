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
(v3) driver and supports TWO authentication modes, chosen automatically at
runtime. Secrets (passwords, tokens) are NEVER logged or printed, and we never
log a full connection string.

Mode A - Local / manual (used when LAKEBASE_PASSWORD is set):
    LAKEBASE_HOST       - Lakebase Postgres host
    LAKEBASE_PORT       - Postgres port (e.g. 5432)
    LAKEBASE_DATABASE   - database name
    LAKEBASE_USER       - username
    LAKEBASE_PASSWORD   - password (secret - never logged)

Mode B - Databricks App / managed credentials (used when LAKEBASE_RESOURCE is
set and no manual password is provided):
    LAKEBASE_RESOURCE   - the Databricks App database resource (resource key
                          "lakebase-db"), which inside Databricks Apps resolves
                          to the Lakebase database INSTANCE NAME. We then use the
                          Databricks SDK (authenticated as the App's service
                          principal) to look up the instance host and mint a
                          SHORT-LIVED OAuth credential used as the Postgres
                          password. A fresh token is generated per connection,
                          so credentials rotate automatically and no static
                          password is ever stored.
    LAKEBASE_DATABASE / LAKEBASE_PORT / LAKEBASE_HOST / LAKEBASE_USER are
    optional overrides in this mode (sensible defaults are used otherwise).

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

# Env vars that make up the manual (local) credential set.
_MANUAL_ENV_VARS = (
    "LAKEBASE_HOST",
    "LAKEBASE_PORT",
    "LAKEBASE_DATABASE",
    "LAKEBASE_USER",
    "LAKEBASE_PASSWORD",
)

# Env var that the Databricks App injects for the attached Lakebase database
# resource (resource key "lakebase-db"). Its value is the database instance name.
_RESOURCE_ENV_VAR = "LAKEBASE_RESOURCE"

# Defaults used in managed mode when an explicit override is not provided.
_DEFAULT_DB_NAME = "databricks_postgres"
_DEFAULT_DB_PORT = "5432"


def _resolve_manual_params() -> Optional[Dict[str, Any]]:
    """Build psycopg connect kwargs from the manual LAKEBASE_* env vars.

    Returns the kwargs dict, or None if any required variable is missing. Only
    the missing variable NAMES are logged - never any values.
    """
    missing = [name for name in _MANUAL_ENV_VARS if not os.environ.get(name)]
    if missing:
        logger.error(
            "Lakebase manual mode: missing environment variable(s): %s",
            ", ".join(missing),
        )
        return None
    return {
        # psycopg uses `dbname`. The password is passed straight to the driver
        # and is never logged.
        "host": os.environ["LAKEBASE_HOST"],
        "port": os.environ["LAKEBASE_PORT"],
        "dbname": os.environ["LAKEBASE_DATABASE"],
        "user": os.environ["LAKEBASE_USER"],
        "password": os.environ["LAKEBASE_PASSWORD"],
    }


def _resolve_managed_params(resource: str) -> Optional[Dict[str, Any]]:
    """Build psycopg connect kwargs using Databricks-managed credentials.

    Inside a Databricks App, the App authenticates as its service principal. We
    use the Databricks SDK to look up the Lakebase instance host and mint a
    short-lived OAuth credential to use as the Postgres password. A new token is
    generated on every call, so credentials rotate automatically. No password or
    token is ever logged.

    Returns connect kwargs, or None if the SDK is unavailable or credential
    resolution fails (only the exception type/message is logged).
    """
    try:
        from databricks.sdk import WorkspaceClient
    except ImportError:
        logger.error(
            "Lakebase managed mode requires the 'databricks-sdk' package "
            "(pip install databricks-sdk)."
        )
        return None

    try:
        # WorkspaceClient() auto-authenticates as the App's service principal
        # when running inside a Databricks App.
        w = WorkspaceClient()

        # Look up the database instance (host) for the attached resource.
        instance = w.database.get_database_instance(name=resource)

        # Mint a short-lived OAuth credential (rotates per connection).
        cred = w.database.generate_database_credential(
            request_id=str(uuid.uuid4()), instance_names=[resource]
        )

        # Host/user can be overridden via env, else derived from the instance /
        # current identity. dbname/port fall back to the standard defaults.
        host = os.environ.get("LAKEBASE_HOST") or getattr(
            instance, "read_write_dns", None
        )
        user = os.environ.get("LAKEBASE_USER") or w.current_user.me().user_name

        if not host:
            logger.error(
                "Lakebase managed mode: could not resolve a host for resource "
                "'%s' (no read_write_dns and no LAKEBASE_HOST override).",
                resource,
            )
            return None

        return {
            "host": host,
            "port": os.environ.get("LAKEBASE_PORT", _DEFAULT_DB_PORT),
            "dbname": os.environ.get("LAKEBASE_DATABASE", _DEFAULT_DB_NAME),
            "user": user,
            "password": cred.token,  # short-lived OAuth token - never logged
            "sslmode": "require",
        }
    except Exception as exc:  # noqa: BLE001 - degrade gracefully on any failure
        # Log only the exception type/message; never credentials or a DSN.
        logger.error(
            "Lakebase managed credential resolution failed: %s: %s",
            type(exc).__name__,
            exc,
        )
        return None


def _resolve_connection_params() -> Optional[Dict[str, Any]]:
    """Pick the auth mode and return psycopg connect kwargs (or None).

    Priority:
      * Manual mode when LAKEBASE_PASSWORD is set (local/dev - never broken).
      * Managed mode when a Databricks App database resource (LAKEBASE_RESOURCE)
        is present.
    Returns None (with a clear log) when neither is configured.
    """
    # Manual mode wins when an explicit password is supplied - this preserves
    # local/dev behavior exactly.
    if os.environ.get("LAKEBASE_PASSWORD"):
        logger.info("Lakebase: using manual credential mode.")
        return _resolve_manual_params()

    # Databricks App managed-credential mode.
    resource = os.environ.get(_RESOURCE_ENV_VAR)
    if resource:
        logger.info("Lakebase: using Databricks App managed-credential mode.")
        return _resolve_managed_params(resource)

    logger.error(
        "Cannot connect to Lakebase: no credentials configured. Set "
        "LAKEBASE_PASSWORD (+ LAKEBASE_HOST/PORT/DATABASE/USER) for manual mode, "
        "or attach a Databricks App database resource exposed as %s.",
        _RESOURCE_ENV_VAR,
    )
    return None


def _connect():
    """Open a psycopg connection to Lakebase.

    Resolves credentials via _resolve_connection_params() (manual or managed),
    then connects. Returns a live connection on success, or None if config is
    missing, the driver is unavailable, or the connection fails. Only
    present/missing status and exception type/message are logged - never
    secrets or full connection strings.
    """
    params = _resolve_connection_params()
    if params is None:
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
        return psycopg.connect(**params)
    except Exception as exc:  # noqa: BLE001 - degrade gracefully on any failure
        # Log only the exception type/message; params (incl. password) are never
        # logged.
        logger.error(
            "Failed to connect to Lakebase Postgres: %s: %s",
            type(exc).__name__,
            exc,
        )
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
        logger.error(
            "Failed to write family intake event to Lakebase: %s: %s",
            type(exc).__name__,
            exc,
        )
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
        logger.error(
            "Failed to write program matches to Lakebase: %s: %s",
            type(exc).__name__,
            exc,
        )
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
        logger.error(
            "Failed to write action plan to Lakebase: %s: %s",
            type(exc).__name__,
            exc,
        )
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
        logger.error(
            "Failed to write user feedback to Lakebase: %s: %s",
            type(exc).__name__,
            exc,
        )
        return None
    finally:
        conn.close()
