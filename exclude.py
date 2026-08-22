"""Filter out strips whose source notes explicitly say not to land without
the owner's permission, or otherwise flag the strip as closed to visitors.

Most private-ownership strips are NOT excluded here -- FAA and other
sources routinely mark small privately-owned airstrips as "private" simply
as an ownership fact, and many of those explicitly welcome visitors in
their notes (e.g. a strip owner who "welcomes visitors who would like to
take a minute and chat"). Only strips whose notes contain an explicit
do-not-land / permission-required / no-trespassing signal are dropped.

This is a blunt regex pass, not a legal read of each strip's actual access
policy -- when in doubt, a strip stays in rather than being silently
dropped. Review PERMISSION_REQUIRED_PATTERNS periodically against new
source text rather than trying to make the pattern list exhaustive upfront.
"""

import re

PERMISSION_REQUIRED_PATTERNS = [
    r"do\s*not\s*land",
    r"don'?t\s*land",
    r"prior\s*permission",
    r"permission\s*required",
    r"permission\s*from\s*the\s*owner",
    r"without\s*(?:the\s*)?(?:owner'?s?\s*)?permission",
    r"no\s*trespassing",
    r"not\s*open\s*to\s*the\s*public",
    r"closed\s*to\s*(?:the\s*)?public",
]

_PATTERN = re.compile("|".join(PERMISSION_REQUIRED_PATTERNS), re.IGNORECASE)


def _permission_required(strip):
    text = " ".join(
        filter(None, [strip.get("condition_notes"), strip.get("access_notes"), strip.get("hazards")])
    )
    return bool(_PATTERN.search(text))


def remove_permission_required(strips):
    """Return (kept, excluded) -- excluded strips are the ones whose notes
    explicitly require permission or forbid landing."""
    kept, excluded = [], []
    for strip in strips:
        (excluded if _permission_required(strip) else kept).append(strip)
    return kept, excluded
