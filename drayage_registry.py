"""Persistent drayage supplier profiles and full import from container assignments."""
import os
from contextlib import closing, contextmanager
from datetime import datetime, timezone

from db_backend import connect, is_neon
from import_data import DB

REGISTRY_DB = os.path.join(os.path.dirname(DB), "drayage_suppliers.db")
STAGES = ("港前", "港后")
STATUSES = ("待核实", "启用", "停用")
PLACEHOLDERS = {"", "nan", "none", "null", "港前拖车测试", "港后拖车测试",
                "待分配", "未分配", "未记录", "待分配/未记录", "未分配/未记录"}


@contextmanager
def registry_transaction(neon):
    with closing(connect(REGISTRY_DB)) as conn:
        try:
            if neon:
                conn.execute("SELECT pg_advisory_xact_lock(857230104)")
            else:
                conn.execute("BEGIN IMMEDIATE")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS drayage_suppliers (
                    stage TEXT NOT NULL CHECK (stage IN ('港前', '港后')),
                    name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT '待核实'
                        CHECK (status IN ('待核实', '启用', '停用')),
                    contact TEXT NOT NULL DEFAULT '',
                    phone TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    updated_by TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (stage, name)
                )
            """)
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def assigned_suppliers(conn):
    rows = conn.execute("""
        SELECT DISTINCT '港前' AS stage, "港前拖车行" AS name FROM containers
        UNION ALL
        SELECT DISTINCT '港后' AS stage, "港后拖车行" AS name FROM containers
    """)
    suppliers = set()
    for row in rows:
        name = (row["name"] or "").strip()
        if name.casefold() not in PLACEHOLDERS:
            suppliers.add((row["stage"], name))
    return suppliers


def read_and_sync_registry():
    """Backfill every distinct assignment while preserving existing profiles."""
    neon = is_neon()
    source_available = neon or os.path.exists(DB)
    with registry_transaction(neon) as conn:
        if neon:
            assigned = assigned_suppliers(conn)
        elif source_available:
            with closing(connect(DB)) as source:
                assigned = assigned_suppliers(source)
        else:
            assigned = set()
        existing = {
            (row["stage"], row["name"])
            for row in conn.execute("SELECT stage, name FROM drayage_suppliers")
        }
        missing = assigned - existing
        if missing:
            now = datetime.now(timezone.utc).isoformat()
            conn.executemany("""
                INSERT INTO drayage_suppliers (stage, name, created_at, updated_at)
                VALUES (?, ?, ?, ?) ON CONFLICT (stage, name) DO NOTHING
            """, [(stage, name, now, now) for stage, name in sorted(missing)])
        profiles = [
            dict(row) for row in conn.execute(
                "SELECT * FROM drayage_suppliers ORDER BY stage, name"
            )
        ]
    return profiles, assigned, len(missing), source_available


def update_profile(user, profile, status, contact, phone, email, notes):
    if user["role"] != "管理员":
        raise PermissionError("仅管理员可编辑供应商档案。")
    if status not in STATUSES:
        raise ValueError("供应商状态无效。")
    with registry_transaction(is_neon()) as conn:
        result = conn.execute("""
            UPDATE drayage_suppliers
            SET status = ?, contact = ?, phone = ?, email = ?, notes = ?,
                updated_at = ?, updated_by = ?
            WHERE stage = ? AND name = ? AND updated_at = ?
        """, (status, contact.strip(), phone.strip(), email.strip(), notes.strip(),
              datetime.now(timezone.utc).isoformat(), user["username"],
              profile["stage"], profile["name"], profile["updated_at"]))
        return result.rowcount == 1
