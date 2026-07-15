# Task Candidate Matrix

This matrix is a working sampling list, not a final task taxonomy or behavior
codebook. Use these simple task-type labels only to plan trajectory collection.
Naming (2026-07-15): `SP` (specified production) · `SF` (text/data
sensemaking) · `SV` (visual/spatial sensemaking) · `OP` (open-ended
production). An app sets a modality prior; the task deliverable decides the
type.

Near-term priority:

1. GUI-vs-CLI tasks.
2. DOMSteer TensorFlow Playground tasks.
3. Hosted WebArena tasks when URLs and success criteria arrive.
4. TheAgentCompany after adapter/data/evaluator details are ready.

## Cognitive Task Types

| ID | Name | Primary Cognitive Operation | Graded Deliverable | Epistemic Bottleneck | Canonical Sources |
| --- | --- | --- | --- | --- | --- |
| `SP` | Specified production | Produce a substantially prescribed state or artifact. | State change or artifact with specified content, structure, or settings. | Correct sequencing and execution of a specification. | Form filling; fixed image edits; specified diagrams. |
| `SF` | Text/data sensemaking | Search, filter, cross-reference, or synthesize a fact/judgment from text or number-readable space. | Answer or synthesis. | Search cost, source verification, integration. | WebArena information seeking; Wikipedia multi-tab; Calc formula analytics. |
| `SV` | Visual/spatial sensemaking | Derive an answer or judgment through perceptual decoding of rendered graphics, image content, layouts, or spatial structure. | Answer or judgment. | Reading/comparing values off visuals; spatial inspection. | DataVoyager charts; embedded-chart Calc; point-cloud inspection. |
| `OP` | Open-ended production | Produce an artifact or configuration whose form is underdetermined; multiple qualitatively different solutions can satisfy the task. | Artifact, configuration, scene, model, or document. | Iterative refinement, generative search, and deciding when the result is sufficient. | Godot controller design; TF Playground network design; open visual composition. |

Decision rules:

1. If the deliverable's form is underdetermined and the actor must choose a
   design, composition, or configuration, label it `OP`. A task can be
   open-ended even when it has an objective evaluator.
2. Otherwise, if the primary deliverable is an answer or judgment, label it
   `SV` when the answer requires perceptual decoding of rendered graphics,
   spatial structure, image content, or chart-like visual encodings. Label it
   `SF` when the answer is reachable through text, number, formula, grid,
   or DOM representations.
3. Otherwise, label it `SP`: the requested state or artifact is specified
   enough that the main challenge is executing the requested change correctly.

`SF` can carry sublabels such as `foraging` and `analytic`, but these are not
separate top-level types. The `SF` vs `SV` split is important for channel
substitution: in `SF`, a text-channel route can be equivalent; in `SV`, a
text-channel shortcut is a meaningful visual-bypass condition.

## Immediate Collection Shortlist

Use this shortlist before expanding the task inventory. All entries have a
standard/grounded pair with a meaningful prompt delta, except where the table
explicitly calls for one startup smoke. It deliberately favors tasks with an
available seed and deterministic final answer or upstream verifier.

| Type | Task | App | Why now | Readiness |
| --- | --- | --- | --- | --- |
| `SF` | `wikipedia_birth_order` | Chrome / Wikipedia | Small, controlled cross-page answer task. | `ready_smoke` |
| `SF` | `calc_highest_average_salary` | LibreOffice Calc | Text/number analytic answer over an existing GUI-vs-CLI seed. | `ready_smoke` |
| `SF` | `zotero_doi_year_lookup` | Zotero | Textual library lookup over an existing GUI-vs-CLI seed. | `ready_smoke` |
| `SV` | DataVoyager T1 `datavoyager_most_fuel_efficient` | DataVoyager | Answer-verifiable visual analytics. | `ready` |
| `SV` | DataVoyager T2 `datavoyager_origin_horsepower_range` | DataVoyager | Answer-verifiable grouped-range comparison. | `ready` |
| `SV` | DataVoyager T3 `datavoyager_europe_hp_gt_100_four_cyl` | DataVoyager | Answer-verifiable filter/count comparison. | `ready` |
| `SP` | `gimp_add_alpha_transparent` | GIMP | Existing seed, paired prompts, and deterministic image verifier. | `ready` |
| `OP` | `godot4_full_enemy_controller` | Godot 4 | Existing paired seed and 10 deterministic script checks. Treat it as an early code-artifact proxy, not a broad creativity claim. | `ready` |

