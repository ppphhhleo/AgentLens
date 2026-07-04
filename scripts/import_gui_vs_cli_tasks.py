from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO_ROOT / "third_party" / "gui-vs-cli" / "task_generator"
DEFAULT_OUTPUT = REPO_ROOT / "tasks" / "gui_vs_cli"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import gui-vs-cli standard and grounded task catalogs."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source = args.source
    output = args.output
    output.mkdir(parents=True, exist_ok=True)

    standard = _load_task_dir(
        source / "tasks",
        source_type="standard",
        github_prefix="task_generator/tasks",
    )
    grounded = _load_task_dir(
        source / "tasks_grounding",
        source_type="grounded_prompt",
        github_prefix="task_generator/tasks_grounding",
    )

    _write_jsonl(output / "tasks.jsonl", standard)
    _write_jsonl(output / "tasks_standard.jsonl", standard)
    _write_jsonl(output / "tasks_grounding.jsonl", grounded)
    pairs = _build_pairs(standard, grounded)
    _write_jsonl(output / "task_pairs.jsonl", pairs)

    print(f"standard={len(standard)} -> {output / 'tasks.jsonl'}")
    print(f"grounded_prompt={len(grounded)} -> {output / 'tasks_grounding.jsonl'}")
    print(f"pairs={len(pairs)} -> {output / 'task_pairs.jsonl'}")
    return 0


def _load_task_dir(
    path: Path,
    *,
    source_type: str,
    github_prefix: str,
) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"missing gui-vs-cli task directory: {path}")

    records: list[dict[str, Any]] = []
    for task_file in sorted(path.glob("*/task.json")):
        record = json.loads(task_file.read_text())
        task_id = record["id"]
        record["source_type"] = source_type
        record["paired_task_id"] = task_id
        record["github_task_path"] = f"{github_prefix}/{task_file.parent.name}"
        records.append(record)
    return records


def _build_pairs(
    standard: list[dict[str, Any]],
    grounded: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    standard_by_id = {record["id"]: record for record in standard}
    pairs: list[dict[str, Any]] = []
    for grounded_record in grounded:
        task_id = grounded_record["id"]
        standard_record = standard_by_id.get(task_id)
        if standard_record is None:
            raise ValueError(f"grounded task has no standard counterpart: {task_id}")
        pairs.append(
            {
                "id": task_id,
                "app": grounded_record.get("app"),
                "standard_task_id": task_id,
                "grounded_task_id": task_id,
                "standard_github_task_path": standard_record.get("github_task_path"),
                "grounded_github_task_path": grounded_record.get("github_task_path"),
                "same_base_task_text": standard_record.get("task")
                == grounded_record.get("task"),
                "has_task_grounding": bool(grounded_record.get("task_grounding")),
            }
        )
    return pairs


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            f.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
