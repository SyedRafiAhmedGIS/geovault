# GeoVault — developer tasks
PYTHON ?= python3
FLAVOR := geovault
MODULE := geovault_core

.PHONY: help install inspect inspect-json inspect-strict test ci rehash clean zip

help:
	@echo "GeoVault — Remote Sensing, GIS & ML Data Stewardship Pipeline"
	@echo ""
	@echo "Targets:"
	@echo "  make install        Install runtime + dev dependencies (editable)"
	@echo "  make inspect        Run the compliance audit"
	@echo "  make inspect-json   Emit the machine-readable audit report"
	@echo "  make inspect-strict Run the audit with warnings as errors"
	@echo "  make test           Run the pytest compliance suite"
	@echo "  make ci             inspect-strict + test (what CI runs)"
	@echo "  make rehash         Regenerate all integrity.sha256 manifests"
	@echo "  make clean          Remove caches and build artifacts"
	@echo "  make zip            Package the repository into ../$$(FLAVOR).zip"

install:
	$(PYTHON) -m pip install -q -r requirements.txt
	$(PYTHON) -m pip install -e .

inspect:
	$(PYTHON) -m $(MODULE).inspector

inspect-json:
	$(PYTHON) -m $(MODULE).inspector --json

inspect-strict:
	$(PYTHON) -m $(MODULE).inspector --strict

test:
	$(PYTHON) -m pytest tests/ -q

ci: inspect-strict test

rehash:
	$(PYTHON) -m $(MODULE).inspector --rehash

clean:
	rm -rf .pytest_cache .mypy_cache build dist *.egg-info src/*.egg-info
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type d -name ".ipynb_checkpoints" -prune -exec rm -rf {} +

zip:
	cd .. && zip -r $(FLAVOR).zip $(FLAVOR) -x "*/__pycache__/*" "*/.git/*" "*/.venv/*" "*/.pytest_cache/*" "*.pyc"
