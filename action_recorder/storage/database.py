"""SQLite database connection manager for ActionRecorder Pro."""

import os
import sqlite3

from config import DB_PATH, DATA_DIR
from storage.queries import CREATE_TABLES, DEFAULT_SETTINGS, SCHEMA_VERSION
from utils.logging_config import get_logger

logger = get_logger("database")


class DatabaseManager:
    def __init__(self, db_path: str = None):
        self._db_path = db_path or DB_PATH
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._conn = None

    def get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.row_factory = sqlite3.Row
            logger.info(f"Database connected: {self._db_path}")
        return self._conn

    def initialize_schema(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        # Create tables
        cursor.executescript(CREATE_TABLES)

        # Check schema version
        cursor.execute("SELECT MAX(version) FROM schema_version")
        row = cursor.fetchone()
        current_version = row[0] if row[0] is not None else 0

        if current_version < SCHEMA_VERSION:
            cursor.execute(
                "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,)
            )
            logger.info(f"Schema initialized at version {SCHEMA_VERSION}")

        # Insert default settings
        for key, value in DEFAULT_SETTINGS.items():
            cursor.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value)
            )

        conn.commit()
        logger.info("Database schema ready")

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("Database connection closed")

    def __enter__(self):
        self.get_connection()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._conn.rollback()
        else:
            self._conn.commit()
        return False