Quick additions after one no-model application smoke:

| Type | Task | App | Why defer it slightly |
| --- | --- | --- | --- |
| `SP` | `calc_text_parse_contacts` | LibreOffice Calc | Strong paired prompt delta and deterministic verifier, but not yet in an active AgentLens batch config. |
| `SP` | `drawio_aws_cloud_arch` | draw.io | Strong pair and verifier, but prior draw.io attempts failed; repair the app/harness startup before using it as a main condition. |

This is intentionally not yet a balanced 3-by-4 factorial sample: the three
ready `SF` and `SV` tasks are strong, while a defensible third `SP` and two
additional `OP` tasks still need smoke/evaluator work.

## Available Tasks And Readiness

Readiness labels are operational, not claims about task difficulty:

| Status | Meaning |
| --- | --- |
| `ready` | Task, environment, and evaluator are available for collection. |
| `ready_smoke` | Task and evaluator are available; run one no-model and one model smoke first. |
| `ready_with_startup_check` / `ready_check_required` | The task exists, but app launch or seed-state behavior needs a fresh control check. |
| `needs_evaluator` | Environment/task exists; do not make outcome claims until an evaluator is implemented. |
| `requires_hosted_urls` | Benchmark task/config exists but its web service endpoint or credentials are unavailable. |
| `candidate` | A useful upstream seed exists, but the answer/artifact overlay or evaluator is not yet defined. |

### `SF`: Text/Data Sensemaking

| Readiness | Benchmark | App / Domain | Task | Brief Detail |
| --- | --- | --- | --- | --- |
| ready_smoke | Custom web | Chrome / Wikipedia | `wikipedia_birth_order` | Cross-page birth-date comparison; answer is text evidence. |
| ready_smoke | AgentLens-authored on GUI-vs-CLI seed | LibreOffice Calc | `calc_highest_average_salary` | Compute/compare department averages from a grid; answer is `Engineering`. |
| ready_smoke | AgentLens-authored on GUI-vs-CLI seed | Zotero | `zotero_doi_year_lookup` | Find an item by DOI and return its year; answer is `2018`. |
| requires_hosted_urls | BrowserGym WebArena | Shopping admin | `browsergym/webarena.0` | Answer the top-selling product in 2022 from text/numeric admin data. |
| requires_hosted_urls | BrowserGym WebArena | Shopping | `browsergym/webarena.21` | Extract reviewers who mention small ear cups. |
| requires_hosted_urls | BrowserGym WebArena | Reddit/forum | `browsergym/webarena.67` | Synthesize recommended book names from forum posts. |
| candidate | GUI-vs-CLI seed | LibreOffice Writer / PDF | termination-clause lookup | Answer a date from seeded document text. |
| candidate | GUI-vs-CLI seed | Desktop file system | PDF-size or policy-term lookup | Answer from file metadata or document text. |

### `SV`: Visual/Spatial Sensemaking

| Readiness | Benchmark | App / Domain | Task | Brief Detail |
| --- | --- | --- | --- | --- |
| ready | DOMSteer | DataVoyager | `datavoyager_most_fuel_efficient` | Visual/data exploration to identify the most fuel-efficient car. |
| ready | DOMSteer | DataVoyager | `datavoyager_origin_horsepower_range` | Compare grouped ranges to identify origin with widest horsepower span. |
| ready | DOMSteer | DataVoyager | `datavoyager_europe_hp_gt_100_four_cyl` | Filter and count a chart/data subset. |
| needs_evaluator | DOMSteer | TensorFlow Playground | `tfplayground_discretize_effect` | Locate and explain a visible control effect. |
| needs_evaluator | DOMSteer | TensorFlow Playground | `tfplayground_misclassified_point` | Inspect a rendered decision boundary and identify a misclassified point. |
| candidate | GUI-vs-CLI seed | CloudCompare | cluster inspection | Reuse `cloudcompare_gap_label_connected_components`; author a final-answer task such as identifying the larger spatial cluster. |
| candidate | GUI-vs-CLI seed | LibreOffice Calc | embedded-chart question | Answer a chart-reading question over a fixed spreadsheet/chart state. |
| requires_hosted_urls | BrowserGym VisualWebArena | Shopping / forum / classifieds | `.450`, `.352`, `.251`, `.101` | Image-dependent product, person, subreddit, and city/painting questions. |

### `SP`: Specified Production

