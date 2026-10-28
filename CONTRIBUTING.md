# Contributing to GeoVault

Thank you for investing in better research-data stewardship! This repository is
designed to stay small, auditable and dependency-light, and every change must
keep the compliance gate green.

## Getting started

```bash
git clone <your-fork-url> && cd geovault
python -m venv .venv && source .venv/bin/activate
make install          # runtime + dev dependencies and editable install
make ci               # strict audit + pytest suite
```

## Repository ground rules

- Only `pyyaml` (runtime) and `pytest` (dev) are external dependencies. Do not
  add dependencies without discussing the licensing impact first.
- Every dataset directory must contain `record.yaml`, at least one real data
  file, `LICENSE.txt` and an up-to-date `integrity.sha256`.
- Asset versions and `registry_version` follow strict `MAJOR.MINOR.PATCH`.
- Licenses must be approved in `policies/rights_catalog.yaml`.

## Working with datasets

1. Add or edit files under `inventory/<asset_id>/`.
2. Regenerate the manifest: `make rehash`, or
   `python -m geovault_core.inspector --rehash inventory/<asset_id>`.
3. Run `make ci` — the audit and the pytest suite must both pass.

## Code style

- Python 3.9+, standard library plus `pyyaml` only.
- 4-space indentation, UTF-8, LF line endings (enforced by `.editorconfig`
  and `.gitattributes`).
- `make inspect-strict` must stay warning-free.

## Submitting changes

1. Create a topic branch (`feat/...`, `fix/...`, `docs/...`).
2. Commit in small, logically complete steps.
3. Open a pull request against `main` and complete the PR checklist.
4. The Compliance Gate workflow runs the strict audit and the test suite on
   every push; a green check is required before merge.

## Reporting problems

- Bugs and regressions: open a GitHub issue using the bug report template.
- Security-sensitive findings: see `SECURITY.md` for private disclosure.
- Conduct concerns: see `CODE_OF_CONDUCT.md`.

By opening a pull request you agree that your contribution is released under
the repository license (MIT © 2026 Syed Rafi Ahmed, RS/GIS/ML Lab).
