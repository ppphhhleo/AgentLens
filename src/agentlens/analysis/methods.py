from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from agentlens.analysis.actonomy import analyze_actonomy, write_actonomy_outputs
from agentlens.analysis.canonical import resolve_trajectory_paths
from agentlens.analysis.llm_refinement import refine_methods_with_llm
from agentlens.analysis.wang_workflow import analyze_wang_workflow, write_wang_outputs


def analyze_trajectory_methods(
    trajectory_path: Path,
    output_dir: Path,
    *,
    state_diff_threshold: float = 8000.0,
    annotation_mode: str = "rule",
    llm_provider: str = "auto",
    llm_model: str | None = None,
) -> dict[str, Any]:
    """Run Wang-style and Act-onomy-style methods over one trajectory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    _clear_legacy_flat_outputs(output_dir)
    layout = _prepare_single_run_layout(output_dir, trajectory_path)
    wang = analyze_wang_workflow(
        trajectory_path,
        state_diff_threshold=state_diff_threshold,
    )
    actonomy = analyze_actonomy(trajectory_path)
    llm_meta = None
    if annotation_mode == "llm":
        try:
            refined = refine_methods_with_llm(
                wang,
                actonomy,
                provider=llm_provider,
                model=llm_model,
            )
            wang = refined["wang"]
            actonomy = refined["actonomy"]
            llm_meta = refined["llm"]
            (layout["llm"] / "response.raw.txt").write_text(
                refined["raw"],
                encoding="utf-8",
            )
            llm_meta["raw_response_path"] = str(layout["llm"] / "response.raw.txt")
        except Exception as exc:  # noqa: BLE001
            llm_meta = {
                "annotation_mode": "llm_failed_rule_fallback",
                "provider": llm_provider,
                "model": llm_model,
                "error": str(exc),
            }
    canonical_path = layout["canonical"] / "events.jsonl"
    _write_many_path(canonical_path, wang["canonical_events"])
    wang_paths = write_wang_outputs(wang, layout["wang"])
    actonomy_paths = write_actonomy_outputs(actonomy, layout["actonomy"])
    manifest = {
        "trajectory_path": str(trajectory_path.resolve()),
        "output_dir": str(output_dir.resolve()),
        "annotation_mode": annotation_mode,
        "llm": llm_meta,
        "layout": {
            "original": {
                "source_trajectory_path": str(trajectory_path.resolve()),
                "copied_trajectory_path": str(layout["original"] / "trajectory.json"),
                "source_metadata_path": str(layout["original"] / "source.json"),
            },
            "canonical": {
                "description": "Framework-neutral action-bearing turns extracted from the original trajectory.",
                "paths": {"events": str(canonical_path)},
            },
            "wang": {
                "description": "Wang-style workflow induction outputs.",
                "dir": str(layout["wang"]),
            },
            "actonomy": {
                "description": "Act-onomy-style per-turn codebook labels and named behavior sessions.",
                "dir": str(layout["actonomy"]),
            },
            "llm": {
                "description": "Raw LLM response used to refine phase names and annotations, when enabled.",
                "dir": str(layout["llm"]),
            },
        },
        "methods": {
            "wang_workflow": {
                "description": "Structure-first workflow induction: action nodes -> state segments -> workflow steps.",
                "summary": wang["summary"],
                "paths": {name: str(path) for name, path in wang_paths.items()},
            },
            "actonomy": {
                "description": "Codebook-first behavior coding: turns -> Act-onomy labels -> behavior sessions/profile.",
                "summary": actonomy["profile"],
                "paths": {name: str(path) for name, path in actonomy_paths.items()},
            },
        },
    }
    manifest_path = output_dir / "method_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_output_readme(output_dir, manifest)
    return {
        "manifest": manifest,
        "manifest_path": manifest_path,
        "wang": wang,
        "actonomy": actonomy,
        "paths": {
            "original_trajectory": layout["original"] / "trajectory.json",
            "canonical_events": canonical_path,
            **{f"wang_{name}": path for name, path in wang_paths.items()},
            **{f"actonomy_{name}": path for name, path in actonomy_paths.items()},
            "manifest": manifest_path,
        },
    }


def process_method_outputs(
    inputs: list[Path],
    output_dir: Path,
    *,
    state_diff_threshold: float = 8000.0,
) -> dict[str, Path]:
    """Run both methods on many trajectories and write aggregate JSONL outputs."""
    trajectory_paths = resolve_trajectory_paths(inputs)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "canonical_events": output_dir / "canonical_events.jsonl",
        "wang_action_nodes": output_dir / "wang_action_nodes.jsonl",
        "wang_state_segments": output_dir / "wang_state_segments.jsonl",
        "wang_workflow_steps": output_dir / "wang_workflow_steps.jsonl",
        "wang_summaries": output_dir / "wang_summaries.jsonl",
        "actonomy_annotations": output_dir / "actonomy_annotations.jsonl",
        "actonomy_sessions": output_dir / "actonomy_sessions.jsonl",
        "actonomy_profiles": output_dir / "actonomy_profiles.jsonl",
        "method_manifest": output_dir / "method_manifest.json",
    }
    handles = {name: path.open("w", encoding="utf-8") for name, path in paths.items() if name != "method_manifest"}
    manifest_runs = []
    try:
        for trajectory_path in trajectory_paths:
            wang = analyze_wang_workflow(
                trajectory_path,
                state_diff_threshold=state_diff_threshold,
            )
            actonomy = analyze_actonomy(trajectory_path)
            _write_many(handles["canonical_events"], wang["canonical_events"])
            _write_many(handles["wang_action_nodes"], wang["action_nodes"])
            _write_many(handles["wang_state_segments"], wang["state_segments"])
            _write_many(handles["wang_workflow_steps"], wang["workflow_steps"])
            handles["wang_summaries"].write(json.dumps(wang["summary"], ensure_ascii=False) + "\n")
            _write_many(handles["actonomy_annotations"], actonomy["turns"])
            _write_many(handles["actonomy_sessions"], actonomy["sessions"])
            handles["actonomy_profiles"].write(
                json.dumps(actonomy["profile"], ensure_ascii=False) + "\n"
            )
            manifest_runs.append(
                {
                    "trajectory_path": str(trajectory_path),
                    "wang": wang["summary"],
                    "actonomy": actonomy["profile"],
                }
            )
    finally:
        for handle in handles.values():
            handle.close()

    paths["method_manifest"].write_text(
        json.dumps(
            {
                "trajectory_count": len(trajectory_paths),
                "state_diff_threshold": state_diff_threshold,
                "outputs": {name: str(path) for name, path in paths.items()},
                "runs": manifest_runs,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return paths


def _write_many(handle, records: list[dict[str, Any]]) -> None:
    for record in records:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _write_many_path(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        _write_many(handle, records)


def _prepare_single_run_layout(output_dir: Path, trajectory_path: Path) -> dict[str, Path]:
    layout = {
        "original": output_dir / "original",
        "canonical": output_dir / "canonical",
        "wang": output_dir / "wang",
        "actonomy": output_dir / "actonomy",
        "llm": output_dir / "llm",
    }
    for path in layout.values():
        path.mkdir(parents=True, exist_ok=True)
    copied_trajectory_path = layout["original"] / "trajectory.json"
    if trajectory_path.resolve() != copied_trajectory_path.resolve():
        shutil.copy2(trajectory_path, copied_trajectory_path)
    source = {
        "source_trajectory_path": str(trajectory_path.resolve()),
        "copied_trajectory_path": str(copied_trajectory_path.resolve()),
        "source_directory": str(trajectory_path.parent.resolve()),
        "screenshots_directory": str((trajectory_path.parent / "screenshots").resolve())
        if (trajectory_path.parent / "screenshots").exists()
        else None,
    }
    (layout["original"] / "source.json").write_text(
        json.dumps(source, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return layout


def _write_output_readme(output_dir: Path, manifest: dict[str, Any]) -> None:
    layout = manifest["layout"]
    text = f"""# AgentLens Method Comparison Output

