# High-Delta Standard/Grounded GUI-vs-CLI Task Pairs

This note identifies matched GUI-vs-CLI task pairs where the grounded prompt is
meaningfully different from the standard prompt. Use this list when the
experiment is specifically about whether procedural grounding changes behavior,
not just task success.

Source catalogs:

```text
tasks/gui_vs_cli/tasks_standard.jsonl
tasks/gui_vs_cli/tasks_grounding.jsonl
tasks/gui_vs_cli/task_pairs.jsonl
```

Prompt-delta strength:

| Level | Meaning | Use |
| --- | --- | --- |
| `0` | Grounded prompt is effectively the same as standard. | Avoid for grounded-vs-standard behavior claims. |
| `1` | Small clarification or minor UI hint. | Use only when the app/category is important. |
| `2` | Clear additional procedural guidance. | Good candidate. |
| `3` | Strong procedure: menus, object locations, exact interaction sequence, or detailed constraints. | Best candidate. |

Already-run GUI-vs-CLI pilot pairs:

```text
gimp_add_alpha_transparent
drawio_aws_cloud_arch
godot4_full_enemy_controller
calc_3d_quarterly_consolidation
impress_add_entry_animations_to_bullets
chrome_multi_tab_wikipedia
```

Do not treat these as unused high-delta candidates. They remain useful for
comparisons against already-collected Opus/GPT runs.

## Recommended Next Candidates

| Task ID | App | Category | Delta | Why it is useful | Caveat |
| --- | --- | --- | ---: | --- | --- |
| `gimp_rotate_180_tiff_export` | GIMP | image editing | 3 | Standard is a terse rotate/export task; grounded adds image structure, menu path, output dimensions. | Simple task, likely ceiling effects. |
| `gimp_fill_bucket_background` | GIMP | image editing | 2 | Grounded describes layers and transparent-background replacement procedure. | Still relatively short. |
| `drawio_restyle_erd` | draw.io | diagram editing | 3 | Grounded names object ids, fill colors, added entities, and edge operations explicitly. | draw.io has failed in recent runs; use after harness diagnosis. |
| `drawio_fix_and_color_workflow` | draw.io | diagram editing | 2 | Grounded turns a compact diagram-edit request into explicit object/color/edge operations. | Same draw.io caveat. |
| `calc_text_parse_contacts` | LibreOffice Calc | data/spreadsheet analysis | 2 | Grounded includes concrete formulas and fill-down procedure; most other Calc grounded prompts are near-identical to standard. | Good Calc candidate. |
| `cloudcompare_gap_csf_ground_filter` | CloudCompare | point-cloud visualization | 3 | Grounded adds plugin path, expected geometry, export target, and what not to export. | Requires CloudCompare verifier/image stability. |
| `cloudcompare_obj_to_mesh_xyz_asc` | CloudCompare | point-cloud / mesh conversion | 2 | Grounded clarifies mesh-vs-vertices export distinction and exact output formats. | Good visual-spatial candidate. |
| `freecad_export_multi_format` | FreeCAD | CAD / visual-spatial | 3 | Grounded specifies selecting the object, export menu, file types, filenames, and target directory. | More programmatic alternatives may be strong. |
| `freecad_create_parametric_box` | FreeCAD | CAD / visual-spatial | 3 | Grounded adds workbench/menu path and property-panel instructions. | Fairly deterministic. |
| `krita_wrap_around_and_mirror` | Krita | image/design editing | 2 | Grounded adds menu/shortcut and settings-location hints. | More configuration than artifact creation. |
| `obs_create_scene_collection` | OBS Studio | visual media setup | 2 | Grounded expands scene/source creation and names acceptable source variants. | OBS GUI may have startup dialogs. |
| `zotero_gap_import_ris_file` | Zotero | information management | 2 | Grounded adds File > Import procedure and import-dialog guidance. | Not visual analytics, but useful occupational workflow. |

## Lower-Priority But Relevant

| Task ID | App | Delta | Reason |
| --- | --- | ---: | --- |
| `impress_consolidate_two_decks` | LibreOffice Impress | 2 | Good presentation task, but recent Impress runs were slow/noisy. |
| `impress_add_transitions_to_slides` | LibreOffice Impress | 2 | Good if we keep presentation tasks, but lower priority after recent runtime issues. |
| `chrome_wikipedia_history_trail` | Chrome | 1 | Best remaining Chrome grounded pair, but the prompt delta is small. Use only if Chrome coverage is required. |
| `audacity_add_chapter_labels` | Audacity | 3 | Very strong procedural delta; not in our current target app set, but useful as a clean high-delta control. |

## Practical Sampling Rule

For early grounded-vs-standard behavior tests:

1. Prefer Level `2` or `3` pairs.
2. Keep one task per app/category before increasing repeats.
3. Avoid drawing conclusions from Level `0` or `1` pairs, because the prompt
   manipulation is weak.
4. Keep standard and grounded variants matched by `paired_task_id`.
5. Keep the model, agent style, screen size, verifier, and Docker image fixed
   within each pair.

