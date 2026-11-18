import os
import sqlite3
from db_backend import connect as db_connect, read_sql, is_neon
import tempfile
from datetime import date, timedelta

import pandas as pd
import streamlit as st
from import_data import DB, load
from container_detail import show_container_detail
from supplier_overview import show_supplier_overview
from kpi_overview import show_kpi_overview
from monthly_kpi import show_monthly_kpi
from monthly_supplier_entry import show_monthly_supplier_entry
from global_overview import show_global_overview, is_us_country
from theme import apply_theme
from auth import login_gate, manage_users, change_own_password
from database_backup import show_database_backup
from database_status import show_database_status
from intelligent_operations import show_intelligent_lfd, show_ai_fee_review, show_supplier_capacity

st.set_page_config(page_title="司顺国际物流港后运营工作台", page_icon="🚢", layout="wide")
apply_theme()
st.markdown("""<div class="vevor-topbar">
  <div class="vevor-logo">VEVOR®</div>
  <div class="vevor-divider"></div>
  <div class="vevor-title">国际物流港后运营工作台 <span style="font-weight:500">|</span> 全球港后运营管理</div>
  <div class="vevor-tag">数据驱动 · 异常预警 · 高效提柜</div>
</div><div class="vevor-subtitle">全球国家业务分析 + 美国六大区域运营 · 仅按港后拖车行统计 · 数据非实时码头状态</div>""",unsafe_allow_html=True)

@st.cache_data(show_spinner=False, ttl=60)
def read_db(mtime):
    with db_connect(DB) as conn:
        return read_sql("SELECT * FROM containers", conn)

def region(value):
    s = str(value).lower()
    mappings = {
        "新泽西 NJ": ["新泽西", "new jersey", "-nj", "nj-"],
        "洛杉矶 LA/LB": ["洛杉矶", "美西ca", "los angeles", "long beach"],
        "休斯顿 HOU": ["休斯顿", "houston", "德州", "texas"],
        "芝加哥 CHI": ["芝加哥", "chicago", "伊利诺伊"],
        "亚特兰大 ATL": ["亚特兰大", "atlanta", "佐治亚"],
        "萨凡纳 SAV": ["萨凡纳", "savannah"],
    }
    return next((name for name, keys in mappings.items() if any(k in s for k in keys)), "其他区域")

def grid(data, key="default"):
    columns = ["排柜单号", "箱号", "柜号显示", "区域", "目的仓", "船公司", "实际船名", "实际航次",
               "ETA日期", "ATA日期", "港后拖车行", "LFD", "进口实际提箱时间", "预计还柜时间",
               "实际送仓时间", "实际还柜日期", "风险"]
    # Some pages pass raw database rows without the derived display column.
    # Build it locally so every report can reuse this detail table safely.
    data = data.copy()
    if "柜号显示" not in data.columns:
        container_no = data["箱号"] if "箱号" in data.columns else pd.Series("", index=data.index)
        order_no = data["排柜单号"] if "排柜单号" in data.columns else pd.Series("", index=data.index)
        data["柜号显示"] = container_no.replace("", pd.NA).fillna(order_no)
    for field in columns:
        if field not in data.columns:
            data[field] = ""
    visible = data[columns].rename(columns={"柜号显示": "显示柜号", "LFD": "提柜LFD", "预计还柜时间": "还柜LFD"})
    st.dataframe(visible, hide_index=True, use_container_width=True, height=450)
    st.download_button("导出当前结果 CSV",
                       visible.to_csv(index=False).encode("utf-8-sig"),
                       file_name="港后货柜查询.csv", mime="text/csv",
                       key=f"download_csv_{key}")

user = login_gate()

with st.sidebar:
    st.markdown('<div class="vevor-sidebar-logo">VEVOR®<span>全球港后运营管理</span></div>', unsafe_allow_html=True)
    st.caption(f'当前用户：{user["username"]} · {user["role"]}')
    pages = ["运营总览", "全球港后运营总览", "全美港后供应商总览", "货柜查询", "货柜详情", "LFD预警", "拖车商分析", "港后供应商KPI考核"]
    pages += ["🧠 智能运营中心｜LFD预警与催办", "🧠 智能运营中心｜AI异常费用审核", "🧠 智能运营中心｜供应商绩效与产能"]
    if user["role"] == "管理员":
        pages.append("数据管理")
        pages.append("数据库连接状态")
        pages.append("业务主键质量检查")
    if user["role"] == "管理员":
        pages.append("用户管理")
        pages.append("数据库备份中心")
    pages.append("我的账号")
    page = st.radio("业务模块", pages)
    if st.button("退出登录", key="logout_user"):
        st.session_state.pop("auth_username", None)
        st.session_state.pop("sqlite_backup_zip", None)
        st.session_state.pop("sqlite_backup_filename", None)
        st.rerun()
    st.caption("统计业务主键：排柜单号；供应商仅使用港后拖车行。")

if page == "数据库连接状态":
    show_database_status(user, DB)
    st.stop()

