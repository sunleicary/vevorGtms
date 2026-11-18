"""Create Neon PostgreSQL tables without copying or deleting data.

Usage:
    python -m pip install "psycopg[binary]>=3.2,<4"
    export DATABASE_URL='...'  # keep credentials out of source control
    python create_neon_schema.py

This script is idempotent and does not switch the Streamlit application backend.
"""
import os
import sys

import psycopg

BUSINESS_FIELDS = [
    "排柜单号", "目的仓", "目的仓物流区域", "目的仓国家", "ATA日期", "目的港/站卸柜日期",
    "货代", "港前拖车行", "卸货港", "卸货码头", "目的港码头", "码头", "Terminal",
    "目的地", "船公司", "实际船名", "实际航次", "ETA日期", "箱号", "MB/L No.",
    "港后拖车行", "LFD", "海关放行时间", "清关完成时间", "进口实际提箱时间",
    "约仓时间", "实际送仓时间", "实际到海外仓日期", "实际还柜日期",
    "预计还柜时间", "进口查验开始日期", "进口查验完成日期", "港后内部备注",
]


KPI_TABLES = {
    "港后提柜及时率": "kpi_pickup_timeliness",
    "送仓准时率": "kpi_delivery_punctuality",
    "送仓时效": "kpi_delivery_duration",
    "提空及时率": "kpi_empty_pickup_timeliness",
    "还柜及时率": "kpi_empty_return_timeliness",
    "台账": "kpi_source_ledger",
}


def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("请先在当前终端设置 DATABASE_URL 环境变量。")

    from psycopg import sql

    try:
        with psycopg.connect(url, connect_timeout=15) as conn:
            with conn.transaction():
                conn.execute("CREATE TABLE IF NOT EXISTS containers (id BIGINT PRIMARY KEY)")
                for field in BUSINESS_FIELDS:
                    conn.execute(
                        sql.SQL("ALTER TABLE containers ADD COLUMN IF NOT EXISTS {} TEXT").format(
                            sql.Identifier(field)
                        )
                    )
                conn.execute("""CREATE TABLE IF NOT EXISTS kpi_raw_rows_v2 (
                    month TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    source_row INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    source_file TEXT NOT NULL,
                    imported_at TEXT NOT NULL,
                    PRIMARY KEY (month, metric, source_row)
                )""")
                # Six independent KPI detail tables; payload preserves all original Excel columns.
                for table in KPI_TABLES.values():
                    conn.execute(sql.SQL("""CREATE TABLE IF NOT EXISTS {} (
                        month TEXT NOT NULL,
                        source_row INTEGER NOT NULL,
                        order_no TEXT,
                        supplier TEXT,
                        payload JSONB NOT NULL,
                        source_file TEXT NOT NULL,
                        imported_at TEXT NOT NULL,
                        PRIMARY KEY (month, source_row)
                    )""").format(sql.Identifier(table)))
                    conn.execute(sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} (month, supplier)").format(
                        sql.Identifier("idx_" + table + "_month_supplier"), sql.Identifier(table)))
                    conn.execute(sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} (order_no)").format(
                        sql.Identifier("idx_" + table + "_order"), sql.Identifier(table)))
                conn.execute("""CREATE TABLE IF NOT EXISTS kpi_batches_v2 (
                    month TEXT PRIMARY KEY,
                    source_file TEXT NOT NULL,
                    imported_at TEXT NOT NULL,
                    row_count INTEGER NOT NULL
                )""")
                conn.execute("""CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )""")
                conn.execute('CREATE INDEX IF NOT EXISTS idx_containers_order ON containers ("排柜单号")')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_containers_region ON containers ("目的仓物流区域")')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_containers_supplier ON containers ("港后拖车行")')
                conn.execute("CREATE INDEX IF NOT EXISTS idx_kpi_month_metric ON kpi_raw_rows_v2 (month, metric)")
                conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_username_lower_idx ON users (lower(username))")

            for table in ("containers", "kpi_raw_rows_v2", "kpi_batches_v2", "users", *KPI_TABLES.values()):
                count = conn.execute(
                    sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table))
                ).fetchone()[0]
                print(f"OK {table}: {count:,} rows")
        print("Neon schema created/verified. No records were deleted.")
    except Exception as exc:
        # Never print connection strings or passwords in error output.
        print(f"建表失败：{type(exc).__name__}。请检查 Neon 连接、权限及目标表结构。")
        sys.exit(1)


if __name__ == "__main__":
    main()
