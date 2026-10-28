#!/usr/bin/env python3
"""GeoVault Inspector — core compliance engine.

Audits this repository against its institutional rights catalog:

  * YAML validity (line numbers reported on parse errors)
  * registry.yaml <-> record.yaml <-> directory identity checks
  * strict semantic versioning (MAJOR.MINOR.PATCH)
  * licensing policy enforcement via policies/rights_catalog.yaml
  * presence of at least one real data file per dataset
  * SHA-256 integrity manifests with path-traversal protection
  * figure provenance map (figures/figure_manifest.yaml) tying every
    published figure to versioned, registered inputs

CLI
---
  python -m geovault_core.inspector                 # human-readable audit
  python -m geovault_core.inspector --json          # machine-readable report
  python -m geovault_core.inspector --strict        # warnings become errors
  python -m geovault_core.inspector --rehash        # regenerate all manifests
  python -m geovault_core.inspector --rehash DIR    # one manifest (DIR must be
                                                 # inside inventory/)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

TITLE = "GeoVault"
ICON = "🌍"
FLAVOR = "geovault"
VERSION = "1.3.0"

MANIFEST_NAME = "integrity.sha256"
REQUIRED_FIELDS = ("asset_id", "title", "version", "custodian", "license_ref", "abstract")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
DATA_EXTENSIONS = {".csv", ".tsv", ".json", ".parquet", ".xlsx", ".h5", ".nc", ".sav", ".dta"}
CHECKSUM_SKIP = ("README.md", "CHANGELOG.md", ".DS_Store", "Thumbs.db")


def sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def yaml_line_hint(error: Exception) -> str:
    mark = getattr(error, "problem_mark", None)
    if mark is not None:
        return " (line " + str(mark.line + 1) + ", column " + str(mark.column + 1) + ")"
    return ""


def load_yaml(path: Path) -> Tuple[Optional[Any], Optional[str]]:
    """Safely load a YAML file. Returns (data, error_message)."""
    if not path.is_file():
        return None, "file not found: " + str(path)
    try:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle), None
    except yaml.YAMLError as error:
        problem = getattr(error, "problem", None) or str(error)
        return None, ("invalid YAML syntax in " + path.name + yaml_line_hint(error)
                      + ": " + str(problem))
    except OSError as error:
        return None, "unreadable file " + path.name + ": " + str(error)


def is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def real_data_files(directory: Path) -> List[Path]:
    found = []
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.suffix.lower() in DATA_EXTENSIONS and path.stat().st_size > 0:
            found.append(path)
    return found


def tracked_files(directory: Path) -> List[Path]:
    """Files that belong in the integrity manifest: never the manifest itself,
    never the skip-listed housekeeping files."""
    tracked = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        if path.name == MANIFEST_NAME or path.name in CHECKSUM_SKIP:
            continue
        if path.suffix.lower() in {".pyc", ".pyo"}:
            continue
        tracked.append(path)
    return tracked


def write_integrity_manifest(directory: Path) -> List[str]:
    """Auto-generate integrity.sha256 for one dataset directory."""
    lines = [
        "# SHA-256 integrity manifest",
        "# Asset directory: " + directory.name,
        "# Regenerate with: python -m " + FLAVOR + "_core.inspector --rehash",
        "",
    ]
    tracked = []
    for path in tracked_files(directory):
        relative = path.relative_to(directory).as_posix()
        lines.append(sha256_of_file(path) + "  " + relative)
        tracked.append(relative)
    write_text(directory / MANIFEST_NAME, "\n".join(lines) + "\n")
    return tracked


def parse_manifest(directory: Path) -> Tuple[Optional[List[Tuple[str, str]]], List[str]]:
    """Parse integrity.sha256 into (digest, relative_path) pairs."""
    manifest = directory / MANIFEST_NAME
    if not manifest.is_file():
        return None, ["Missing " + MANIFEST_NAME + " (generate with --rehash)"]
    entries: List[Tuple[str, str]] = []
    errors: List[str] = []
    try:
        text = manifest.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        return None, ["unreadable " + MANIFEST_NAME + ": " + str(error)]
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            errors.append(MANIFEST_NAME + " line " + str(lineno) + ": malformed entry")
            continue
        digest, relative = parts[0].lower(), parts[1].strip()
        while relative.startswith("*"):
            relative = relative[1:]
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            errors.append(MANIFEST_NAME + " line " + str(lineno) + ": invalid SHA-256 digest")
            continue
        entries.append((digest, relative))
    return entries, errors


class ComplianceInspector:
    """Policy-driven compliance auditor for the repository."""

    def __init__(self, repo_root: Path, strict: bool = False) -> None:
        self.root = repo_root.resolve()
        self.strict = strict
        self.issues: List[str] = []
        self.warnings: List[str] = []
        self.assets_seen = 0
        self.checksums_verified = 0
        self.figures_seen = 0

    def _issue(self, message: str) -> None:
        self.issues.append(message)

    def _warn(self, message: str) -> None:
        self.warnings.append(message)

    # -- registry ----------------------------------------------------------
    def check_registry(self) -> List[Dict]:
        data, error = load_yaml(self.root / "inventory" / "registry.yaml")
        if error or not isinstance(data, dict):
            self._issue("inventory/registry.yaml: " + (error or "expected a mapping"))
            return []
        version = str(data.get("registry_version", ""))
        if not SEMVER.match(version):
            self._issue("inventory/registry.yaml: registry_version " + repr(version)
                        + " is not MAJOR.MINOR.PATCH")
        if not str(data.get("maintainer", "")).strip():
            self._warn("inventory/registry.yaml: no maintainer recorded")
        assets = data.get("assets")
        if not isinstance(assets, list) or not assets:
            self._issue("inventory/registry.yaml: 'assets' must be a non-empty list")
            return []
        seen = set()
        valid: List[Dict] = []
        for entry in assets:
            if not isinstance(entry, dict):
                self._issue("inventory/registry.yaml: every asset entry must be a mapping")
                continue
            asset_id = str(entry.get("asset_id", "")).strip()
            if not asset_id:
                self._issue("inventory/registry.yaml: asset entry missing asset_id")
            elif asset_id in seen:
                self._issue("inventory/registry.yaml: duplicate asset_id " + repr(asset_id))
            else:
                seen.add(asset_id)
                valid.append(entry)
        return valid

    # -- policies ----------------------------------------------------------
    def check_policies(self) -> set:
        data, error = load_yaml(self.root / "policies" / "rights_catalog.yaml")
        if error or not isinstance(data, dict):
            self._issue("policies/rights_catalog.yaml: " + (error or "expected a mapping"))
            return set()
        allowed = set()
        for entry in data.get("approved_licenses") or []:
            if isinstance(entry, dict) and str(entry.get("id", "")).strip():
                allowed.add(str(entry["id"]).strip())
                if not str(entry.get("name", "")).strip():
                    self._warn("policies/rights_catalog.yaml: license " + str(entry["id"])
                               + " has no name")
            else:
                self._issue("policies/rights_catalog.yaml: malformed license entry")
        if not allowed:
            self._issue("policies/rights_catalog.yaml: no approved licenses defined")
        return allowed

    # -- assets ------------------------------------------------------------
    def check_asset(self, asset: Dict, allowed: set) -> None:
        asset_id = str(asset.get("asset_id", "")).strip()
        if not asset_id:
            self._issue("[?] registry entry missing asset_id")
            return
        tag = "[" + asset_id + "]"
        location = str(asset.get("location", "")).strip()
        if not location:
            self._issue(tag + " registry entry missing location")
            return
        asset_dir = (self.root / location).resolve()
        if not is_within(asset_dir, (self.root / "inventory").resolve()):
            self._issue(tag + " location escapes inventory/: " + location)
            return
        if not asset_dir.is_dir():
            self._issue(tag + " missing directory: " + location)
            return

        self._check_record(asset_id, tag, asset_dir, asset, allowed)
        self._check_license_file(tag, asset_dir)
        self._check_data_presence(tag, asset_dir)
        self._check_manifest(tag, asset_dir)

    def _check_record(self, asset_id: str, tag: str, asset_dir: Path,
                      asset: Dict, allowed: set) -> None:
        record, error = load_yaml(asset_dir / "record.yaml")
        if error:
            self._issue(tag + " " + error)
            return
        if record is None:
            self._issue(tag + " record.yaml is empty")
            return
        if not isinstance(record, dict):
            self._issue(tag + " record.yaml must be a mapping")
            return
        record_id = str(record.get("asset_id", "")).strip()
        if record_id != asset_id:
            self._issue(tag + " record.yaml asset_id " + repr(record.get("asset_id"))
                        + " does not match registry entry " + repr(asset_id))
        if record_id and record_id != asset_dir.name:
            self._issue(tag + " record.yaml asset_id does not match directory name "
                        + repr(asset_dir.name))
        for field in REQUIRED_FIELDS:
            value = record.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                self._issue(tag + " missing required field: " + field)
        version = str(record.get("version", ""))
        if version and not SEMVER.match(version):
            self._issue(tag + " version " + repr(version)
                        + " is not strict semver (MAJOR.MINOR.PATCH)")
        abstract = str(record.get("abstract", "") or "")
        if abstract and len(abstract.strip()) < 20:
            self._warn(tag + " abstract is very short (< 20 characters)")
        if not (record.get("keywords") or []):
            self._warn(tag + " no keywords recorded")
        license_ref = str(record.get("license_ref", "") or "").strip()
        registry_license = str(asset.get("license_ref", "") or "").strip()
        if license_ref and allowed and license_ref not in allowed:
            self._issue(tag + " license " + repr(license_ref)
                        + " is not approved in policies/rights_catalog.yaml")
        if license_ref and registry_license and license_ref != registry_license:
            self._issue(tag + " license mismatch between registry and record.yaml")

    def _check_license_file(self, tag: str, asset_dir: Path) -> None:
        license_file = asset_dir / "LICENSE.txt"
        if not license_file.is_file():
            self._issue(tag + " missing LICENSE.txt")
            return
        text = license_file.read_text(encoding="utf-8", errors="replace").strip()
        if len(text) < 40:
            self._warn(tag + " LICENSE.txt is very short")

    def _check_data_presence(self, tag: str, asset_dir: Path) -> None:
        if not real_data_files(asset_dir):
            self._issue(tag + " no real data file found (expected e.g. data.csv)")

    def _check_manifest(self, tag: str, asset_dir: Path) -> None:
        entries, errors = parse_manifest(asset_dir)
        for error in errors:
            self._issue(tag + " " + error)
        if entries is None:
            return
        verified_names = set()
        for digest, relative in entries:
            if relative in CHECKSUM_SKIP:
                continue  # housekeeping files are intentionally untracked
            relative_path = Path(relative)
            if relative_path.is_absolute() or ".." in relative_path.parts:
                self._issue(tag + " path traversal in " + MANIFEST_NAME + ": " + relative)
                continue
            target = (asset_dir / relative_path).resolve()
            if not is_within(target, asset_dir):
                self._issue(tag + " path traversal in " + MANIFEST_NAME + ": " + relative)
                continue
            if not target.is_file():
                self._issue(tag + " tracked file missing: " + relative)
                continue
            if sha256_of_file(target) != digest:
                self._issue(tag + " hash mismatch: " + relative)
            else:
                self.checksums_verified += 1
                verified_names.add(relative)
        for data_file in real_data_files(asset_dir):
            name = data_file.relative_to(asset_dir).as_posix()
            if name not in verified_names and name not in CHECKSUM_SKIP:
                self._warn(tag + " data file not covered by " + MANIFEST_NAME + ": " + name)

    # -- figure provenance -------------------------------------------------
    def check_provenance(self, registry_versions: Dict[str, str]) -> None:
        """Verify every published figure traces to versioned, registered inputs.

        Each entry in figures/figure_manifest.yaml must declare non-empty
        outputs (existing files inside the repository) and non-empty inputs,
        where every input references a registered asset_id pinned at exactly
        the version currently recorded in inventory/registry.yaml. A stale pin
        fails the audit so a registry version bump forces dependent figures to
        be reviewed and regenerated.
        """
        manifest_path = self.root / "figures" / "figure_manifest.yaml"
        if not manifest_path.is_file():
            self._warn("figures/figure_manifest.yaml: missing — published figures cannot "
                       "be traced to versioned inputs (create the file, even with "
                       "'figures: []' if nothing is published yet)")
            return
        data, error = load_yaml(manifest_path)
        if error or not isinstance(data, dict):
            self._issue("figures/figure_manifest.yaml: " + (error or "expected a mapping"))
            return
        manifest_version = str(data.get("figure_manifest_version", ""))
        if manifest_version and not SEMVER.match(manifest_version):
            self._issue("figures/figure_manifest.yaml: figure_manifest_version "
                        + repr(manifest_version) + " is not MAJOR.MINOR.PATCH")
        figures = data.get("figures")
        if figures is None:
            self._warn("figures/figure_manifest.yaml: no 'figures' list — declare "
                       "'figures: []' explicitly when nothing is published yet")
            return
        if not isinstance(figures, list):
            self._issue("figures/figure_manifest.yaml: 'figures' must be a list")
            return
        seen_ids = set()
        for figure in figures:
            if not isinstance(figure, dict):
                self._issue("figures/figure_manifest.yaml: every figure must be a mapping")
                continue
            figure_id = str(figure.get("figure_id", "")).strip()
            tag = "figures/" + (figure_id or "?")
            if not figure_id:
                self._issue(tag + ": missing figure_id")
            elif figure_id in seen_ids:
                self._issue(tag + ": duplicate figure_id")
            else:
                seen_ids.add(figure_id)
            outputs = figure.get("outputs") or []
            if not isinstance(outputs, list) or not outputs:
                self._issue(tag + ": outputs must be a non-empty list")
            else:
                for output in outputs:
                    output_path = (self.root / str(output)).resolve()
                    if not is_within(output_path, self.root):
                        self._issue(tag + ": output escapes the repository: " + str(output))
                        continue
                    if not output_path.is_file():
                        self._issue(tag + ": output file missing: " + str(output))
            inputs = figure.get("inputs") or []
            if not isinstance(inputs, list) or not inputs:
                self._issue(tag + ": inputs must be a non-empty list of versioned asset references")
                continue
            for entry in inputs:
                if not isinstance(entry, dict):
                    self._issue(tag + ": every input must be a mapping of asset_id to version")
                    continue
                asset_id = str(entry.get("asset_id", "")).strip()
                input_version = str(entry.get("version", "")).strip()
                if not asset_id or not input_version:
                    self._issue(tag + ": input needs both asset_id and version")
                    continue
                if asset_id not in registry_versions:
                    self._issue(tag + ": input " + repr(asset_id)
                                + " is not registered in inventory/registry.yaml")
                    continue
                registered_version = registry_versions[asset_id]
                if not registered_version:
                    self._issue(tag + ": input " + asset_id
                                + " has no version recorded in inventory/registry.yaml")
                elif input_version != registered_version:
                    self._issue(tag + ": input " + asset_id + " pinned at version "
                                + repr(input_version) + " but the registry records "
                                + repr(registered_version) + " — regenerate or re-pin the figure")
            self.figures_seen += 1

    # -- orchestration -------------------------------------------------------
    def run(self) -> bool:
        assets = self.check_registry()
        allowed = self.check_policies()
        registry_versions: Dict[str, str] = {}
        for asset in assets:
            asset_id = str(asset.get("asset_id", "")).strip()
            if asset_id:
                registry_versions[asset_id] = str(asset.get("version", "")).strip()
            self.check_asset(asset, allowed)
            self.assets_seen += 1
        self.check_provenance(registry_versions)
        return not self.issues

    def report(self) -> Dict:
        passed = not self.issues and not (self.strict and self.warnings)
        return {
            "tool": TITLE + " Inspector",
            "flavor": FLAVOR,
            "version": VERSION,
            "repo_root": str(self.root),
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "strict": self.strict,
            "passed": passed,
            "issues": list(self.issues),
            "warnings": list(self.warnings),
            "stats": {
                "assets": self.assets_seen,
                "checksums_verified": self.checksums_verified,
                "figures_tracked": self.figures_seen,
            },
        }


def print_human(inspector: ComplianceInspector) -> None:
    bar = "-" * 62
    print(ICON + " " + TITLE + " Compliance Audit v" + VERSION)
    print(bar)
    print("Repository root : " + str(inspector.root))
    print("Mode            : " + ("strict (warnings are errors)" if inspector.strict else "standard"))
    print(bar)
    if inspector.issues:
        print("\U0001F6A8 AUDIT FAILED — " + str(len(inspector.issues)) + " issue(s):")
        for item in inspector.issues:
            print("  • " + item)
    else:
        print("✅ AUDIT PASSED — " + str(inspector.assets_seen) + " asset(s) compliant, "
              + str(inspector.checksums_verified) + " checksum(s) verified, "
              + str(inspector.figures_seen) + " figure(s) traced.")
    if inspector.warnings:
        label = "warning(s) — fatal under --strict" if inspector.strict else "warning(s)"
        print("⚠️  " + str(len(inspector.warnings)) + " " + label)
        for item in inspector.warnings:
            print("  • " + item)
    print(bar)


def cmd_rehash(repo_root: Path, target: str, as_json: bool) -> int:
    def fail(message: str) -> int:
        if as_json:
            print(json.dumps({"rehashed": [], "error": message}, indent=2))
        else:
            print("❌ " + message)
        return 1

    if target:
        directory = (repo_root / target).resolve()
        if not directory.is_dir():
            return fail("directory not found: " + str(directory))
        # Security guard (see SECURITY.md): --rehash may only write manifests
        # inside inventory/. Without this check a target such as "../docs" or
        # an absolute path would escape the repository root.
        inventory_root = (repo_root / "inventory").resolve()
        if not is_within(directory, inventory_root):
            return fail("refusing to rehash outside inventory/ (see SECURITY.md): "
                        + str(directory))
        directories = [directory]
    else:
        data, error = load_yaml(repo_root / "inventory" / "registry.yaml")
        if error or not isinstance(data, dict):
            return fail("inventory/registry.yaml: " + (error or "expected a mapping"))
        directories = []
        inventory_root = (repo_root / "inventory").resolve()
        for entry in data.get("assets") or []:
            if not isinstance(entry, dict):
                continue
            location = str(entry.get("location", "")).strip()
            if not location:
                continue
            candidate = (repo_root / location).resolve()
            if is_within(candidate, inventory_root) and candidate.is_dir():
                directories.append(candidate)
        if not directories:
            return fail("no registered assets to rehash")
    summary = []
    for directory in directories:
        tracked = write_integrity_manifest(directory)
        summary.append({"directory": directory.name, "files_tracked": len(tracked)})
        if not as_json:
            print("🔐 " + directory.name + ": wrote " + MANIFEST_NAME
                  + " (" + str(len(tracked)) + " file(s) tracked)")
    if as_json:
        print(json.dumps({"rehashed": summary}, indent=2))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass
    parser = argparse.ArgumentParser(
        prog="python -m " + FLAVOR + "_core.inspector",
        description=TITLE + " compliance inspector",
    )
    parser.add_argument("--json", action="store_true",
                        help="emit a machine-readable JSON report on stdout")
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    parser.add_argument("--rehash", nargs="?", const="", default=None, metavar="DIR",
                        help="(re)generate integrity.sha256 for DIR, or for every registered "
                             "asset; DIR must resolve inside inventory/")
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parent.parent

    if args.rehash is not None:
        return cmd_rehash(repo_root, args.rehash, as_json=args.json)

    inspector = ComplianceInspector(repo_root, strict=args.strict)
    inspector.run()
    if args.json:
        print(json.dumps(inspector.report(), indent=2, ensure_ascii=False))
    else:
        print_human(inspector)
    if inspector.issues:
        return 1
    if args.strict and inspector.warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
