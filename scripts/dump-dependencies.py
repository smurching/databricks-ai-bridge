#!/usr/bin/env python3
"""
dump-dependencies.py

Walks the repo and dumps all declared dependencies from pyproject.toml and
package.json files to a CSV with columns:

  ecosystem, package, version_spec, dep_type, source_file

ecosystem    : "pypi" or "npm"
package      : normalized package name (lowercase, hyphens)
version_spec : raw version constraint from the manifest (e.g. ">=1.2,<2")
dep_type     : "dependency", "optional:<group>", "dev", "build", "peer"
source_file  : repo-relative path to the manifest

Usage:
  python scripts/dump-dependencies.py [--root REPO_ROOT] [--out FILE]

Defaults:
  --root  : directory containing this script's parent (i.e. repo root)
  --out   : dependencies.csv (in repo root)
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # pip install tomli
    except ModuleNotFoundError:
        sys.exit("Error: requires Python 3.11+ or `pip install tomli`")


# ── Helpers ────────────────────────────────────────────────────────────────────

def normalize_pypi(name: str) -> str:
    """Lowercase and replace underscores/dots with hyphens (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def split_pypi_spec(dep: str) -> tuple[str, str]:
    """Split 'package>=1.0,<2 ; python_requires...' into (name, version_spec)."""
    # Strip environment markers
    dep = dep.split(";")[0].strip()
    # Split on first version operator
    m = re.match(r"^([A-Za-z0-9_.\-\[\]]+)\s*(.*)$", dep)
    if m:
        pkg = re.sub(r"\[.*?\]", "", m.group(1)).strip()  # drop extras [foo]
        spec = m.group(2).strip()
        return normalize_pypi(pkg), spec
    return normalize_pypi(dep), ""


# ── Parsers ────────────────────────────────────────────────────────────────────

def parse_pyproject(path: Path, repo_root: Path) -> list[dict]:
    rows = []
    with open(path, "rb") as f:
        data = tomllib.load(f)

    rel = str(path.relative_to(repo_root))
    project = data.get("project", {})

    # [project.dependencies]
    for dep in project.get("dependencies", []):
        name, spec = split_pypi_spec(dep)
        rows.append({"ecosystem": "pypi", "package": name, "version_spec": spec,
                     "dep_type": "dependency", "source_file": rel})

    # [project.optional-dependencies]
    for group, deps in project.get("optional-dependencies", {}).items():
        for dep in deps:
            name, spec = split_pypi_spec(dep)
            rows.append({"ecosystem": "pypi", "package": name, "version_spec": spec,
                         "dep_type": f"optional:{group}", "source_file": rel})

    # [build-system] requires
    for dep in data.get("build-system", {}).get("requires", []):
        name, spec = split_pypi_spec(dep)
        rows.append({"ecosystem": "pypi", "package": name, "version_spec": spec,
                     "dep_type": "build", "source_file": rel})

    # [dependency-groups] (PEP 735) or [tool.uv.dev-dependencies]
    for group, deps in data.get("dependency-groups", {}).items():
        for dep in deps:
            if isinstance(dep, str):
                name, spec = split_pypi_spec(dep)
                rows.append({"ecosystem": "pypi", "package": name, "version_spec": spec,
                             "dep_type": f"dev-group:{group}", "source_file": rel})

    uv = data.get("tool", {}).get("uv", {})
    for dep in uv.get("dev-dependencies", []):
        name, spec = split_pypi_spec(dep)
        rows.append({"ecosystem": "pypi", "package": name, "version_spec": spec,
                     "dep_type": "dev", "source_file": rel})

    return rows


def parse_package_json(path: Path, repo_root: Path) -> list[dict]:
    rows = []
    with open(path) as f:
        data = json.load(f)

    rel = str(path.relative_to(repo_root))

    type_map = {
        "dependencies": "dependency",
        "devDependencies": "dev",
        "peerDependencies": "peer",
        "optionalDependencies": "optional",
    }

    for key, dep_type in type_map.items():
        for pkg, spec in data.get(key, {}).items():
            rows.append({
                "ecosystem": "npm",
                "package": pkg.lower(),
                "version_spec": spec,
                "dep_type": dep_type,
                "source_file": rel,
            })

    return rows


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    script_dir = Path(__file__).resolve().parent
    default_root = script_dir.parent

    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=default_root,
                        help="Repo root (default: parent of scripts/)")
    parser.add_argument("--out", type=Path, default=None,
                        help="Output CSV path (default: <root>/dependencies.csv)")
    args = parser.parse_args()

    root = args.root.resolve()
    out = args.out or (root / "dependencies.csv")

    EXCLUDE_DIRS = {"node_modules", ".venv", ".git", "__pycache__", "dist", "build"}

    rows = []

    for pyproject in sorted(root.rglob("pyproject.toml")):
        if any(p in EXCLUDE_DIRS for p in pyproject.parts):
            continue
        try:
            rows.extend(parse_pyproject(pyproject, root))
        except Exception as e:
            print(f"Warning: could not parse {pyproject}: {e}", file=sys.stderr)

    for pkg_json in sorted(root.rglob("package.json")):
        if any(p in EXCLUDE_DIRS for p in pkg_json.parts):
            continue
        try:
            rows.extend(parse_package_json(pkg_json, root))
        except Exception as e:
            print(f"Warning: could not parse {pkg_json}: {e}", file=sys.stderr)

    rows.sort(key=lambda r: (r["ecosystem"], r["package"], r["source_file"]))

    fieldnames = ["ecosystem", "package", "version_spec", "dep_type", "source_file"]
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} dependencies to {out}")

    # Print a quick summary table to stdout
    by_eco: dict[str, int] = {}
    for r in rows:
        by_eco[r["ecosystem"]] = by_eco.get(r["ecosystem"], 0) + 1
    for eco, count in sorted(by_eco.items()):
        print(f"  {eco}: {count} entries")


if __name__ == "__main__":
    main()