| Readiness | Benchmark | App / Domain | Task | Brief Detail |
| --- | --- | --- | --- | --- |
| ready | GUI-vs-CLI | GIMP | `gimp_add_alpha_transparent` | Prescribed background/transparency edit. |
| ready_with_startup_check | GUI-vs-CLI | draw.io | `drawio_aws_cloud_arch` | Exact vertices, labels, colors, and edge requirements. |
| ready_not_useful_for_prompt_effect | GUI-vs-CLI | LibreOffice Calc | `calc_3d_quarterly_consolidation` | Prescribed workbook construction; source prompt pair has delta 0. |
| ready_not_useful_for_prompt_effect | GUI-vs-CLI | Chrome | `chrome_multi_tab_wikipedia` | Specified tab/bookmark state; source prompt pair has delta 0. |
| ready_check_required | GUI-vs-CLI | Zoom / Zotero / Obsidian | preference, child-note, and cross-link tasks | Prescribed application state; run a fresh seed/app control first. |
| candidate | GUI-vs-CLI | Chrome / CloudCompare / Writer | form fill, point-cloud transforms, find/replace | Upstream environments and artifact verifiers exist; select only needed baseline tasks. |
| requires_hosted_urls | Hosted WebArena | Shopping / forum | cart, purchase, or prescribed reply/state tasks | Classify as `do-spec` when success is a target website state. |

### `OP`: Open-Ended Production

| Readiness | Benchmark | App / Domain | Task | Brief Detail |
| --- | --- | --- | --- | --- |
| ready | GUI-vs-CLI | Godot 4 | `godot4_full_enemy_controller` | Multiple valid controller implementations satisfy the required behavior. |
| candidate | GUI-vs-CLI | Godot 4 | `godot4_implement_gdscript_class` | A second code/configuration design case; assess evaluator sensitivity before use. |
| ready_after_reset_smoke | DOMSteer | TensorFlow Playground | regression/classification network design | Open network design with final-state screenshot LLM judgment; fresh-profile reset smoke is still required. |
| candidate | GUI-vs-CLI | GIMP / draw.io | open visual composition | Do not use fixed-coordinate or exact-shape tasks; require a design brief and rubric. |
| candidate | TheAgentCompany | workplace documents | occupational document revision | Requires adapter, seed, and rubric. |

## Detailed Candidate Records

