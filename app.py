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
from auth import login_gate, manage_users, change_own_password, manage_roles, permitted_modules, is_admin
from database_backup import show_database_backup
from database_status import show_database_status
from drayage_suppliers import show_drayage_suppliers
from country_regions import show_country_regions
from global_ports_terminals import show_global_ports_terminals
from shipping_lines import show_shipping_lines
from customs_brokers import show_customs_brokers
from warehouses import show_warehouses
from drayage_master import show_drayage_master
from postport_do_assignment import show_do_assignment
from contract_rates import show_contract_rates
from logistics_ai import show_logistics_ai
from arrival_workbench import show_arrival_workbench
from intelligent_operations import show_intelligent_lfd, show_ai_fee_review, show_supplier_capacity

st.set_page_config(page_title="司顺国际物流港后运营工作台", page_icon="🚢", layout="wide")
apply_theme()

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
    st.markdown('<div class="vevor-sidebar-logo">VEVOR®</div>', unsafe_allow_html=True)
    st.caption(f'{user["username"]} · {user["role"]}')
    # Five business domains; labels are kept separate from legacy handlers.
    navigation = {
        "港后运营管理": [
            "港后运营工作台", "港口与铁路到站动态监控中心", "货柜详细信息查询", "物流AI助理", "港后拖车商DO分配", "港后LFD智能预警管理",
            "港后供应商产能与计划管理", "港后供应商绩效KPI管理",
        ],
        "港后拖车行结算管理": [
            "拖车行合同管理", "拖车行异常费用管理", "账期与费用结算管理",
        ],
        "企业主数据管理": [
            "全球国家与业务区域管理", "全球港口与码头管理",
            "船司管理", "清关行管理", "海外仓主数据管理", "拖车行主数据管理",
        ],
        "权限管理": ["角色管理", "用户管理"],
        "系统管理": ["系统数据备份", "业务数据导入管理", "数据库连接状态管理"],
    }
    allowed_modules = permitted_modules(user)
    visible_domains = [domain for domain in navigation if any(item in allowed_modules for item in navigation[domain])]
    # Tree navigation: expand/collapse first-level groups and click child pages.
    icons = {
        "港后运营管理": "01", "港后拖车行结算管理": "02",
        "企业主数据管理": "03", "权限管理": "04",
        "系统管理": "05",
    }
    available_modules = [item for group in visible_domains for item in navigation[group] if item in allowed_modules]
    if not available_modules:
        st.warning("当前角色尚未开放业务页面，请联系系统管理员授权。")
        st.stop()
    if st.session_state.get("gtms_active_module") not in available_modules:
        st.session_state["gtms_active_module"] = "港口与铁路到站动态监控中心" if "港口与铁路到站动态监控中心" in available_modules else available_modules[0]
    module = st.session_state["gtms_active_module"]
    for domain in visible_domains:
        with st.expander(
            f'{icons[domain]} {domain}',
            expanded=module in navigation[domain],
        ):
            for item in navigation[domain]:
                if item not in allowed_modules:
                    continue
                active = item == module
                if st.button(
                    f'{"▏ " if active else ""}{item}',
                    key=f"gtms_tree_{domain}_{item}",
                    use_container_width=True,
                    type="primary" if active else "secondary",
                ):
                    st.session_state["gtms_active_module"] = item
                    st.rerun()
    page_aliases = {
        "货柜详细信息查询": "货柜详情",
        "用户管理": "用户管理",
        "拖车行主数据管理": "港前港后拖车供应商管理",
        "港后LFD智能预警管理": "🧠 智能运营中心｜LFD预警与催办",
        "港后供应商产能与计划管理": "🧠 智能运营中心｜供应商绩效与产能",
        "港后供应商绩效KPI管理": "港后供应商KPI考核",
        "拖车行异常费用管理": "🧠 智能运营中心｜AI异常费用审核",
        "系统数据备份": "数据库备份中心",
        "业务数据导入管理": "数据管理",
        "数据库连接状态管理": "数据库连接状态",
    }
    page = page_aliases.get(module, module)
    if module == "港后运营工作台":
        # Preserve all existing reporting functions inside the operations workbench.
        workbench_views = {
            "运营总览": "运营总览",
            "全球港后运营总览": "全球港后运营总览",
            "全美港后供应商总览": "全美港后供应商总览",
            "货柜查询": "货柜查询",
            "货柜详情": "货柜详情",
            "LFD预警": "LFD预警",
            "拖车商分析": "拖车商分析",
            "港后供应商KPI考核": "港后供应商KPI考核",
        }
        view = st.selectbox("工作台视图", list(workbench_views), key="gtms_workbench_view")
        page = workbench_views[view]
    st.divider()
    if st.button("↪ 退出登录", key="logout_user", use_container_width=True):
        st.session_state.pop("auth_username", None)
        st.session_state.pop("gtms_active_module", None)
        st.session_state.pop("sqlite_backup_zip", None)
        st.session_state.pop("sqlite_backup_filename", None)
        st.rerun()

