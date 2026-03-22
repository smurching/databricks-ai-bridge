#!/usr/bin/env python3
"""
dump-dependencies.py

Clones (or scans a local) repo and dumps all direct AND transitive
dependencies from pyproject.toml, package.json, uv.lock, and
package-lock.json to a CSV.

Output columns:
  repo, package_name, dependency_type, dependency, version_spec, min_version

  repo             : basename of the repo URL / local path
  package_name     : name from the manifest (project.name / package.json#name);
                     repo name for lockfile rows
  dependency_type  : pyproject: dependency | optional:<group> | build | dev-group:<g>
                     package.json: dependencies | devDependencies | peerDependencies | optionalDependencies
                     lockfiles: transitive-pypi | transitive-npm
  dependency       : normalized dependency name
  version_spec     : raw constraint from manifest, or pinned version from lockfile
  min_version      : lowest semver implied by version_spec (best-effort, may be blank)

Usage:
  python scripts/dump-dependencies.py --repo <url-or-local-path> [--out FILE]
"""

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]  # pip install tomli
    except ModuleNotFoundError:
        sys.exit("Error: requires Python 3.11+ or `pip install tomli`")

try:
    from min_version import min_version
except ImportError:
    from scripts.min_version import min_version  # type: ignore[no-redef]

EXCLUDE_DIRS = {"node_modules", ".venv", ".git", "__pycache__", "dist", "build"}
FIELDNAMES = ["repo", "package_name", "dependency_type", "dependency", "version_spec", "min_version"]
MANIFEST_NAMES = {"pyproject.toml", "package.json", "uv.lock", "package-lock.json"}


def normalize_pypi(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def split_pypi_dep(dep: str) -> tuple[str, str]:
    """'package>=1.0,<2 ; marker' → (name, spec)"""
    dep = dep.split(";")[0].strip()
    m = re.match(r"^([A-Za-z0-9_.\-\[\]]+)\s*(.*)$", dep)
    if m:
        pkg = re.sub(r"\[.*?\]", "", m.group(1)).strip()
        return normalize_pypi(pkg), m.group(2).strip()
    return normalize_pypi(dep), ""


def row(repo: str, package_name: str, dependency_type: str,
        dependency: str, version_spec: str) -> dict:
    return {
        "repo": repo,
        "package_name": package_name,
        "dependency_type": dependency_type,
        "dependency": dependency,
        "version_spec": version_spec,
        "min_version": min_version(version_spec),
    }


def parse_pyproject(path: Path, repo: str) -> list[dict]:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    project = data.get("project", {})
    pkg_name = normalize_pypi(project.get("name", repo))
    rows = []

    for dep in project.get("dependencies", []):
        n, s = split_pypi_dep(dep)
        rows.append(row(repo, pkg_name, "dependencies", n, s))

    for group, deps in project.get("optional-dependencies", {}).items():
        for dep in deps:
            n, s = split_pypi_dep(dep)
            rows.append(row(repo, pkg_name, f"optional:{group}", n, s))

    for dep in data.get("build-system", {}).get("requires", []):
        n, s = split_pypi_dep(dep)
        rows.append(row(repo, pkg_name, "build", n, s))

    for grp, deps in data.get("dependency-groups", {}).items():
        for dep in deps:
            if isinstance(dep, str):
                n, s = split_pypi_dep(dep)
                rows.append(row(repo, pkg_name, f"dev-group:{grp}", n, s))

    for dep in data.get("tool", {}).get("uv", {}).get("dev-dependencies", []):
        n, s = split_pypi_dep(dep)
        rows.append(row(repo, pkg_name, "dev-group:dev", n, s))

    return rows


def parse_package_json(path: Path, repo: str) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    pkg_name = data.get("name", repo)
    rows = []
    for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        for dep, spec in data.get(section, {}).items():
            rows.append(row(repo, pkg_name, section, dep, str(spec)))
    return rows


def parse_uv_lock(path: Path, repo: str) -> list[dict]:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    rows = []
    for pkg in data.get("package", []):
        name = normalize_pypi(pkg.get("name", ""))
        version = pkg.get("version", "")
        if name and version:
            rows.append(row(repo, repo, "transitive-pypi", name, version))
    return rows


def parse_package_lock(path: Path, repo: str) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    rows = []
    for key, info in data.get("packages", {}).items():
        if key == "":
            continue
        dep_name = key.removeprefix("node_modules/")
        rows.append(row(repo, repo, "transitive-npm", dep_name, info.get("version", "")))
    return rows


def resolve_repo(repo_arg: str) -> tuple[Path, str, tempfile.TemporaryDirectory | None]:
    if repo_arg.startswith(("https://", "git@", "http://", "git://", "ssh://")):
        if not shutil.which("git"):
            sys.exit("Error: git not found in PATH")
        tmpdir = tempfile.TemporaryDirectory()
        dest = Path(tmpdir.name) / "repo"
        print(f"Cloning {repo_arg} …", file=sys.stderr)
        subprocess.run(["git", "clone", "--depth=1", repo_arg, str(dest)],
                       check=True, capture_output=True)
        repo_name = Path(repo_arg.rstrip("/").split("/")[-1].removesuffix(".git")).name
        return dest, repo_name, tmpdir
    local = Path(repo_arg).resolve()
    if not local.is_dir():
        sys.exit(f"Error: not a directory: {local}")
    return local, local.name, None


_PARSERS = {
    "pyproject.toml": parse_pyproject,
    "package.json": parse_package_json,
    "uv.lock": parse_uv_lock,
    "package-lock.json": parse_package_lock,
}


def collect_rows(root: Path, repo_name: str) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(root.rglob("*")):
        if path.name not in MANIFEST_NAMES:
            continue
        if any(p in EXCLUDE_DIRS for p in path.parts):
            continue
        try:
            rows.extend(_PARSERS[path.name](path, repo_name))
        except Exception as e:
            print(f"Warning: could not parse {path}: {e}", file=sys.stderr)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True,
                        help="Git URL to clone or local path to scan")
    parser.add_argument("--out", type=Path, default=None,
                        help="Output CSV (default: <repo-name>-dependencies.csv)")
    args = parser.parse_args()

    root, repo_name, tmpdir = resolve_repo(args.repo)
    out = args.out or Path(f"{repo_name}-dependencies.csv")

    try:
        rows = collect_rows(root, repo_name)
        rows.sort(key=lambda r: (r["dependency_type"], r["dependency"], r["package_name"]))

        with open(out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)

        print(f"Wrote {len(rows)} rows to {out}")
        by_type: dict[str, int] = {}
        for r in rows:
            by_type[r["dependency_type"]] = by_type.get(r["dependency_type"], 0) + 1
        for t, c in sorted(by_type.items()):
            print(f"  {t}: {c}")
    finally:
        if tmpdir:
            tmpdir.cleanup()


if __name__ == "__main__":
    main()
