"""Recording list and management panel for ActionRecorder Pro."""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional

from core.action_types import RecordingSession
from storage.models import SessionDAO
from storage.database import DatabaseManager
from utils.logging_config import get_logger

logger = get_logger("recording_panel")


class RecordingPanel(ttk.Frame):
    """Tab panel showing recording sessions list with search and management."""

    def __init__(self, parent, db: DatabaseManager,
                 on_replay: Callable[[RecordingSession], None] = None,
                 on_select: Callable[[RecordingSession], None] = None):
        super().__init__(parent)
        self._db = db
        self._session_dao = SessionDAO(db)
        self._on_replay = on_replay
        self._on_select = on_select
        self._sessions: list = []
        self._selected_session: Optional[RecordingSession] = None

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Search bar
        search_frame = ttk.Frame(self)
        search_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *a: self._on_search())
        search_entry = ttk.Entry(search_frame, textvariable=self._search_var, width=30)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        ttk.Button(search_frame, text="Refresh", command=self.refresh).pack(side=tk.RIGHT)

        # Session list
        list_frame = ttk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        columns = ("name", "date", "duration", "actions", "tags")
        self._tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=12)

        self._tree.heading("name", text="Name")
        self._tree.heading("date", text="Date")
        self._tree.heading("duration", text="Duration")
        self._tree.heading("actions", text="Actions")
        self._tree.heading("tags", text="Tags")

        self._tree.column("name", width=200)
        self._tree.column("date", width=140, anchor=tk.CENTER)
        self._tree.column("duration", width=80, anchor=tk.CENTER)
        self._tree.column("actions", width=80, anchor=tk.CENTER)
        self._tree.column("tags", width=150)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)

        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self._tree.bind("<Double-1>", self._on_double_click)

        # Details and buttons
        detail_frame = ttk.LabelFrame(self, text="Selected Recording")
        detail_frame.pack(fill=tk.X, padx=5, pady=5)

        # Info labels
        info_frame = ttk.Frame(detail_frame)
        info_frame.pack(fill=tk.X, padx=5, pady=5)

        self._detail_var = tk.StringVar(value="No recording selected")
        ttk.Label(info_frame, textvariable=self._detail_var, wraplength=600).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )

        # Action buttons
        btn_frame = ttk.Frame(detail_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        self._replay_btn = ttk.Button(btn_frame, text="Replay", command=self._replay)
        self._replay_btn.pack(side=tk.LEFT, padx=2)

        self._rename_btn = ttk.Button(btn_frame, text="Rename", command=self._rename)
        self._rename_btn.pack(side=tk.LEFT, padx=2)

        self._delete_btn = ttk.Button(btn_frame, text="Delete", command=self._delete)
        self._delete_btn.pack(side=tk.LEFT, padx=2)

        self._template_btn = ttk.Button(
            btn_frame, text="Set as Template", command=self._toggle_template
        )
        self._template_btn.pack(side=tk.LEFT, padx=2)

        # Notes
        notes_frame = ttk.LabelFrame(detail_frame, text="Notes")
        notes_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        self._notes_text = tk.Text(notes_frame, height=3, width=60)
        self._notes_text.pack(fill=tk.X, padx=5, pady=5)

        save_notes_btn = ttk.Button(notes_frame, text="Save Notes", command=self._save_notes)
        save_notes_btn.pack(anchor=tk.E, padx=5, pady=(0, 5))

    def refresh(self):
        """Reload sessions from database."""
        self._tree.delete(*self._tree.get_children())
        search = self._search_var.get().strip()

        if search:
            self._sessions = self._session_dao.search(search)
        else:
            self._sessions = self._session_dao.get_all(limit=100)

        for session in self._sessions:
            duration_s = session.duration_ms // 1000
            duration_str = f"{duration_s // 60}:{duration_s % 60:02d}"
            tags_str = ", ".join(session.tags)

            self._tree.insert("", tk.END, values=(
                session.name,
                session.created_at[:16] if session.created_at else "",
                duration_str,
                session.action_count,
                tags_str,
            ))

    def _on_search(self):
        self.refresh()

    def _on_tree_select(self, event=None):
        selection = self._tree.selection()
        if not selection:
            return

        index = self._tree.index(selection[0])
        if 0 <= index < len(self._sessions):
            self._selected_session = self._sessions[index]
            s = self._selected_session
            region = s.region
            region_str = f"({region.left}, {region.top}) {region.width}x{region.height}" if region else "N/A"
            self._detail_var.set(
                f"Name: {s.name}  |  Region: {region_str}  |  "
                f"Actions: {s.action_count}  |  Template: {'Yes' if s.is_template else 'No'}"
            )
            self._notes_text.delete("1.0", tk.END)
            self._notes_text.insert("1.0", s.notes)

            if self._on_select:
                self._on_select(s)

    def _on_double_click(self, event=None):
        self._replay()

    def _replay(self):
        if self._selected_session and self._on_replay:
            self._on_replay(self._selected_session)

    def _rename(self):
        if not self._selected_session:
            return
        from tkinter import simpledialog
        new_name = simpledialog.askstring(
            "Rename Recording",
            "New name:",
            initialvalue=self._selected_session.name,
            parent=self,
        )
        if new_name and new_name.strip():
            self._selected_session.name = new_name.strip()
            self._session_dao.update(self._selected_session)
            self.refresh()

    def _delete(self):
        if not self._selected_session:
            return
        if messagebox.askyesno("Confirm Delete",
                               f"Delete '{self._selected_session.name}'?"):
            self._session_dao.delete(self._selected_session.session_id)
            self._selected_session = None
            self._detail_var.set("No recording selected")
            self.refresh()

    def _toggle_template(self):
        if not self._selected_session:
            return
        self._selected_session.is_template = not self._selected_session.is_template
        self._session_dao.update(self._selected_session)
        self._on_tree_select()
        self.refresh()

    def _save_notes(self):
        if not self._selected_session:
            return
        self._selected_session.notes = self._notes_text.get("1.0", tk.END).strip()
        self._session_dao.update(self._selected_session)
        logger.info(f"Notes saved for session {self._selected_session.session_id}")