# Pages without a migrated backend are visible as planned modules, not fake data forms.
planned_modules = {

    "账期与费用结算管理": "待建设对账、账期和结算管理。",
}
if module not in allowed_modules:
    st.error("当前账号无权访问此模块。")
    st.stop()

if page == "全球国家与业务区域管理":
    show_country_regions(user, DB)
    st.stop()

if page == "全球港口与码头管理":
    show_global_ports_terminals(user, DB)
    st.stop()

if page == "拖车行主数据管理":
    show_drayage_master(user, DB)
    st.stop()

if page == "海外仓主数据管理":
    show_warehouses(user, DB)
    st.stop()

if page == "清关行管理":
    show_customs_brokers(user, DB)
    st.stop()

if page == "船司管理":
    show_shipping_lines(user, DB)
    st.stop()

if page == "角色管理":
    manage_roles(user)
    st.stop()

if page == "物流AI助理":
    show_logistics_ai(user, DB)
    st.stop()

if page == "拖车行合同管理":
    show_contract_rates(user, DB)
    st.stop()

if page in planned_modules:
    st.title(page)
    st.info(planned_modules[page])
    st.caption("当前为菜单占位页面，尚未接入数据库或启用编辑操作。")
    st.stop()

if page == "港前港后拖车供应商管理":
    show_drayage_suppliers(user)
    st.stop()

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
    if not is_admin(user):
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
    if not is_admin(user):
        st.error("权限不足：仅管理员可访问数据管理及上传业务数据。")
        st.stop()
    st.subheader("业务数据管理")
    st.warning("当前使用 SQLite：Streamlit Cloud 实例本地文件不保证持久保存，重启或重新部署后可能丢失。请定期从「系统数据备份」下载备份。")
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
    st.warning("当前 SQLite 尚无业务数据库。请管理员进入「业务数据导入管理」上传原始业务数据。")
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
if "目的港预计卸柜时间" not in df.columns:
    st.warning("当前数据库尚未保存目的港预计卸柜时间，请重新导入完整源表以启用 ETA 缺失补充。")
    df["目的港预计卸柜时间"] = ""
if "ETA（计算）" not in df and "ETA(计算)" not in df:
    st.warning("数据库尚未保存ETA（计算），请重新上传完整源表启用第三级日期兜底。")
