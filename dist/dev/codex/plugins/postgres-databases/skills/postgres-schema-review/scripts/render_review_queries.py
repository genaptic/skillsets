#!/usr/bin/env python3
"""Render a read-only PostgreSQL catalog query bundle for a bounded schema review.

Requires Python 3.11 or newer and only the standard library. It reads no database content,
never connects to PostgreSQL or the network, and executes no SQL or external commands. It
writes SQL to stdout or to one explicit new output file and refuses overwrites.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TIMEOUT_PATTERN = re.compile(r"(?P<amount>[1-9][0-9]*)(?P<unit>ms|s|min|h)\Z")
TIMEOUT_UNIT_MILLISECONDS = {
    "ms": 1,
    "s": 1_000,
    "min": 60_000,
    "h": 3_600_000,
}
MAX_TIMEOUT_MILLISECONDS = 24 * 60 * 60 * 1_000


SECTIONS: dict[str, str] = {
    "context": r"""
SELECT current_database() AS database_name,
       current_user AS session_user,
       current_setting('server_version') AS server_version,
       current_setting('search_path') AS search_path;
""",
    "schemas": r"""
SELECT n.nspname AS schema_name,
       pg_get_userbyid(n.nspowner) AS owner,
       n.nspacl
FROM pg_namespace AS n
WHERE n.nspname !~ '^pg_toast'
ORDER BY n.nspname;
""",
    "relations": r"""
SELECT c.oid::regclass AS object_name,
       c.relkind,
       pg_get_userbyid(c.relowner) AS owner,
       c.relrowsecurity,
       c.relforcerowsecurity,
       c.relpersistence,
       pg_total_relation_size(c.oid) AS total_bytes
FROM pg_class AS c
JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND n.nspname !~ '^pg_toast'
ORDER BY c.oid::regclass::text;
""",
    "columns": r"""
SELECT a.attrelid::regclass AS table_name,
       a.attnum,
       a.attname,
       format_type(a.atttypid, a.atttypmod) AS data_type,
       a.attnotnull,
       a.attidentity,
       a.attgenerated,
       pg_get_expr(d.adbin, d.adrelid) AS default_expression
FROM pg_attribute AS a
LEFT JOIN pg_attrdef AS d
  ON d.adrelid = a.attrelid AND d.adnum = a.attnum
JOIN pg_class AS c ON c.oid = a.attrelid
JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE a.attnum > 0
  AND NOT a.attisdropped
  AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY a.attrelid::regclass::text, a.attnum;
""",
    "constraints": r"""
SELECT con.conrelid::regclass AS table_name,
       con.conname,
       con.contype,
       con.convalidated,
       con.condeferrable,
       con.condeferred,
       con.confrelid::regclass AS referenced_table,
       pg_get_constraintdef(con.oid, true) AS definition
FROM pg_constraint AS con
JOIN pg_class AS c ON c.oid = con.conrelid
JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY con.conrelid::regclass::text, con.conname;
""",
    "indexes": r"""
SELECT i.indrelid::regclass AS table_name,
       i.indexrelid::regclass AS index_name,
       i.indisunique,
       i.indisprimary,
       i.indisexclusion,
       i.indisvalid,
       i.indisready,
       pg_get_indexdef(i.indexrelid) AS definition,
       pg_relation_size(i.indexrelid) AS index_bytes
FROM pg_index AS i
JOIN pg_class AS c ON c.oid = i.indrelid
JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY i.indrelid::regclass::text, i.indexrelid::regclass::text;
""",
    "rls": r"""
SELECT c.oid::regclass AS table_name,
       c.relrowsecurity,
       c.relforcerowsecurity,
       p.polname AS policy_name,
       p.polpermissive,
       pg_get_userbyid(role_oid) AS policy_role,
       p.polcmd,
       pg_get_expr(p.polqual, p.polrelid) AS using_expression,
       pg_get_expr(p.polwithcheck, p.polrelid) AS with_check_expression
