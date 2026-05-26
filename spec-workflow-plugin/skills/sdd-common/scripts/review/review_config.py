"""Single source of truth for review dimension configuration.

Adding a dimension: append one entry to DIMENSIONS.
All display names, snake_case keys, labels, and validation lists
are derived automatically.
"""
from typing import NamedTuple


class Dimension(NamedTuple):
    key: str        # snake_case for progress state and script args
    display: str    # Title Case for report markdown tables
    step: str       # Step reference (e.g., "4a")
    required: bool  # True for [REQUIRED], False for [CONDITIONAL]


DIMENSIONS = [
    Dimension("code_quality",       "Code Quality",       "4a", True),
    Dimension("architecture",       "Architecture",       "4b", True),
    Dimension("security",           "Security",           "4c", True),
    Dimension("performance",        "Performance",        "4d", True),
    Dimension("testing",            "Testing",            "4e", True),
    Dimension("conventions",        "Conventions",        "4f", True),
    Dimension("general_principles", "General Principles", "4g", True),
]

REQUIRED_DIMENSIONS = [d for d in DIMENSIONS if d.required]

DIMENSION_KEYS = [d.key for d in REQUIRED_DIMENSIONS]
DIMENSION_DISPLAYS = [d.display for d in REQUIRED_DIMENSIONS]
DIMENSION_LABELS = {d.key: f"{d.display} ({d.step})" for d in REQUIRED_DIMENSIONS}

PRINCIPLES = ["DRY", "SRP", "OCP", "LSP", "ISP", "DIP", "KISS", "YAGNI"]

ANTI_PATTERNS = [
    "God object", "Shotgun surgery", "Feature envy",
    "Primitive obsession", "Dead code", "Magic numbers",
]
