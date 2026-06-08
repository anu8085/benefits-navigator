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

import importlib.util
import json
import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional

# psycopg (v3) is imported lazily inside the connection helper so that simply
# importing this module stays cheap and does not hard-require the driver to be
# installed in every environment.

logger = logging.getLogger(__name__)


# ── Safe logging helpers ──────────────────────────────────────────────────────
def _safe_env_status(names: List[str]) -> Dict[str, str]:
    """Return {name: 'present'|'missing'} for each env var - NEVER the value.

    Use this to log which configuration is available without ever exposing the
    underlying secret/identifier values.
    """
    return {n: ("present" if os.environ.get(n) else "missing") for n in names}


def _mask_value(value: Optional[str]) -> str:
    """Mask a NON-SECRET identifier for safe logging.

    - None / empty -> "missing"
    - short value   -> "***"
    - longer value  -> first 6 chars + "..." + last 4 chars

    Only use this for non-secret identifiers (e.g. a host). Passwords and tokens
    are NEVER logged at all, not even masked.
    """
    if not value:
        return "missing"
    if len(value) <= 10:
        return "***"
    return value[:6] + "..." + value[-4:]


# ── Startup diagnostics (safe: only availability, never values) ───────────────
logger.info("lakebase_client.py loaded.")
try:
    if importlib.util.find_spec("psycopg") is not None:
        logger.info("lakebase_client: psycopg driver is available.")
    else:
        logger.warning(
            "lakebase_client: psycopg driver NOT found - Lakebase writes will be "
            "skipped until 'psycopg[binary]' is installed."
        )
except Exception as exc:  # noqa: BLE001 - never fail at import time
    logger.warning(
        "lakebase_client: could not probe for psycopg (%s).", type(exc).__name__
    )

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


