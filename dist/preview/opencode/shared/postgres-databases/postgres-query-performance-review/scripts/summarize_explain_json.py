#!/usr/bin/env python3
"""Summarize a PostgreSQL EXPLAIN (FORMAT JSON) document without executing SQL.

Requires Python 3.11 or newer and only the standard library. Reads JSON from one local file
or stdin and writes the summary only to stdout; it never modifies files, connects to
PostgreSQL, contacts the network, or executes SQL or external commands.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class NodeSummary:
    path: str
    node_type: str
    relation: str | None
    index: str | None
    plan_rows: float | None
    actual_rows: float | None
    loops: float | None
    estimate_ratio: float | None
    actual_rows_all_loops: float | None
    actual_total_time: float | None
    rows_removed: float
    shared_read_blocks: float
    temp_blocks: float
    sort_method: str | None
    sort_space_type: str | None
    sort_space_used_kb: float | None
    hash_batches: float | None


def number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def child_nodes(node: dict[str, Any]) -> list[dict[str, Any]]:
    plans = node.get("Plans", [])
    return [item for item in plans if isinstance(item, dict)] if isinstance(plans, list) else []


def walk(node: dict[str, Any], path: str = "0") -> Iterator[tuple[str, dict[str, Any]]]:
    yield path, node
    for index, child in enumerate(child_nodes(node)):
        yield from walk(child, f"{path}.{index}")


def ratio(estimated: float | None, actual: float | None) -> float | None:
    if estimated is None or actual is None:
        return None
    if estimated == 0:
        return math.inf if actual > 0 else 1.0
    if actual == 0:
        return 0.0
    return actual / estimated


def summarize_node(path: str, node: dict[str, Any]) -> NodeSummary:
    plan_rows = number(node.get("Plan Rows"))
    actual_rows = number(node.get("Actual Rows"))
    loops = number(node.get("Actual Loops"))
    rows_removed = sum(
        number(node.get(key)) or 0.0
        for key in (
            "Rows Removed by Filter",
            "Rows Removed by Join Filter",
            "Rows Removed by Index Recheck",
            "Rows Removed by Conflict Filter",
        )
    )
    temp_blocks = sum(
        number(node.get(key)) or 0.0 for key in ("Temp Read Blocks", "Temp Written Blocks")
    )
    return NodeSummary(
        path=path,
        node_type=str(node.get("Node Type", "Unknown")),
        relation=str(node["Relation Name"]) if "Relation Name" in node else None,
        index=str(node["Index Name"]) if "Index Name" in node else None,
        plan_rows=plan_rows,
        actual_rows=actual_rows,
        loops=loops,
        estimate_ratio=ratio(plan_rows, actual_rows),
        actual_rows_all_loops=(actual_rows * loops)
        if actual_rows is not None and loops is not None
        else None,
        actual_total_time=number(node.get("Actual Total Time")),
        rows_removed=rows_removed,
        shared_read_blocks=number(node.get("Shared Read Blocks")) or 0.0,
        temp_blocks=temp_blocks,
        sort_method=str(node["Sort Method"]) if "Sort Method" in node else None,
        sort_space_type=str(node["Sort Space Type"]) if "Sort Space Type" in node else None,
        sort_space_used_kb=number(node.get("Sort Space Used")),
        hash_batches=number(node.get("Hash Batches")),
    )


def extract_document(data: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    item: Any
    item = data[0] if isinstance(data, list) and data else data
    if not isinstance(item, dict):
        raise ValueError("expected an object or a non-empty array containing one object")
    plan = item.get("Plan", item)
    if not isinstance(plan, dict) or "Node Type" not in plan:
        raise ValueError("could not find a PostgreSQL plan object with Node Type")
    return item, plan


def noteworthy(nodes: list[NodeSummary]) -> list[NodeSummary]:
    def score(item: NodeSummary) -> tuple[float, float, float]:
        ratio_value = item.estimate_ratio
        ratio_score = (
            1_000_000.0
            if ratio_value == math.inf
            else max(
                ratio_value or 0.0, 1.0 / ratio_value if ratio_value not in (None, 0.0) else 0.0
            )
        )
        return (
            item.temp_blocks + item.shared_read_blocks,
            item.actual_total_time or 0.0,
            ratio_score,
        )

    return sorted(nodes, key=score, reverse=True)[:10]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path, help="EXPLAIN JSON file; use '-' for standard input.")
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable summary.")
    parser.add_argument(
        "--all-nodes",
        action="store_true",
        help="Include all nodes rather than the ten most noteworthy.",
    )
    args = parser.parse_args()

    try:
        text = sys.stdin.read() if str(args.plan) == "-" else args.plan.read_text(encoding="utf-8")
        document, root = extract_document(json.loads(text))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))

    nodes = [summarize_node(path, node) for path, node in walk(root)]
    selected = nodes if args.all_nodes else noteworthy(nodes)
    report = {
        "planningTimeMs": number(document.get("Planning Time")),
        "executionTimeMs": number(document.get("Execution Time")),
        "nodeCount": len(nodes),
        "hasActuals": any(item.actual_rows is not None for item in nodes),
        "nodes": [asdict(item) for item in selected],
        "caveats": [
            "Node total time can include child work; do not sum it across the tree.",
            "Actual rows are per loop; actualRowsAllLoops is a convenience multiplication.",
            "This offline summary cannot establish workload representativeness or query safety.",
        ],
    }

    if args.json:
        json.dump(report, sys.stdout, indent=2, allow_nan=False)
        print()
    else:
        print(f"planning_ms: {report['planningTimeMs']}")
        print(f"execution_ms: {report['executionTimeMs']}")
        print(f"nodes: {report['nodeCount']}; actuals: {report['hasActuals']}")
        for item in selected:
            relation = f" relation={item.relation}" if item.relation else ""
            index = f" index={item.index}" if item.index else ""
            ratio_text = (
                "n/a"
                if item.estimate_ratio is None
                else (
                    "infinite" if math.isinf(item.estimate_ratio) else f"{item.estimate_ratio:.2f}x"
                )
            )
            print(
                f"{item.path} {item.node_type}{relation}{index} "
                f"est={item.plan_rows} actual={item.actual_rows} loops={item.loops} "
                f"ratio={ratio_text} time_ms={item.actual_total_time} "
                f"read_blocks={item.shared_read_blocks:g} temp_blocks={item.temp_blocks:g} "
                f"removed={item.rows_removed:g}"
            )
        for caveat in report["caveats"]:
            print(f"caveat: {caveat}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
