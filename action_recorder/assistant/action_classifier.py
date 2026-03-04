"""Assigns human-readable names to discovered action patterns."""

from core.action_types import ActionPattern
from utils.logging_config import get_logger

logger = get_logger("action_classifier")

# Known action sequences and their names
KNOWN_PATTERNS = {
    "KC_ctrl+c": "Copy",
    "KC_ctrl+v": "Paste",
    "KC_ctrl+x": "Cut",
    "KC_ctrl+z": "Undo",
    "KC_ctrl+y": "Redo",
    "KC_ctrl+s": "Save",
    "KC_ctrl+a": "Select All",
    "KC_ctrl+f": "Find",
    "KC_alt+tab": "Switch Window",
    "KC_alt+f4": "Close Window",
}


class ActionClassifier:
    """Assigns human-readable names to action patterns."""

    def classify(self, pattern: ActionPattern) -> str:
        """Generate a human-readable name for a pattern."""
        symbols = pattern.symbol_sequence.split(" ")

        if not symbols:
            return f"Pattern #{pattern.pattern_id}"

        # Check for known key combo patterns
        known_parts = []
        for sym in symbols:
            if sym in KNOWN_PATTERNS:
                known_parts.append(KNOWN_PATTERNS[sym])

        if known_parts:
            name = " then ".join(known_parts)
            if len(symbols) > len(known_parts):
                name += f" (+{len(symbols) - len(known_parts)} actions)"
            return name

        # Analyze composition
        type_counts = {}
        for sym in symbols:
            prefix = sym.split("_")[0]
            type_counts[prefix] = type_counts.get(prefix, 0) + 1

        parts = []
        if "MC" in type_counts:
            parts.append(f"{type_counts['MC']} clicks")
        if "KC" in type_counts:
            parts.append(f"{type_counts['KC']} combos")
        if "KP" in type_counts:
            parts.append(f"{type_counts['KP']} keystrokes")
        if "MS" in type_counts:
            parts.append(f"{type_counts['MS']} scrolls")
        if "MDS" in type_counts or "MDE" in type_counts:
            parts.append("drag")

        if parts:
            return ", ".join(parts)

        return f"Pattern ({len(symbols)} actions)"

    def set_custom_name(self, pattern: ActionPattern, name: str):
        """Allow user to set a custom name."""
        pattern.name = name
        pattern.user_confirmed = True
