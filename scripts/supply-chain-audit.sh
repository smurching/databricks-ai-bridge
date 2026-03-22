#!/usr/bin/env bash
# supply-chain-audit.sh
# Audits this repo for supply chain attack indicators.
# Usage: ./scripts/supply-chain-audit.sh [--packages "pkg1 pkg2"] [--iocs "domain1 domain2"]
#
# Checks performed:
#   1. Compromised packages/tools in current code and git history
#   2. Known IOC domains/files
#   3. GitHub Actions pinning (tags vs commit SHAs)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESULTS_FILE="$REPO_ROOT/supply-chain-audit-results.md"

# ── Defaults (extend via flags) ────────────────────────────────────────────────
SUSPECT_PACKAGES=(
  "trivy"
  "aquasecurity"
  "emilgroup"
)
IOCS=(
  "scan.aquasecurtiy.org"   # typosquatted Trivy exfil domain
  "tpcp-docs"               # Trivy exfil fallback repo
  "sysmon.py"               # Trivy C2 loader path
)

# ── Argument parsing ───────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --packages)
      IFS=' ' read -ra EXTRA_PACKAGES <<< "$2"
      SUSPECT_PACKAGES+=("${EXTRA_PACKAGES[@]}")
      shift 2 ;;
    --iocs)
      IFS=' ' read -ra EXTRA_IOCS <<< "$2"
      IOCS+=("${EXTRA_IOCS[@]}")
      shift 2 ;;
    *) echo "Unknown flag: $1"; exit 1 ;;
  esac
done

# ── Helpers ────────────────────────────────────────────────────────────────────
PASS="✅"
FAIL="❌"
WARN="⚠️"

findings=0
warnings=0

emit() { echo "$1" | tee -a "$RESULTS_FILE"; }
section() { emit ""; emit "## $1"; emit ""; }
result() {
  local icon="$1" label="$2" detail="$3"
  emit "$icon **$label** — $detail"
  [[ "$icon" == "$FAIL" ]] && (( findings++ )) || true
  [[ "$icon" == "$WARN" ]] && (( warnings++ )) || true
}

# ── Start report ───────────────────────────────────────────────────────────────
cd "$REPO_ROOT"
: > "$RESULTS_FILE"   # truncate

emit "# Supply Chain Audit Results"
emit ""
emit "**Date:** $(date -u '+%Y-%m-%d %H:%M UTC')"
emit "**Repo:** $(git remote get-url origin 2>/dev/null || echo '(local)')"
emit "**Branch:** $(git rev-parse --abbrev-ref HEAD)"
emit "**Commit:** $(git rev-parse HEAD)"

# ══════════════════════════════════════════════════════════════════════════════
section "1. Suspect Packages / Tools"
emit "Searching current files and full git history for: \`${SUSPECT_PACKAGES[*]}\`"
emit ""

for pkg in "${SUSPECT_PACKAGES[@]}"; do
  # Current files (case-insensitive, skip node_modules/.venv/.git and this script's own output files)
  current_hits=$(grep -ril "$pkg" \
    --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv \
    --exclude="supply-chain-audit*.md" \
    --exclude="supply-chain-audit.sh" \
    "$REPO_ROOT" 2>/dev/null || true)

  # Git history (commits predating this audit script)
  history_hits=$(git log --all --oneline -S "$pkg" \
    -- ':!scripts/supply-chain-audit.sh' ':!supply-chain-audit*.md' \
    2>/dev/null || true)

  if [[ -z "$current_hits" && -z "$history_hits" ]]; then
    result "$PASS" "$pkg" "not found in current files or git history"
  else
    if [[ -n "$current_hits" ]]; then
      result "$FAIL" "$pkg" "found in current files:"
      while IFS= read -r f; do
        emit "  - \`${f#$REPO_ROOT/}\`"
      done <<< "$current_hits"
    fi
    if [[ -n "$history_hits" ]]; then
      result "$FAIL" "$pkg" "found in git history:"
      while IFS= read -r line; do
        emit "  - $line"
      done <<< "$history_hits"
    fi
  fi
done

# ══════════════════════════════════════════════════════════════════════════════
section "2. Indicators of Compromise (IOCs)"
emit "Searching for known malicious domains, filenames, and artifacts."
emit ""

