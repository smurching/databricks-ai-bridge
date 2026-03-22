# Supply Chain Security Assessment: Trivy / trivy-action Compromise

**Date:** 2026-03-21
**Scope:** databricks-ai-bridge (this repository)
**Threat:** Trivy supply chain attack — malicious Trivy binary v0.69.4 + 76 poisoned `aquasecurity/trivy-action` tags (March 19–20, 2026)

---

## Executive Summary

This repository was **not exposed** to the Trivy supply chain attack. Trivy has never appeared anywhere in the codebase or git history. No credentials were at risk from this specific incident. However, the attack vector it exploited — GitHub Actions pinned by mutable tag instead of commit SHA — is present across **all 11 workflows** in this repo, meaning a similar attack against any of the 5 third-party Actions used here could succeed.

---

## 1. Threat Overview

Attackers with write access to the `aquasecurity/trivy-action` GitHub repository force-pushed 76 of 77 release tags to point at malicious commits, replacing the legitimate scanner with a 5-stage credential stealer:

1. Enumerate CI runner processes and extract environment variables
2. Steal credentials (GitHub tokens, AWS/GCP/Azure keys, SSH keys, Kubernetes configs, DB creds, crypto wallets) — from memory on GitHub-hosted runners, from filesystem on self-hosted runners
3. Encrypt stolen data with AES-256-CBC + RSA-wrapped session keys
4. Exfiltrate via HTTPS POST to typosquatted domain `scan.aquasecurtiy[.]org` (note the typo) with fallback to GitHub release uploads
5. Delete temp files; run legitimate Trivy scan to avoid detection

A Trivy binary (`v0.69.4`) was also compromised, installing a C2 loader at `~/.config/sysmon.py` that polled infrastructure on the Internet Computer blockchain (resistant to domain takedowns).

The root cause: **git tags are mutable**. Any repo that references a GitHub Action by tag instead of commit SHA can have the tag repointed without warning.

**Attack window:** March 19–20, 2026
**Compromised versions:** `trivy-action` tags v0.0.1–v0.34.2 (76 tags); `setup-trivy`; Trivy binary v0.69.4
**Safe versions:** `trivy-action >= 0.35.0`; Trivy binary `<= v0.69.3`

---

## 2. Impact Assessment: Current Exposure

### 2.1 Direct Dependencies — NOT AFFECTED

Searched all dependency manifests (`pyproject.toml`, `package.json`, `uv.lock`, `requirements*.txt`) for `trivy` and `aquasecurity`: **zero matches**.

### 2.2 Transitive Dependencies — NOT AFFECTED

`trivy` is a standalone binary, not a library dependency. Not present in any lockfile.

### 2.3 CI/CD Tools — NOT AFFECTED

Searched all 11 workflow files and full git history (`git log -S 'trivy'`, `git log -S 'aquasecurity'`) across all branches: **zero matches**. Trivy was never used in CI at any point in this repository's history.

### 2.4 Indicators of Compromise — NOT FOUND

- No references to `scan.aquasecurtiy[.]org`
- No references to `tpcp-docs` repository (exfil fallback)
- No `~/.config/sysmon.py` loader
- No `tpcp.tar.gz` staging files

**Files audited:**
- `.github/workflows/` — all 11 workflow files + `generate_release_workflows.py`
- Full git history via `git log --all -S 'trivy'` and `git log --all -S 'aquasecurity'`
- All `pyproject.toml`, `package.json`, lockfiles

---

## 3. Risk Assessment: Future Exposure

### 3.1 Published Packages at Risk

This repo publishes to two registries:

**PyPI** (6 packages):
- `databricks-ai-bridge`, `databricks-langchain`, `databricks-openai`, `databricks-mcp`, `databricks-dspy` (via DSPy release workflow)
- Publishing uses **OIDC Trusted Publishing** (`id-token: write` + `pypa/gh-action-pypi-publish`) — no long-lived `PYPI_TOKEN` present in workflows. This is best practice.
- Release jobs run on `databricks-protected-runner-group` (self-hosted, protected runners).

