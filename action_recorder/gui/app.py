"""Main application window for ActionRecorder Pro."""

import datetime
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from config import APP_NAME, APP_VERSION, WINDOW_WIDTH, WINDOW_HEIGHT
from core.action_types import ActionEvent, RecordingSession, ScreenRegion
from core.recorder import ActionRecorder
from storage.database import DatabaseManager
from storage.models import SessionDAO, ActionDAO, SettingsDAO
from gui.widgets.status_bar import StatusBar
from gui.widgets.action_list import ActionListWidget
from gui.recording_panel import RecordingPanel
from gui.timeline_panel import TimelinePanel
from gui.assistant_panel import AssistantPanel, PredictionToast
from gui.settings_panel import SettingsPanel
from gui.region_overlay import select_region
from assistant.predictor import ActionPredictor
from utils.logging_config import get_logger

logger = get_logger("app")


class ActionRecorderApp:
    """Main application class orchestrating all panels and features."""

    def __init__(self, db: DatabaseManager):
        self._db = db
        self._session_dao = SessionDAO(db)
        self._action_dao = ActionDAO(db)
        self._settings_dao = SettingsDAO(db)

        self._root = tk.Tk()
        self._root.title(f"{APP_NAME} v{APP_VERSION}")
        self._root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self._root.minsize(800, 600)

        # State
        self._region: Optional[ScreenRegion] = None
        self._recorder: Optional[ActionRecorder] = None
        self._replayer = None
        self._predictor: Optional[ActionPredictor] = None
        self._current_session_id: int = 0
        self._event_count: int = 0
        self._update_timer_id = None
        self._prediction_toast: Optional[PredictionToast] = None

        # Speed variable
        self._speed_var = tk.DoubleVar(value=1.0)

        # Build UI
        self._build_menu()
        self._build_toolbar()
        self._build_tabs()
        self._build_status_bar()

        # Handle window close
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

    def run(self):
        """Start the tkinter main loop."""
        logger.info("Application started")
        self._root.mainloop()

    def _build_menu(self):
        menubar = tk.Menu(self._root)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        # Recording menu
        rec_menu = tk.Menu(menubar, tearoff=0)
        rec_menu.add_command(label="Select Region", command=self._on_select_region,
                             accelerator="Ctrl+R")
        rec_menu.add_separator()
        rec_menu.add_command(label="Start Recording", command=self._on_record,
                             accelerator="F9")
        rec_menu.add_command(label="Pause/Resume", command=self._on_pause,
                             accelerator="F10")
        rec_menu.add_command(label="Stop Recording", command=self._on_stop,
                             accelerator="F11")
        menubar.add_cascade(label="Recording", menu=rec_menu)

        # Replay menu
        replay_menu = tk.Menu(menubar, tearoff=0)
        replay_menu.add_command(label="Replay Selected", command=self._on_replay,
                                accelerator="F5")
        replay_menu.add_command(label="Stop Replay", command=self._on_stop_replay,
                                accelerator="Escape")
        menubar.add_cascade(label="Replay", menu=replay_menu)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self._root.config(menu=menubar)

        # Keyboard shortcuts
        self._root.bind("<F9>", lambda e: self._on_record())
        self._root.bind("<F10>", lambda e: self._on_pause())
        self._root.bind("<F11>", lambda e: self._on_stop())
        self._root.bind("<F5>", lambda e: self._on_replay())
        self._root.bind("<Escape>", lambda e: self._on_stop_replay())

    def _build_toolbar(self):
        toolbar = ttk.Frame(self._root)
        toolbar.pack(fill=tk.X, padx=5, pady=3)

        # Left side - recording controls
        self._select_btn = ttk.Button(toolbar, text="Select Region",
                                       command=self._on_select_region)
        self._select_btn.pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)

        self._record_btn = ttk.Button(toolbar, text="Record (F9)",
                                       command=self._on_record)
        self._record_btn.pack(side=tk.LEFT, padx=2)

        self._pause_btn = ttk.Button(toolbar, text="Pause (F10)",
                                      command=self._on_pause, state=tk.DISABLED)
        self._pause_btn.pack(side=tk.LEFT, padx=2)

        self._stop_btn = ttk.Button(toolbar, text="Stop (F11)",
                                     command=self._on_stop, state=tk.DISABLED)
        self._stop_btn.pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)

        self._replay_btn = ttk.Button(toolbar, text="Replay (F5)",
                                       command=self._on_replay)
        self._replay_btn.pack(side=tk.LEFT, padx=2)

        # Right side - speed control
        ttk.Label(toolbar, text="Speed:").pack(side=tk.RIGHT, padx=(5, 2))
        speed_combo = ttk.Combobox(
            toolbar, textvariable=self._speed_var, width=5,
            values=["0.25", "0.5", "1.0", "2.0", "4.0", "8.0"],
            state="readonly"
        )
        speed_combo.set("1.0")
        speed_combo.pack(side=tk.RIGHT, padx=2)

    def _build_tabs(self):
        self._notebook = ttk.Notebook(self._root)
        self._notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Recordings tab
        self._recording_panel = RecordingPanel(
            self._notebook, self._db,
            on_replay=self._replay_session,
        )
        self._notebook.add(self._recording_panel, text="  Recordings  ")

        # Live Actions tab (shows events during recording)
        self._live_frame = ttk.Frame(self._notebook)
        self._notebook.add(self._live_frame, text="  Live Actions  ")

        self._action_list = ActionListWidget(self._live_frame)
        self._action_list.pack(fill=tk.BOTH, expand=True)

        # Timeline tab
        self._timeline_panel = TimelinePanel(self._notebook, self._db)
        self._notebook.add(self._timeline_panel, text="  Timeline  ")

        # Assistant tab
        self._assistant_panel = AssistantPanel(self._notebook, self._db)
        self._notebook.add(self._assistant_panel, text="  Assistant  ")

        # Settings tab
        self._settings_panel = SettingsPanel(self._notebook, self._db)
        self._notebook.add(self._settings_panel, text="  Settings  ")

    def _build_status_bar(self):
        self._status_bar = StatusBar(self._root)
        self._status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=(0, 3))

    # ---- Actions ----

    def _on_select_region(self):
        """Open region selection overlay."""
        select_region(self._root, self._on_region_selected)

    def _on_region_selected(self, region: ScreenRegion):
        """Called when user selects a screen region."""
        self._region = region
        self._status_bar.set_region(
            f"({region.left}, {region.top}) {region.width}x{region.height}"
        )
        logger.info(f"Region selected: {region}")

    def _on_record(self):
        """Start recording."""
        if self._recorder and self._recorder.is_recording:
            return

        if self._region is None:
            messagebox.showwarning("No Region", "Please select a screen region first.")
            return

        # Create session name
        now = datetime.datetime.now()
        session_name = f"Recording {now.strftime('%Y-%m-%d %H:%M:%S')}"

        # Create session in DB
        session = RecordingSession(
            name=session_name,
            region=self._region,
        )
        self._current_session_id = self._session_dao.create(session)
        self._event_count = 0

        # Clear live action list
        self._action_list.clear()
        self._notebook.select(1)  # Switch to Live Actions tab

        # Start recorder
        self._recorder = ActionRecorder(
            region=self._region,
            session_id=self._current_session_id,
            on_event=self._on_event_captured,
        )
        self._recorder.start()

        # Start predictor if assistant is enabled
        if self._assistant_panel.is_enabled:
            patterns = self._assistant_panel.get_active_patterns()
            self._predictor = ActionPredictor(
                patterns=patterns,
                region=self._region,
                on_prediction=self._on_prediction,
                confidence_threshold=self._assistant_panel.confidence_threshold,
            )
            self._predictor.start()

        # Update UI state
        self._record_btn.config(state=tk.DISABLED)
        self._pause_btn.config(state=tk.NORMAL)
        self._stop_btn.config(state=tk.NORMAL)
        self._select_btn.config(state=tk.DISABLED)
        self._status_bar.set_state("Recording", "red")

        # Start UI update timer
        self._start_update_timer()

        logger.info(f"Recording started: session={self._current_session_id}")

    def _on_pause(self):
        """Toggle pause/resume."""
        if not self._recorder or not self._recorder.is_recording:
            return

        if self._recorder.is_paused:
            self._recorder.resume()
            self._pause_btn.config(text="Pause (F10)")
            self._status_bar.set_state("Recording", "red")
        else:
            self._recorder.pause()
            self._pause_btn.config(text="Resume (F10)")
            self._status_bar.set_state("Paused", "#FFC107")

    def _on_stop(self):
        """Stop recording and save."""
        if not self._recorder or not self._recorder.is_recording:
            return

        events = self._recorder.stop()

        # Save to database
        if events:
            duration_ms = events[-1].timestamp_ns // 1_000_000 if events else 0
            self._action_dao.bulk_insert(self._current_session_id, events)

            # Update session metadata
            session = self._session_dao.get_by_id(self._current_session_id)
            if session:
                session.duration_ms = duration_ms
                session.action_count = len(events)
                self._session_dao.update(session)

            logger.info(
                f"Recording saved: {len(events)} events, {duration_ms}ms"
            )

        # Stop predictor
        if self._predictor:
            self._predictor.stop()
            self._predictor = None

        # Reset UI
        self._recorder = None
        self._record_btn.config(state=tk.NORMAL)
        self._pause_btn.config(state=tk.DISABLED, text="Pause (F10)")
        self._stop_btn.config(state=tk.DISABLED)
        self._select_btn.config(state=tk.NORMAL)
        self._status_bar.set_state("Ready", "gray")

        self._stop_update_timer()

        # Refresh all panels
        self._recording_panel.refresh()
        self._timeline_panel._refresh_sessions()
        self._assistant_panel.refresh()

    def _on_replay(self):
        """Replay the selected recording."""
        # Get selected session from recording panel
        pass  # Implemented in Phase 4

    def _on_stop_replay(self):
        """Stop current replay."""
        if self._replayer:
            self._replayer.stop()
            self._replayer = None
            self._status_bar.set_state("Ready", "gray")

    def _replay_session(self, session: RecordingSession):
        """Replay a specific session."""
        if not session.session_id:
            return

        # Load events
        events = self._action_dao.get_by_session(session.session_id)
        if not events:
            messagebox.showinfo("Empty", "This recording has no events.")
            return

        # Import replayer (Phase 4)
        try:
            from core.replayer import ActionReplayer

            speed = self._speed_var.get()
            target_region = self._region or session.region

            self._replayer = ActionReplayer(
                events=events,
                source_region=session.region,
                target_region=target_region,
                speed=speed,
                on_progress=self._on_replay_progress,
                on_complete=self._on_replay_complete,
            )

            self._status_bar.set_state("Replaying", "#2196F3")

            replay_thread = threading.Thread(
                target=self._replayer.play, daemon=True
            )
            replay_thread.start()
            logger.info(f"Replay started: session={session.session_id}, speed={speed}x")

        except ImportError:
            messagebox.showinfo("Not Available", "Replay module not yet available.")

    def _on_event_captured(self, event: ActionEvent):
        """Called from recorder thread when a new event is captured."""
        self._event_count += 1
        # Schedule UI update on main thread
        self._root.after(0, self._update_live_event, self._event_count, event)
        # Feed to predictor
        if self._predictor:
            self._predictor.feed_event(event)

    def _update_live_event(self, index: int, event: ActionEvent):
        """Update live action list (called on main thread)."""
        self._action_list.add_event(index, event)

    def _on_prediction(self, prediction):
        """Called from predictor when a prediction is made."""
        self._root.after(0, self._show_prediction, prediction)

    def _show_prediction(self, prediction):
        """Show prediction toast on main thread."""
        # Close existing toast
        if self._prediction_toast:
            try:
                self._prediction_toast.destroy()
            except tk.TclError:
                pass

        self._prediction_toast = PredictionToast(
            self._root, prediction,
            on_accept=self._on_prediction_accepted,
            on_reject=self._on_prediction_rejected,
        )

    def _on_prediction_accepted(self, prediction):
        """User accepted a prediction."""
        if self._predictor:
            self._predictor.accept_prediction(prediction.prediction_id)
        self._prediction_toast = None

    def _on_prediction_rejected(self, prediction):
        """User rejected a prediction."""
        if self._predictor:
            self._predictor.reject_prediction(prediction.prediction_id)
        self._prediction_toast = None

    def _on_replay_progress(self, current: int, total: int):
        """Called during replay with progress info."""
        self._root.after(0, lambda: self._status_bar.set_state(
            f"Replaying {current}/{total}", "#2196F3"
        ))

    def _on_replay_complete(self):
        """Called when replay finishes."""
        self._root.after(0, lambda: self._status_bar.set_state("Ready", "gray"))
        self._replayer = None

    def _start_update_timer(self):
        """Start periodic UI updates during recording."""
        def update():
            if self._recorder and self._recorder.is_recording:
                self._status_bar.set_action_count(self._recorder.event_count)
                self._status_bar.set_duration(self._recorder.elapsed_ms)
                self._update_timer_id = self._root.after(100, update)
        self._update_timer_id = self._root.after(100, update)

    def _stop_update_timer(self):
        if self._update_timer_id:
            self._root.after_cancel(self._update_timer_id)
            self._update_timer_id = None

    def _show_about(self):
        messagebox.showinfo(
            "About",
            f"{APP_NAME} v{APP_VERSION}\n\n"
            "Screen action recorder, replayer, and assistant.\n"
            "Record mouse and keyboard actions within a selected\n"
            "screen region, replay them, and get AI-assisted\n"
            "action predictions."
        )

    def _on_close(self):
        """Handle window close."""
        if self._recorder and self._recorder.is_recording:
            if not messagebox.askyesno(
                "Recording Active",
                "A recording is in progress. Stop and exit?"
            ):
                return
            self._on_stop()

        self._stop_update_timer()
        self._db.close()
        self._root.destroy()
        logger.info("Application closed")
