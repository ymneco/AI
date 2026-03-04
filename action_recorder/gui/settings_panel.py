"""Settings panel for ActionRecorder Pro."""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from config import DATA_DIR
from gui.widgets.hotkey_entry import HotkeyEntry
from storage.database import DatabaseManager
from storage.models import SettingsDAO
from utils.logging_config import get_logger

logger = get_logger("settings_panel")


class SettingsPanel(ttk.Frame):
    """Tab panel for application settings."""

    def __init__(self, parent, db: DatabaseManager):
        super().__init__(parent)
        self._db = db
        self._settings_dao = SettingsDAO(db)

        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        # Settings notebook (sub-tabs)
        self._settings_notebook = ttk.Notebook(self)
        self._settings_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # General tab
        general_frame = ttk.Frame(self._settings_notebook, padding=10)
        self._settings_notebook.add(general_frame, text="  General  ")
        self._build_general(general_frame)

        # Hotkeys tab
        hotkey_frame = ttk.Frame(self._settings_notebook, padding=10)
        self._settings_notebook.add(hotkey_frame, text="  Hotkeys  ")
        self._build_hotkeys(hotkey_frame)

        # Recording tab
        recording_frame = ttk.Frame(self._settings_notebook, padding=10)
        self._settings_notebook.add(recording_frame, text="  Recording  ")
        self._build_recording(recording_frame)

        # Replay tab
        replay_frame = ttk.Frame(self._settings_notebook, padding=10)
        self._settings_notebook.add(replay_frame, text="  Replay  ")
        self._build_replay(replay_frame)

        # Data tab
        data_frame = ttk.Frame(self._settings_notebook, padding=10)
        self._settings_notebook.add(data_frame, text="  Data  ")
        self._build_data(data_frame)

        # Bottom buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text="Apply", command=self._save_settings).pack(
            side=tk.RIGHT, padx=5
        )
        ttk.Button(btn_frame, text="Reset to Defaults",
                   command=self._reset_defaults).pack(side=tk.RIGHT, padx=5)

    def _build_general(self, parent):
        row = 0
        ttk.Label(parent, text="General Settings",
                  font=("Segoe UI", 11, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 10)
        )

        row += 1
        self._assistant_enabled = tk.BooleanVar(value=True)
        ttk.Label(parent, text="Enable Assistant:").grid(
            row=row, column=0, sticky=tk.W, pady=3
        )
        ttk.Checkbutton(parent, variable=self._assistant_enabled).grid(
            row=row, column=1, sticky=tk.W, pady=3
        )

        row += 1
        ttk.Label(parent, text="Assistant Confidence:").grid(
            row=row, column=0, sticky=tk.W, pady=3
        )
        self._confidence_var = tk.DoubleVar(value=0.7)
        ttk.Spinbox(parent, from_=0.1, to=1.0, increment=0.05,
                     textvariable=self._confidence_var, width=8).grid(
            row=row, column=1, sticky=tk.W, pady=3
        )

    def _build_hotkeys(self, parent):
        row = 0
        ttk.Label(parent, text="Hotkey Settings",
                  font=("Segoe UI", 11, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 10)
        )

        self._hotkey_entries = {}
        hotkeys = [
            ("Start Recording:", "hotkey_record", "F9"),
            ("Pause/Resume:", "hotkey_pause", "F10"),
            ("Stop Recording:", "hotkey_stop", "F11"),
            ("Start Replay:", "hotkey_replay", "F5"),
        ]

        for label, key, default in hotkeys:
            row += 1
            ttk.Label(parent, text=label).grid(
                row=row, column=0, sticky=tk.W, pady=3
            )
            entry = HotkeyEntry(parent, initial_value=default)
            entry.grid(row=row, column=1, sticky=tk.W, pady=3)
            self._hotkey_entries[key] = entry

    def _build_recording(self, parent):
        row = 0
        ttk.Label(parent, text="Recording Settings",
                  font=("Segoe UI", 11, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 10)
        )

        row += 1
        self._record_moves = tk.BooleanVar(value=True)
        ttk.Label(parent, text="Record mouse movement:").grid(
            row=row, column=0, sticky=tk.W, pady=3
        )
        ttk.Checkbutton(parent, variable=self._record_moves).grid(
            row=row, column=1, sticky=tk.W, pady=3
        )

        row += 1
        ttk.Label(parent, text="Mouse throttle (px):").grid(
            row=row, column=0, sticky=tk.W, pady=3
        )
        self._throttle_var = tk.IntVar(value=3)
        ttk.Spinbox(parent, from_=1, to=20,
                     textvariable=self._throttle_var, width=8).grid(
            row=row, column=1, sticky=tk.W, pady=3
        )

        row += 1
        ttk.Label(parent, text="Screenshot interval (ms):").grid(
            row=row, column=0, sticky=tk.W, pady=3
        )
        self._screenshot_interval = tk.IntVar(value=2000)
        ttk.Spinbox(parent, from_=500, to=30000, increment=500,
                     textvariable=self._screenshot_interval, width=8).grid(
            row=row, column=1, sticky=tk.W, pady=3
        )

    def _build_replay(self, parent):
        row = 0
        ttk.Label(parent, text="Replay Settings",
                  font=("Segoe UI", 11, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 10)
        )

        row += 1
        ttk.Label(parent, text="Default speed:").grid(
            row=row, column=0, sticky=tk.W, pady=3
        )
        self._speed_var = tk.DoubleVar(value=1.0)
        ttk.Combobox(parent, textvariable=self._speed_var, width=8,
                      values=["0.25", "0.5", "1.0", "2.0", "4.0"],
                      state="readonly").grid(
            row=row, column=1, sticky=tk.W, pady=3
        )

        row += 1
        ttk.Label(parent, text="Loop count:").grid(
            row=row, column=0, sticky=tk.W, pady=3
        )
        self._loop_var = tk.IntVar(value=1)
        ttk.Spinbox(parent, from_=1, to=100,
                     textvariable=self._loop_var, width=8).grid(
            row=row, column=1, sticky=tk.W, pady=3
        )

        row += 1
        self._failsafe_var = tk.BooleanVar(value=True)
        ttk.Label(parent, text="Fail-safe (corner abort):").grid(
            row=row, column=0, sticky=tk.W, pady=3
        )
        ttk.Checkbutton(parent, variable=self._failsafe_var).grid(
            row=row, column=1, sticky=tk.W, pady=3
        )

    def _build_data(self, parent):
        row = 0
        ttk.Label(parent, text="Data Management",
                  font=("Segoe UI", 11, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 10)
        )

        row += 1
        self._db_info_var = tk.StringVar(value="Loading...")
        ttk.Label(parent, textvariable=self._db_info_var).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=3
        )

        row += 1
        btn_frame = ttk.Frame(parent)
        btn_frame.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=10)

        ttk.Button(btn_frame, text="Compact Database",
                   command=self._compact_db).pack(side=tk.LEFT, padx=5)

        self._update_data_info()

    def _load_settings(self):
        """Load settings from database."""
        settings = self._settings_dao.get_all()

        self._assistant_enabled.set(settings.get("assistant_enabled", "1") == "1")
        self._confidence_var.set(float(settings.get("assistant_confidence_threshold", "0.7")))
        self._record_moves.set(settings.get("mouse_move_recording", "1") == "1")
        self._throttle_var.set(int(settings.get("mouse_throttle_px", "3")))
        self._screenshot_interval.set(int(settings.get("screenshot_interval_ms", "2000")))
        self._speed_var.set(float(settings.get("replay_speed", "1.0")))

        for key, entry in self._hotkey_entries.items():
            val = settings.get(key, "")
            if val:
                entry.set(val)

    def _save_settings(self):
        """Save all settings to database."""
        self._settings_dao.set("assistant_enabled",
                               "1" if self._assistant_enabled.get() else "0")
        self._settings_dao.set("assistant_confidence_threshold",
                               str(self._confidence_var.get()))
        self._settings_dao.set("mouse_move_recording",
                               "1" if self._record_moves.get() else "0")
        self._settings_dao.set("mouse_throttle_px", str(self._throttle_var.get()))
        self._settings_dao.set("screenshot_interval_ms",
                               str(self._screenshot_interval.get()))
        self._settings_dao.set("replay_speed", str(self._speed_var.get()))

        for key, entry in self._hotkey_entries.items():
            self._settings_dao.set(key, entry.get())

        messagebox.showinfo("Settings", "Settings saved successfully.")
        logger.info("Settings saved")

    def _reset_defaults(self):
        """Reset settings to defaults."""
        from storage.queries import DEFAULT_SETTINGS
        for key, value in DEFAULT_SETTINGS.items():
            self._settings_dao.set(key, value)
        self._load_settings()
        messagebox.showinfo("Settings", "Settings reset to defaults.")

    def _compact_db(self):
        """Compact the SQLite database."""
        conn = self._db.get_connection()
        conn.execute("VACUUM")
        self._update_data_info()
        messagebox.showinfo("Database", "Database compacted successfully.")

    def _update_data_info(self):
        """Update database info display."""
        import os
        from config import DB_PATH, SCREENSHOTS_DIR

        db_size = 0
        if os.path.exists(DB_PATH):
            db_size = os.path.getsize(DB_PATH) / (1024 * 1024)

        screenshots_size = 0
        if os.path.exists(SCREENSHOTS_DIR):
            for dirpath, dirnames, filenames in os.walk(SCREENSHOTS_DIR):
                for f in filenames:
                    screenshots_size += os.path.getsize(os.path.join(dirpath, f))
        screenshots_size /= (1024 * 1024)

        conn = self._db.get_connection()
        session_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        action_count = conn.execute("SELECT COUNT(*) FROM actions").fetchone()[0]

        self._db_info_var.set(
            f"Database: {db_size:.1f} MB  |  Screenshots: {screenshots_size:.1f} MB\n"
            f"Sessions: {session_count}  |  Total Actions: {action_count}"
        )
