"""Global monthly KPI workbook import: preserve every source data row for reconciliation."""
import json
import os
import sqlite3
from db_backend import connect as db_connect, read_sql, is_neon
from create_neon_schema import KPI_TABLES
from kpi_summary import summarize
import kpi_neon_queries as neon_kpi
from datetime import datetime, timezone
from io import BytesIO
import pandas as pd
import streamlit as st

DB = os.environ.get("KPI_DB_PATH", os.path.join(os.path.dirname(__file__), "supplier_kpi.db"))
SHEETS = ["港后提柜及时率", "送仓准时率", "送仓时效", "提空及时率", "还柜及时率"]
IMPORT_SHEETS = SHEETS + ["台账"]

def connect():
    conn = db_connect(DB, timeout=60)
    if not is_neon():
        conn.execute("""CREATE TABLE IF NOT EXISTS kpi_raw_rows_v2(
            month TEXT NOT NULL, metric TEXT NOT NULL, source_row INTEGER NOT NULL,
            payload TEXT NOT NULL, source_file TEXT NOT NULL, imported_at TEXT NOT NULL,
            PRIMARY KEY(month,metric,source_row))""")
        conn.execute("""CREATE TABLE IF NOT EXISTS kpi_batches_v2(
            month TEXT PRIMARY KEY, source_file TEXT NOT NULL, imported_at TEXT NOT NULL,
            row_count INTEGER NOT NULL)""")
        conn.commit()
    return conn

def parse_month(value, chosen_month):
    if value is None or str(value).strip() == "":
        return chosen_month
    if isinstance(value, datetime):
        m = value.month
        year = value.year
    else:
        raw = str(value).strip()
        try:
            if raw.replace(".0", "").isdigit() and int(float(raw)) <= 12:
                m = int(float(raw))
                year = int(chosen_month[:4])
            else:
                parsed = pd.to_datetime(raw, errors="raise")
                m, year = parsed.month, parsed.year
        except (ValueError, TypeError):
            raise ValueError(f"无法识别源文件月份：{raw}")
    month = f"{year}-{m:02d}"
    if month != chosen_month:
        raise ValueError(f"源文件月份 {month} 与所选考核月份 {chosen_month} 不一致。")
    return month

def parse_workbook(payload, month):
    from openpyxl import load_workbook
    book = load_workbook(BytesIO(payload), read_only=True, data_only=True)
    missing = [s for s in SHEETS if s not in book.sheetnames]
    if missing:
        book.close()
        raise ValueError("缺少工作表：" + "、".join(missing))
    rows = []
    counts = {}
    for sheet in IMPORT_SHEETS:
        if sheet not in book.sheetnames:
            continue
        ws = book[sheet]
        header_row = 1 if sheet == "台账" else 2
        headers = next(ws.iter_rows(min_row=header_row, max_row=header_row, values_only=True))
        columns = [str(v).strip() if v is not None and str(v).strip()
                   else f"未命名列_{i+1}" for i,v in enumerate(headers)]
        if sheet != "台账" and "月份" not in columns:
            book.close()
            raise ValueError(f"{sheet} 缺少月份字段")
        count = 0
        for source_row, values in enumerate(ws.iter_rows(min_row=header_row + 1, values_only=True), start=header_row + 1):
            # Preserve global original rows, except blank order numbers in 送仓时效.
            if not any(v is not None and str(v).strip() for v in values):
                continue
            data = {}
            for i, col in enumerate(columns):
                v = values[i] if i < len(values) else None
                if isinstance(v, (datetime, pd.Timestamp)):
                    v = v.isoformat()
                data[col] = "" if v is None else str(v)
            if sheet != "台账":
                parse_month(data.get("月份"), month)
            if sheet == "送仓时效" and not str(data.get("排柜单号", "")).strip():
                continue
            rows.append((month, sheet, source_row, json.dumps(data, ensure_ascii=False, default=str)))
            count += 1
        counts[sheet] = count
    book.close()
    return rows, counts

