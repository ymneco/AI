"""Real-time action prediction engine."""

import threading
import time
from collections import deque
from typing import Callable, List, Optional

from config import SLIDING_WINDOW_SIZE, DEFAULT_CONFIDENCE_THRESHOLD
from core.action_types import ActionEvent, ActionPattern, Prediction, ScreenRegion
from assistant.feature_extractor import FeatureExtractor
from assistant.pattern_engine import PatternEngine, PatternMatch
from assistant.action_classifier import ActionClassifier
from utils.logging_config import get_logger

logger = get_logger("predictor")


class ActionPredictor:
    """Real-time prediction engine running in a background thread.

    Maintains a sliding window of recent actions and compares them
    against known patterns to predict next actions.
    """

    def __init__(self,
                 patterns: List[ActionPattern],
                 region: ScreenRegion = None,
                 on_prediction: Optional[Callable[[Prediction], None]] = None,
                 confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
                 window_size: int = SLIDING_WINDOW_SIZE):
        self._patterns = patterns
        self._region = region
        self._on_prediction = on_prediction
        self._confidence_threshold = confidence_threshold
        self._window_size = window_size

        self._feature_extractor = FeatureExtractor(region)
        self._pattern_engine = PatternEngine()
        self._classifier = ActionClassifier()

        self._event_buffer: deque = deque(maxlen=window_size * 2)
        self._symbol_window: deque = deque(maxlen=window_size)
        self._running = False
        self._lock = threading.Lock()

        self._last_prediction_time = 0
        self._min_prediction_interval = 2.0  # seconds between predictions
        self._prediction_counter = 0

    def set_region(self, region: ScreenRegion):
        self._region = region
        self._feature_extractor.set_region(region)

    def update_patterns(self, patterns: List[ActionPattern]):
        with self._lock:
            self._patterns = patterns

    def feed_event(self, event: ActionEvent):
        """Feed a new event into the predictor."""
        if not self._running:
            return

        with self._lock:
            self._event_buffer.append(event)

            # Symbolize the event
            symbol = self._feature_extractor.symbolize(event)
            if symbol and symbol != "MM":  # Skip moves for prediction
                self._symbol_window.append(symbol)

        # Check for predictions
        self._check_predictions()

    def start(self):
        self._running = True
        self._event_buffer.clear()
        self._symbol_window.clear()
        logger.info("Predictor started")

    def stop(self):
        self._running = False
        logger.info("Predictor stopped")

    def _check_predictions(self):
        """Check if current action sequence matches any pattern."""
        now = time.time()
        if now - self._last_prediction_time < self._min_prediction_interval:
            return

        with self._lock:
            if len(self._symbol_window) < 3:  # Need at least 3 actions
                return

            recent = list(self._symbol_window)
            patterns = self._patterns

        # Find matches
        matches = self._pattern_engine.find_matches(
            recent, patterns,
            min_match_ratio=self._confidence_threshold
        )

        if not matches:
            return

        best_match = matches[0]
        pattern = best_match.pattern

        # Only predict if confidence is high enough
        effective_confidence = best_match.match_score * pattern.confidence
        if effective_confidence < self._confidence_threshold:
            return

        self._last_prediction_time = now
        self._prediction_counter += 1

        # Generate prediction
        name = pattern.name
        if not pattern.user_confirmed:
            name = self._classifier.classify(pattern)

        remaining_str = " -> ".join(best_match.remaining_symbols[:5])
        if len(best_match.remaining_symbols) > 5:
            remaining_str += f" ... (+{len(best_match.remaining_symbols) - 5} more)"

        prediction = Prediction(
            prediction_id=self._prediction_counter,
            pattern=pattern,
            message=f"Next action: {name}?\nRemaining: {remaining_str}",
            remaining_actions=[],  # Will be filled with actual events if needed
            confidence=effective_confidence,
            match_score=best_match.match_score,
        )

        logger.info(f"Prediction: {name} (confidence={effective_confidence:.2f})")

        if self._on_prediction:
            self._on_prediction(prediction)

    def accept_prediction(self, prediction_id: int):
        """User accepted a prediction - boost pattern confidence."""
        logger.info(f"Prediction {prediction_id} accepted")

    def reject_prediction(self, prediction_id: int):
        """User rejected a prediction - decrease pattern confidence."""
        logger.info(f"Prediction {prediction_id} rejected")