| Priority | Type | Benchmark | App / Domain | Task ID | Brief Detail | Status / Notes |
| --- | --- | --- | --- | --- | --- | --- |
| P0 | SV | DOMSteer | DataVoyager | `datavoyager_most_fuel_efficient` | Identify the most fuel-efficient car from visual/data exploration. | Runnable; final-answer evaluator. |
| P0 | SV | DOMSteer | DataVoyager | `datavoyager_origin_horsepower_range` | Determine which origin has widest horsepower range. | Runnable; final-answer evaluator. |
| P0 | SV | DOMSteer | DataVoyager | `datavoyager_europe_hp_gt_100_four_cyl` | Count European cars with horsepower > 100 and four cylinders. | Runnable; final-answer evaluator. |
| P0 | SP | GUI-vs-CLI | LibreOffice Calc | `calc_conditional_formatting_sales_heatmap` | Apply red-green color scale and high-total highlighting to a sales table. | Relabeled P: *applying* formatting is a specified state change — it produces a visual, does not decode one. SV variant: ask "which region is hottest per the heatmap?" |
| P0 | SP | GUI-vs-CLI | LibreOffice Calc | `calc_3d_quarterly_consolidation` | Consolidate quarterly sheets and compute annual/prior-year/YoY fields. | Relabeled P: fully specified build recipe (deliverable = target sheet state, 22 checks), no answer deliverable. SF-analytic variant: ask a question answered from the resulting grid. |
| P0 | SP | GUI-vs-CLI | Zotero | `zotero_add_note_to_item` | Find a research item and add a child note. | Relabeled P: find-then-modify with a specified end state. SF variant exists in sensemaking text/data list (DOI lookup). Config added; standard + grounded. |
| P0 | SP | GUI-vs-CLI | Obsidian | `obsidian_add_links_to_existing` | Add cross-links and a map-of-content note across a vault. | Relabeled P: the task enumerates the links and map-of-content state. Not SF: deliverable is vault state, not an answer. Config added. |
| P0 | SP | GUI-vs-CLI | Zoom | `zoom_mute_mic_on_join` | Change setting so microphone is muted when joining meetings. | Config added; standard + AgentLens-curated grounded. |
| P0 | SP | GUI-vs-CLI | GIMP | `gimp_add_alpha_transparent` | Remove white background by following a specified edit operation. | Existing task option; deterministic image-editing state change. |
| P0 | SP | GUI-vs-CLI | draw.io | `drawio_aws_cloud_arch` | Extend an AWS architecture diagram with labeled components. | Relabeled P: exact components, labels, colors, and edges are specified. Existing task option; draw.io startup needs a readiness check. |
| P0 | OP | GUI-vs-CLI | Godot 4 | `godot4_full_enemy_controller` | Create an enemy controller script/class in a game project. | Existing task option; code-like creative artifact. |
| P1 | SV | DOMSteer | TensorFlow Playground | `tfplayground_discretize_effect` | Locate and explain the effect of the Discretize toggle. | Task YAML added; manual/rubric required. |
| P1 | SV | DOMSteer | TensorFlow Playground | `tfplayground_misclassified_point` | Locate one misclassified test point. | Task YAML added; manual/rubric required. |
| P1 | OP | DOMSteer | TensorFlow Playground | `tfplayground_regression_two_datasets` | Design a NN configuration that works on two regression datasets. | Final-state screenshot LLM judge: visible loss below 0.01; fresh-profile reset smoke required. |
| P1 | OP | DOMSteer | TensorFlow Playground | `tfplayground_classification_four_datasets` | Design a NN configuration that works on four classification datasets. | Final-state screenshot LLM judge: visible loss below 0.01 plus clear boundary; fresh-profile reset smoke required. |
| P1 | SP | GUI-vs-CLI | Chrome | `chrome_multi_tab_wikipedia` | Open 4 pages in tabs and bookmark 2. | Relabeled P: the task text is a tab/bookmark checklist — no synthesis (see sensemaking text/data multi-hop variant for a true SF replacement). |
| P1 | SP | GUI-vs-CLI | Chrome | `chrome_form_fill_httpbin` | Fill a browser form and submit/request expected state. | Candidate; good basic web baseline. |
| P1 | SP | GUI-vs-CLI | Chrome | `chrome_wikipedia_research` | Open/bookmark/close specified Wikipedia tabs. | Candidate; despite its name, the deliverable is a tab/bookmark checklist, not answer synthesis. |
| P1 | SP | GUI-vs-CLI | CloudCompare | `cloudcompare_colorize_add_rgb` | Add RGB colorization to a point cloud. | Relabeled P: colorize = specified state change. SV variant: inspect-and-answer ("which cluster is densest?"). |
| P1 | SP | GUI-vs-CLI | CloudCompare | `cloudcompare_scale_cloud_2x` | Scale a point cloud 2x and verify geometry. | Relabeled P: transform-to-spec. Grounded variant available. |
| P1 | SP | GUI-vs-CLI | draw.io | `drawio_uml_class_diagram` | Create a UML-like class diagram with nodes/edges. | Candidate; required nodes and edges are specified. |
| P1 | SP | GUI-vs-CLI | draw.io | `drawio_incident_runbook` | Create a two-page incident-response process diagram. | Candidate; required pages, nodes, and edges are specified. |
| P1 | SP | GUI-vs-CLI | LibreOffice Writer | `writer_report_restructure` | Restructure and format an existing report. | Fully specified headings, bold text, table contents, and save state; no upstream grounded counterpart. |
| P1 | SP | GUI-vs-CLI | LibreOffice Writer | `libreoffice_writer_grant_proposal_v2` | Construct a grant proposal with exact headings, tables, dates, margins, header, and output path. | Deterministic upstream verifier; an AgentLens-local grounded overlay preserves the same environment and checks. |
| P1 | SP | GUI-vs-CLI | LibreOffice Writer | `libreoffice_writer_find_replace` | Find/replace contract terms and dates. | Candidate; specified text state change. |
| P1 | SP | GUI-vs-CLI | LibreOffice Calc | `calc_employee_data_cleanup` | Concatenate names, create department summary formulas. | Relabeled P: transformation to a specified table state. SF-analytic variant in sensemaking text/data list (highest-avg-salary question). |
| P1 | SP | GUI-vs-CLI | LibreOffice Calc | `calc_text_parse_contacts` | Parse contact strings into structured columns. | Relabeled P: parse-to-specified-columns is a state change. |
| P1 | OP | GUI-vs-CLI | Godot 4 | `godot4_implement_gdscript_class` | Implement a GDScript class from requirements. | Candidate; code-like artifact. |
| P1 | SP | GUI-vs-CLI | Godot 4 | `godot4_attach_script_to_node` | Attach a script resource to a scene node. | Candidate; specified project state change. |
| P2 | SP | Hosted WebArena | Shopping / Amazon-like | `webarena_shopping_basic_requires_hosted_url` | Search/add/compare a product in hosted shopping site. | Requires hosted URL and success criteria; label P if target is purchase/cart state. |
| P2 | SF (foraging) | Hosted WebArena | Shopping / Amazon-like | TBD shopping comparison task | Compare product specs/reviews/price/shipping under constraints. | Requires hosted URL and task prompt. |
| P2 | SF (foraging) | Hosted WebArena | Forum / Reddit-like | `webarena_forum_basic_requires_hosted_url` | Search/read forum content or answer from thread context. | Requires hosted URL and success criteria. |
| P2 | SF (foraging) | Hosted WebArena | Forum / Reddit-like | TBD forum synthesis task | Find relevant post/comment and synthesize answer or reply. | Requires hosted URL and task prompt. |
| P1 | SF (analytic) | BrowserGym WebArena | Shopping admin | `browsergym/webarena.0` | Answer the top-1 best-selling product in 2022. | Task/config exists; requires deployed WebArena sites and `WA_*` URLs. |
| P1 | SF (foraging) | BrowserGym WebArena | Shopping | `browsergym/webarena.21` | List reviewers who mention small ear cups. | Task/config exists; requires deployed WebArena sites and `WA_*` URLs. |
| P1 | SF (foraging) | BrowserGym WebArena | Reddit/forum | `browsergym/webarena.67` | Extract book names from top posts recommending a single book. | Task/config exists; requires deployed WebArena sites and `WA_*` URLs. |
| P1 | SV | BrowserGym VisualWebArena | Shopping | `browsergym/visualwebarena.450` | Identify red products in shopping results and report price range. | Task/config exists; requires deployed VisualWebArena sites and URLs. |
| P1 | SV | BrowserGym VisualWebArena | Reddit/forum | `browsergym/visualwebarena.352` | Identify person in red jacket image, then answer birth year via Wikipedia. | Task/config exists; requires deployed VisualWebArena sites and URLs. |
| P1 | SV | BrowserGym VisualWebArena | Reddit/forum | `browsergym/visualwebarena.251` | Use input image as task specification and navigate to similar subreddit. | Task/config exists; requires deployed VisualWebArena sites and URLs. |
| P1 | SV | BrowserGym VisualWebArena | Classifieds | `browsergym/visualwebarena.101` | Use city input image to find the most expensive painting of that city. | Task/config exists; requires deployed VisualWebArena sites and URLs. |
| P3 | SP | TheAgentCompany | Plane / project tool | TBD issue update | Update issue status/assignee/metadata in workplace project tool. | Later expansion; needs adapter/evaluator. |
| P3 | SF (foraging) | TheAgentCompany | OwnCloud / docs | TBD policy/doc extraction | Read internal docs and extract required facts or summary. | Later expansion; needs data mount/evaluator. |
| P3 | SF (foraging) | TheAgentCompany | RocketChat | TBD colleague info gathering | Ask/read colleague messages to resolve missing information. | Later expansion; collaboration behavior. |
| P3 | SF (analytic) | TheAgentCompany | Finance/data artifacts | TBD finance report task | Extract/verify numbers from workplace spreadsheet/report artifacts. | Later expansion; likely full-sandbox. |
| P3 | OP | TheAgentCompany | Product/admin/HR docs | TBD workplace document | Produce or revise an occupational document from context. | Later expansion; rubric/evaluator needed. |

