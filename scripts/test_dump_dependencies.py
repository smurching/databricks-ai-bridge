"""Tests for dump-dependencies.py and min_version.py."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# ── Import the hyphen-named script as a module ─────────────────────────────────
_SCRIPTS = Path(__file__).parent
sys.path.insert(0, str(_SCRIPTS))

spec = importlib.util.spec_from_file_location("dump_deps", _SCRIPTS / "dump-dependencies.py")
dump_deps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dump_deps)

from min_version import min_version  # noqa: E402

# ── min_version ────────────────────────────────────────────────────────────────

class TestMinVersion:
    def test_exact_version(self):
        assert min_version("1.2.3") == "1.2.3"

    def test_caret_range(self):
        assert min_version("^3.0.0") == "3.0.0"

    def test_tilde_range(self):
        assert min_version("~1.2.3") == "1.2.3"

    def test_gte_constraint(self):
        assert min_version(">=2.1.0") == "2.1.0"

    def test_range_picks_lower_bound(self):
        assert min_version(">=1.2.0,<2.0.0") == "1.2.0"

    def test_prerelease(self):
        assert min_version("1.0.0-alpha.1") == "1.0.0-alpha.1"

    def test_prerelease_vs_stable_picks_prerelease(self):
        # 1.0.0-alpha < 1.0.0 (stable)
        assert min_version(">=1.0.0-alpha,<2.0.0") == "1.0.0-alpha"

    def test_npm_alias(self):
        assert min_version("npm:rolldown-vite@7.1.14") == "7.1.14"

    def test_npm_scoped_alias(self):
        assert min_version("npm:@scope/pkg@1.2.3") == "1.2.3"

    def test_wildcard_star(self):
        assert min_version("*") == ""

    def test_wildcard_x(self):
        assert min_version("x") == ""

    def test_empty(self):
        assert min_version("") == ""

    def test_workspace_protocol(self):
        assert min_version("workspace:*") == ""

    def test_file_protocol(self):
        assert min_version("file:../foo") == ""

    def test_git_url(self):
        assert min_version("git+https://github.com/org/repo") == ""

    def test_https_url(self):
        assert min_version("https://example.com/pkg.tar.gz") == ""

    def test_non_semver_string(self):
        assert min_version("latest") == ""


# ── normalize_pypi ─────────────────────────────────────────────────────────────

class TestNormalizePypi:
    def test_underscores_to_hyphens(self):
        assert dump_deps.normalize_pypi("my_package") == "my-package"

    def test_dots_to_hyphens(self):
        assert dump_deps.normalize_pypi("my.package") == "my-package"

    def test_mixed_separators(self):
        assert dump_deps.normalize_pypi("My__Package.Name") == "my-package-name"

    def test_lowercase(self):
        assert dump_deps.normalize_pypi("Django") == "django"

    def test_already_normalized(self):
        assert dump_deps.normalize_pypi("requests") == "requests"


# ── split_pypi_dep ─────────────────────────────────────────────────────────────

class TestSplitPypiDep:
    def test_bare_package(self):
        assert dump_deps.split_pypi_dep("requests") == ("requests", "")

    def test_with_version(self):
        assert dump_deps.split_pypi_dep("requests>=2.0.0") == ("requests", ">=2.0.0")

    def test_with_range(self):
        assert dump_deps.split_pypi_dep("django>=3.0,<4.0") == ("django", ">=3.0,<4.0")

    def test_strips_marker(self):
        name, spec = dump_deps.split_pypi_dep("importlib-metadata>=1.0 ; python_version < '3.8'")
        assert name == "importlib-metadata"
        assert "python_version" not in spec

    def test_strips_extras(self):
        name, _ = dump_deps.split_pypi_dep("uvicorn[standard]>=0.12")
        assert name == "uvicorn"

    def test_normalizes_name(self):
        name, _ = dump_deps.split_pypi_dep("My_Package>=1.0")
        assert name == "my-package"


# ── parse_pyproject ────────────────────────────────────────────────────────────

class TestParsePyproject:
    def _write(self, tmp_path, content):
        p = tmp_path / "pyproject.toml"
        p.write_text(content)
        return p

    def test_direct_dependencies(self, tmp_path):
        p = self._write(tmp_path, """
[project]
name = "my-pkg"
dependencies = ["requests>=2.0", "click"]
""")
        rows = dump_deps.parse_pyproject(p, "myrepo")
        deps = {r["dependency"]: r for r in rows}
        assert "requests" in deps
        assert deps["requests"]["version_spec"] == ">=2.0"
        assert deps["requests"]["dependency_type"] == "dependencies"
        assert deps["requests"]["package_name"] == "my-pkg"
        assert "click" in deps

    def test_optional_dependencies(self, tmp_path):
        p = self._write(tmp_path, """
[project]
name = "my-pkg"
[project.optional-dependencies]
memory = ["chromadb>=0.4"]
""")
        rows = dump_deps.parse_pyproject(p, "myrepo")
        assert any(r["dependency"] == "chromadb" and r["dependency_type"] == "optional:memory"
                   for r in rows)

    def test_build_dependencies(self, tmp_path):
        p = self._write(tmp_path, """
[project]
name = "my-pkg"
[build-system]
requires = ["hatchling"]
""")
        rows = dump_deps.parse_pyproject(p, "myrepo")
        assert any(r["dependency"] == "hatchling" and r["dependency_type"] == "build"
                   for r in rows)

    def test_dev_groups(self, tmp_path):
        p = self._write(tmp_path, """
