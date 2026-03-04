"""Serialization utilities for ActionEvent <-> database conversion."""

import json
from core.action_types import ActionEvent, ActionType


def event_to_db_row(event: ActionEvent, session_id: int, sequence_order: int) -> tuple:
    """Convert an ActionEvent to a database row tuple."""
    return (
        session_id,
        sequence_order,
        event.action_type.name,
        event.timestamp_ns,
        event.x,
        event.y,
        event.region_x,
        event.region_y,
        event.button,
        event.scroll_dx,
        event.scroll_dy,
        event.key,
        event.key_char,
        json.dumps(event.modifiers) if event.modifiers else "[]",
        event.screenshot_path,
        json.dumps(event.metadata) if event.metadata else "{}",
    )


def db_row_to_event(row: tuple) -> ActionEvent:
    """Convert a database row to an ActionEvent.

    Expected row order:
    (id, session_id, sequence_order, action_type, timestamp_ns,
     abs_x, abs_y, region_x, region_y, button, scroll_dx, scroll_dy,
     key_name, key_char, modifiers, screenshot_path, metadata_json)
    """
    return ActionEvent(
        action_type=ActionType[row[3]],
        timestamp_ns=row[4],
        x=row[5],
        y=row[6],
        region_x=row[7],
        region_y=row[8],
        button=row[9],
        scroll_dx=row[10] or 0,
        scroll_dy=row[11] or 0,
        key=row[12],
        key_char=row[13],
        modifiers=json.loads(row[14]) if row[14] else [],
        screenshot_path=row[15],
        metadata=json.loads(row[16]) if row[16] else {},
    )