df["统计日期_dt"] = df["ETA日期_dt"].fillna(pd.to_datetime(df["目的港预计卸柜时间"], errors="coerce", format="mixed")).fillna(pd.to_datetime(df.get("ETA（计算）", df.get("ETA(计算)", pd.Series("", index=df.index))), errors="coerce", format="mixed"))
# Shared sidebar filters for operational reports. Always use post-port supplier field.
# The date range is inclusive; missing/invalid ETA is excluded only when a range is enabled.
with st.sidebar:
    st.markdown('<div class="gtms-filter-title">运营数据筛选</div>', unsafe_allow_html=True)
    # Keep a global option, but default to all US destinations.
    us_mask = df["目的仓国家"].map(is_us_country)
    country_names = df["目的仓国家"].fillna("").astype(str).str.strip()
    global_regions = sorted(set(df["区域"].dropna().tolist()))
    # Non-US areas retain their country so different countries are not conflated.
    df["运营区域选项"] = df["区域"]
    non_us = ~us_mask
    df.loc[non_us, "运营区域选项"] = (
        country_names.loc[non_us].replace("", "国家未填写")
        + " / " + df.loc[non_us, "目的仓物流区域"].fillna("区域未填写").astype(str)
    )
    region_options = ["美国所有区域", "全球所有区域"] + sorted(
        set(df["运营区域选项"].dropna().tolist()) - {"美国所有区域", "全球所有区域"}
    )
    selected_region = st.selectbox("运营区域", region_options, key="gtms_filter_region")
    if selected_region == "美国所有区域":
        scope = df.loc[us_mask]
    elif selected_region == "全球所有区域":
        scope = df
    else:
        scope = df.loc[df["运营区域选项"].eq(selected_region)]
    supplier_options = sorted(
        v for v in scope["港后拖车行"].fillna("").astype(str).str.strip().unique()
        if v and v.casefold() not in ("nan", "none", "null")
    )
    supplier_choices = ["美国所有拖车商" if selected_region == "美国所有区域" else "全部拖车商"] + supplier_options
    if st.session_state.get("gtms_filter_supplier") not in supplier_choices:
        st.session_state["gtms_filter_supplier"] = supplier_choices[0]
    selected_supplier = st.selectbox("港后拖车商", supplier_choices, key="gtms_filter_supplier")
    eta_enabled = st.checkbox("启用 ETA 范围筛选", value=True, key="gtms_filter_eta_enabled")
    eta_range = None
    if eta_enabled:
        today_filter = date.today()
        start_default = today_filter - timedelta(days=14)
        end_default = today_filter + timedelta(days=14)
        eta_range = st.date_input("ETA范围（含起止日）", value=(start_default, end_default),
                                  key="gtms_filter_eta_range")
# Apply geographic scope first, then supplier and inclusive ETA.
df = scope.copy()
if selected_supplier not in ("美国所有拖车商", "全部拖车商"):
    df = df[df["港后拖车行"].fillna("").astype(str).str.strip().eq(selected_supplier)].copy()
if page == "港口与铁路到站动态监控中心":
    show_arrival_workbench(df, eta_range=eta_range, eta_enabled=eta_enabled)
    st.stop()
if eta_enabled:
    if eta_range is not None and len(eta_range) == 2:
        start_eta, end_eta = eta_range
        df = df[df["统计日期_dt"].dt.date.between(start_eta, end_eta)].copy()
    else:
        st.info("请选择完整的 ETA 起止日期。")
        st.stop()
st.caption(f"当前记录：{len(df):,} 柜")

if page == "港后拖车商DO分配":
    show_do_assignment(user, DB, df)
    st.stop()

if page == "全球港后运营总览":
    show_global_overview(df)
    st.stop()

# Existing US operations pages must not include newly imported non-US records.
df = df[df["目的仓国家"].map(is_us_country)].copy()

