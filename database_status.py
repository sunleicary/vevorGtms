"""Administrator-only read-only database status panel. Never expose DSN or credentials."""
from datetime import datetime, timezone
import sqlite3
import streamlit as st
from db_backend import connect, is_neon

TABLES = ("containers", "kpi_raw_rows_v2", "kpi_batches_v2", "users",
          "kpi_pickup_timeliness", "kpi_delivery_punctuality",
          "kpi_delivery_duration", "kpi_empty_pickup_timeliness",
          "kpi_empty_return_timeliness", "kpi_source_ledger")
EXPECTED = {"containers": 35657, "kpi_raw_rows_v2": 78488,
            "kpi_batches_v2": 1, "users": 1,
            "kpi_pickup_timeliness": 2529, "kpi_delivery_punctuality": 2796,
            "kpi_delivery_duration": 929, "kpi_empty_pickup_timeliness": 2651,
            "kpi_empty_return_timeliness": 2651, "kpi_source_ledger": 66932}

def show_database_status(user, sqlite_path):
    if user.get("role") not in ("管理员", "系统管理员"):
        st.error("仅管理员可以查看数据库状态。")
        return
    st.subheader("数据库连接状态")
    st.caption("实时只读检测当前应用使用的数据库；不修改业务数据，不展示连接字符串或密码。")
    if st.button("刷新数据库状态", key="refresh_database_status"):
        st.rerun()
    neon = is_neon()
    st.metric("应用数据库后端", "Neon PostgreSQL" if neon else "SQLite")
    try:
        with connect(sqlite_path) as conn:
            if neon:
                info = conn.execute("SELECT current_database(), current_schema(), version()").fetchone()
                db_name, schema, version = info[0], info[1], info[2]
                st.success("PostgreSQL 查询成功：应用当前已连接 Neon 配置的数据库。")
                st.write(f"数据库名称：`{db_name}` · Schema：`{schema}`")
                st.caption("服务端版本：" + version.split(",")[0][:100])
            else:
                st.success("当前使用 SQLite 本地数据库。旧 DATABASE_URL 已被程序忽略。")
            counts = {}
            for table in TABLES if neon else TABLES[:1]:
                try:
                    counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                except Exception:
                    counts[table] = None
            st.metric("货柜记录数", f"{counts['containers']:,}" if counts["containers"] is not None else "读取失败")
            if neon:
                st.metric("KPI 原始记录数", f"{counts['kpi_raw_rows_v2']:,}" if counts["kpi_raw_rows_v2"] is not None else "读取失败")
                st.dataframe([{"表名": name, "当前记录数": counts[name],
                               "迁移时基准数": EXPECTED[name],
                               "与基准一致": ("是" if counts[name] == EXPECTED[name] else "否") if counts[name] is not None else "读取失败"}
                              for name in TABLES], hide_index=True, use_container_width=True)
                st.caption("迁移时基准数仅供参考；后续正常业务导入可能导致记录数变化。")
            st.caption("检测时间（UTC）：" + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
    except Exception as exc:
        st.error("数据库连接或查询失败。请检查连接配置、网络和数据库权限。")
        st.caption("错误类型：" + type(exc).__name__ + "（敏感连接信息已隐藏）")
