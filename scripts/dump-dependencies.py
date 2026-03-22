#!/usr/bin/env python3
"""
dump-dependencies.py

Clones (or scans a local) repo and dumps all direct AND transitive
dependencies from pyproject.toml, package.json, uv.lock, and
package-lock.json to a CSV.

Output columns (match the shared audit schema):
  repo, package_name, dependency_type, dependency, version_spec, min_version

  repo             : basename of the repo URL / local path
  package_name     : name declared in the manifest that introduces this dep
                     (project.name / package.json#name); "repo" for lockfile rows
  dependency_type  : section that lists the dep
                     pyproject : dependency | optional:<group> | build | dev-group:<g>
                     package.json : dependencies | devDependencies | peerDependencies | optionalDependencies
                     lockfiles    : transitive-pypi | transitive-npm
  dependency       : normalized dependency name
  version_spec     : raw constraint from manifest, or exact pinned version from lockfile
  min_version      : lowest semver implied by version_spec (best-effort; blank when non-semver)

Usage:
  python scripts/dump-dependencies.py --repo <url-or-local-path> [--out FILE]

Examples:
  python scripts/dump-dependencies.py --repo https://github.com/org/repo
  python scripts/dump-dependencies.py --repo /path/to/local/repo --out deps.csv
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

EXCLUDE_DIRS = {"node_modules", ".venv", ".git", "__pycache__", "dist", "build"}
FIELDNAMES = ["repo", "package_name", "dependency_type", "dependency", "version_spec", "min_version"]


# ── min_version extraction (ported from reference bash/node script) ────────────

_SEMVER_RE = re.compile(r"(\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)")
_NON_SEMVER_PREFIXES = (
    "workspace:", "file:", "link:", "portal:", "patch:",
    "git:", "git+", "github:", "gitlab:", "bitbucket:",
    "http://", "https://",
)


def _parse_semver(s: str) -> tuple | None:
    """Return (major, minor, patch, prerelease) or None."""
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?", s)
    if not m:
        return None
    return (int(m[1]), int(m[2]), int(m[3]), m[4] or "")


def _semver_key(t: tuple) -> tuple:
    major, minor, patch, pre = t
    # stable > prerelease: put stable last so min() works
    return (major, minor, patch, 0 if pre else 1, pre)


def min_version(spec: str) -> str:
    """Extract the lowest semver implied by a version spec string."""
    if not spec:
        return ""
    spec = spec.strip()
    if any(spec.startswith(p) for p in _NON_SEMVER_PREFIXES):
        return ""
    # npm alias: npm:@scope/pkg@1.2.3
    if spec.startswith("npm:"):
        inner = spec[4:]
        at = inner.rfind("@")
        if at > 0:
            spec = inner[at + 1:].strip()
    if spec in ("*", "x", "X", ""):
        return ""
    # Already exact semver
    if re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", spec):
        return spec
    candidates = [_parse_semver(m) for m in _SEMVER_RE.findall(spec)]
    candidates = [c for c in candidates if c is not None]
    if not candidates:
        return ""
    return "{}.{}.{}{}".format(
        *min(candidates, key=_semver_key)[:3],
        ("-" + min(candidates, key=_semver_key)[3]) if min(candidates, key=_semver_key)[3] else "",
    )


# ── Name helpers ───────────────────────────────────────────────────────────────

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


# ── Row builder ────────────────────────────────────────────────────────────────

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


# ── Parsers — direct deps ──────────────────────────────────────────────────────

def parse_pyproject(path: Path, repo: str) -> list[dict]:
    rows = []
    with open(path, "rb") as f:
        data = tomllib.load(f)

    project = data.get("project", {})
    pkg_name = normalize_pypi(project.get("name", repo))

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
    rows = []
    with open(path) as f:
        data = json.load(f)

    pkg_name = data.get("name", repo)
    section_map = {
        "dependencies": "dependencies",
        "devDependencies": "devDependencies",
        "peerDependencies": "peerDependencies",
        "optionalDependencies": "optionalDependencies",
    }
    for key, dep_type in section_map.items():
        for dep, spec in data.get(key, {}).items():
            rows.append(row(repo, pkg_name, dep_type, dep, str(spec)))

    return rows


# ── Parsers — transitive deps from lockfiles ───────────────────────────────────

def parse_uv_lock(path: Path, repo: str) -> list[dict]:
    """
    uv.lock is TOML. Each [[package]] has name + version (exact pinned).
    We emit one row per resolved package — these are the transitive closure.
    """
    rows = []
    with open(path, "rb") as f:
        data = tomllib.load(f)

    for pkg in data.get("package", []):
        name = normalize_pypi(pkg.get("name", ""))
        version = pkg.get("version", "")
        if not name or not version:
            continue
        rows.append(row(repo, repo, "transitive-pypi", name, version))

    return rows


def parse_package_lock(path: Path, repo: str) -> list[dict]:
    """
    package-lock.json v2/v3: packages dict maps 'node_modules/pkg' → {version, ...}.
    The root entry key is '' (empty string).
    """
    rows = []
    with open(path) as f:
        data = json.load(f)

    for key, info in data.get("packages", {}).items():
        if key == "":          # root package itself — skip
            continue
        # key is 'node_modules/foo' or 'node_modules/foo/node_modules/bar'
        dep_name = key.removeprefix("node_modules/")
        version = info.get("version", "")
        rows.append(row(repo, repo, "transitive-npm", dep_name, version))

    return rows


# ── Repo setup ─────────────────────────────────────────────────────────────────

def resolve_repo(repo_arg: str) -> tuple[Path, str, tempfile.TemporaryDirectory | None]:
    """
    Returns (repo_root_path, repo_name, tmpdir_or_None).
    Caller must clean up tmpdir if not None.
    """
    is_url = repo_arg.startswith(("https://", "git@", "http://", "git://", "ssh://"))
    if is_url:
        if not shutil.which("git"):
            sys.exit("Error: git not found in PATH — needed to clone the repo")
        tmpdir = tempfile.TemporaryDirectory()
        dest = Path(tmpdir.name) / "repo"
        print(f"Cloning {repo_arg} …", file=sys.stderr)
        subprocess.run(["git", "clone", "--depth=1", repo_arg, str(dest)],
                       check=True, capture_output=True)
        repo_name = Path(repo_arg.rstrip("/").split("/")[-1].removesuffix(".git")).name
        return dest, repo_name, tmpdir
    else:
        local = Path(repo_arg).resolve()
        if not local.is_dir():
            sys.exit(f"Error: not a directory: {local}")
        return local, local.name, None


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--repo", required=True,
        help="Git URL to clone (https://... or git@...) or local path to scan",
    )
    parser.add_argument(
        "--out", type=Path, default=None,
        help="Output CSV path (default: <repo-name>-dependencies.csv in cwd)",
    )
    args = parser.parse_args()

    root, repo_name, tmpdir = resolve_repo(args.repo)
    out = args.out or Path(f"{repo_name}-dependencies.csv")

    try:
        rows: list[dict] = []
        warn = lambda msg: print(f"Warning: {msg}", file=sys.stderr)

        # Direct deps
        for pyproject in sorted(root.rglob("pyproject.toml")):
            if any(p in EXCLUDE_DIRS for p in pyproject.parts):
                continue
            try:
                rows.extend(parse_pyproject(pyproject, repo_name))
            except Exception as e:
                warn(f"could not parse {pyproject}: {e}")

        for pkg_json in sorted(root.rglob("package.json")):
            if any(p in EXCLUDE_DIRS for p in pkg_json.parts):
                continue
            try:
                rows.extend(parse_package_json(pkg_json, repo_name))
            except Exception as e:
                warn(f"could not parse {pkg_json}: {e}")

        # Transitive deps from lockfiles
        for uv_lock in sorted(root.rglob("uv.lock")):
            if any(p in EXCLUDE_DIRS for p in uv_lock.parts):
                continue
            try:
                rows.extend(parse_uv_lock(uv_lock, repo_name))
            except Exception as e:
                warn(f"could not parse {uv_lock}: {e}")

        for pkg_lock in sorted(root.rglob("package-lock.json")):
            if any(p in EXCLUDE_DIRS for p in pkg_lock.parts):
                continue
            try:
                rows.extend(parse_package_lock(pkg_lock, repo_name))
            except Exception as e:
                warn(f"could not parse {pkg_lock}: {e}")

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
