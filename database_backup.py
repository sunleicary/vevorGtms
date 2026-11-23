"""Administrator-only consistent SQLite backups.

Backups are built in a temporary directory with sqlite3.Connection.backup(),
packaged in memory, and never written to the Git repository.
"""
import io
import os
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from import_data import DB as PORT_DB
from monthly_supplier_entry import DB as KPI_DB
from auth import AUTH_DB, is_admin

DATABASES = (
    ("port_ops.db", PORT_DB),
    ("supplier_kpi.db", KPI_DB),
    ("users.db", AUTH_DB),
)


def show_database_backup(user):
    if not user or not is_admin(user):
        st.error("权限不足：仅管理员可备份数据库。")
        st.stop()

    st.title("数据库备份中心")
    st.warning("备份包含业务数据及用户密码哈希。仅在可信设备下载，下载后请加密保存，不要上传到公开 GitHub 或共享网盘。")
    st.caption("通过 SQLite Backup API 获取一致性快照；只读取当前运行实例中的数据库，不会修改原始数据。")
    found = []
    missing = []
    for filename, path in DATABASES:
        if os.path.isfile(path):
            found.append((filename, path))
            st.write(f"✓ {filename} — {os.path.getsize(path):,} bytes")
        else:
            missing.append(filename)
            st.write(f"✗ {filename} — 当前实例中不存在")
    if not found:
        st.error("当前实例没有可备份的数据库。")
        return
    if missing:
        st.warning("将生成部分备份。缺少数据库：" + "、".join(missing) + "。")

    if st.button("生成当前数据库备份", type="primary", key="prepare_sqlite_backup"):
        try:
            with st.spinner("正在生成 SQLite 快照并压缩，请勿刷新页面..."):
                output = io.BytesIO()
                with tempfile.TemporaryDirectory(prefix="sqlite_backup_") as tmp:
                    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                        for filename, path in found:
                            target = Path(tmp) / filename
                            # Open source read-only: never create a missing DB by mistake.
                            source = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=30)
                            try:
                                with sqlite3.connect(str(target), timeout=30) as destination:
                                    source.backup(destination, pages=256, sleep=0.1)
                                with sqlite3.connect(str(target)) as check:
                                    integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
                                    if integrity != "ok":
                                        raise RuntimeError(f"{filename} integrity check failed")
                                archive.write(target, arcname=filename)
                            finally:
                                source.close()
                        included = "、".join(filename for filename, _ in found)
                        omitted = "、".join(missing) or "无"
                        archive.writestr("backup_manifest.txt", f"包含：{included}\n缺少：{omitted}\n")
                st.session_state["sqlite_backup_zip"] = output.getvalue()
                st.session_state["sqlite_backup_filename"] = (
                    ("sqlite-backup-partial-" if missing else "sqlite-backup-")
                    + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-UTC.zip"
                )
            st.success(f"已生成 {len(found)} 个数据库快照并通过完整性检查。")
        except Exception:
            st.session_state.pop("sqlite_backup_zip", None)
            st.session_state.pop("sqlite_backup_filename", None)
            st.error("备份生成失败，请检查服务器数据库状态及可用内存。")
    if "sqlite_backup_zip" in st.session_state:
        st.download_button(
            "下载 SQLite 备份 ZIP",
            data=st.session_state["sqlite_backup_zip"],
            file_name=st.session_state["sqlite_backup_filename"],
            mime="application/zip",
            key="download_sqlite_backup",
        )
        if st.button("清除本次备份缓存", key="clear_sqlite_backup"):
            st.session_state.pop("sqlite_backup_zip", None)
            st.session_state.pop("sqlite_backup_filename", None)
            st.rerun()
    st.caption("ZIP 本身未加密；下载后应在本机加密保存。退出登录时应用将清除备份缓存。")
