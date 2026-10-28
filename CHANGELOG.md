# Changelog — GeoVault

All notable changes to this project are documented in this file.
Versions follow semantic versioning (`MAJOR.MINOR.PATCH`).

## [1.3.0] — 2026-10-28

### Added
- Initial public release of GeoVault (Remote Sensing, GIS & ML Data Stewardship Pipeline).
- Core compliance engine (`geovault_core.inspector`) with `--json`, `--strict`
  and `--rehash` modes, YAML line-number diagnostics and path-traversal guards.
- Inventory of 6 demo datasets with auto-generated SHA-256
  integrity manifests.
- Institutional rights catalog with 4 approved licenses.
- Governance blueprints: record template, DMP template, SOP template and an
  ISO 19115-inspired spatial metadata template
  (`blueprints/metadata_iso19115_template.yaml`) with CRS, extent and
  lineage fields for geospatial assets.
- Optional geo-ML extras (`requirements-ml.txt`): rasterio, geopandas,
  xarray/NetCDF, scikit-learn and selectable TensorFlow/PyTorch backends.
- Deterministic brand logo (`assets/logo.svg`) embedded in the README hero
  and the dashboard header.
- Figure provenance map (`figures/figure_manifest.yaml`) with demo figures;
  the inspector verifies every published figure traces to versioned,
  registered inputs.
- Animated compliance demo (`figures/fig_03_pipeline.gif`) — a
  pure-standard-library pixel animation of the audit pipeline, embedded in
  the README and dashboard and tracked by the provenance map like any
  published figure.
- pytest compliance suite (`tests/test_compliance.py`).
- GitHub Actions compliance gate (`.github/workflows/compliance.yml`).
- Interactive validator notebook (`notebooks/validator.ipynb`): *Runtime →
  Run all* completes automatically with an environment banner, a live
  required-files checklist (expected CSV headers included), one-click
  template downloads for every registered dataset, auto-preview of uploads,
  auto-saved `compliance_report.json` / `compliance_report.txt` /
  `integrity.sha256` / `audit_summary.html` artifacts after every audit, an
  optional Google-Drive mount toggle, and a bundled demo dataset so the
  audit is green before you upload anything.
- Interactive compliance dashboard (`dashboard.html`).

### Security
- The checksum manifest parser rejects absolute paths, `..` components and any
  target resolving outside its dataset directory.
- `--rehash` refuses any target that resolves outside `inventory/`.