# Report on US post-port records with the explicit sidebar filters applied.
q = df.copy()

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
            arrived = z["ATA日期_dt"].dt.normalize().le(today)
            discharged = pd.to_datetime(z["目的港/站卸柜日期"], errors="coerce", format="mixed").dt.normalize().le(today)
            picked = z["进口实际提箱时间_dt"].notna()
            delivered = z["实际送仓时间_dt"].notna()
            returned = z["实际还柜日期_dt"].notna()
            metric_masks = [
                ("货柜记录", pd.Series(True, index=z.index)),
                ("已到港/站", arrived),
                ("已卸柜", discharged),
                ("LFD已过待核实", z["风险"].eq("LFD已过/提箱待核实")),
                ("已提柜", picked),
                ("已送仓", delivered),
                ("已还空", returned),
                ("LFD三天内", z["风险"].eq("LFD 3天内")),
                ("到港/站未记录提柜", arrived & ~picked),
            ]
            selected_metric_key = f"overview_selected_metric_{i}"
            for metric_idx, (col, (label, mask)) in enumerate(zip(st.columns(len(metric_masks)), metric_masks)):
                count = int(mask.sum())
                with col:
                    if st.button(f"{label}\n\n**{count:,}**", key=f"overview_metric_{i}_{metric_idx}",
                                 help=f"点击查看「{label}」的 {count:,} 条货柜记录",
                                 disabled=count == 0, use_container_width=True):
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
                st.caption("缺少提箱记录不等于确认未提箱。")
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
                    table_col, chart_col = st.columns([3,2])
                    table_col.dataframe(vendor_alerts, hide_index=True, use_container_width=True, height=min(340, 38+35*len(vendor_alerts)))
                    table_col.download_button("导出该区域供应商LFD预警汇总 CSV",
                        vendor_alerts.to_csv(index=False).encode("utf-8-sig"),
                        file_name=f"港后供应商LFD预警_{i}.csv", mime="text/csv",
                        key=f"overview_vendor_lfd_export_{i}")
                    warning_rows = alert_data[alert_data["是否LFD预警"]]
                    if not warning_rows.empty:
                        chart_col.markdown("##### 各供应商 LFD 预警柜量")
                        plot = vendor_alerts.set_index("港后供应商")[
                            ["LFD已过待核实", "LFD三天内", "提箱晚于LFD"]]
                        chart_col.bar_chart(plot, horizontal=True, color=["#ba3c43","#d99b31","#547ca5"],
                                     height=max(190, min(320, len(plot) * 28)))
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

            st.markdown("### 📊 区域业务与拖车商分配")
            chart_left, chart_right = st.columns([1, 1], gap="large")
            with chart_left:
                with st.container(border=True):
                    st.markdown("#### 各区域总业务柜量")
                    volume = z["区域"].value_counts().sort_values(ascending=True)
                    if volume.empty:
                        st.info("当前范围内暂无货柜记录")
                    else:
                        st.bar_chart(volume, horizontal=True, height=240,
                                     x_label="柜量", y_label="运营区域")
            with chart_right:
                with st.container(border=True):
                    st.markdown("#### 各区域港后拖车商占比")
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
                            "height": 220,
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
            if not z.empty:
                with st.expander("🔎 区域柜量及港后拖车商占比 · 条件查询", expanded=False):
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
                ships["预计到港 ETA"] = pd.to_datetime(ships.get("卸货港ETA日期", pd.Series("", index=ships.index)), errors="coerce", format="mixed").dt.strftime("%Y-%m-%d").fillna("未记录")
                ships["实际到港 ATA"] = pd.to_datetime(ships.get("卸货港ATA日期", pd.Series("", index=ships.index)), errors="coerce", format="mixed").dt.strftime("%Y-%m-%d").fillna("未记录")
                discharge_dt = pd.to_datetime(
                    ships["目的港/站卸柜日期"], errors="coerce", format="mixed")
                ships["最终卸柜日期"] = discharge_dt.dt.strftime("%Y-%m-%d").fillna("未记录")
                ships["船公司"] = ships["船公司"].fillna("").astype(str).str.strip().replace("", "未记录")
                summary = (
                    ships.groupby(["船公司", "船舶/航次", "卸货港", "停靠码头",
                                   "预计到港 ETA", "实际到港 ATA", "最终卸柜日期"],
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
