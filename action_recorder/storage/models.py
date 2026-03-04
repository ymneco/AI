"""Data Access Objects for ActionRecorder Pro."""

import json
from typing import List, Optional

from core.action_types import (
    ActionEvent, ActionPattern, ScreenRegion, RecordingSession
)
from storage.database import DatabaseManager
from storage import queries
from utils.serialization import event_to_db_row, db_row_to_event
from utils.logging_config import get_logger

logger = get_logger("models")


class SessionDAO:
    def __init__(self, db: DatabaseManager):
        self._db = db

    def create(self, session: RecordingSession) -> int:
        conn = self._db.get_connection()
        region = session.region or ScreenRegion(0, 0, 0, 0)
        cursor = conn.execute(queries.INSERT_SESSION, (
            session.name,
            region.left, region.top, region.width, region.height,
            region.monitor_index, region.dpi_scale,
            session.duration_ms, session.action_count,
            int(session.is_template),
            ",".join(session.tags),
            session.notes,
            session.default_speed,
            session.loop_count,
        ))
        conn.commit()
        session_id = cursor.lastrowid
        logger.info(f"Session created: id={session_id}, name='{session.name}'")
        return session_id

    def get_by_id(self, session_id: int) -> Optional[RecordingSession]:
        conn = self._db.get_connection()
        row = conn.execute(queries.SELECT_SESSION_BY_ID, (session_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_session(row)

    def get_all(self, limit: int = 50, offset: int = 0) -> List[RecordingSession]:
        conn = self._db.get_connection()
        rows = conn.execute(queries.SELECT_ALL_SESSIONS, (limit, offset)).fetchall()
        return [self._row_to_session(r) for r in rows]

    def update(self, session: RecordingSession):
        conn = self._db.get_connection()
        conn.execute(queries.UPDATE_SESSION, (
            session.name,
            session.duration_ms, session.action_count,
            int(session.is_template),
            ",".join(session.tags),
            session.notes,
            session.default_speed,
            session.loop_count,
            session.session_id,
        ))
        conn.commit()

    def delete(self, session_id: int):
        conn = self._db.get_connection()
        conn.execute(queries.DELETE_SESSION, (session_id,))
        conn.commit()
        logger.info(f"Session deleted: id={session_id}")

    def search(self, query: str) -> List[RecordingSession]:
        conn = self._db.get_connection()
        pattern = f"%{query}%"
        rows = conn.execute(queries.SEARCH_SESSIONS, (pattern, pattern)).fetchall()
        return [self._row_to_session(r) for r in rows]

    def _row_to_session(self, row) -> RecordingSession:
        tags_str = row["tags"] or ""
        return RecordingSession(
            session_id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            region=ScreenRegion(
                left=row["region_left"],
                top=row["region_top"],
                width=row["region_width"],
                height=row["region_height"],
                monitor_index=row["monitor_index"],
                dpi_scale=row["dpi_scale"],
            ),
            duration_ms=row["duration_ms"],
            action_count=row["action_count"],
            is_template=bool(row["is_template"]),
            tags=[t for t in tags_str.split(",") if t],
            notes=row["notes"] or "",
            default_speed=row["default_speed"],
            loop_count=row["loop_count"],
        )


class ActionDAO:
    def __init__(self, db: DatabaseManager):
        self._db = db

    def bulk_insert(self, session_id: int, events: List[ActionEvent]):
        conn = self._db.get_connection()
        rows = [
            event_to_db_row(e, session_id, i)
            for i, e in enumerate(events)
        ]
        conn.executemany(queries.INSERT_ACTION, rows)
        conn.commit()
        logger.info(f"Bulk inserted {len(rows)} actions for session {session_id}")

    def get_by_session(self, session_id: int) -> List[ActionEvent]:
        conn = self._db.get_connection()
        rows = conn.execute(queries.SELECT_ACTIONS_BY_SESSION, (session_id,)).fetchall()
        return [db_row_to_event(tuple(r)) for r in rows]

    def get_time_range(self, session_id: int, start_ns: int, end_ns: int) -> List[ActionEvent]:
        conn = self._db.get_connection()
        rows = conn.execute(
            queries.SELECT_ACTIONS_TIME_RANGE, (session_id, start_ns, end_ns)
        ).fetchall()
        return [db_row_to_event(tuple(r)) for r in rows]


class PatternDAO:
    def __init__(self, db: DatabaseManager):
        self._db = db

    def save_pattern(self, pattern: ActionPattern) -> int:
        conn = self._db.get_connection()
        cursor = conn.execute(queries.INSERT_PATTERN, (
            pattern.name,
            pattern.description,
            pattern.symbol_sequence,
            json.dumps(pattern.action_types),
            pattern.avg_duration_ms,
            pattern.frequency,
            pattern.confidence,
            int(pattern.is_active),
            int(pattern.user_confirmed),
        ))
        conn.commit()
        return cursor.lastrowid

    def get_active_patterns(self) -> List[ActionPattern]:
        conn = self._db.get_connection()
        rows = conn.execute(queries.SELECT_ALL_PATTERNS).fetchall()
        return [self._row_to_pattern(r) for r in rows]

    def get_all_patterns(self) -> List[ActionPattern]:
        conn = self._db.get_connection()
        rows = conn.execute(queries.SELECT_ALL_PATTERNS_INCLUDE_INACTIVE).fetchall()
        return [self._row_to_pattern(r) for r in rows]

    def update_confidence(self, pattern_id: int, confidence: float, frequency: int):
        conn = self._db.get_connection()
        conn.execute(queries.UPDATE_PATTERN_CONFIDENCE, (confidence, frequency, pattern_id))
        conn.commit()

    def delete_pattern(self, pattern_id: int):
        conn = self._db.get_connection()
        conn.execute(queries.DELETE_PATTERN, (pattern_id,))
        conn.commit()

    def _row_to_pattern(self, row) -> ActionPattern:
        return ActionPattern(
            pattern_id=row["id"],
            name=row["name"],
            description=row["description"],
            symbol_sequence=row["symbol_sequence"],
            action_types=json.loads(row["action_types"]) if row["action_types"] else [],
            avg_duration_ms=row["avg_duration_ms"],
            frequency=row["frequency"],
            confidence=row["confidence"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            is_active=bool(row["is_active"]),
            user_confirmed=bool(row["user_confirmed"]),
        )


class PredictionLogDAO:
    def __init__(self, db: DatabaseManager):
        self._db = db

    def log_prediction(self, pattern_id: int, was_accepted: Optional[bool],
                       match_score: float, context: dict = None):
        conn = self._db.get_connection()
        conn.execute(queries.INSERT_PREDICTION_LOG, (
            pattern_id,
            int(was_accepted) if was_accepted is not None else None,
            match_score,
            json.dumps(context or {}),
        ))
        conn.commit()

    def get_recent(self, limit: int = 20) -> list:
        conn = self._db.get_connection()
        return conn.execute(queries.SELECT_PREDICTION_LOG, (limit,)).fetchall()


class SettingsDAO:
    def __init__(self, db: DatabaseManager):
        self._db = db

    def get(self, key: str, default: str = "") -> str:
        conn = self._db.get_connection()
        row = conn.execute(queries.GET_SETTING, (key,)).fetchone()
        return row[0] if row else default

    def set(self, key: str, value: str):
        conn = self._db.get_connection()
        conn.execute(queries.SET_SETTING, (key, value))
        conn.commit()

    def get_all(self) -> dict:
        conn = self._db.get_connection()
        rows = conn.execute(queries.GET_ALL_SETTINGS).fetchall()
        return {row[0]: row[1] for row in rows}
