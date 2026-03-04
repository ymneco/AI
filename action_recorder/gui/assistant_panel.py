"""Assistant panel for pattern management and prediction display."""

import tkinter as tk
from tkinter import ttk, simpledialog
from typing import List, Optional

from core.action_types import ActionPattern, Prediction, RecordingSession
from assistant.pattern_engine import PatternEngine
from assistant.action_classifier import ActionClassifier
from storage.database import DatabaseManager
from storage.models import SessionDAO, ActionDAO, PatternDAO, PredictionLogDAO
from utils.logging_config import get_logger

logger = get_logger("assistant_panel")


class PredictionToast(tk.Toplevel):
    """Small popup window showing a prediction suggestion."""

    def __init__(self, parent, prediction: Prediction,
                 on_accept=None, on_reject=None, on_dismiss=None):
        super().__init__(parent)
        self._prediction = prediction
        self._on_accept = on_accept
        self._on_reject = on_reject
        self._on_dismiss = on_dismiss

        self.title("Action Prediction")
        self.attributes("-topmost", True)
        self.resizable(False, False)

        # Position near bottom-right of screen
        self.geometry("+{}+{}".format(
            parent.winfo_screenwidth() - 420,
            parent.winfo_screenheight() - 200
        ))

        self._build_ui()

        # Auto-dismiss after 8 seconds
        self._dismiss_timer = self.after(8000, self._dismiss)

    def _build_ui(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Action Prediction",
                  font=("Segoe UI", 11, "bold")).pack(anchor=tk.W)

        ttk.Label(frame, text=self._prediction.message,
                  wraplength=350, font=("Segoe UI", 9)).pack(
            anchor=tk.W, pady=(5, 5)
        )

        conf_str = f"Confidence: {self._prediction.confidence:.0%}"
        ttk.Label(frame, text=conf_str, font=("Segoe UI", 8)).pack(anchor=tk.W)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(btn_frame, text="Yes, do it",
                   command=self._accept).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="No",
                   command=self._reject).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Dismiss",
                   command=self._dismiss).pack(side=tk.LEFT, padx=2)

    def _accept(self):
        self.after_cancel(self._dismiss_timer)
        if self._on_accept:
            self._on_accept(self._prediction)
        self.destroy()

    def _reject(self):
        self.after_cancel(self._dismiss_timer)
        if self._on_reject:
            self._on_reject(self._prediction)
        self.destroy()

    def _dismiss(self):
        if self._on_dismiss:
            self._on_dismiss(self._prediction)
        try:
            self.destroy()
        except tk.TclError:
            pass