**npm** (2 packages):
- `@databricks/langchainjs`, `@databricks/ai-sdk-provider`
- Publishing uses `--provenance` flag (requires `id-token: write`) and scoped GitHub environments (`npm` / `npm-next`).
- `NODE_AUTH_TOKEN` is not explicitly visible in workflow YAML — set via the environment secret. Scoping to the environment is good practice.
- npm release jobs run on `ubuntu-latest` (GitHub-hosted runners, not protected).

**Self-propagation risk:** If a compromised Action stole publish credentials during a release workflow, it could publish malicious versions of any of these 8 packages to PyPI or npm. However, OIDC Trusted Publishing significantly reduces this risk for PyPI — there's no persistent token to steal, only a short-lived OIDC exchange scoped to the specific environment.

### 3.2 Existing Protections

| Protection | Status | Notes |
|---|---|---|
| OIDC Trusted Publishing (PyPI) | ✅ All Python release workflows | No long-lived PYPI_TOKEN |
| npm provenance attestation | ✅ All npm release workflows | `--provenance` flag used |
| GitHub Environments for secrets | ✅ All release workflows | `pypi` / `testpypi` / `npm` / `npm-next` |
| Protected runner group (release) | ✅ Python releases | `databricks-protected-runner-group` |
| `pull_request` (not `pull_request_target`) | ✅ `main.yml` | Secrets not exposed to fork PRs |
| `uv run --exact` lockfile enforcement | ✅ Most CI jobs | Prevents floating dependency resolution |
| npm `--ignore-scripts` on publish | ✅ `release-langchainjs.yml`, `release-ai-sdk-provider.yml` | Prevents postinstall hooks during publish |
| GitHub Actions pinned to SHA | ❌ All 11 workflows | All use mutable tags |
| Dependency audit in CI | ❌ Not present | No `pip-audit`, `npm audit`, or similar |
| Dependabot / Renovate | Not assessed | Not visible from repo files |

### 3.3 Identified Gaps

**CRITICAL — GitHub Actions not pinned to commit SHA**

Every workflow uses mutable tag references. A tag-poisoning attack identical to the Trivy incident against any of these Actions would succeed:

| Action | Tag Used | Risk |
|---|---|---|
| `actions/checkout` | `@v4` | High — used in every job, runs before any secrets are scoped |
| `actions/setup-python` | `@v5` | Medium — runs before build/publish |
| `actions/setup-node` | `@v4` | Medium — sets up `NODE_AUTH_TOKEN` |
| `astral-sh/setup-uv` | `@v6`, `@v5` | Medium — runs before test/build |
| `pypa/gh-action-pypi-publish` | `@release/v1` | **Critical** — directly handles publish credentials |
| `ncipollo/release-action` | `@v1` | Medium — has `contents: write` permission |
| `actions/upload-artifact` | `@v5`, `@v4` | Low |
| `actions/download-artifact` | `@v4` | Low |

The highest risk is `pypa/gh-action-pypi-publish@release/v1` — a rolling branch tag (`release/v1`), not even a version tag, making it especially mutable.

**MEDIUM — Bare `pip install` in some CI jobs (no lockfile)**

`main.yml` lines 131–147 (`langchain_cross_version_test`) use bare `pip install .` and `pip install integrations/langchain --group dev` without lockfile constraints. If a transitive dependency were compromised, this job would silently pull the malicious version.

**LOW — npm releases on GitHub-hosted runners**

npm release workflows run on `ubuntu-latest` (GitHub-hosted) while Python release workflows use the protected runner group. Consistency would be better.

### 3.4 Attack Scenarios

**Scenario A: Repo as victim (tag poisoning)**
An attacker compromises `pypa/gh-action-pypi-publish` and repoints `@release/v1` to a malicious commit. On next release, the malicious action runs with `id-token: write` in scope. Even with OIDC, the action could abuse the token during the publish step. The `ncipollo/release-action@v1` has `contents: write` which could be used to create or modify GitHub releases.