if page == "数据库备份中心":
    if is_neon():
        st.info("当前使用 Neon PostgreSQL。此页面仅支持 SQLite 快照备份；请使用 Neon 的备份或导出功能。")
    else:
        show_database_backup(user)
    st.stop()

if page == "用户管理":
    manage_users(user)
    st.stop()

if page == "我的账号":
    change_own_password(user)
    st.stop()

# Allow first-time cloud imports before attempting to read the database.
if page == "业务主键质量检查":
    if user["role"] != "管理员":
        st.error("仅管理员可查看数据质量检查。")
        st.stop()
    if not is_neon() and not os.path.exists(DB):
        st.info("尚无业务数据。")
        st.stop()
    raw = read_db("neon" if is_neon() else os.path.getmtime(DB))
    keys = raw["排柜单号"].fillna("").astype(str).str.strip()
    missing = keys.eq("")
    duplicated = keys.ne("") & keys.duplicated(keep=False)
    st.title("🔎 业务主键质量检查")
    st.caption("排柜单号是唯一业务标识；箱号允许重复。检查现有数据库，不修改原始记录。")
    a, b, c, d = st.columns(4)
    a.metric("原始记录行数", f"{len(raw):,}")
    b.metric("唯一有效排柜单号", f"{keys[keys.ne('')].nunique():,}")
    c.metric("排柜单号为空", f"{int(missing.sum()):,}")
    d.metric("涉及重复排柜单号的行数", f"{int(duplicated.sum()):,}")
    bad = raw.loc[missing | duplicated].copy()
    bad.insert(0, "异常类型", ["排柜单号为空" if v else "排柜单号重复"
                              for v in missing.loc[bad.index]])
    if bad.empty:
        st.success("当前数据库的排柜单号完整且唯一。")
    else:
        st.warning("存在业务主键异常。统计看板会按排柜单号只计一次，重复业务保留原始记录供核实。"
                   "同一排柜单号多行信息不一致时，暂按原始记录中最后一行展示，需核对后重新导入。")
        st.dataframe(bad, hide_index=True, use_container_width=True)
        st.download_button("导出异常记录 CSV", bad.to_csv(index=False).encode("utf-8-sig"),
                           file_name="排柜单号异常记录.csv", mime="text/csv", key="key_quality_export")
    box = raw["箱号"].fillna("").astype(str).str.strip()
    repeated_boxes = box.ne("") & box.duplicated(keep=False)
    st.caption(f"重复箱号涉及 {int(repeated_boxes.sum()):,} 行（允许，不作为业务主键异常）。")
    st.stop()

if page == "数据管理":
    if user["role"] != "管理员":
        st.error("权限不足：仅管理员可访问数据管理及上传业务数据。")
        st.stop()
    st.subheader("业务数据管理")
    st.caption("Neon 模式下上传将更新云端 PostgreSQL；SQLite 模式下仍使用实例本地文件。")
    if not is_neon() and not os.path.exists(DB):
        st.info("尚未导入业务数据。请先上传源文件。")
    else:
        with db_connect(DB) as conn:
            st.metric("当前数据库记录数", conn.execute("SELECT COUNT(*) FROM containers").fetchone()[0])
    uploaded = st.file_uploader("上传 HTML 表格导出格式的 .xls / .html 文件", type=["xls", "html", "htm"])
    if uploaded is not None and st.button("确认导入并替换当前数据库", type="primary"):
        with tempfile.NamedTemporaryFile(suffix=".xls", delete=False) as tmp:
            tmp.write(uploaded.getbuffer())
            path = tmp.name
        try:
            with st.spinner("正在导入并校验数据..."):
                load(path)
                read_db.clear()
            st.success("导入成功，报表已可使用。请在左侧切换到运营总览。")
            st.rerun()
        except Exception as exc:
            st.error(f"导入失败，原有数据库未被替换：{exc}")
        finally:
            os.unlink(path)
    st.stop()

if not is_neon() and not os.path.exists(DB):
    st.warning("云端尚无业务数据库。请联系管理员在「数据管理」上传全球完整源文件。")
    st.stop()

df = read_db("neon" if is_neon() else os.path.getmtime(DB))
# All reporting uses 排柜单号 as the business key; 箱号 is allowed to repeat.
order_keys = df["排柜单号"].fillna("").astype(str).str.strip()
valid_orders = order_keys.ne("")
duplicate_orders = valid_orders & order_keys.duplicated(keep=False)
if (~valid_orders).any() or duplicate_orders.any():
    st.warning(f"业务主键质量提示：排柜单号为空 {int((~valid_orders).sum()):,} 行，"
               f"重复排柜单号涉及 {int(duplicate_orders.sum()):,} 行。"
               "统计按排柜单号去重；空主键记录不计入业务量。管理员可在「业务主键质量检查」查看明细。")
df = df.loc[valid_orders].copy()
df["排柜单号"] = order_keys.loc[df.index]
df = df.drop_duplicates(subset=["排柜单号"], keep="last").copy()
df["区域"] = df["目的仓物流区域"].fillna("").map(region)
for col in ["ETA日期", "ATA日期", "LFD", "进口实际提箱时间", "实际送仓时间", "实际还柜日期"]:
    df[col + "_dt"] = pd.to_datetime(df[col], errors="coerce", format="mixed")