def show_monthly_supplier_entry(df, user):
    st.title("港后供应商 KPI 考核｜全球原始数据核对")
    st.caption("仅展示五项供应商考核指标；如工作簿包含台账，导入时仍保留其原始数据。送仓时效排除排柜单号为空的记录。")
    try:
        with connect() as conn:
            batches = read_sql("SELECT * FROM kpi_batches_v2 ORDER BY month DESC", conn)
    except Exception as exc:
        st.error(f"无法读取数据库：{exc}")
        return
    if user.get("role") == "管理员":
        with st.expander("统一导入 KPI 文件", expanded=batches.empty):
            uploaded = st.file_uploader("上传完整 KPI 工作簿", type=["xlsx"], key="kpi_global_upload")
            choices = [f"{y}-{m:02d}" for y in range(2024, 2036) for m in range(1,13)]
            now = datetime.now()
            default = f"{now.year}-{now.month:02d}"
            month = st.selectbox("考核月份", choices,
                                 index=choices.index(default) if default in choices else 0,
                                 key="kpi_global_month")
            if st.button("导入并保存全部原始记录", disabled=uploaded is None, type="primary"):
                try:
                    rows, counts = parse_workbook(uploaded.getvalue(), month)
                    timestamp = datetime.now(timezone.utc).isoformat()
                    with connect() as conn:
                        conn.execute("DELETE FROM kpi_raw_rows_v2 WHERE month=?", (month,))
                        conn.execute("DELETE FROM kpi_batches_v2 WHERE month=?", (month,))
                        conn.executemany("""INSERT INTO kpi_raw_rows_v2
                            (month,metric,source_row,payload,source_file,imported_at)
                            VALUES (?,?,?,?,?,?)""",
                            [(m,s,n,p,uploaded.name,timestamp) for m,s,n,p in rows])
                        conn.execute("""INSERT INTO kpi_batches_v2
                            (month,source_file,imported_at,row_count) VALUES (?,?,?,?)""",
                            (month,uploaded.name,timestamp,len(rows)))
                        if is_neon():
                            # Keep the six materialized KPI tables consistent with the legacy raw table.
                            for metric, table in KPI_TABLES.items():
                                conn.execute(f"DELETE FROM {table} WHERE month=?", (month,))
                            for metric, table in KPI_TABLES.items():
                                subset = []
                                for m, sheet, source_row, payload in rows:
                                    if sheet != metric:
                                        continue
                                    data = json.loads(payload)
                                    subset.append((m, source_row,
                                                   str(data.get("排柜单号", "")).strip(),
                                                   str(data.get("港后拖车行", "")).strip(),
                                                   payload, uploaded.name, timestamp))
                                conn.executemany(
                                    f"""INSERT INTO {table}
                                    (month,source_row,order_no,supplier,payload,source_file,imported_at)
                                    VALUES (?,?,?,?,?::jsonb,?,?)""", subset)
                        conn.commit()
                    st.success(f"已保存 {len(rows):,} 条原始明细。")
                    st.dataframe(pd.DataFrame([{"指标":k,"导入记录数":counts.get(k,0)} for k in SHEETS]),
                                 hide_index=True,use_container_width=True)
                    st.rerun()
                except Exception as exc:
                    st.error(f"导入失败，原有数据保持不变：{exc}")
            st.caption("再次导入相同考核月份将覆盖该月原始记录；不会修改 Excel 中的原始考核结果。")
    if batches.empty:
        st.info("尚无已导入的全球 KPI 文件。")
        return
    selected = st.selectbox("已导入考核月份", batches["month"].tolist(), key="kpi_global_saved_month")
    batch = batches[batches["month"].eq(selected)].iloc[0]
    st.caption(f"来源文件：{batch['source_file']}｜总记录数：{int(batch['row_count']):,}")
    if is_neon():
        # Neon: fetch only distinct filter options and five aggregate rows.
        # No whole-month JSON payload transfer on filter changes.
        with connect() as conn:
            suppliers = neon_kpi.options(conn, selected)
        supplier_options = ["全部供应商"] + sorted(v for v in suppliers if v)
        if "" in suppliers:
            supplier_options.append("未填写港后拖车行")
        st.markdown("### 考核范围")
        st.caption("先选择港后拖车供应商，再选择该供应商覆盖的美国区域。默认统计美国全区域。")
        filter_supplier_col, filter_region_col = st.columns(2, gap="large")
        with filter_supplier_col:
            selected_supplier = st.selectbox(
                "① 港后拖车供应商", supplier_options, key="kpi_global_supplier")
        supplier_value = (None if selected_supplier == "全部供应商"
                          else "" if selected_supplier == "未填写港后拖车行"
                          else selected_supplier)
        with connect() as conn:
            regions = neon_kpi.region_options(conn, selected, supplier_value)
        region_options = ["美国全区域"] + sorted(v for v in regions if v)
        if "" in regions:
            region_options.append("未填写区域")
        region_key = "kpi_global_us_region"
        if st.session_state.get(region_key) not in region_options:
            st.session_state[region_key] = "美国全区域"
        with filter_region_col:
            selected_region = st.selectbox(
                "② 美国目的仓物流区域", region_options, key=region_key)
        region_value = (None if selected_region == "美国全区域"
                        else "" if selected_region == "未填写区域"
                        else selected_region)
        with connect() as conn:
            summary, warnings = neon_kpi.summary(conn, selected, supplier_value, region_value)
    else:
        with connect() as conn:
            raw = read_sql("""SELECT metric,source_row,payload FROM kpi_raw_rows_v2
                WHERE month=? AND metric!='台账' ORDER BY metric,source_row""",conn,params=(selected,))
        # Apply the same rule to records imported before this release.
        if not raw.empty:
            mask = raw["metric"].eq("送仓时效")
            if mask.any():
                valid = raw.loc[mask, "payload"].map(
                    lambda p: bool(str(json.loads(p).get("排柜单号", "")).strip()))
                raw = raw.loc[~mask | raw.index.isin(valid.index[valid])].copy()
        # Scope this dashboard to US records and region by 目的仓物流区域.
        # Supplier attribution must come exclusively from 港后拖车行.
        if not raw.empty:
            raw = raw.copy()
            payloads = raw["payload"].map(json.loads)
            raw["_country"] = payloads.map(
                lambda p: str(p.get("目的仓国家", "") or "").strip().upper())
            raw["_region"] = payloads.map(
                lambda p: str(p.get("目的仓物流区域", "") or "").strip())
            raw["_supplier"] = payloads.map(
                lambda p: str(p.get("港后拖车行", "") or "").strip())
            us_names = {"美国", "US", "USA", "AMERICA",
                        "UNITED STATES", "UNITED STATES OF AMERICA"}
            raw = raw.loc[raw["_country"].isin(us_names)].copy()
        else:
            raw = raw.copy()
            for column in ("_country", "_region", "_supplier"):
                raw[column] = pd.Series(dtype=str)

        st.markdown("### 考核范围")
        st.caption("先选择港后拖车供应商，再选择该供应商覆盖的美国区域。默认统计美国全区域。")
        suppliers = sorted(v for v in raw["_supplier"].unique() if v)
        supplier_options = ["全部供应商"] + suppliers
        if raw["_supplier"].eq("").any():
            supplier_options.append("未填写港后拖车行")

        filter_supplier_col, filter_region_col = st.columns(2, gap="large")
        with filter_supplier_col:
            selected_supplier = st.selectbox(
                "① 港后拖车供应商", supplier_options, key="kpi_global_supplier")
        if selected_supplier == "未填写港后拖车行":
            supplier_raw = raw.loc[raw["_supplier"].eq("")].copy()
        elif selected_supplier == "全部供应商":
            supplier_raw = raw
        else:
            supplier_raw = raw.loc[raw["_supplier"].eq(selected_supplier)].copy()

        region_options = ["美国全区域"] + sorted(
            v for v in supplier_raw["_region"].unique() if v)
        if supplier_raw["_region"].eq("").any():
            region_options.append("未填写区域")
        # Clear a stale region when changing suppliers, so the widget always has
        # a valid selection for the newly chosen supplier.
        region_key = "kpi_global_us_region"
        if st.session_state.get(region_key) not in region_options:
            st.session_state[region_key] = "美国全区域"
        with filter_region_col:
            selected_region = st.selectbox(
                "② 美国目的仓物流区域", region_options, key=region_key)
        if selected_region == "美国全区域":
            visible_raw = supplier_raw
        elif selected_region == "未填写区域":
            visible_raw = supplier_raw.loc[supplier_raw["_region"].eq("")].copy()
        else:
            visible_raw = supplier_raw.loc[
                supplier_raw["_region"].eq(selected_region)].copy()
        summary, warnings = summarize(visible_raw)
    st.markdown("### 五项考核指标汇总")
    st.caption(f"考核月份：{selected}　｜　供应商：{selected_supplier}　｜　区域：{selected_region}")
    # Top-line operational scorecards: each metric is calculated independently
    # from the same supplier/region-filtered rows as the detailed summary.
    metric_cols = st.columns(5, gap="small")
    for col, row in zip(metric_cols, summary.to_dict("records")):
        with col:
            with st.container(border=True):
                st.caption(row["指标"])
                st.metric("达标率", row["指标值"])
                st.caption(f'考核 {row["考核期间总记录数"]:,} 条 · 不达标 {row["考核不达标记录数"]:,} 条')
    st.dataframe(
        summary, hide_index=True, use_container_width=True,
        column_config={
            "指标": st.column_config.TextColumn("指标", width="medium"),
            "考核期间总记录数": st.column_config.NumberColumn("考核期间总记录数", format="%d"),
            "考核不达标记录数": st.column_config.NumberColumn("考核不达标记录数", format="%d"),
            "供应商无责记录数": st.column_config.NumberColumn("供应商无责记录数", format="%d"),
            "指标值": st.column_config.TextColumn("指标值（达标率）", width="medium"),
        })
    with st.expander("查看考核规则与计算公式"):
        st.markdown("**达标率 = 1 −（不达标记录数 − 供应商无责记录数）÷ 考核期间总记录数**")
        st.caption("港后提柜：超LFD天数 > 0；送仓准时率：送仓时效 > 时效标准；其他时效指标按各自实际时效与标准时效比较。供应商无责仅计入不达标且运营判责为「车队无责」的记录。")
    for warning in dict.fromkeys(warnings):
        st.warning(warning)
    st.markdown("### 考核明细核对")
    tabs = st.tabs(SHEETS)
    for tab, metric in zip(tabs, SHEETS):
        with tab:
            total = int(summary.loc[
                summary["指标"].eq(metric), "考核期间总记录数"].iloc[0])
            if is_neon():
                # Retrieve only the selected month/supplier/region/metric,
                # but return every matching detail row without pagination.
                with connect() as conn:
                    part = neon_kpi.all_details(
                        conn, selected, metric, supplier_value, region_value)
            else:
                part = visible_raw[visible_raw["metric"].eq(metric)]
            records = [json.loads(v) if isinstance(v, str) else v
                       for v in part["payload"]]
            detail = pd.DataFrame(records)
            detail.insert(0, "序列号", range(1, len(detail) + 1))
            detail.insert(1, "Excel原始行号", part["source_row"].tolist())
            st.caption(f"匹配 {total:,} 条｜显示全部 {len(detail):,} 条")
            st.dataframe(detail, hide_index=True, use_container_width=True, height=540)
            st.download_button(
                "导出全部明细 CSV",
                detail.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"{selected}_{metric}_美国筛选全部明细.csv",
                mime="text/csv", key=f"kpi_global_export_{metric}")
    st.caption("当前数据后端：" + ("Neon PostgreSQL（云端持久化）" if is_neon() else "SQLite（本地临时存储）"))
