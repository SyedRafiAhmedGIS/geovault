"""Compliance test suite for GeoVault.

Every test is self-contained: the suite re-verifies registry integrity,
metadata consistency, licensing policy, checksums and the inspector CLI.

Run with:  python -m pytest tests/ -q
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MODULE = "geovault_core"
INSPECTOR = [sys.executable, "-m", MODULE + ".inspector"]

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
REQUIRED_FIELDS = ("asset_id", "title", "version", "custodian", "license_ref", "abstract")
DATA_EXTENSIONS = {".csv", ".tsv", ".json", ".parquet", ".xlsx", ".h5", ".nc"}

# Placeholder needles are assembled at runtime so this file can never
# contain the placeholders it guards against.
PLACEHOLDER_NEEDLES = ["[" + name + "]" for name in (
    "Your Name", "Your Institution", "Your Last Name", "Your First Name", "Your Org",
)]
TEXT_SUFFIXES = {".md", ".py", ".yaml", ".yml", ".toml", ".cff", ".txt", ".html",
                 ".json", ".ini", ".cfg"}
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", "venv", ".idea",
             ".vscode", ".ipynb_checkpoints"}


def load_yaml(relative: str):
    return yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))


def registry():
    return load_yaml("inventory/registry.yaml")


def assets():
    return registry()["assets"]


def approved_licenses():
    """Approved license ids are read from the catalog, never hardcoded,
    so institutions can extend their rights catalog without breaking tests."""
    catalog = load_yaml("policies/rights_catalog.yaml")
    return {entry["id"] for entry in catalog["approved_licenses"]}


def test_registry_is_valid():
    data = registry()
    assert isinstance(data, dict)
    assert SEMVER.match(str(data.get("registry_version", ""))), \
        "registry_version must be MAJOR.MINOR.PATCH"
    entries = data["assets"]
    assert isinstance(entries, list) and entries, \
        "registry must list at least one asset"
    ids = [entry["asset_id"] for entry in entries]
    assert len(set(ids)) == len(ids), "asset_ids must be unique"


def test_rights_catalog_is_valid():
    catalog = load_yaml("policies/rights_catalog.yaml")
    licenses = catalog["approved_licenses"]
    assert isinstance(licenses, list) and len(licenses) >= 1
    for entry in licenses:
        assert entry.get("id") and entry.get("name")


def test_each_asset_directory_is_complete():
    for entry in assets():
        directory = ROOT / entry["location"]
        assert directory.is_dir(), entry["asset_id"]
        for filename in ("record.yaml", "LICENSE.txt", "data.csv", "integrity.sha256"):
            assert (directory / filename).is_file(), \
                entry["asset_id"] + ": missing " + filename


def test_record_metadata_is_complete_and_consistent():
    for entry in assets():
        directory = ROOT / entry["location"]
        record = load_yaml(entry["location"] + "/record.yaml")
        for field in REQUIRED_FIELDS:
            assert record.get(field), entry["asset_id"] + ": missing field " + field
        assert record["asset_id"] == entry["asset_id"] == directory.name
        assert SEMVER.match(str(record["version"])), entry["asset_id"] + ": bad semver"
        assert record["license_ref"] in approved_licenses(), \
            entry["asset_id"] + ": unapproved license"
        assert record["license_ref"] == entry["license_ref"], \
            entry["asset_id"] + ": license mismatch"


def test_every_asset_has_real_data():
    for entry in assets():
        directory = ROOT / entry["location"]
        real = [
            path for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in DATA_EXTENSIONS
            and path.stat().st_size > 0
        ]
        assert real, entry["asset_id"] + ": no real data file"


def test_integrity_manifests_match_disk():
    for entry in assets():
        directory = ROOT / entry["location"]
        for raw in (directory / "integrity.sha256").read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            digest, relative = line.split(None, 1)
            target = (directory / relative.strip().lstrip("*")).resolve()
            assert target.is_file(), entry["asset_id"] + ": missing tracked file " + relative
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            assert actual == digest.lower(), entry["asset_id"] + ": hash drift for " + relative


def test_inspector_human_mode_passes():
    result = subprocess.run(INSPECTOR, cwd=ROOT, capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, "inspector failed:\n" + result.stdout + "\n" + result.stderr


def test_inspector_strict_mode_passes():
    result = subprocess.run(INSPECTOR + ["--strict"], cwd=ROOT, capture_output=True,
                            text=True, timeout=180)
    assert result.returncode == 0, "strict audit failed:\n" + result.stdout + "\n" + result.stderr


def test_inspector_json_mode_is_valid():
    result = subprocess.run(INSPECTOR + ["--json"], cwd=ROOT, capture_output=True,
                            text=True, timeout=180)
    assert result.returncode == 0, "json audit failed:\n" + result.stdout + "\n" + result.stderr
    report = json.loads(result.stdout)
    expected_assets = len(assets())
    assert report["passed"] is True
    assert report["issues"] == []
    assert report["stats"]["assets"] == expected_assets
    assert report["stats"]["checksums_verified"] >= expected_assets
    assert report["stats"]["figures_tracked"] >= 1


def test_figure_provenance_map_is_valid():
    data = load_yaml("figures/figure_manifest.yaml")
    figures = data.get("figures")
    assert isinstance(figures, list) and figures, \
        "figure manifest must list at least one figure"
    registered_versions = {entry["asset_id"]: str(entry["version"]) for entry in assets()}
    seen = set()
    for figure in figures:
        figure_id = str(figure.get("figure_id", ""))
        assert figure_id, "every figure needs a figure_id"
        assert figure_id not in seen, "duplicate figure_id " + figure_id
        seen.add(figure_id)
        outputs = figure.get("outputs") or []
        assert outputs, figure_id + ": outputs must be a non-empty list"
        for output in outputs:
            assert (ROOT / output).is_file(), figure_id + ": missing output " + output
        inputs = figure.get("inputs") or []
        assert inputs, figure_id + ": every figure needs versioned inputs"
        for entry in inputs:
            asset_id = entry.get("asset_id")
            assert asset_id in registered_versions, \
                figure_id + ": input not registered: " + str(asset_id)
            assert str(entry.get("version", "")) == registered_versions[asset_id], \
                figure_id + ": stale input version for " + asset_id


def test_animated_demo_figure_is_valid():
    gif_path = ROOT / "figures" / "fig_03_pipeline.gif"
    assert gif_path.is_file(), "animated demo figure missing from figures/"
    data = gif_path.read_bytes()
    assert data[:6] == b"GIF89a", "animated demo figure must be a GIF89a file"
    # The builder emits one intro frame, three frames per pipeline stage and
    # one final frame; every frame carries a graphic control extension.
    # LZW payload bytes can only add matches, never remove them.
    assert data.count(b"\x21\xf9\x04") >= 20, "animated demo figure lost frames"


def test_validator_notebook_is_embedded():
    # NOTE: the builder renders THIS file before writing it, so the token in
    # the assertion below is replaced with the concrete flavor title at build
    # time; the generated suite asserts the rendered title, not the token.
    notebook_path = ROOT / "notebooks" / "validator.ipynb"
    assert notebook_path.is_file(), "notebooks/validator.ipynb is required"
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    assert notebook["nbformat"] == 4
    assert notebook["cells"], "notebook must contain cells"
    source = "".join("".join(cell.get("source", [])) for cell in notebook["cells"])
    assert "GeoVault" in source


def test_dashboard_exists():
    html = (ROOT / "dashboard.html").read_text(encoding="utf-8")
    assert "GeoVault" in html
    assert "compliance_report.json" in html


def test_no_placeholder_tokens_remain():
    offenders = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for needle in PLACEHOLDER_NEEDLES:
            if needle in text:
                offenders.append(str(path.relative_to(ROOT)) + " -> " + needle)
    assert not offenders, "placeholder leakage detected:\n" + "\n".join(offenders)