if page == "全球港后运营总览":
    show_global_overview(df)
    st.stop()

# Existing US operations pages must not include newly imported non-US records.
df = df[df["目的仓国家"].map(is_us_country)].copy()

with st.sidebar:
    regions = sorted(df["区域"].unique())
    selected = st.multiselect("运营区域", regions, default=regions)
    carriers = sorted(df["港后拖车行"].dropna().astype(str).loc[lambda s: s.str.strip().ne("")].unique())
    carrier = st.selectbox("港后拖车商", ["全部"] + carriers)
    eta_range = st.date_input("ETA范围", value=(date.today()-timedelta(days=30), date.today()+timedelta(days=60)))

q = df[df["区域"].isin(selected)].copy()
if carrier != "全部":
    q = q[q["港后拖车行"] == carrier]
if len(eta_range) == 2:
    q = q[q["ETA日期_dt"].between(pd.Timestamp(eta_range[0]),
        pd.Timestamp(eta_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))]

today = pd.Timestamp(date.today())
lfd, pickup = q["LFD_dt"], q["进口实际提箱时间_dt"]
q["风险"] = "正常/待核实"
q.loc[lfd.isna(), "风险"] = "缺少LFD"
q.loc[lfd.notna() & pickup.isna() & (lfd < today), "风险"] = "LFD已过/提箱待核实"
q.loc[lfd.notna() & pickup.isna() & (lfd >= today) & (lfd < today + pd.Timedelta(days=3)), "风险"] = "LFD 3天内"
q.loc[lfd.notna() & pickup.notna() & (pickup.dt.normalize() > lfd.dt.normalize()), "风险"] = "提箱晚于LFD"
q.loc[lfd.notna() & pickup.notna() & (pickup.dt.normalize() <= lfd.dt.normalize()), "风险"] = "已按LFD提箱"
q["柜号显示"] = q["箱号"].replace("", pd.NA).fillna(q["排柜单号"])

if page == "🧠 智能运营中心｜LFD预警与催办":
    show_intelligent_lfd(df)
elif page == "🧠 智能运营中心｜AI异常费用审核":
    show_ai_fee_review(df)
elif page == "🧠 智能运营中心｜供应商绩效与产能":
    show_supplier_capacity(df)
elif page == "港后供应商KPI考核":
    show_monthly_supplier_entry(df, user)
elif page == "全美港后供应商总览":
    show_supplier_overview(df, grid)
