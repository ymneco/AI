"""N-gram based sequence pattern detection engine."""

from collections import Counter
from typing import Dict, List, Optional, Tuple

from config import MIN_PATTERN_FREQUENCY, MIN_PATTERN_LENGTH, MAX_PATTERN_LENGTH
from core.action_types import ActionEvent, ActionPattern, ScreenRegion
from assistant.feature_extractor import FeatureExtractor
from utils.logging_config import get_logger

logger = get_logger("pattern_engine")


class PatternMatch:
    """Represents a match between recent actions and a known pattern."""
    def __init__(self, pattern: ActionPattern, match_score: float,
                 matched_length: int, remaining_symbols: List[str]):
        self.pattern = pattern
        self.match_score = match_score
        self.matched_length = matched_length
        self.remaining_symbols = remaining_symbols


class PatternEngine:
    """Discovers recurring action subsequences using n-gram matching.

    Algorithm:
    1. Convert action sequences to symbolic strings
    2. Find repeated subsequences of length 3..20
    3. Score by frequency * sqrt(length) * timing_consistency
    4. Merge overlapping patterns
    """

    def __init__(self):
        self._feature_extractor = FeatureExtractor()

    def analyze_sessions(
        self,
        sessions_data: List[Tuple[ScreenRegion, List[ActionEvent]]]
    ) -> List[ActionPattern]:
        """Analyze multiple sessions to discover patterns.

        Args:
            sessions_data: List of (region, events) tuples

        Returns:
            List of discovered ActionPatterns
        """
        if not sessions_data:
            return []

        # Symbolize all sessions
        all_symbol_sequences: List[List[str]] = []
        for region, events in sessions_data:
            self._feature_extractor.set_region(region)
            symbols = self._feature_extractor.symbolize_sequence(events)
            if len(symbols) >= MIN_PATTERN_LENGTH:
                all_symbol_sequences.append(symbols)

        if not all_symbol_sequences:
            return []

        # Find repeated n-grams across sessions
        ngram_counts: Counter = Counter()
        ngram_session_counts: Dict[tuple, set] = {}

        for session_idx, symbols in enumerate(all_symbol_sequences):
            seen_in_session: set = set()

            for window_size in range(MIN_PATTERN_LENGTH, MAX_PATTERN_LENGTH + 1):
                for start in range(len(symbols) - window_size + 1):
                    ngram = tuple(symbols[start:start + window_size])

                    if ngram not in seen_in_session:
                        seen_in_session.add(ngram)
                        if ngram not in ngram_session_counts:
                            ngram_session_counts[ngram] = set()
                        ngram_session_counts[ngram].add(session_idx)

                    ngram_counts[ngram] += 1

        # Filter: keep patterns appearing in >= MIN_PATTERN_FREQUENCY sessions
        frequent_patterns: List[Tuple[tuple, int, int]] = []
        for ngram, count in ngram_counts.items():
            session_count = len(ngram_session_counts.get(ngram, set()))
            if session_count >= MIN_PATTERN_FREQUENCY:
                frequent_patterns.append((ngram, count, session_count))

        # Score and sort
        scored = []
        for ngram, total_count, session_count in frequent_patterns:
            length = len(ngram)
            score = total_count * (length ** 0.5) * (session_count / len(all_symbol_sequences))
            scored.append((ngram, score, total_count, session_count))

        scored.sort(key=lambda x: x[1], reverse=True)

        # Remove subpatterns (if a longer pattern fully contains a shorter one)
        filtered = self._remove_subpatterns(scored)

        # Convert to ActionPattern objects
        patterns = []
        for ngram, score, total_count, session_count in filtered[:50]:  # top 50
            symbol_seq = " ".join(ngram)
            action_types = list(set(s.split("_")[0] for s in ngram))

            pattern = ActionPattern(
                name=f"Pattern ({len(ngram)} actions)",
                description=f"Seen {total_count} times across {session_count} sessions",
                symbol_sequence=symbol_seq,
                action_types=action_types,
                frequency=total_count,
                confidence=min(0.9, 0.3 + 0.1 * session_count),
            )
            patterns.append(pattern)

        logger.info(f"Discovered {len(patterns)} patterns from "
                     f"{len(all_symbol_sequences)} sessions")
        return patterns

    def find_matches(
        self,
        recent_symbols: List[str],
        patterns: List[ActionPattern],
        min_match_ratio: float = 0.5
    ) -> List[PatternMatch]:
        """Find patterns that match the recent action sequence.

        Checks if the suffix of recent_symbols matches a prefix of any pattern.
        """
        matches = []

        for pattern in patterns:
            if not pattern.is_active:
                continue

            pattern_symbols = pattern.symbol_sequence.split(" ")
            pattern_len = len(pattern_symbols)

            if pattern_len == 0:
                continue

            # Try different suffix lengths of recent_symbols
            best_match_len = 0
            for suffix_len in range(min(len(recent_symbols), pattern_len), 0, -1):
                suffix = recent_symbols[-suffix_len:]
                prefix = pattern_symbols[:suffix_len]

                if suffix == prefix:
                    best_match_len = suffix_len
                    break

            if best_match_len > 0:
                match_ratio = best_match_len / pattern_len

                if match_ratio >= min_match_ratio:
                    remaining = pattern_symbols[best_match_len:]
                    matches.append(PatternMatch(
                        pattern=pattern,
                        match_score=match_ratio,
                        matched_length=best_match_len,
                        remaining_symbols=remaining,
                    ))

        # Sort by match score descending
        matches.sort(key=lambda m: m.match_score, reverse=True)
        return matches

    def _remove_subpatterns(
        self, scored: List[Tuple[tuple, float, int, int]]
    ) -> List[Tuple[tuple, float, int, int]]:
        """Remove patterns that are fully contained in higher-scoring patterns."""
        if not scored:
            return []

        result = []
        used_ngrams = set()

        for item in scored:
            ngram = item[0]
            ngram_str = " ".join(ngram)

            # Check if this is a substring of any already-accepted pattern
            is_sub = False
            for used in used_ngrams:
                if ngram_str in used:
                    is_sub = True
                    break

            if not is_sub:
                result.append(item)
                used_ngrams.add(ngram_str)

        return result
