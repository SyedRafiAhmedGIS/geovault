# Standard Operating Procedure (SOP)

**SOP ID:** SOP-<XXXX>
**Title:** <short title>
**Version:** 1.0
**Owner:** Syed Rafi Ahmed (RS/GIS/ML Lab)
**Last review:** YYYY-MM-DD

## 1. Purpose

<Why this procedure exists and which assets it covers.>

## 2. Procedure

1. <Step one>
2. <Step two>
3. <Step three>
4. When a figure is published, or an input dataset version changes, update
   `figures/figure_manifest.yaml` (and regenerate the figure) before the audit.
5. For spatial assets, refresh the ISO 19115-inspired metadata block
   (`blueprints/metadata_iso19115_template.yaml`) whenever the CRS, extent
   or processing lineage changes.

## 3. Quality control

- The compliance audit (`python -m geovault_core.inspector --strict`) must pass
  after every data-changing step.
- Checksums are regenerated with `--rehash` whenever files change.
- Deviations are recorded in the asset's `provenance.processing` field.

## 4. Records

<Where run logs, approvals and manifests are archived.>
