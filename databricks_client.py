"""
databricks_client.py

Reads TRUSTED, source-labeled benefits program data from Unity Catalog.

The table `benefits_navigator.trusted.benefit_programs` is a curated
("trusted") layer in Unity Catalog. Every row is expected to carry
provenance / source-labeling columns (source_name, source_url, source_type,
last_verified_date) so the app can show users where each benefit program
fact came from and when it was last verified.

This module only READS data. It connects to a Databricks SQL Warehouse using
the official `databricks-sql-connector` and credentials supplied through
environment variables (never hard-coded, never printed):

    DATABRICKS_SERVER_HOSTNAME  - e.g. "adb-1234567890.7.azuredatabricks.net"
    DATABRICKS_HTTP_PATH        - e.g. "/sql/1.0/warehouses/abc123def456"
    DATABRICKS_TOKEN            - a Databricks personal access token

Secrets are read from the environment and are NEVER logged or printed.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

# The connector is an optional/heavy dependency, so we import it lazily inside
# the function. That keeps `import databricks_client` cheap and lets the rest
# of the app run even if the connector isn't installed in a given environment.

logger = logging.getLogger(__name__)

# Required environment variables for connecting to the SQL Warehouse.
_REQUIRED_ENV_VARS = (
    "DATABRICKS_SERVER_HOSTNAME",
    "DATABRICKS_HTTP_PATH",
    "DATABRICKS_TOKEN",
)

# Query against the trusted Unity Catalog table. Only active programs are
# returned, ordered for stable, human-friendly display. The selected columns
# include the source-labeling / provenance fields described above.
_BENEFIT_PROGRAMS_QUERY = """
SELECT program_id, program_name, category, description,
       eligibility_summary, apply_url, apply_phone,
       source_name, source_url, source_type,
       state, active_flag, last_verified_date,
       rule_key, income_limit_pct_fpl, accepts_undocumented,
       min_child_age, max_child_age, requires_work_or_school
FROM benefits_navigator.trusted.benefit_programs
WHERE active_flag = true
ORDER BY category, program_name
""".strip()


def get_benefit_programs_from_databricks() -> List[Dict[str, Any]]:
    """Read active, trusted benefit programs from Unity Catalog.

    Connects to the configured Databricks SQL Warehouse, runs the trusted
    benefit-programs query, and returns the result set as a list of plain
    dictionaries (one dict per program row, keyed by column name).

    Returns:
        A list of dictionaries on success. On any configuration, connection,
        or query error the problem is logged (without exposing secrets) and an
        empty list is returned so callers can degrade gracefully.
    """
    # Read credentials from the environment. We do NOT log their values.
    missing = [name for name in _REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        # Report only the variable NAMES that are missing, never any values.
        logger.error(
            "Cannot query Databricks: missing environment variable(s): %s",
            ", ".join(missing),
        )
        return []

    server_hostname = os.environ["DATABRICKS_SERVER_HOSTNAME"]
    http_path = os.environ["DATABRICKS_HTTP_PATH"]
    access_token = os.environ["DATABRICKS_TOKEN"]  # secret - never logged

    try:
        # Lazy import so the module loads even when the connector is absent.
        from databricks import sql as databricks_sql
    except ImportError:
        logger.error(
            "The 'databricks-sql-connector' package is not installed. "
            "Install it with: pip install databricks-sql-connector"
        )
        return []

    programs: List[Dict[str, Any]] = []

    try:
        # Use context managers so the connection and cursor are always closed,
        # even if an error occurs mid-query.
        with databricks_sql.connect(
            server_hostname=server_hostname,
            http_path=http_path,
            access_token=access_token,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(_BENEFIT_PROGRAMS_QUERY)

                # Map each row to a dict keyed by the SELECTed column names.
                column_names = [col[0] for col in cursor.description]
                for row in cursor.fetchall():
                    programs.append(dict(zip(column_names, row)))

    except Exception as exc:  # noqa: BLE001 - degrade gracefully on any failure
        # Log the error type/message but never the credentials. The token is
        # not part of the exception text, so this is safe to log.
        logger.error(
            "Failed to read trusted benefit programs from Databricks "
            "(Unity Catalog: benefits_navigator.trusted.benefit_programs): %s",
            exc,
        )
        return []

    logger.info(
        "Loaded %d trusted benefit program(s) from Unity Catalog.",
        len(programs),
    )
    return programs


if __name__ == "__main__":
    # Simple manual smoke test. Prints only the row COUNT and column names,
    # never any secrets.
    logging.basicConfig(level=logging.INFO)
    rows = get_benefit_programs_from_databricks()
    print(f"Retrieved {len(rows)} trusted benefit program(s).")
    if rows:
        print("Columns:", ", ".join(rows[0].keys()))
