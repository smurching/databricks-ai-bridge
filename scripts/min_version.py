"""
Best-effort extraction of the minimum semver implied by a version spec string.

This is a separate module because the core dependency dumper doesn't need it —
the primary audit question is "do we depend on this package at all". Import this
only when you need the min_version column populated with parsed values.
"""

import re

_SEMVER_FINDALL = re.compile(r"(\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)")
_SEMVER_EXACT = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
_NON_SEMVER_PREFIXES = (
    "workspace:", "file:", "link:", "portal:", "patch:",
    "git:", "git+", "github:", "gitlab:", "bitbucket:",
    "http://", "https://",
)


def _parse(s: str) -> tuple | None:
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?", s)
    if not m:
        return None
    return (int(m[1]), int(m[2]), int(m[3]), m[4] or "")


def _key(t: tuple) -> tuple:
    major, minor, patch, pre = t
    return (major, minor, patch, 0 if pre else 1, pre)  # stable > prerelease


def min_version(spec: str) -> str:
    """Return the lowest semver implied by spec, or '' if not determinable."""
    if not spec:
        return ""
    spec = spec.strip()
    if any(spec.startswith(p) for p in _NON_SEMVER_PREFIXES):
        return ""
    if spec.startswith("npm:"):
        inner = spec[4:]
        at = inner.rfind("@")
        if at > 0:
            spec = inner[at + 1:].strip()
    if spec in ("*", "x", "X", ""):
        return ""
    if _SEMVER_EXACT.match(spec):
        return spec
    candidates = [c for c in (_parse(m) for m in _SEMVER_FINDALL.findall(spec)) if c is not None]
    if not candidates:
        return ""
    best = min(candidates, key=_key)
    return "{}.{}.{}{}".format(best[0], best[1], best[2], f"-{best[3]}" if best[3] else "")