for ioc in "${IOCS[@]}"; do
  hits=$(grep -ril "$ioc" \
    --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv \
    --exclude="supply-chain-audit*.md" \
    --exclude="supply-chain-audit.sh" \
    "$REPO_ROOT" 2>/dev/null || true)
  git_hits=$(git log --all --oneline -S "$ioc" \
    -- ':!scripts/supply-chain-audit.sh' ':!supply-chain-audit*.md' \
    2>/dev/null || true)

  if [[ -z "$hits" && -z "$git_hits" ]]; then
    result "$PASS" "$ioc" "not found"
  else
    result "$FAIL" "$ioc" "FOUND — potential indicator of compromise"
    [[ -n "$hits" ]] && while IFS= read -r f; do emit "  - \`${f#$REPO_ROOT/}\`"; done <<< "$hits"
    [[ -n "$git_hits" ]] && while IFS= read -r line; do emit "  - (history) $line"; done <<< "$git_hits"
  fi
done

# ══════════════════════════════════════════════════════════════════════════════
section "3. GitHub Actions Pinning"
emit "Checking whether Actions are pinned to commit SHAs (safe) or mutable tags/branches (at risk)."
emit ""

workflow_files=$(find "$REPO_ROOT/.github/workflows" -name "*.yml" -o -name "*.yaml" 2>/dev/null | sort)

if [[ -z "$workflow_files" ]]; then
  result "$PASS" "No workflow files found" "nothing to check"
else
  tag_pinned=()
  sha_pinned=()
  branch_pinned=()

  while IFS= read -r wf; do
    wf_name="${wf#$REPO_ROOT/}"
    # Extract all `uses:` lines
    while IFS= read -r uses_line; do
      action=$(echo "$uses_line" | sed 's/.*uses:[[:space:]]*//' | tr -d '"'"'" | xargs)
      [[ -z "$action" ]] && continue

      # Classify by ref
      if echo "$action" | grep -qE '@[0-9a-f]{40}$'; then
        sha_pinned+=("$wf_name | $action")
      elif echo "$action" | grep -qE '@(v[0-9]|[0-9]+\.[0-9]+)'; then
        tag_pinned+=("$wf_name | $action")
      elif echo "$action" | grep -qE '@(master|main|release/)'; then
        branch_pinned+=("$wf_name | $action")
      elif echo "$action" | grep -qE '@'; then
        tag_pinned+=("$wf_name | $action")  # unknown ref — treat as unsafe
      fi
    done < <(grep -E '^\s+uses:' "$wf")
  done <<< "$workflow_files"

  if [[ ${#sha_pinned[@]} -gt 0 ]]; then
    emit "**SHA-pinned (safe):**"
    for entry in "${sha_pinned[@]}"; do result "$PASS" "${entry##* | }" "in \`${entry%% |*}\`"; done
    emit ""
  fi

  if [[ ${#tag_pinned[@]} -gt 0 ]]; then
    emit "**Tag-pinned (at risk — tags are mutable):**"
    for entry in "${tag_pinned[@]}"; do result "$FAIL" "${entry##* | }" "in \`${entry%% |*}\`"; done
    emit ""
  fi

  if [[ ${#branch_pinned[@]} -gt 0 ]]; then
    emit "**Branch-pinned (high risk — branch HEAD changes constantly):**"
    for entry in "${branch_pinned[@]}"; do result "$FAIL" "${entry##* | }" "in \`${entry%% |*}\`"; done
    emit ""
  fi
fi

# ══════════════════════════════════════════════════════════════════════════════
section "Summary"
total_checks=$(( findings + warnings ))
if [[ $findings -eq 0 && $warnings -eq 0 ]]; then
  emit "$PASS **No issues found.** Repository appears clean."
else
  emit "$FAIL **$findings finding(s), $warnings warning(s) require attention.**"
  emit ""
  emit "Review the sections above and:"
  emit "- Investigate any package or IOC findings immediately"
  emit "- Pin all tag/branch-referenced Actions to full commit SHAs"
fi

emit ""
emit "---"
emit "_Generated by \`scripts/supply-chain-audit.sh\`_"

echo ""
echo "Report written to: $RESULTS_FILE"
echo "Findings: $findings | Warnings: $warnings"
[[ $findings -gt 0 ]] && exit 1 || exit 0
