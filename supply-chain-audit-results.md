# Supply Chain Audit Results

**Date:** 2026-03-22 02:36 UTC
**Repo:** git@github.com:smurching/databricks-ai-bridge.git
**Branch:** add-npm-release-workflow
**Commit:** 5dc3abdcd5d450f48cd0658e189deac572d949f7

## 1. Suspect Packages / Tools

Searching current files and full git history for: `trivy aquasecurity emilgroup`

✅ **trivy** — not found in current files or git history
✅ **aquasecurity** — not found in current files or git history
✅ **emilgroup** — not found in current files or git history

## 2. Indicators of Compromise (IOCs)

Searching for known malicious domains, filenames, and artifacts.

✅ **scan.aquasecurtiy.org** — not found
✅ **tpcp-docs** — not found
✅ **sysmon.py** — not found

## 3. GitHub Actions Pinning

Checking whether Actions are pinned to commit SHAs (safe) or mutable tags/branches (at risk).

**Tag-pinned (at risk — tags are mutable):**
❌ **actions/checkout@v4** — in `.github/workflows/ai-sdk-provider.yml`
❌ **actions/setup-node@v4** — in `.github/workflows/ai-sdk-provider.yml`
❌ **actions/checkout@v4** — in `.github/workflows/ai-sdk-provider.yml`
❌ **actions/setup-node@v4** — in `.github/workflows/ai-sdk-provider.yml`
❌ **actions/checkout@v4** — in `.github/workflows/ai-sdk-provider.yml`
❌ **actions/setup-node@v4** — in `.github/workflows/ai-sdk-provider.yml`
❌ **actions/checkout@v4** — in `.github/workflows/ai-sdk-provider.yml`
❌ **actions/setup-node@v4** — in `.github/workflows/ai-sdk-provider.yml`
❌ **actions/checkout@v4** — in `.github/workflows/ai-sdk-provider.yml`
❌ **actions/setup-node@v4** — in `.github/workflows/ai-sdk-provider.yml`
❌ **actions/checkout@v4** — in `.github/workflows/databricks-dspy-release.yml`
❌ **actions/setup-python@v5** — in `.github/workflows/databricks-dspy-release.yml`
❌ **actions/upload-artifact@v4** — in `.github/workflows/databricks-dspy-release.yml`
❌ **actions/upload-artifact@v4** — in `.github/workflows/databricks-dspy-release.yml`
❌ **actions/checkout@v4** — in `.github/workflows/databricks-dspy-release.yml`
❌ **actions/setup-python@v5** — in `.github/workflows/databricks-dspy-release.yml`
❌ **actions/download-artifact@v4** — in `.github/workflows/databricks-dspy-release.yml`
❌ **actions/checkout@v4** — in `.github/workflows/databricks-dspy-release.yml`
❌ **actions/setup-python@v5** — in `.github/workflows/databricks-dspy-release.yml`
❌ **actions/download-artifact@v4** — in `.github/workflows/databricks-dspy-release.yml`
❌ **actions/checkout@v4** — in `.github/workflows/langchainjs.yml`
❌ **actions/setup-node@v4** — in `.github/workflows/langchainjs.yml`
❌ **actions/checkout@v4** — in `.github/workflows/langchainjs.yml`
❌ **actions/setup-node@v4** — in `.github/workflows/langchainjs.yml`
❌ **actions/checkout@v4** — in `.github/workflows/langchainjs.yml`
❌ **actions/setup-node@v4** — in `.github/workflows/langchainjs.yml`
❌ **actions/checkout@v4** — in `.github/workflows/langchainjs.yml`
❌ **actions/setup-node@v4** — in `.github/workflows/langchainjs.yml`
❌ **actions/checkout@v4** — in `.github/workflows/langchainjs.yml`
❌ **actions/setup-node@v4** — in `.github/workflows/langchainjs.yml`
❌ **actions/checkout@v4** — in `.github/workflows/main.yml`
❌ **astral-sh/setup-uv@v6** — in `.github/workflows/main.yml`
❌ **actions/checkout@v4** — in `.github/workflows/main.yml`
❌ **astral-sh/setup-uv@v6** — in `.github/workflows/main.yml`
❌ **actions/checkout@v4** — in `.github/workflows/main.yml`
❌ **astral-sh/setup-uv@v6** — in `.github/workflows/main.yml`
❌ **actions/checkout@v4** — in `.github/workflows/main.yml`
❌ **astral-sh/setup-uv@v6** — in `.github/workflows/main.yml`
❌ **actions/checkout@v4** — in `.github/workflows/main.yml`
❌ **actions/setup-python@v5** — in `.github/workflows/main.yml`
❌ **actions/checkout@v4** — in `.github/workflows/main.yml`
❌ **actions/checkout@v4** — in `.github/workflows/main.yml`
❌ **astral-sh/setup-uv@v6** — in `.github/workflows/main.yml`
❌ **actions/checkout@v4** — in `.github/workflows/main.yml`
❌ **astral-sh/setup-uv@v6** — in `.github/workflows/main.yml`
❌ **actions/checkout@v4** — in `.github/workflows/main.yml`
❌ **actions/setup-python@v5** — in `.github/workflows/main.yml`
❌ **actions/checkout@v4** — in `.github/workflows/main.yml`
❌ **actions/checkout@v4** — in `.github/workflows/main.yml`
❌ **astral-sh/setup-uv@v6** — in `.github/workflows/main.yml`
❌ **actions/checkout@v4** — in `.github/workflows/main.yml`
❌ **astral-sh/setup-uv@v6** — in `.github/workflows/main.yml`
❌ **actions/checkout@v4** — in `.github/workflows/main.yml`
❌ **astral-sh/setup-uv@v6** — in `.github/workflows/main.yml`
❌ **actions/upload-artifact@v5** — in `.github/workflows/release-databricks-ai-bridge.yml`
❌ **actions/upload-artifact@v5** — in `.github/workflows/release-databricks-langchain.yml`
❌ **actions/upload-artifact@v5** — in `.github/workflows/release-databricks-mcp.yml`
❌ **actions/upload-artifact@v5** — in `.github/workflows/release-databricks-openai.yml`
❌ **actions/checkout@v4** — in `.github/workflows/ty.yml`
❌ **astral-sh/setup-uv@v5** — in `.github/workflows/ty.yml`
❌ **actions/checkout@v4** — in `.github/workflows/ty.yml`
❌ **astral-sh/setup-uv@v5** — in `.github/workflows/ty.yml`
❌ **actions/checkout@v4** — in `.github/workflows/ty.yml`
❌ **astral-sh/setup-uv@v5** — in `.github/workflows/ty.yml`

