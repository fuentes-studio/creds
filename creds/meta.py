"""SQLite metadata store for credential tracking (rotation, flags, context)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DEFAULT_DB = Path.home() / ".creds" / "meta.db"

DEFAULT_SETTINGS = {
    "rotation_warn_days": "90",
    "rotation_overdue_days": "180",
}


@dataclass
class CredMeta:
    service_id: str
    instance: str
    field_id: str
    context: str
    status: str
    added_at: str
    updated_at: str
    flag_reason: Optional[str]
    flagged_at: Optional[str]


class MetaStore:
    def __init__(self, db_path: Path = DEFAULT_DB) -> None:
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        cur = self._conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS creds (
                service_id  TEXT NOT NULL,
                instance    TEXT NOT NULL DEFAULT '',
                field_id    TEXT NOT NULL,
                context     TEXT NOT NULL DEFAULT 'personal',
                status      TEXT NOT NULL DEFAULT 'active',
                added_at    TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                flag_reason TEXT,
                flagged_at  TEXT,
                PRIMARY KEY (service_id, instance, field_id)
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        # Seed default settings
        for k, v in DEFAULT_SETTINGS.items():
            cur.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v)
            )
        self._conn.commit()

    def upsert(
        self,
        service_id: str,
        instance: str,
        field_id: str,
        context: str = "personal",
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """
            INSERT INTO creds (service_id, instance, field_id, context, status, added_at, updated_at)
            VALUES (?, ?, ?, ?, 'active', ?, ?)
            ON CONFLICT (service_id, instance, field_id)
            DO UPDATE SET updated_at = excluded.updated_at
            """,
            (service_id, instance, field_id, context, now, now),
        )
        self._conn.commit()

    def get(
        self, service_id: str, instance: str, field_id: str
    ) -> Optional[CredMeta]:
        row = self._conn.execute(
            "SELECT * FROM creds WHERE service_id=? AND instance=? AND field_id=?",
            (service_id, instance, field_id),
        ).fetchone()
        if row is None:
            return None
        return CredMeta(
            service_id=row["service_id"],
            instance=row["instance"],
            field_id=row["field_id"],
            context=row["context"],
            status=row["status"],
            added_at=row["added_at"],
            updated_at=row["updated_at"],
            flag_reason=row["flag_reason"],
            flagged_at=row["flagged_at"],
        )

    def delete(self, service_id: str, instance: str, field_id: str) -> None:
        self._conn.execute(
            "DELETE FROM creds WHERE service_id=? AND instance=? AND field_id=?",
            (service_id, instance, field_id),
        )
        self._conn.commit()

    def flag(
        self, service_id: str, instance: str, field_id: str, reason: str
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """
            UPDATE creds SET status='flagged', flag_reason=?, flagged_at=?, updated_at=?
            WHERE service_id=? AND instance=? AND field_id=?
            """,
            (reason, now, now, service_id, instance, field_id),
        )
        self._conn.commit()

    def unflag(self, service_id: str, instance: str, field_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """
            UPDATE creds SET status='active', flag_reason=NULL, flagged_at=NULL, updated_at=?
            WHERE service_id=? AND instance=? AND field_id=?
            """,
            (now, service_id, instance, field_id),
        )
        self._conn.commit()

    def all_for_service(self, service_id: str) -> list[CredMeta]:
        rows = self._conn.execute(
            "SELECT * FROM creds WHERE service_id=?", (service_id,)
        ).fetchall()
        return [
            CredMeta(
                service_id=r["service_id"],
                instance=r["instance"],
                field_id=r["field_id"],
                context=r["context"],
                status=r["status"],
                added_at=r["added_at"],
                updated_at=r["updated_at"],
                flag_reason=r["flag_reason"],
                flagged_at=r["flagged_at"],
            )
            for r in rows
        ]

    def setting(self, key: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT value FROM settings WHERE key=?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def set_setting(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "MetaStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
