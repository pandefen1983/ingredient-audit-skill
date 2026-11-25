"""Local SQLite cache for recall runs.

Two reasons it matters:

1. Rate limits. A plan can legitimately be 200 requests; re-fetching pages
   that were fetched an hour ago is exactly what gets an IP throttled.
2. Diffable recall. Storing every (platform, sku_id) lets a later run say
   "180 recalled, 40 new since last time" instead of starting from zero.

Standard library only (``sqlite3``), no runtime dependency added.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

DEFAULT_PATH = Path(".cache/recall.sqlite3")


def _now(at: datetime | None = None) -> datetime:
    return at or datetime.now(timezone.utc)


def _stamp(at: datetime | None = None) -> str:
    return _now(at).isoformat(timespec="seconds")


class SkuCache:
    """Tiny cache around a SQLite file."""

    def __init__(self, path: Path | str = DEFAULT_PATH) -> None:
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS queries (
                platform TEXT NOT NULL,
                query    TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                n_items  INTEGER NOT NULL DEFAULT 0,
                source   TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (platform, query)
            );
            CREATE TABLE IF NOT EXISTS skus (
                platform TEXT NOT NULL,
                sku_id   TEXT NOT NULL,
                payload  TEXT NOT NULL,
                evidence_type TEXT NOT NULL DEFAULT 'D',
                first_seen TEXT NOT NULL,
                last_seen  TEXT NOT NULL,
                PRIMARY KEY (platform, sku_id)
            );
            """
        )
        self.conn.commit()

    # ---------------- query log ----------------

    def record_query(
        self,
        platform: str,
        query: str,
        n_items: int = 0,
        source: str = "",
        at: datetime | None = None,
    ) -> None:
        stamp = _stamp(at)
        self.conn.execute(
            """
            INSERT INTO queries (platform, query, fetched_at, n_items, source)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(platform, query) DO UPDATE SET
                fetched_at = excluded.fetched_at,
                n_items   = excluded.n_items,
                source    = excluded.source
            """,
            (platform, query, stamp, int(n_items), source),
        )
        self.conn.commit()

    def last_fetch(self, platform: str, query: str) -> str | None:
        row = self.conn.execute(
            "SELECT fetched_at FROM queries WHERE platform = ? AND query = ?",
            (platform, query),
        ).fetchone()
        return row[0] if row else None

    def should_refetch(
        self, platform: str, query: str, ttl_days: int = 7, at: datetime | None = None
    ) -> bool:
        last = self.last_fetch(platform, query)
        if last is None:
            return True
        try:
            last_dt = datetime.fromisoformat(last)
        except ValueError:
            return True
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        return _now(at) - last_dt > timedelta(days=ttl_days)

    def query_log(self, platform: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT platform, query, fetched_at, n_items, source FROM queries"
        params: tuple[Any, ...] = ()
        if platform:
            sql += " WHERE platform = ?"
            params = (platform,)
        sql += " ORDER BY fetched_at DESC"
        rows = self.conn.execute(sql, params).fetchall()
        return [
            {
                "platform": row[0],
                "query": row[1],
                "fetched_at": row[2],
                "n_items": row[3],
                "source": row[4],
            }
            for row in rows
        ]

    # ---------------- sku store ----------------

    def upsert_sku(
        self,
        platform: str,
        sku_id: str,
        payload: dict[str, Any],
        evidence_type: str = "D",
        at: datetime | None = None,
    ) -> None:
        stamp = _stamp(at)
        self.conn.execute(
            """
            INSERT INTO skus (platform, sku_id, payload, evidence_type, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform, sku_id) DO UPDATE SET
                payload = excluded.payload,
                evidence_type = excluded.evidence_type,
                last_seen = excluded.last_seen
            """,
            (platform, str(sku_id), json.dumps(payload, ensure_ascii=False), evidence_type, stamp, stamp),
        )
        self.conn.commit()

    def upsert_many(self, rows: Iterable[tuple[str, str, dict[str, Any], str]]) -> int:
        count = 0
        for platform, sku_id, payload, evidence in rows:
            self.upsert_sku(platform, sku_id, payload, evidence)
            count += 1
        return count

    def load_raw(self, platform: str | None = None) -> list[tuple[str, dict[str, Any]]]:
        sql = "SELECT platform, payload FROM skus"
        params: tuple[Any, ...] = ()
        if platform:
            sql += " WHERE platform = ?"
            params = (platform,)
        rows = self.conn.execute(sql, params).fetchall()
        return [(row[0], json.loads(row[1])) for row in rows]

    def stats(self) -> dict[str, Any]:
        sku_count = self.conn.execute("SELECT COUNT(*) FROM skus").fetchone()[0]
        query_count = self.conn.execute("SELECT COUNT(*) FROM queries").fetchone()[0]
        by_platform = self.conn.execute(
            "SELECT platform, COUNT(*) FROM skus GROUP BY platform"
        ).fetchall()
        return {
            "skus": sku_count,
            "queries": query_count,
            "by_platform": {row[0]: row[1] for row in by_platform},
            "path": str(self.path),
        }

    def close(self) -> None:
        self.conn.close()