**Branch-pinned (high risk — branch HEAD changes constantly):**
❌ **pypa/gh-action-pypi-publish@release/v1** — in `.github/workflows/databricks-dspy-release.yml`
❌ **pypa/gh-action-pypi-publish@release/v1** — in `.github/workflows/databricks-dspy-release.yml`
❌ **pypa/gh-action-pypi-publish@release/v1** — in `.github/workflows/release-databricks-ai-bridge.yml`
❌ **pypa/gh-action-pypi-publish@release/v1** — in `.github/workflows/release-databricks-ai-bridge.yml`
❌ **pypa/gh-action-pypi-publish@release/v1** — in `.github/workflows/release-databricks-langchain.yml`
❌ **pypa/gh-action-pypi-publish@release/v1** — in `.github/workflows/release-databricks-langchain.yml`
❌ **pypa/gh-action-pypi-publish@release/v1** — in `.github/workflows/release-databricks-mcp.yml`
❌ **pypa/gh-action-pypi-publish@release/v1** — in `.github/workflows/release-databricks-mcp.yml`
❌ **pypa/gh-action-pypi-publish@release/v1** — in `.github/workflows/release-databricks-openai.yml`
❌ **pypa/gh-action-pypi-publish@release/v1** — in `.github/workflows/release-databricks-openai.yml`


## Summary

❌ **74 finding(s), 0 warning(s) require attention.**

Review the sections above and:
- Investigate any package or IOC findings immediately
- Pin all tag/branch-referenced Actions to full commit SHAs

---
_Generated by `scripts/supply-chain-audit.sh`_
