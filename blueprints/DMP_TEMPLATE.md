# Data Management Plan (DMP)

**Project:** <project name>
**Principal investigator:** Syed Rafi Ahmed (RS/GIS/ML Lab)
**Version:** 1.0
**Date:** YYYY-MM-DD

## 1. Data description

- <What data will be collected or reused? Which formats and volumes?>
- <Which existing datasets does it build on?>

## 2. Collection & processing methods

- <How is the data collected or generated?>
- <Which transformations are applied, and how are they documented?>
- Spatial collections record CRS, extent and lineage per the ISO 19115-
  inspired template in `blueprints/metadata_iso19115_template.yaml`.
- Published figures are mapped to the dataset versions they consumed in
  `figures/figure_manifest.yaml`; regenerate and re-pin figures after any
  input version change.

## 3. Storage, backup & integrity

- Primary storage: <location>
- Backup schedule: <frequency, retention>
- Integrity: SHA-256 manifests regenerated via
  `python -m geovault_core.inspector --rehash` after every change.

## 4. Access, licensing & ethics

- Access level: <open / restricted / embargoed>
- License: <must be approved in policies/rights_catalog.yaml>
- Ethical and privacy considerations: <consent, anonymization, GDPR…>

## 5. Roles & responsibilities

| Role | Person | Responsibility |
| ---- | ------ | -------------- |
| Custodian | Syed Rafi Ahmed | Metadata quality, versioning, manifests |
| Data manager | <name> | Storage, backup, access requests |
| Auditor | <name> | Runs the compliance audit each release |
