from pathlib import Path

import yaml

from agentlens.schemas import load_experiment_config


def test_load_experiment_config_includes_task_files(tmp_path: Path) -> None:
    task_path = tmp_path / "tasks" / "task.yaml"
    task_path.parent.mkdir()
    task_path.write_text(
        yaml.safe_dump(
            {
                "id": "task_one",
                "benchmark": "custom",
                "task_id": "custom.task_one",
                "goal": "Answer the question.",
                "validator": "final_answer",
                "expected_answer": "ok",
                "answer_validator": "exact",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "batch.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "0.1",
                "id": "include_smoke",
                "models": [
                    {
                        "id": "model",
                        "provider": "openai",
                        "name": "gpt-test",
                    }
                ],
                "tool_harnesses": [
                    {
                        "id": "tool",
                        "runner": "custom",
                        "tier": "full_sandbox",
                        "tools": ["task.final_answer"],
                    }
                ],
                "memory_harnesses": [{"id": "memory", "kind": "none", "scope": "none"}],
                "task_files": ["tasks/task.yaml"],
                "tasks": [],
                "runs": [
                    {
                        "id": "run",
                        "model": "model",
                        "tool_harness": "tool",
                        "memory_harness": "memory",
                        "task": "task_one",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    config = load_experiment_config(config_path)

    assert [task.id for task in config.tasks] == ["task_one"]
    assert config.runs[0].task == "task_one"