elif page == "运营总览":
    names = [None, "新泽西 NJ", "萨凡纳 SAV", "洛杉矶 LA/LB", "休斯顿 HOU", "芝加哥 CHI", "亚特兰大 ATL"]
    tabs = st.tabs(["🇺🇸 全美总览", "🗽 新泽西 NJ", "🚢 萨凡纳 SAV", "⚓ 洛杉矶 LA/LB",
                    "🚛 休斯顿 HOU", "🚆 芝加哥 CHI", "🏭 亚特兰大 ATL"])
    for i, (tab, name) in enumerate(zip(tabs, names)):
        with tab:
            z = q if name is None else q[q["区域"] == name]
            st.subheader(name or "美国港后运营总览")
            if len(eta_range) == 2:
                st.markdown(
                    f'<div style="display:inline-flex;align-items:center;gap:9px;'
                    f'background:#e8f2ff;border:1px solid #bdd5fa;border-left:4px solid #ff5a19;'
                    f'border-radius:8px;padding:7px 13px;margin:0 0 12px 0;'
                    f'color:#09275d;font-weight:700;font-size:.91rem">'
                    f'📅 ETA 统计窗口：{eta_range[0]:%Y/%m/%d} — {eta_range[1]:%Y/%m/%d}'
                    f' <span style="font-weight:400;color:#4b6a9b">｜按预计到港日期统计 · 随左侧筛选同步更新</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.caption("ETA 统计窗口：请选择完整的开始和结束日期")
            arrived = z["ATA日期_dt"].notna()
            picked = z["进口实际提箱时间_dt"].notna()
            delivered = z["实际送仓时间_dt"].notna()
            returned = z["实际还柜日期_dt"].notna()
            metric_masks = [
                ("货柜记录", pd.Series(True, index=z.index)),
                ("已到港", arrived),
                ("LFD已过待核实", z["风险"].eq("LFD已过/提箱待核实")),
                ("已提柜", picked),
                ("已送仓", delivered),
                ("已还空", returned),
                ("LFD三天内", z["风险"].eq("LFD 3天内")),
                ("到港未记录提柜", arrived & ~picked),
            ]
            selected_metric_key = f"overview_selected_metric_{i}"
            for metric_idx, (col, (label, mask)) in enumerate(zip(st.columns(8), metric_masks)):
                count = int(mask.sum())
                with col:
                    st.caption(label)
                    if st.button(f"{count:,}", key=f"overview_metric_{i}_{metric_idx}",
                                 help=f"点击查看「{label}」的 {count:,} 条货柜记录",
                                 disabled=count == 0):
                        st.session_state[selected_metric_key] = (
                            None if st.session_state.get(selected_metric_key) == metric_idx else metric_idx
                        )
            selected_metric = st.session_state.get(selected_metric_key)
            if selected_metric is not None and 0 <= selected_metric < len(metric_masks):
                detail_label, detail_mask = metric_masks[selected_metric]
                detail_rows = z.loc[detail_mask].copy()
                with st.container(border=True):
                    header_col, close_col = st.columns([5, 1])
                    header_col.markdown(f"#### 📋 {detail_label} · {len(detail_rows):,} 柜")
                    if close_col.button("收起明细", key=f"overview_metric_close_{i}"):
                        st.session_state[selected_metric_key] = None
                        st.rerun()
                    st.caption("明细受当前区域、拖车商及 ETA 范围筛选影响；缺少提柜记录不代表确认未提柜。")
                    grid(detail_rows, key=f"metric_detail_{i}_{selected_metric}")

            st.markdown("### 🚨 区域港后供应商 LFD 预警统计")
            with st.container(border=True):
                st.caption("按当前区域及 ETA 范围统计；仅使用「港后拖车行」字段。"
                           "预警分为已过待核实、三天内到期、提箱晚于LFD；缺少提箱记录不等于确认未提箱。")
                alert_data = z.copy()
                alert_data["港后供应商"] = alert_data["港后拖车行"].fillna("").astype(str).str.strip()
                alert_data.loc[alert_data["港后供应商"].isin(
                    ["", "nan", "None", "港后拖车测试"]), "港后供应商"] = "待分配/未记录"
                alert_types = ["LFD已过/提箱待核实", "LFD 3天内", "提箱晚于LFD"]
                alert_data["是否LFD预警"] = alert_data["风险"].isin(alert_types)
                if alert_data.empty:
                    st.info("当前区域及筛选条件下没有货柜记录。")
                else:
                    vendor_totals = alert_data.groupby("港后供应商").size().rename("区域内供应商总柜量")
                    vendor_alerts = (pd.crosstab(alert_data["港后供应商"], alert_data["风险"])
                                     .reindex(index=vendor_totals.index, columns=alert_types, fill_value=0))
                    vendor_alerts = vendor_alerts.rename(columns={
                        "LFD已过/提箱待核实": "LFD已过待核实",
                        "LFD 3天内": "LFD三天内",
                        "提箱晚于LFD": "提箱晚于LFD"})
                    vendor_alerts.insert(0, "区域内供应商总柜量", vendor_totals)
                    vendor_alerts["预警合计"] = vendor_alerts[
                        ["LFD已过待核实", "LFD三天内", "提箱晚于LFD"]].sum(axis=1)
                    vendor_alerts["预警占比(%)"] = (
                        vendor_alerts["预警合计"] / vendor_alerts["区域内供应商总柜量"] * 100
                    ).round(1)
                    vendor_alerts = vendor_alerts.sort_values(
                        ["预警合计", "区域内供应商总柜量"], ascending=False).reset_index()
                    st.dataframe(vendor_alerts, hide_index=True, use_container_width=True)
                    st.download_button("导出该区域供应商LFD预警汇总 CSV",
                        vendor_alerts.to_csv(index=False).encode("utf-8-sig"),
                        file_name=f"港后供应商LFD预警_{i}.csv", mime="text/csv",
                        key=f"overview_vendor_lfd_export_{i}")
                    warning_rows = alert_data[alert_data["是否LFD预警"]]
                    if not warning_rows.empty:
                        st.markdown("##### 各供应商 LFD 预警柜量")
                        plot = vendor_alerts.set_index("港后供应商")[
                            ["LFD已过待核实", "LFD三天内", "提箱晚于LFD"]]
                        st.bar_chart(plot, horizontal=True,
                                     height=max(260, min(650, len(plot) * 32)))
                        with st.expander("🔎 按供应商查看 LFD 预警货柜明细", expanded=False):
                            suppliers = vendor_alerts.loc[
                                vendor_alerts["预警合计"] > 0, "港后供应商"].tolist()
                            selected_vendor = st.selectbox("港后拖车商", ["全部供应商"] + suppliers,
                                key=f"overview_vendor_lfd_select_{i}")
                            selected_type = st.selectbox("LFD预警类型", ["全部类型"] + alert_types,
                                key=f"overview_vendor_lfd_type_{i}")
                            details = warning_rows
                            if selected_vendor != "全部供应商":
                                details = details[details["港后供应商"].eq(selected_vendor)]
                            if selected_type != "全部类型":
                                details = details[details["风险"].eq(selected_type)]
                            details = details.sort_values("LFD_dt", na_position="last")
                            st.caption(f"符合条件 {len(details):,} 柜")
                            grid(details, key=f"overview_vendor_lfd_detail_{i}")
                    if carrier != "全部":
                        st.caption("左侧已筛选单个港后拖车商；切换为「全部」可比较该区域所有供应商。")

            st.markdown("### 📊 区域业务与拖车商分配")
            chart_left, chart_right = st.columns([1, 1], gap="large")
            with chart_left:
                with st.container(border=True):
                    st.markdown("#### 各区域总业务柜量")
                    st.caption("单位：柜 · 当前筛选范围")
                    volume = z["区域"].value_counts().sort_values(ascending=True)
                    if volume.empty:
                        st.info("当前范围内暂无货柜记录")
                    else:
                        st.bar_chart(volume, horizontal=True, height=350,
                                     x_label="柜量", y_label="运营区域")
            with chart_right:
                with st.container(border=True):
                    st.markdown("#### 各区域港后拖车商占比")
                    st.caption("100% 堆叠 · 按港后拖车行统计（含未分配）")
                    share_data = z[["区域", "港后拖车行"]].copy()
                    share_data["港后拖车行"] = share_data["港后拖车行"].fillna("").astype(str).str.strip()
                    share_data.loc[share_data["港后拖车行"].eq(""), "港后拖车行"] = "未分配/未记录"
                    counts = pd.crosstab(share_data["区域"], share_data["港后拖车行"])
                    if counts.empty:
                        st.info("当前范围内暂无货柜记录")
                    else:
                        shares = counts.div(counts.sum(axis=1), axis=0).mul(100).round(2)
                        chart_rows = (counts.stack().rename("柜量").to_frame()
                                      .join(shares.stack().rename("占比"))
                                      .reset_index().rename(columns={"港后拖车行": "港后拖车商"}))
                        chart_rows["区域总柜量"] = chart_rows.groupby("区域")["柜量"].transform("sum")
                        chart_rows["图上标签"] = chart_rows.apply(
                            lambda row: f'{int(row["柜量"]):,}柜 · {row["占比"]:.1f}%',
                            axis=1)
                        base_encoding = {
                            "y": {"field": "区域", "type": "nominal", "title": "运营区域",
                                  "sort": list(counts.index)},
                            "x": {"field": "占比", "type": "quantitative", "stack": "zero",
                                  "title": "占比 (%)", "scale": {"domain": [0, 100]}},
                            "color": {"field": "港后拖车商", "type": "nominal",
                                      "legend": {"orient": "bottom", "title": "港后拖车商"}},
                            "order": {"field": "港后拖车商", "type": "nominal"},
                            "tooltip": [
                                {"field": "区域", "type": "nominal"},
                                {"field": "港后拖车商", "type": "nominal"},
                                {"field": "柜量", "type": "quantitative", "format": ","},
                                {"field": "占比", "type": "quantitative", "format": ".2f", "title": "占比 (%)"},
                                {"field": "区域总柜量", "type": "quantitative", "format": ","},
                            ],
                        }
                        st.vega_lite_chart({
                            "data": {"values": chart_rows.to_dict("records")},
                            "height": 290,
                            "layer": [
                                {"mark": {"type": "bar", "cornerRadiusEnd": 2},
                                 "encoding": base_encoding},
                                {"transform": [{"filter": "datum['占比'] >= 13"}],
                                 "mark": {"type": "text", "color": "white", "fontSize": 10,
                                          "fontWeight": "bold", "baseline": "middle"},
                                 "encoding": {
                                     "y": base_encoding["y"],
                                     "x": base_encoding["x"],
                                     "detail": {"field": "港后拖车商", "type": "nominal"},
                                     "order": base_encoding["order"],
                                     "text": {"field": "图上标签", "type": "nominal"},
                                 }},
                            ],
                            "view": {"stroke": None},
                        }, use_container_width=True, key=f"overview_supplier_share_{i}")
                        st.caption("色块显示柜量与占比；占比不足13%的色块请悬停查看，避免标签重叠。")
                        if carrier != "全部":
                            st.caption("当前已筛选单个拖车商；选择左侧「全部」查看完整供应商占比。")
            if not z.empty:
                with st.expander("🔎 区域柜量及港后拖车商占比 · 条件查询", expanded=True):
                    st.caption("在当前 ETA、区域和拖车商全局筛选范围内进一步查询；占比以所选区域的全部货柜为分母。")
                    query_data = z[["区域", "港后拖车行"]].copy()
                    query_data["港后拖车商"] = query_data["港后拖车行"].fillna("").astype(str).str.strip()
                    query_data.loc[query_data["港后拖车商"].eq(""), "港后拖车商"] = "未分配/未记录"
                    query_regions = sorted(query_data["区域"].dropna().unique().tolist())
                    qc1, qc2, qc3 = st.columns([1, 1.3, 1], gap="medium")
                    with qc1:
                        query_region = st.selectbox("运营区域", ["全部区域"] + query_regions,
                                                    key=f"overview_query_region_{i}")
                    region_scope = query_data if query_region == "全部区域" else query_data[
                        query_data["区域"].eq(query_region)]
                    query_vendors = sorted(region_scope["港后拖车商"].unique().tolist())
                    with qc2:
                        query_vendor = st.selectbox("港后拖车商", ["全部拖车商"] + query_vendors,
                                                    key=f"overview_query_vendor_{i}")
                    with qc3:
                        query_view = st.selectbox("统计视图", ["供应商占比明细", "区域汇总", "货柜记录"],
                                                  key=f"overview_query_view_{i}")
                    query_filtered = region_scope if query_vendor == "全部拖车商" else region_scope[
                        region_scope["港后拖车商"].eq(query_vendor)]
                    # Denominators stay based on the entire region after the global filters,
                    # so choosing one vendor does not incorrectly inflate its share to 100%.
                    region_totals = query_data.groupby("区域").size().rename("区域总柜量")
                    detail_counts = (query_filtered.groupby(["区域", "港后拖车商"])
                                     .size().rename("供应商柜量").reset_index())
                    detail_counts = detail_counts.merge(region_totals.reset_index(), on="区域", how="left")
                    detail_counts["占比 (%)"] = (
                        detail_counts["供应商柜量"].div(detail_counts["区域总柜量"]).mul(100).round(2))
                    detail_counts = detail_counts.sort_values(
                        ["区域", "供应商柜量"], ascending=[True, False])
                    st.caption(f"当前匹配 {len(query_filtered):,} 柜 · "
                               f"区域基数 {len(region_scope):,} 柜")
                    if query_view == "供应商占比明细":
                        st.dataframe(detail_counts, hide_index=True, use_container_width=True)
                        result_csv = detail_counts.to_csv(index=False).encode("utf-8-sig")
                    elif query_view == "区域汇总":
                        region_summary = (query_filtered.groupby("区域").size().rename("匹配柜量")
                                          .reset_index().merge(region_totals.reset_index(), on="区域"))
                        region_summary["占比 (%)"] = (
                            region_summary["匹配柜量"].div(region_summary["区域总柜量"]).mul(100).round(2))
                        st.dataframe(region_summary, hide_index=True, use_container_width=True)
                        result_csv = region_summary.to_csv(index=False).encode("utf-8-sig")
                    else:
                        matched_rows = z.loc[query_filtered.index].copy()
                        grid(matched_rows, key=f"overview_query_containers_{i}")
                        result_csv = None
                    if result_csv is not None:
                        st.download_button("导出当前查询结果 CSV", result_csv,
                                           file_name="区域港后拖车商占比查询.csv",
                                           mime="text/csv", key=f"overview_query_export_{i}")

            st.markdown("### 🚢 近期船舶与到港计划")
            with st.container(border=True):
                ships = z.copy()
                ships["船舶/航次"] = (
                    ships["实际船名"].fillna("").astype(str).str.strip().replace("", "未记录")
                    + " / " +
                    ships["实际航次"].fillna("").astype(str).str.strip().replace("", "未记录"))
                ships["卸货港"] = ships["卸货港"].fillna("").astype(str).str.strip().replace("", "未记录")
                terminal_candidates = ["卸货码头", "目的港码头", "码头", "Terminal"]
                ships["停靠码头"] = pd.Series(pd.NA, index=ships.index, dtype="string")
                for terminal_col in terminal_candidates:
                    if terminal_col in ships.columns:
                        candidate = ships[terminal_col].astype("string").str.strip().replace("", pd.NA)
                        ships["停靠码头"] = ships["停靠码头"].fillna(candidate)
                ships["停靠码头"] = ships["停靠码头"].fillna("未记录")
                ships["预计到港 ETA"] = ships["ETA日期_dt"].dt.strftime("%Y-%m-%d").fillna("未记录")
                ships["实际到港 ATA"] = ships["ATA日期_dt"].dt.strftime("%Y-%m-%d").fillna("未记录")
                discharge_dt = pd.to_datetime(
                    ships["目的港/站卸柜日期"], errors="coerce", format="mixed")
                ships["卸柜日期"] = discharge_dt.dt.strftime("%Y-%m-%d").fillna("未记录")
                ships["船公司"] = ships["船公司"].fillna("").astype(str).str.strip().replace("", "未记录")
                summary = (
                    ships.groupby(["船公司", "船舶/航次", "卸货港", "停靠码头",
                                   "预计到港 ETA", "实际到港 ATA", "卸柜日期"],
                                  dropna=False)
                    .size().reset_index(name="柜量"))
                summary["_sort_eta"] = pd.to_datetime(summary["预计到港 ETA"], errors="coerce")
                summary = summary.sort_values(
                    ["_sort_eta", "船公司", "船舶/航次"], ascending=[True, True, True],
                    na_position="last").drop(columns="_sort_eta")
                st.caption(f"共 {len(summary):,} 条船舶靠港计划记录，涉及 {len(ships):,} 柜；"
                           "按卸货港和码头区分，ETA 从早到晚排列。")
                if ships["停靠码头"].eq("未记录").all():
                    st.info("当前数据库尚无停靠码头信息。已显示卸货港；如源文件包含码头字段，"
                            "请在数据管理重新上传，以便补充码头信息。")
                st.dataframe(summary, hide_index=True, use_container_width=True, height=420)
                st.download_button(
                    "导出船舶靠港计划 CSV",
                    summary.to_csv(index=False).encode("utf-8-sig"),
                    file_name="美国港后船舶靠港计划.csv",
                    mime="text/csv", key=f"ship_schedule_export_{i}")
            st.subheader("重点货柜明细")
            choices = st.multiselect("风险筛选", ["LFD已过/提箱待核实", "LFD 3天内", "提箱晚于LFD", "缺少LFD"],
                                    default=["LFD已过/提箱待核实", "LFD 3天内", "提箱晚于LFD"],
                                    key=f"overview_filter_{i}")
            focused = z[z["风险"].isin(choices)].sort_values("LFD_dt", na_position="last")
            st.caption(f"匹配 {len(focused):,} 条；缺少提柜记录不等于确认未提柜。")
            grid(focused.head(1000), key=f"overview_{i}")
elif page == "货柜详情":
    show_container_detail(q)
elif page == "货柜查询":
    term = st.text_input("搜索柜号 / 提单号 / 船名 / 排柜单号")
    if term:
        q = q[q[["箱号", "MB/L No.", "实际船名", "排柜单号"]].fillna("").astype(str)
              .apply(lambda s: s.str.contains(term, case=False, regex=False)).any(axis=1)]
    st.caption(f"符合条件 {len(q):,} 条")
    grid(q, key="container_search")
elif page == "LFD预警":
    st.title("🚨 全美 LFD 风险监控中心")
    st.caption("统计基于已上传业务数据，不代表实时码头状态；区域、港后供应商及 ETA 范围受左侧筛选控制。")
    st.info("「已过LFD待核实」表示 LFD 已过且尚无实际提箱时间记录，需人工确认；"
            "「历史超期提箱」表示记录的实际提箱日期晚于 LFD。两者分别统计，不重复计算。")
    alert = q.copy()
    alert["港后供应商"] = alert["港后拖车行"].fillna("").astype(str).str.strip()
    alert.loc[alert["港后供应商"].isin(["", "nan", "None"]), "港后供应商"] = "未分配/未记录"
    alert["超期天数"] = (today - alert["LFD_dt"].dt.normalize()).dt.days
    alert["历史提箱超期天数"] = (
        alert["进口实际提箱时间_dt"].dt.normalize() - alert["LFD_dt"].dt.normalize()
    ).dt.days
    active_overdue = alert["风险"].eq("LFD已过/提箱待核实")
    approaching = alert["风险"].eq("LFD 3天内")
    historical = alert["风险"].eq("提箱晚于LFD")
    no_lfd = alert["风险"].eq("缺少LFD")
    kpi_items = [
        ("已过LFD待核实", int(active_overdue.sum())),
        ("超期≥3天待核实", int((active_overdue & alert["超期天数"].ge(3)).sum())),
        ("LFD三天内", int(approaching.sum())),
        ("历史超期提箱", int(historical.sum())),
        ("缺少LFD", int(no_lfd.sum())),
    ]
    for col, (label, count) in zip(st.columns(5), kpi_items):
        col.metric(label, f"{count:,}")
    st.markdown("### 🗺️ 各区域 LFD 风险排名")
    region_totals = alert.groupby("区域").size().rename("总柜量")
    region_risks = pd.DataFrame(index=region_totals.index)
    region_risks["总柜量"] = region_totals
    for label, mask in [
        ("已过LFD待核实", active_overdue),
        ("超期≥3天", active_overdue & alert["超期天数"].ge(3)),
        ("超期≥7天", active_overdue & alert["超期天数"].ge(7)),
        ("LFD三天内", approaching),
        ("历史超期提箱", historical),
        ("缺少LFD", no_lfd),
    ]:
        region_risks[label] = alert.loc[mask].groupby("区域").size().reindex(
            region_risks.index, fill_value=0)
    region_risks["待核实超期占比(%)"] = (
        region_risks["已过LFD待核实"] / region_risks["总柜量"] * 100
    ).round(1)
    region_risks = region_risks.sort_values(
        ["已过LFD待核实", "超期≥7天"], ascending=False).reset_index()
    st.dataframe(region_risks, hide_index=True, use_container_width=True)
    if not region_risks.empty:
        st.bar_chart(region_risks.set_index("区域")[
            ["已过LFD待核实", "LFD三天内", "历史超期提箱"]],
            horizontal=True, height=max(280, len(region_risks) * 48))
    st.download_button("导出各区域LFD风险汇总 CSV",
        region_risks.to_csv(index=False).encode("utf-8-sig"),
        file_name="全美区域LFD风险汇总.csv", mime="text/csv", key="lfd_region_export")

    st.markdown("### 🔎 区域及港后供应商风险追踪")
    r1, r2, r3 = st.columns([1.1, 1.4, 1.3])
    with r1:
        selected_lfd_region = st.selectbox("查看区域",
            ["全部区域"] + region_risks["区域"].tolist(), key="lfd_region_focus")
    scope = alert if selected_lfd_region == "全部区域" else alert[
        alert["区域"].eq(selected_lfd_region)]
    with r2:
        selected_lfd_vendor = st.selectbox("港后拖车商",
            ["全部供应商"] + sorted(scope["港后供应商"].unique().tolist()),
            key="lfd_vendor_focus")
    with r3:
        selected_lfd_status = st.selectbox("风险类别", [
            "已过LFD待核实", "LFD三天内", "历史超期提箱", "缺少LFD", "全部风险"
        ], key="lfd_status_focus")
    vendor_summary = pd.DataFrame(index=scope.groupby("港后供应商").size().index)
    vendor_summary["总柜量"] = scope.groupby("港后供应商").size()
    for label, risk_name in [
        ("已过LFD待核实", "LFD已过/提箱待核实"),
        ("LFD三天内", "LFD 3天内"),
        ("历史超期提箱", "提箱晚于LFD"),
        ("缺少LFD", "缺少LFD"),
    ]:
        vendor_summary[label] = scope.loc[scope["风险"].eq(risk_name)].groupby(
            "港后供应商").size().reindex(vendor_summary.index, fill_value=0)
    vendor_summary["超期≥3天"] = scope.loc[
        scope["风险"].eq("LFD已过/提箱待核实") & scope["超期天数"].ge(3)
    ].groupby("港后供应商").size().reindex(vendor_summary.index, fill_value=0)
    vendor_summary = vendor_summary.sort_values(
        ["已过LFD待核实", "LFD三天内"], ascending=False).reset_index()
    if selected_lfd_vendor != "全部供应商":
        vendor_summary = vendor_summary[
            vendor_summary["港后供应商"].eq(selected_lfd_vendor)]
    st.markdown("#### 港后供应商 LFD 风险汇总")
    st.dataframe(vendor_summary, hide_index=True, use_container_width=True)
    st.download_button("导出港后供应商风险汇总 CSV",
        vendor_summary.to_csv(index=False).encode("utf-8-sig"),
        file_name="港后供应商LFD风险汇总.csv", mime="text/csv", key="lfd_vendor_export")

    status_mapping = {
        "已过LFD待核实": ["LFD已过/提箱待核实"],
        "LFD三天内": ["LFD 3天内"],
        "历史超期提箱": ["提箱晚于LFD"],
        "缺少LFD": ["缺少LFD"],
        "全部风险": ["LFD已过/提箱待核实", "LFD 3天内", "提箱晚于LFD", "缺少LFD"],
    }
    details = scope[scope["风险"].isin(status_mapping[selected_lfd_status])].copy()
    if selected_lfd_vendor != "全部供应商":
        details = details[details["港后供应商"].eq(selected_lfd_vendor)]
    if selected_lfd_status == "已过LFD待核实":
        age = st.selectbox("超期程度", ["全部", "1–2天", "3–6天", "7天及以上"],
                           key="lfd_age_filter")
        if age == "1–2天":
            details = details[details["超期天数"].between(1, 2)]
        elif age == "3–6天":
            details = details[details["超期天数"].between(3, 6)]
        elif age == "7天及以上":
            details = details[details["超期天数"].ge(7)]
    details = details.sort_values("LFD_dt", na_position="last")
    st.markdown(f"#### 📋 风险货柜明细 · {len(details):,} 柜")
    if not details.empty:
        view_cols = ["柜号显示", "区域", "目的仓", "港后拖车行", "船公司",
                     "ETA日期", "ATA日期", "LFD", "超期天数",
                     "历史提箱超期天数", "进口实际提箱时间", "风险"]
        st.dataframe(details[view_cols].rename(columns={
            "柜号显示": "箱号/排柜单号", "超期天数": "距LFD已过天数",
            "历史提箱超期天数": "历史提箱超期天数"
        }), hide_index=True, use_container_width=True, height=480)
    else:
        st.success("当前筛选条件下无匹配风险货柜。")
    st.download_button("导出当前风险货柜 CSV",
        details.to_csv(index=False).encode("utf-8-sig"),
        file_name="LFD风险货柜明细.csv", mime="text/csv", key="lfd_detail_export")
elif page == "拖车商分析":
    st.subheader("港后拖车商业务量")
    s = q[q["港后拖车行"].fillna("").astype(str).str.strip().ne("")]
    st.bar_chart(s["港后拖车行"].value_counts().head(25))
    st.dataframe(pd.crosstab(s["港后拖车行"], s["区域"]), use_container_width=True)
else:
    st.warning("上传将替换本地数据库，请先备份 port_ops.db。")
    uploaded = st.file_uploader("上传 HTML 导出格式 .xls", type=["xls", "html", "htm"])
    if uploaded and st.button("确认导入并重建数据库", type="primary"):
        with tempfile.NamedTemporaryFile(suffix=".xls", delete=False) as tmp:
            tmp.write(uploaded.getbuffer())
            path = tmp.name
        try:
            with st.spinner("正在导入..."):
                load(path)
                read_db.clear()
            st.success("导入完成，请刷新页面")
        finally:
            os.unlink(path)
    st.write("数据库记录数", len(df))