[project]
name = "my-pkg"
[dependency-groups]
tests = ["pytest>=7", "pytest-cov"]
""")
        rows = dump_deps.parse_pyproject(p, "myrepo")
        assert any(r["dependency"] == "pytest" and r["dependency_type"] == "dev-group:tests"
                   for r in rows)

    def test_falls_back_to_repo_name(self, tmp_path):
        p = self._write(tmp_path, "[project]\ndependencies = []\n")
        rows = dump_deps.parse_pyproject(p, "myrepo")
        # No deps, but should not crash and package_name defaults to repo
        assert rows == []

    def test_min_version_populated(self, tmp_path):
        p = self._write(tmp_path, """
[project]
name = "my-pkg"
dependencies = ["requests>=2.28.0"]
""")
        rows = dump_deps.parse_pyproject(p, "myrepo")
        assert rows[0]["min_version"] == "2.28.0"


# ── parse_package_json ─────────────────────────────────────────────────────────

class TestParsePackageJson:
    def _write(self, tmp_path, data):
        p = tmp_path / "package.json"
        p.write_text(json.dumps(data))
        return p

    def test_dependencies(self, tmp_path):
        p = self._write(tmp_path, {
            "name": "@myorg/pkg",
            "dependencies": {"react": "^18.0.0"},
        })
        rows = dump_deps.parse_package_json(p, "myrepo")
        assert any(r["dependency"] == "react" and r["dependency_type"] == "dependencies"
                   for r in rows)

    def test_dev_dependencies(self, tmp_path):
        p = self._write(tmp_path, {
            "name": "@myorg/pkg",
            "devDependencies": {"vitest": "^1.0.0"},
        })
        rows = dump_deps.parse_package_json(p, "myrepo")
        assert any(r["dependency"] == "vitest" and r["dependency_type"] == "devDependencies"
                   for r in rows)

    def test_peer_and_optional(self, tmp_path):
        p = self._write(tmp_path, {
            "name": "pkg",
            "peerDependencies": {"react": ">=17"},
            "optionalDependencies": {"fsevents": "~2.3.2"},
        })
        rows = dump_deps.parse_package_json(p, "myrepo")
        types = {r["dependency"]: r["dependency_type"] for r in rows}
        assert types["react"] == "peerDependencies"
        assert types["fsevents"] == "optionalDependencies"

    def test_package_name_from_json(self, tmp_path):
        p = self._write(tmp_path, {"name": "@scope/my-lib", "dependencies": {"lodash": "^4.0.0"}})
        rows = dump_deps.parse_package_json(p, "myrepo")
        assert rows[0]["package_name"] == "@scope/my-lib"

    def test_min_version_caret(self, tmp_path):
        p = self._write(tmp_path, {"name": "pkg", "dependencies": {"lodash": "^4.17.21"}})
        rows = dump_deps.parse_package_json(p, "myrepo")
        assert rows[0]["min_version"] == "4.17.21"


# ── parse_uv_lock ──────────────────────────────────────────────────────────────

class TestParseUvLock:
    def test_extracts_packages(self, tmp_path):
        p = tmp_path / "uv.lock"
        p.write_bytes(b"""
version = 1
[[package]]
name = "requests"
version = "2.31.0"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "urllib3"
version = "2.0.7"
source = { registry = "https://pypi.org/simple" }
""")
        rows = dump_deps.parse_uv_lock(p, "myrepo")
        deps = {r["dependency"]: r for r in rows}
        assert "requests" in deps
        assert deps["requests"]["version_spec"] == "2.31.0"
        assert deps["requests"]["dependency_type"] == "transitive-pypi"
        assert deps["requests"]["min_version"] == "2.31.0"
        assert "urllib3" in deps

    def test_normalizes_package_name(self, tmp_path):
        p = tmp_path / "uv.lock"
        p.write_bytes(b"""
version = 1
[[package]]
name = "My_Package"
version = "1.0.0"
""")
        rows = dump_deps.parse_uv_lock(p, "myrepo")
        assert rows[0]["dependency"] == "my-package"

    def test_skips_entries_without_version(self, tmp_path):
        p = tmp_path / "uv.lock"
        p.write_bytes(b"""
version = 1
[[package]]
name = "incomplete"
""")
        rows = dump_deps.parse_uv_lock(p, "myrepo")
        assert rows == []


# ── parse_package_lock ─────────────────────────────────────────────────────────

class TestParsePackageLock:
    def test_extracts_packages(self, tmp_path):
        p = tmp_path / "package-lock.json"
        p.write_text(json.dumps({
            "lockfileVersion": 3,
            "packages": {
                "": {"name": "root", "version": "1.0.0"},
                "node_modules/lodash": {"version": "4.17.21"},
                "node_modules/react": {"version": "18.2.0"},
            }
        }))
        rows = dump_deps.parse_package_lock(p, "myrepo")
        deps = {r["dependency"]: r for r in rows}
        assert "lodash" in deps
        assert deps["lodash"]["version_spec"] == "4.17.21"
        assert deps["lodash"]["dependency_type"] == "transitive-npm"
        assert "react" in deps
        assert "" not in deps  # root entry skipped

    def test_nested_hoisted_packages(self, tmp_path):
        p = tmp_path / "package-lock.json"
        p.write_text(json.dumps({
            "packages": {
                "node_modules/foo/node_modules/bar": {"version": "2.0.0"},
            }
        }))
        rows = dump_deps.parse_package_lock(p, "myrepo")
        assert rows[0]["dependency"] == "foo/node_modules/bar"

    def test_min_version_from_exact(self, tmp_path):
        p = tmp_path / "package-lock.json"
        p.write_text(json.dumps({
            "packages": {"node_modules/zod": {"version": "3.22.4"}}
        }))
        rows = dump_deps.parse_package_lock(p, "myrepo")
        assert rows[0]["min_version"] == "3.22.4"
