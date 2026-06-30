# GPT-5.4 DataVoyager Smoke Results

This curated example contains three successful trajectories for the same
DOMSteer/DataVoyager task:

```text
What is the most fuel-efficient car in the dataset?
```

Expected answer:

```text
Mazda GLC
```

## Files

```text
batch_config.yaml
dashboard/
  dashboard.html
  dashboard.manifest.json
trajectories/
  browser/
    trajectory.json
    trajectory_viewer.html
    screenshots/
  sandbox/
    trajectory.json
    trajectory_viewer.html
    screenshots/
  nogui/
    trajectory.json
    trajectory_viewer.html
    screenshots/
```

`trajectory.json` is the canonical machine-readable data. `trajectory_viewer.html`
is a convenience view for inspecting one trajectory in a browser.

Heavy runtime artifacts such as Playwright traces and videos are intentionally
not included.