class AssistantPanel(ttk.Frame):
    """Tab panel for managing learned patterns and viewing prediction history."""

    def __init__(self, parent, db: DatabaseManager):
        super().__init__(parent)
        self._db = db
        self._session_dao = SessionDAO(db)
        self._action_dao = ActionDAO(db)
        self._pattern_dao = PatternDAO(db)
        self._prediction_log_dao = PredictionLogDAO(db)
        self._pattern_engine = PatternEngine()
        self._classifier = ActionClassifier()
        self._patterns: List[ActionPattern] = []

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Top controls
        control_frame = ttk.Frame(self)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        self._assistant_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(control_frame, text="Assistant Enabled",
                        variable=self._assistant_var).pack(side=tk.LEFT, padx=5)

        ttk.Label(control_frame, text="Confidence Threshold:").pack(
            side=tk.LEFT, padx=(20, 5)
        )
        self._threshold_var = tk.DoubleVar(value=0.7)
        threshold_spin = ttk.Spinbox(
            control_frame, from_=0.1, to=1.0, increment=0.05,
            textvariable=self._threshold_var, width=5
        )
        threshold_spin.pack(side=tk.LEFT)

        ttk.Button(control_frame, text="Analyze All Sessions",
                   command=self._analyze_patterns).pack(side=tk.RIGHT, padx=5)
        ttk.Button(control_frame, text="Refresh",
                   command=self.refresh).pack(side=tk.RIGHT, padx=5)

        # Patterns table
        pattern_frame = ttk.LabelFrame(self, text="Learned Patterns")
        pattern_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("id", "name", "freq", "conf", "actions", "active")
        self._pattern_tree = ttk.Treeview(
            pattern_frame, columns=columns, show="headings", height=10
        )

        self._pattern_tree.heading("id", text="#")
        self._pattern_tree.heading("name", text="Pattern Name")
        self._pattern_tree.heading("freq", text="Frequency")
        self._pattern_tree.heading("conf", text="Confidence")
        self._pattern_tree.heading("actions", text="Actions")
        self._pattern_tree.heading("active", text="Active")

        self._pattern_tree.column("id", width=40, anchor=tk.CENTER)
        self._pattern_tree.column("name", width=250)
        self._pattern_tree.column("freq", width=80, anchor=tk.CENTER)
        self._pattern_tree.column("conf", width=80, anchor=tk.CENTER)
        self._pattern_tree.column("actions", width=80, anchor=tk.CENTER)
        self._pattern_tree.column("active", width=60, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(pattern_frame, orient=tk.VERTICAL,
                                   command=self._pattern_tree.yview)
        self._pattern_tree.configure(yscrollcommand=scrollbar.set)

        self._pattern_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._pattern_tree.bind("<<TreeviewSelect>>", self._on_pattern_select)

        # Pattern detail
        detail_frame = ttk.LabelFrame(self, text="Pattern Detail")
        detail_frame.pack(fill=tk.X, padx=5, pady=5)

        self._detail_var = tk.StringVar(value="Select a pattern to view details")
        ttk.Label(detail_frame, textvariable=self._detail_var,
                  wraplength=600, font=("Consolas", 9)).pack(
            fill=tk.X, padx=5, pady=5
        )

        btn_frame = ttk.Frame(detail_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        ttk.Button(btn_frame, text="Rename", command=self._rename_pattern).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btn_frame, text="Delete", command=self._delete_pattern).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btn_frame, text="Toggle Active", command=self._toggle_active).pack(
            side=tk.LEFT, padx=2
        )

        # Prediction log
        log_frame = ttk.LabelFrame(self, text="Recent Predictions")
        log_frame.pack(fill=tk.X, padx=5, pady=5)

        log_columns = ("time", "pattern", "score", "result")
        self._log_tree = ttk.Treeview(
            log_frame, columns=log_columns, show="headings", height=5
        )

        self._log_tree.heading("time", text="Time")
        self._log_tree.heading("pattern", text="Pattern")
        self._log_tree.heading("score", text="Score")
        self._log_tree.heading("result", text="Result")

        self._log_tree.column("time", width=140)
        self._log_tree.column("pattern", width=250)
        self._log_tree.column("score", width=80, anchor=tk.CENTER)
        self._log_tree.column("result", width=100, anchor=tk.CENTER)

        self._log_tree.pack(fill=tk.X, padx=5, pady=5)

    def refresh(self):
        """Reload patterns and prediction log from database."""
        # Load patterns
        self._patterns = self._pattern_dao.get_all_patterns()
        self._pattern_tree.delete(*self._pattern_tree.get_children())

        for p in self._patterns:
            name = p.name
            if not p.user_confirmed:
                name = self._classifier.classify(p)
            num_actions = len(p.symbol_sequence.split(" ")) if p.symbol_sequence else 0

            self._pattern_tree.insert("", tk.END, values=(
                p.pattern_id,
                name,
                p.frequency,
                f"{p.confidence:.2f}",
                num_actions,
                "Yes" if p.is_active else "No",
            ))

        # Load prediction log
        self._log_tree.delete(*self._log_tree.get_children())
        try:
            logs = self._prediction_log_dao.get_recent(limit=20)
            for log in logs:
                result = "Pending"
                if log["was_accepted"] is not None:
                    result = "Accepted" if log["was_accepted"] else "Rejected"

                self._log_tree.insert("", tk.END, values=(
                    log["predicted_at"],
                    log["pattern_name"],
                    f"{log['match_score']:.2f}",
                    result,
                ))
        except Exception:
            pass

    def _on_pattern_select(self, event=None):
        selection = self._pattern_tree.selection()
        if not selection:
            return

        index = self._pattern_tree.index(selection[0])
        if 0 <= index < len(self._patterns):
            p = self._patterns[index]
            self._detail_var.set(
                f"ID: {p.pattern_id}\n"
                f"Sequence: {p.symbol_sequence}\n"
                f"Frequency: {p.frequency}  |  Confidence: {p.confidence:.2f}\n"
                f"Created: {p.created_at}  |  Updated: {p.updated_at}"
            )

    def _analyze_patterns(self):
        """Run pattern analysis on all recorded sessions."""
        sessions = self._session_dao.get_all(limit=1000)
        if not sessions:
            logger.info("No sessions to analyze")
            return

        # Load events for each session
        sessions_data = []
        for session in sessions:
            events = self._action_dao.get_by_session(session.session_id)
            if events and session.region:
                sessions_data.append((session.region, events))

        if not sessions_data:
            return

        # Analyze
        discovered = self._pattern_engine.analyze_sessions(sessions_data)

        # Save to database
        for pattern in discovered:
            pattern.name = self._classifier.classify(pattern)
            self._pattern_dao.save_pattern(pattern)

        logger.info(f"Saved {len(discovered)} new patterns")
        self.refresh()

    def _rename_pattern(self):
        selection = self._pattern_tree.selection()
        if not selection:
            return

        index = self._pattern_tree.index(selection[0])
        if 0 <= index < len(self._patterns):
            p = self._patterns[index]
            new_name = simpledialog.askstring(
                "Rename Pattern", "New name:", initialvalue=p.name, parent=self
            )
            if new_name and new_name.strip():
                p.name = new_name.strip()
                p.user_confirmed = True
                # Update in database would need a method - for now just refresh
                self.refresh()

    def _delete_pattern(self):
        selection = self._pattern_tree.selection()
        if not selection:
            return

        index = self._pattern_tree.index(selection[0])
        if 0 <= index < len(self._patterns):
            p = self._patterns[index]
            self._pattern_dao.delete_pattern(p.pattern_id)
            self.refresh()

    def _toggle_active(self):
        selection = self._pattern_tree.selection()
        if not selection:
            return

        index = self._pattern_tree.index(selection[0])
        if 0 <= index < len(self._patterns):
            p = self._patterns[index]
            p.is_active = not p.is_active
            self._pattern_dao.update_confidence(
                p.pattern_id, p.confidence, p.frequency
            )
            self.refresh()

    def get_active_patterns(self) -> List[ActionPattern]:
        """Get currently active patterns for the predictor."""
        return [p for p in self._patterns if p.is_active]

    @property
    def is_enabled(self) -> bool:
        return self._assistant_var.get()

    @property
    def confidence_threshold(self) -> float:
        return self._threshold_var.get()