Original captured trajectory:
- Source: `{layout["original"]["source_trajectory_path"]}`
- Copied input: `original/trajectory.json`
- Source metadata: `original/source.json`

Processed trajectory layers:
- `canonical/events.jsonl`: normalized action-bearing turns extracted from the original trajectory.
- `wang/`: Wang-style action nodes, state segments, workflow steps, and summaries.
- `actonomy/`: Act-onomy-style per-turn annotations, aggregated sessions, profile, and summary.
- `llm/`: raw LLM response used for semantic refinement when LLM mode is enabled.

Report files:
- `method_comparison.html`: browser-readable per-turn alignment table.
- `method_manifest.json`: machine-readable manifest linking every file above.
"""
    (output_dir / "README.md").write_text(text, encoding="utf-8")


def _clear_legacy_flat_outputs(output_dir: Path) -> None:
    legacy_names = {
        "actonomy_annotations.jsonl",
        "actonomy_profile.json",
        "actonomy_sessions.jsonl",
        "actonomy_summary.txt",
        "canonical_events.jsonl",
        "llm_response.raw.txt",
        "wang_action_nodes.jsonl",
        "wang_state_segments.jsonl",
        "wang_summary.json",
        "wang_workflow.json",
        "wang_workflow.txt",
        "wang_workflow_steps.jsonl",
    }
    for name in legacy_names:
        path = output_dir / name
        if path.exists() and path.is_file():
            path.unlink()