**Scenario B: Repo as vector (self-propagation)**
If any credential were stolen during a release workflow, an attacker could publish malicious versions of `databricks-openai`, `databricks-langchain`, etc. to PyPI/npm. Downstream projects installing these packages would then be compromised. OIDC mitigates this significantly for PyPI but depends on environment protection rules being properly configured.

**Scenario C: Compromised `actions/checkout`**
`checkout@v4` runs as the first step in every single job — before any permission scoping. A compromised checkout action runs in the most permissive window possible.

---

## 4. Recommendations

### Priority 1 — Immediate (days)

**Pin all GitHub Actions to commit SHAs.** This single change would have completely prevented the Trivy attack vector. Use a tool like `pin-github-actions` or Renovate's SHA-pinning mode to automate this.

Before:
```yaml
uses: pypa/gh-action-pypi-publish@release/v1
```
After:
```yaml
uses: pypa/gh-action-pypi-publish@ec4db0b4ddc65acdf4bff5fa45ac92d78b56bdf0 # release/v1 @ 2025-xx-xx
```

**Note:** `generate_release_workflows.py` generates the Python release workflows — SHA pinning must be applied there, not just in the generated files.

### Priority 2 — Short-term (weeks)

1. **Add `pip-audit` / `npm audit` to CI.** Catch known-vulnerable transitive deps before merge.

2. **Move npm release workflows to the protected runner group.** Currently npm releases run on `ubuntu-latest` while Python releases use `databricks-protected-runner-group`. Align them.

3. **Pin `setup-uv` version consistency.** `ty.yml` uses `astral-sh/setup-uv@v5` while other workflows use `@v6`. Standardize.

4. **Replace bare `pip install` in `langchain_cross_version_test`.** The cross-version test jobs install without lockfile constraints — consider adding `--constraint` files or pinning at least the test matrix versions.

### Priority 3 — Medium-term (months)

1. **Add Dependabot or Renovate for Actions SHA updates.** Once pinned to SHAs, automated PRs keep them current with verified updates.

2. **Audit npm environment secret configuration.** Confirm `NODE_AUTH_TOKEN` is scoped only to the npm/npm-next environments and not available to CI test jobs.

3. **Add CODEOWNERS for workflow files.** Require review from a security-aware owner for any changes to `.github/workflows/` and `generate_release_workflows.py`.

4. **Consider SLSA Level 2+ for PyPI releases.** The OIDC + provenance setup is already close — formalizing with SLSA attestation would provide a verifiable build chain.

---

## 5. Appendix

### Packages Checked
- `aquasecurity/trivy-action` — not present (current or historical)
- `aquasecurity/setup-trivy` — not present (current or historical)
- Trivy binary `v0.69.4` — not present
- IOC domains (`scan.aquasecurtiy[.]org`) — not present
- IOC repos (`tpcp-docs`) — not present

### Files Audited
- `.github/workflows/main.yml`
- `.github/workflows/release-databricks-ai-bridge.yml`
- `.github/workflows/release-databricks-langchain.yml`
- `.github/workflows/release-databricks-openai.yml`
- `.github/workflows/release-databricks-mcp.yml`
- `.github/workflows/databricks-dspy-release.yml`
- `.github/workflows/release-langchainjs.yml`
- `.github/workflows/release-ai-sdk-provider.yml`
- `.github/workflows/ai-sdk-provider.yml`
- `.github/workflows/langchainjs.yml`
- `.github/workflows/ty.yml`
- `.github/workflows/generate_release_workflows.py`
- Full git history via `git log --all -S 'trivy'` and `git log --all -S 'aquasecurity'`

### Sources
- CrowdStrike: "From Scanner to Stealer: Inside the trivy-action Supply Chain Compromise" (2026-03-xx)
- The Hacker News: "Trivy Security Scanner GitHub Actions Breached, 75 Tags Poisoned" (2026-03-xx)
- Aqua Security blog post on the incident
- Socket.dev: "Trivy Under Attack Again: Widespread GitHub Actions Tag Compromise"
- Chainguard: "Secure-by-default: Chainguard customers unaffected by the Trivy supply chain attack"