## Coverage Snapshot (post-relabel, 2026-07-14)

- **`SP` is oversupplied** (~half of P0/P1): fine — these runs are cheap
  anchors, but don't let them crowd collection budget.
- **`SV` now honestly = DOMSteer x3 + TF Playground T5/T6 only — all chart-app
  class.** The quota "chart_reading across >=3 interface classes" needs the
  flip-variants: Calc embedded-chart question (SV x doc-app) and CloudCompare
  inspect-and-answer (SV x 3d-app).
- **`SV` bypassability flags**: DataVoyager x3 = bypassable (answer reachable via
  data/text route — that is the phenomenon); TF `tfplayground_misclassified_point`
  = **low-bypassable** (canvas only, no text route) — the key control task;
  `tfplayground_discretize_effect` = bypassable via prior knowledge only.
- **`SF` is the thinnest type** in the main table — the balancing list below is
  the fix; promote 2-3 of those to P0/P1 when authored.
- **`OP` has one ready paired anchor** (Godot) plus TF T7/T8 that still need a
  stable evaluator. The upstream Writer tasks are specified-production tasks,
  not open-ended cases. Do not count tightly specified diagram edits as
  creative merely because they use a visual app.

## Sensemaking Text/Data Task Options

These task options help keep the `SF` bucket broad without blurring it into `SV`.
The deliverable is a verifiable answer or synthesis, and the answer is reachable
through text, numbers, DOM, file metadata, or grid/formula representations
without perceptual decoding of a rendered chart or spatial visual structure.