def _build_managed_workspace_client():
    """Construct a WorkspaceClient for managed Lakebase mode.

    A deployed Databricks App has BOTH a PAT (DATABRICKS_TOKEN, used by the SQL
    connector for trusted-data reads) AND OAuth service-principal credentials
    (DATABRICKS_CLIENT_ID / DATABRICKS_CLIENT_SECRET, injected by Databricks
    Apps). If the SDK is allowed to auto-detect, it sees both and fails with:
        "more than one authorization method configured: oauth and pat".

    To avoid that, when OAuth credentials are available we initialize the client
    EXPLICITLY with OAuth machine-to-machine auth and pin auth_type so the SDK
    ignores DATABRICKS_TOKEN. The PAT remains available for the SQL connector
    elsewhere - we simply don't use it here. No secret values are ever logged.
    """
    from databricks.sdk import WorkspaceClient

    # Log only present/missing status for the OAuth inputs - never the values.
    logger.info(
        "Lakebase managed OAuth env status: %s",
        _safe_env_status(
            [
                "DATABRICKS_HOST",
                "DATABRICKS_CLIENT_ID",
                "DATABRICKS_CLIENT_SECRET",
                "DATABRICKS_TOKEN",
            ]
        ),
    )

    client_id = os.environ.get("DATABRICKS_CLIENT_ID")
    client_secret = os.environ.get("DATABRICKS_CLIENT_SECRET")

    # Prefer the explicit DATABRICKS_HOST; fall back to building it from the
    # SQL-warehouse hostname if that is all that is set.
    host = os.environ.get("DATABRICKS_HOST")
    if not host and os.environ.get("DATABRICKS_SERVER_HOSTNAME"):
        host = "https://" + os.environ["DATABRICKS_SERVER_HOSTNAME"]

    if client_id and client_secret and host:
        if os.environ.get("DATABRICKS_TOKEN"):
            logger.info(
                "Lakebase managed mode: DATABRICKS_TOKEN is present but will be "
                "IGNORED for Lakebase auth (using explicit OAuth M2M instead)."
            )
        # Log only present/missing status - never the id/secret/host values.
        logger.info(
            "Lakebase managed mode: initializing WorkspaceClient with explicit "
            "OAuth (oauth-m2m); ignoring DATABRICKS_TOKEN for this client."
        )
        oauth_kwargs = {
            "host": host,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        try:
            # Pin the authenticator so PAT auto-detection is bypassed.
            return WorkspaceClient(auth_type="oauth-m2m", **oauth_kwargs)
        except TypeError:
            # Older SDKs may not accept auth_type; passing OAuth creds explicitly
            # still selects service-principal auth.
            return WorkspaceClient(**oauth_kwargs)

    # No explicit OAuth creds present (e.g. a non-App environment): fall back to
    # the SDK's default credential detection.
    logger.info(
        "Lakebase managed mode: DATABRICKS_CLIENT_ID/SECRET/HOST not all "
        "present; using default WorkspaceClient credential detection."
    )
    return WorkspaceClient()


# A LAKEBASE_RESOURCE that looks like a Lakebase Autoscaling endpoint path:
#   projects/<project>/branches/<branch>/endpoints/<endpoint>
_ENDPOINT_PATH_RE = re.compile(
    r"^projects/[^/]+/branches/[^/]+/endpoints/[^/]+$"
)

# PG* connection env vars that Databricks Apps inject for an attached Lakebase
# (Autoscaling) database resource. The token/password is NOT among them - it is
# minted at runtime via OAuth (see _generate_managed_token).
_PG_REQUIRED_VARS = ("PGHOST", "PGUSER", "PGDATABASE")


def _looks_like_endpoint_path(resource: Optional[str]) -> bool:
    """True if `resource` is a projects/.../branches/.../endpoints/... path."""
    return bool(resource and _ENDPOINT_PATH_RE.match(resource))


def _managed_fallback_to_manual(reason: str) -> Optional[Dict[str, Any]]:
    """Safe fallback: try the manual LAKEBASE_* env vars instead.

    Used when the managed Databricks App path cannot resolve credentials. If the
    manual vars are not all present, _resolve_manual_params() logs the missing
    NAMES and returns None, so writes simply skip gracefully.
    """
    logger.info(
        "Lakebase managed mode: %s; falling back to manual LAKEBASE_* "
        "environment variables if present.",
        reason,
    )
    return _resolve_manual_params()


def _generate_managed_token(endpoint_name: Optional[str]) -> Optional[str]:
    """Mint a short-lived Lakebase OAuth credential (used as the PG password).

    Builds a WorkspaceClient with EXPLICIT OAuth (so it ignores DATABRICKS_TOKEN)
    and calls `w.postgres.generate_database_credential(endpoint=...)`. A fresh
    token is minted per call, so credentials rotate automatically. Returns the
    token string, or None on any failure (only the exception type/message is
    logged - never the token itself).
    """
    try:
        import databricks.sdk  # noqa: F401 - presence check only

        logger.info("Lakebase managed mode: databricks-sdk import succeeded.")
    except ImportError:
        logger.error(
            "Lakebase managed mode: databricks-sdk import FAILED - install the "
            "'databricks-sdk' package (pip install databricks-sdk)."
        )
        return None

    try:
        # Explicit OAuth avoids the PAT/OAuth "more than one authorization
        # method configured" conflict in a deployed App.
        w = _build_managed_workspace_client()

        # Generate the credential. Prefer passing the endpoint name when we have
        # one; some SDK versions can infer it from the App resource if omitted.
        logger.info(
            "Lakebase managed mode: calling generate_database_credential() "
            "(endpoint=%s).",
            "provided" if endpoint_name else "inferred",
        )
        if endpoint_name:
            cred = w.postgres.generate_database_credential(endpoint=endpoint_name)
        else:
            cred = w.postgres.generate_database_credential()

        token = getattr(cred, "token", None)
        if not token:
            logger.error(
                "Lakebase managed mode: credential response contained no token."
            )
            return None
        logger.info(
            "Lakebase managed mode: credential generation succeeded "
            "(token received; value not logged)."
        )
        return token
    except Exception as exc:  # noqa: BLE001 - degrade gracefully on any failure
        # Log only the exception type/message; never the token.
        logger.error(
            "Lakebase managed credential generation failed: %s: %s",
            type(exc).__name__,
            exc,
        )
        return None


def _resolve_managed_params(resource: str) -> Optional[Dict[str, Any]]:
    """Build psycopg connect kwargs for Databricks Apps Lakebase Autoscaling.

    For an attached Lakebase (Autoscaling) database resource, Databricks Apps
    inject the Postgres connection target as PG* environment variables:
        PGHOST, PGDATABASE, PGUSER, PGPORT, PGSSLMODE
    We use those for the connection and mint the password (a short-lived OAuth
    token) at runtime via `w.postgres.generate_database_credential(...)`. We do
    NOT call `w.database.get_database_instance()` here.

    LAKEBASE_RESOURCE is used only as the ENDPOINT name, and only when it looks
    like `projects/<p>/branches/<b>/endpoints/<e>`. If the PG* vars are missing
    or the token cannot be minted, we fall back to manual LAKEBASE_* vars.
    """
    # 1) The PG* connection target must be present (injected by the App).
    logger.info(
        "Lakebase managed mode: PG* env status: %s",
        _safe_env_status(["PGHOST", "PGUSER", "PGDATABASE", "PGPORT", "PGSSLMODE"]),
    )
    missing_pg = [name for name in _PG_REQUIRED_VARS if not os.environ.get(name)]
    if missing_pg:
        logger.warning(
            "Lakebase managed mode: missing required PG* env var(s): %s",
            ", ".join(missing_pg),
        )
        return _managed_fallback_to_manual(
            "PG* connection env var(s) not present: " + ", ".join(missing_pg)
        )

    # 2) Determine the endpoint name from LAKEBASE_RESOURCE (path shape only).
    if _looks_like_endpoint_path(resource):
        endpoint_name: Optional[str] = resource
        # The project/branch/endpoint names are NOT secrets - safe to log.
        parts = resource.split("/")
        logger.info(
            "Lakebase managed mode: endpoint path detected: yes "
            "(project=%s, branch=%s, endpoint=%s).",
            parts[1],
            parts[3],
            parts[5],
        )
    else:
        endpoint_name = None
        logger.info(
            "Lakebase managed mode: endpoint path detected: no; letting the SDK "
            "infer the endpoint from the App resource."
        )

    # 3) Mint the short-lived OAuth token used as the Postgres password.
    token = _generate_managed_token(endpoint_name)
    if not token:
        return _managed_fallback_to_manual(
            "could not mint a Lakebase OAuth credential"
        )

    # 4) Assemble connect kwargs from the injected PG* vars (token = password).
    logger.info(
        "Lakebase managed mode: connecting using injected PG* env vars "
        "(PGHOST/PGUSER/PGDATABASE present) with a minted OAuth token."
    )
    return {
        "host": os.environ["PGHOST"],
        "port": os.environ.get("PGPORT") or _DEFAULT_DB_PORT,
        "dbname": os.environ["PGDATABASE"],
        "user": os.environ["PGUSER"],
        "password": token,  # short-lived OAuth token - never logged
        "sslmode": os.environ.get("PGSSLMODE") or "require",
    }


def _resolve_connection_params() -> Optional[Dict[str, Any]]:
    """Pick the auth mode and return psycopg connect kwargs (or None).

    Priority:
      * Manual mode when LAKEBASE_PASSWORD is set (local/dev - never broken).
      * Managed mode when a Databricks App database resource (LAKEBASE_RESOURCE)
        is present.
    Returns None (with a clear log) when neither is configured.
    """
    # Log what configuration is present (names/status only, never values).
    logger.info(
        "Lakebase mode selection: %s",
        _safe_env_status(
            [
                "LAKEBASE_PASSWORD",
                "LAKEBASE_RESOURCE",
                "PGHOST",
                "PGUSER",
                "PGDATABASE",
                "PGPORT",
                "PGSSLMODE",
            ]
        ),
    )

    # Manual mode wins when an explicit password is supplied - this preserves
    # local/dev behavior exactly.
    if os.environ.get("LAKEBASE_PASSWORD"):
        logger.info("Lakebase: selected MODE A (local/manual credentials).")
        return _resolve_manual_params()

    # Databricks App managed-credential mode.
    resource = os.environ.get(_RESOURCE_ENV_VAR)
    if resource:
        logger.info(
            "Lakebase: selected MODE B (Databricks App managed PG* mode)."
        )
        return _resolve_managed_params(resource)

    logger.warning(
        "Lakebase: selected MODE C (unconfigured) - writes will be skipped. Set "
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
        logger.warning(
            "Lakebase: no connection parameters resolved; skipping connection."
        )
        return None

    # Sanitized view of the connection target. dbname/port/sslmode are not
    # sensitive; host is masked; user is shown as present/missing; the password
    # (token) is never referenced here.
    logger.info(
        "Lakebase connection params (sanitized): dbname=%s, user=%s, host=%s, "
        "port=%s, sslmode=%s",
        params.get("dbname"),
        "present" if params.get("user") else "missing",
        _mask_value(params.get("host")),
        params.get("port"),
        params.get("sslmode"),
    )

    try:
        import psycopg  # lazy import - driver only needed when actually writing
    except ImportError:
        logger.error(
            "The 'psycopg' package is not installed. "
            "Install it with: pip install \"psycopg[binary]\""
        )
        return None

    try:
        logger.info("Lakebase: calling psycopg.connect() ...")
        conn = psycopg.connect(**params)
        logger.info("Lakebase: psycopg.connect() succeeded; connection established.")
        return conn
    except Exception as exc:  # noqa: BLE001 - degrade gracefully on any failure
        # Log only the exception type/message; params (incl. password) are never
        # logged.
        logger.error(
            "Lakebase: psycopg.connect() failed: %s: %s",
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
    logger.info("write_intake_event: started (intake_id generated: yes).")
    intake_id = str(uuid.uuid4())

    # Parameterized INSERT - values are bound by the driver, never concatenated.
    # profile is stored as JSON; the %s::jsonb cast lets Postgres store it in a
    # jsonb column. NOTE: raw_user_text and profile are sensitive and are NEVER
    # logged - only the generated intake_id (a UUID) is.
    sql = """
        INSERT INTO family_intake_events (intake_id, raw_user_text, profile)
        VALUES (%s, %s, %s::jsonb)
    """
    params = (intake_id, raw_user_text, json.dumps(profile or {}))

    conn = _connect()
    if conn is None:
        logger.warning(
            "write_intake_event: no Lakebase connection; skipping write "
            "(intake_id=%s).",
            intake_id,
        )
        return None
    try:
        with conn:
            with conn.cursor() as cur:
                logger.info(
                    "write_intake_event: SQL execute started (intake_id=%s).",
                    intake_id,
                )
                cur.execute(sql, params)
                logger.info("write_intake_event: SQL execute completed.")
        logger.info(
            "write_intake_event: commit completed; wrote intake_id=%s.", intake_id
        )
        return intake_id
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "write_intake_event: failed: %s: %s",
            type(exc).__name__,
            exc,
        )
        return None
    finally:
        conn.close()
        logger.info("write_intake_event: connection closed.")


def write_program_matches(intake_id: str, matches: List[Dict[str, Any]]) -> bool:
    """Persist the program matches surfaced for an intake event.

    Args:
        intake_id: The intake event these matches belong to.
        matches: List of matched-program dicts (as produced by the rules engine).

    Returns:
        True if the matches were written (or there were none to write), False if
        the write failed.
    """
    logger.info(
        "write_program_matches: started (intake_id present: %s, matches to write: %d).",
        "yes" if intake_id else "no",
        len(matches) if matches else 0,
    )
    if not matches:
        # Nothing to persist is not an error.
        logger.info("write_program_matches: 0 matches; nothing to write.")
        return True

    # Build one parameter tuple per match, each with its own UUID. match_reasons
    # is stored as JSON. All values are bound parameters - no string building.
    # NOTE: match content itself is not logged - only the count.
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
        logger.warning(
            "write_program_matches: no Lakebase connection; skipping write "
            "(intake_id=%s).",
            intake_id,
        )
        return False
    try:
        with conn:
            with conn.cursor() as cur:
                logger.info(
                    "write_program_matches: SQL execute started (%d row(s), "
                    "intake_id=%s).",
                    len(rows),
                    intake_id,
                )
                cur.executemany(sql, rows)
                logger.info("write_program_matches: SQL execute completed.")
        logger.info(
            "write_program_matches: commit completed; wrote %d match(es) for "
            "intake_id=%s.",
            len(rows),
            intake_id,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "write_program_matches: failed: %s: %s",
            type(exc).__name__,
            exc,
        )
        return False
    finally:
        conn.close()
        logger.info("write_program_matches: connection closed.")


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
    logger.info(
        "write_action_plan: started (intake_id present: %s).",
        "yes" if intake_id else "no",
    )
    plan_id = str(uuid.uuid4())

    # NOTE: action_plan_text is not logged (may contain sensitive context).
    sql = """
        INSERT INTO action_plans
            (plan_id, intake_id, action_plan_text, generated_by_model)
        VALUES (%s, %s, %s, %s)
    """
    params = (plan_id, intake_id, action_plan_text, generated_by_model)

    conn = _connect()
    if conn is None:
        logger.warning(
            "write_action_plan: no Lakebase connection; skipping write "
            "(intake_id=%s).",
            intake_id,
        )
        return None
    try:
        with conn:
            with conn.cursor() as cur:
                logger.info(
                    "write_action_plan: SQL execute started (plan_id=%s, "
                    "intake_id=%s).",
                    plan_id,
                    intake_id,
                )
                cur.execute(sql, params)
                logger.info("write_action_plan: SQL execute completed.")
        logger.info(
            "write_action_plan: commit completed; wrote plan_id=%s for "
            "intake_id=%s.",
            plan_id,
            intake_id,
        )
        return plan_id
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "write_action_plan: failed: %s: %s",
            type(exc).__name__,
            exc,
        )
        return None
    finally:
        conn.close()
        logger.info("write_action_plan: connection closed.")


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
    logger.info(
        "write_feedback: started (intake_id present: %s).",
        "yes" if intake_id else "no",
    )
    feedback_id = str(uuid.uuid4())

    # NOTE: feedback_text is not logged (free-text user content).
    sql = """
        INSERT INTO user_feedback
            (feedback_id, intake_id, rating, feedback_text)
        VALUES (%s, %s, %s, %s)
    """
    params = (feedback_id, intake_id, rating, feedback_text)

    conn = _connect()
    if conn is None:
        logger.warning(
            "write_feedback: no Lakebase connection; skipping write "
            "(intake_id=%s).",
            intake_id,
        )
        return None
    try:
        with conn:
            with conn.cursor() as cur:
                logger.info(
                    "write_feedback: SQL execute started (feedback_id=%s, "
                    "intake_id=%s).",
                    feedback_id,
                    intake_id,
                )
                cur.execute(sql, params)
                logger.info("write_feedback: SQL execute completed.")
        logger.info(
            "write_feedback: commit completed; wrote feedback_id=%s for "
            "intake_id=%s.",
            feedback_id,
            intake_id,
        )
        return feedback_id
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "write_feedback: failed: %s: %s",
            type(exc).__name__,
            exc,
        )
        return None
    finally:
        conn.close()
        logger.info("write_feedback: connection closed.")
