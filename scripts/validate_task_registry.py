#!/usr/bin/env python3
"""Validate prompt/evaluator invariants for a selected collection task set."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = REPO_ROOT / "tasks/task_inventory/collection_task_registry.jsonl"
DEFAULT_MANIFEST = REPO_ROOT / "configs/patches/balanced_gpt55_standard_grounded_task_set.yaml"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    registry = _load_registry(_resolve(args.registry))
    selected = _selected_task_ids(_resolve(args.manifest))
    errors: list[str] = []
    for task_id in selected:
        record = registry.get(task_id)
        if record is None:
            errors.append(f"selected task is missing from registry: {task_id}")
            continue
        errors.extend(_validate_record(record))

    if errors:
        print("Task registry preflight failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "Task registry preflight passed: "
        f"{len(selected)} selected canonical task(s) have valid paired prompt/evaluator contracts."
    )
    return 0


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _load_registry(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        task_id = str(record.get("canonical_task_id") or "")
        if not task_id:
            raise ValueError(f"{path}:{line_number}: missing canonical_task_id")
        if task_id in records:
            raise ValueError(f"{path}:{line_number}: duplicate canonical_task_id {task_id!r}")
        records[task_id] = record
    return records


def _selected_task_ids(path: Path) -> list[str]:
    manifest = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    selected = [
        str(task_id)
        for task_type in manifest.get("task_types", [])
        for task_id in task_type.get("tasks", [])
    ]
    if len(selected) != len(set(selected)):
        raise ValueError(f"{path}: selected canonical task ids are not unique")
    return selected


def _validate_record(record: dict[str, Any]) -> list[str]:
    label = str(record["canonical_task_id"])
    errors: list[str] = []
    paths = [REPO_ROOT / str(value) for value in record.get("task_files") or []]
    if not str(record.get("prompt_pair") or "").startswith("standard_grounded"):
        errors.append(f"{label}: selected task must have standard_grounded prompts")
        return errors
    if len(paths) != 2:
        errors.append(f"{label}: expected exactly two prompt source files, found {len(paths)}")
        return errors
    if missing := [str(path.relative_to(REPO_ROOT)) for path in paths if not path.exists()]:
        errors.append(f"{label}: missing task file(s): {', '.join(missing)}")
        return errors

    standard, grounded = (_load_task_file(path) for path in paths)
    for field in ("env", "verification", "expected_answer", "answer_validator", "start_url"):
        if field in standard or field in grounded:
            if standard.get(field) != grounded.get(field):
                errors.append(f"{label}: paired prompt files disagree on {field}")
    standard_canonical = _canonical_task(standard)
    grounded_canonical = _canonical_task(grounded)
    if standard_canonical and grounded_canonical and standard_canonical != grounded_canonical:
        errors.append(
            f"{label}: paired prompt files disagree on canonical task "
            f"({standard_canonical!r} != {grounded_canonical!r})"
        )
    if not _prompt_text(standard) or not _prompt_text(grounded):
        errors.append(f"{label}: one paired prompt file has no effective prompt text")
    return errors


def _load_task_file(path: Path) -> dict[str, Any]:
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"{path}: task file must decode to an object")
    return loaded


def _canonical_task(task: dict[str, Any]) -> str | None:
    extra = task.get("extra") or {}
    value = extra.get("canonical_task") or task.get("paired_task_id") or task.get("task_id")
    return str(value) if value else None


def _prompt_text(task: dict[str, Any]) -> str:
    return str(task.get("task_grounding") or task.get("goal") or task.get("task") or "").strip()


if __name__ == "__main__":
    raise SystemExit(main())
