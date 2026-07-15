from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = REPO_ROOT / "scripts" / "gui_vs_cli_full_workflow_smoke.py"


def _runner_module():
    spec = importlib.util.spec_from_file_location("gui_vs_cli_workflow_smoke_test", RUNNER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_authored_task_uses_upstream_seed_and_final_answer_evaluator() -> None:
    module = _runner_module()
    task = module._load_task(
        {
            "id": "calc_highest_average_salary_standard",
            "source_type": "standard",
            "paired_task_id": "calc_highest_average_salary",
            "agentlens_task_file": (
                "tasks/gui_vs_cli_authored/calc_highest_average_salary_standard/task.json"
            ),
        }
    )

    setup_task = module._task_for_environment(task)
    assert setup_task["id"] == "calc_employee_data_cleanup"

    passed, total, details = module._evaluate_task(
        None,
        task["app"],
        task,
        trajectory=[{"final_answer": "Engineering"}],
        traj_dir=REPO_ROOT,
    )
    assert (passed, total) == (1, 1)
    assert details[0]["passed"] is True


def test_authored_answer_evaluator_rejects_wrong_answer() -> None:
    module = _runner_module()
    task = module._load_task(
        {
            "id": "zotero_doi_year_lookup_standard",
            "source_type": "standard",
            "paired_task_id": "zotero_doi_year_lookup",
            "agentlens_task_file": (
                "tasks/gui_vs_cli_authored/zotero_doi_year_lookup_standard/task.json"
            ),
        }
    )

    passed, total, details = module._evaluate_task(
        None,
        task["app"],
        task,
        trajectory=[{"final_answer": "2016"}],
        traj_dir=REPO_ROOT,
    )
    assert (passed, total) == (0, 1)
    assert details[0]["passed"] is False