| Class | `SF` Mode | Benchmark / Source | Candidate Task | Deliverable | Status / Notes |
| --- | --- | --- | --- | --- | --- |
| W1/W2 web | analytic | Hosted WebArena shopping | How many orders did I place in 2023? | Number answer from account/order text. | Requires hosted URL/account data. |
| W1/W2 web | foraging | Hosted WebArena shopping | Find the cheapest product meeting constraints X and Y. | Product name / price. | Requires hosted URL and task prompt. |
| W1/W2 web | foraging | Hosted WebArena forum | What does the top-voted comment recommend for X? | Recommendation / quoted answer. | Requires hosted URL and forum seed state. |
| W1/W2 web | foraging | Custom web / Chrome | `wikipedia_birth_order`: which of Ada Lovelace, Grace Hopper, and Alan Turing was born first? | Person name after cross-page synthesis. | Runnable task added at `tasks/custom_web/wikipedia_birth_order/task.yaml`; better `SF` option than tab-checklist navigation. |
| G structured-doc | analytic | GUI-vs-CLI Calc | Which department has the highest average salary? | Department name from grid/formula output. | Authored standard + grounded answer task reusing the fixed `calc_employee_data_cleanup` seed; answer = Engineering. |
| G structured-doc | analytic | GUI-vs-CLI Calc | Which region has the highest total sales after formulas/summary? | Region/product answer from grid. | Can be authored from existing Calc seed tasks. |
| G structured-doc | foraging | GUI-vs-CLI Writer/PDF or TAC docs | What date does the termination clause take effect? | Date extracted from document text. | Candidate; needs concrete document task/source. |
| G structured-doc | foraging | GUI-vs-CLI Zotero | Which item in the library has DOI X, and what year was it published? | Publication year. | Authored standard + grounded answer task reusing the fixed `zotero_edit_item_doi` library seed; DOI query answer = 2018. |
| W2/docs | foraging | TheAgentCompany | Find the reimbursement limit in the internal handbook. | Limit amount / policy citation. | Later expansion; needs TAC adapter/data. |
| W2/docs | foraging | TheAgentCompany RocketChat | Ask/read colleagues to find who owns service X. | Owner name/team. | Later expansion; collaboration behavior. |
| OS/file | analytic | GUI-vs-CLI / desktop file task | How many PDFs over 1 MB are in this folder tree? | Count from file metadata. | Candidate; could be implemented with file manager or no-GUI baseline. |
| OS/file | foraging | GUI-vs-CLI / desktop file task | Which document in this folder mentions policy term X? | File name / snippet. | Candidate; useful file-system sensemaking baseline. |

## Notes

- Machine-readable sensemaking text/data task records live in
  `tasks/task_inventory/sensemaking_text_data_tasks.jsonl`. Use `status` to distinguish
  runnable tasks from hosted URLs, missing seeds, or missing evaluators.
- `calc_employee_data_cleanup` does not require chart or plot interpretation.
  The existing build task is `SP`; an answer-oriented question over its
  completed grid would be an `SF` analytic variant.
- `calc_conditional_formatting_sales_heatmap` is `SP`, not `SV`:
  *applying* a color scale is a specified state change. A task is `SV`
  only when the deliverable is an answer that must be *read off* rendered
  graphics — flip the deliverable ("which region is hottest per the heatmap?")
  to get the visual-sensemaking twin.
- Shopping can be specified production or text sensemaking depending on the
  prompt: add-to-cart is `SP`; compare products/reviews/specs is `SF` foraging.
- Several tasks can be flipped across categories by changing the deliverable:
  building a summary sheet is often `SP`; answering a question from the
  resulting grid is `SF` analytic; reading a chart rendered from the same data
  is `SV`.
