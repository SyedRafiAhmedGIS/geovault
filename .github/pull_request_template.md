## Summary

<!-- What does this pull request change, and why? -->

## Type of change

- [ ] Bug fix
- [ ] New dataset or metadata change
- [ ] Documentation
- [ ] Tooling / CI
- [ ] Other (please describe)

## Compliance checklist

- [ ] `python -m geovault_core.inspector --strict` passes
- [ ] `python -m pytest tests/ -q` passes
- [ ] Dataset changes include a regenerated `integrity.sha256`
      (`python -m geovault_core.inspector --rehash`)
- [ ] `record.yaml` versions follow `MAJOR.MINOR.PATCH`
- [ ] Licenses are approved in `policies/rights_catalog.yaml`
- [ ] Documentation updated (README / CHANGELOG)
