# Security Policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| 1.3.0 | ✅ Active support |
| earlier | ❌ Please upgrade |

## Reporting a vulnerability

Do **not** open a public issue for an undisclosed security problem.

1. Open a private GitHub security advisory for this repository, **or**
2. Contact the maintainers directly: Syed Rafi Ahmed (RS/GIS/ML Lab).

Include a description, reproduction steps, affected files and — if possible —
a suggested fix. You will receive an acknowledgment within 5 business days and
status updates at least weekly until resolution.

## Scope and design notes

The compliance engine deliberately limits its attack surface:

- `integrity.sha256` parsing rejects absolute paths, `..` components and any
  resolved target outside its dataset directory (path-traversal guard).
- YAML is parsed with `yaml.safe_load` only; no executable constructs.
- The inspector performs read-only audits; `--rehash` refuses any target that
  resolves outside `inventory/` and writes only `integrity.sha256` manifests.
- `figures/figure_manifest.yaml` outputs must resolve inside the repository
  root, and figure inputs must reference registered asset versions.
- Runtime dependencies are limited to `pyyaml`; dev tooling adds `pytest`.

## Hardening checklist for deployments

- Keep the repository read-only for CI service accounts.
- Review new licenses against `policies/rights_catalog.yaml` before merging.
- Run `make ci` in CI so audits and tests gate every change.