FROM pg_class AS c
JOIN pg_namespace AS n ON n.oid = c.relnamespace
LEFT JOIN pg_policy AS p ON p.polrelid = c.oid
LEFT JOIN LATERAL unnest(COALESCE(p.polroles, ARRAY[]::oid[])) AS role_oid ON true
WHERE c.relkind IN ('r', 'p')
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND (c.relrowsecurity OR p.oid IS NOT NULL)
ORDER BY c.oid::regclass::text, p.polname, policy_role;
""",
    "partitions": r"""
SELECT parent.oid::regclass AS parent_table,
       child.oid::regclass AS child_table,
       pg_get_expr(child.relpartbound, child.oid) AS partition_bound
FROM pg_inherits AS inh
JOIN pg_class AS parent ON parent.oid = inh.inhparent
JOIN pg_class AS child ON child.oid = inh.inhrelid
JOIN pg_namespace AS n ON n.oid = parent.relnamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY parent.oid::regclass::text, child.oid::regclass::text;
""",
    "activity-stats": r"""
SELECT s.schemaname,
       s.relname,
       s.seq_scan,
       s.idx_scan,
       s.n_live_tup,
       s.n_dead_tup,
       s.last_analyze,
       s.last_autoanalyze,
       s.last_vacuum,
       s.last_autovacuum
FROM pg_stat_user_tables AS s
ORDER BY s.schemaname, s.relname;

SELECT s.schemaname,
       s.relname,
       s.indexrelname,
       s.idx_scan,
       s.idx_tup_read,
       s.idx_tup_fetch
FROM pg_stat_user_indexes AS s
ORDER BY s.schemaname, s.relname, s.indexrelname;
""",
}


def bounded_timeout(value: str) -> str:
    """Accept a positive, explicitly unit-qualified timeout no longer than 24 hours."""
    match = TIMEOUT_PATTERN.fullmatch(value)
    if match is None:
        raise argparse.ArgumentTypeError(
            "timeout must be a positive integer followed by ms, s, min, or h "
            "(for example, 500ms or 2min)"
        )

    try:
        amount = int(match.group("amount"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("timeout value is too large") from exc

    milliseconds = amount * TIMEOUT_UNIT_MILLISECONDS[match.group("unit")]
    if milliseconds > MAX_TIMEOUT_MILLISECONDS:
        raise argparse.ArgumentTypeError("timeout must not exceed 24h")
    return value


def render(selected: list[str], timeout: str, lock_timeout: str) -> str:
    timeout = bounded_timeout(timeout)
    lock_timeout = bounded_timeout(lock_timeout)
    names = selected or list(SECTIONS)
    chunks = [
        "-- Generated read-only catalog review bundle. Review before execution.",
        "BEGIN TRANSACTION READ ONLY;",
        f"SET LOCAL statement_timeout = '{timeout}';",
        f"SET LOCAL lock_timeout = '{lock_timeout}';",
    ]
    for name in names:
        chunks.append(f"\n-- section: {name}\n{SECTIONS[name].strip()}")
    chunks.append("\nROLLBACK;")
    return "\n".join(chunks) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--section",
        action="append",
        choices=sorted(SECTIONS),
        help="Include one section; repeat as needed. Default: all sections.",
    )
    parser.add_argument(
        "--statement-timeout",
        default="15s",
        type=bounded_timeout,
        help="Bounded SQL statement_timeout (1ms through 24h; units: ms, s, min, h).",
    )
    parser.add_argument(
        "--lock-timeout",
        default="2s",
        type=bounded_timeout,
        help="Bounded SQL lock_timeout (1ms through 24h; units: ms, s, min, h).",
    )
    parser.add_argument("--output", type=Path, help="Write to this new file instead of stdout.")
    args = parser.parse_args()

    text = render(args.section or [], args.statement_timeout, args.lock_timeout)
    if args.output:
        path = args.output.expanduser()
        if path.exists():
            parser.error(f"refusing to overwrite existing file: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        print(f"Wrote {path}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
