"""全球港后业务量分析：目的仓国家口径，供应商只取港后拖车行。"""
from datetime import date
import pandas as pd
import streamlit as st

COUNTRY_NAMES = {
    "美国": "美国", "AMERICA": "美国", "USA": "美国", "US": "美国", "UNITED STATES": "美国", "UNITED STATES OF AMERICA": "美国",
    "加拿大": "加拿大", "CANADA": "加拿大", "CA": "加拿大",
    "英国": "英国", "UNITED KINGDOM": "英国", "UK": "英国", "GREAT BRITAIN": "英国",
    "德国": "德国", "GERMANY": "德国", "DE": "德国",
    "法国": "法国", "FRANCE": "法国",
    "意大利": "意大利", "ITALY": "意大利",
    "西班牙": "西班牙", "SPAIN": "西班牙",
    "澳大利亚": "澳大利亚", "AUSTRALIA": "澳大利亚",
    "日本": "日本", "JAPAN": "日本",
    "墨西哥": "墨西哥", "MEXICO": "墨西哥",
    "荷兰": "荷兰", "NETHERLANDS": "荷兰",
    "波兰": "波兰", "POLAND": "波兰",
    "比利时": "比利时", "BELGIUM": "比利时",
    "新加坡": "新加坡", "SINGAPORE": "新加坡",
    "马来西亚": "马来西亚", "MALAYSIA": "马来西亚",
    "泰国": "泰国", "THAILAND": "泰国",
    "阿联酋": "阿联酋", "UNITED ARAB EMIRATES": "阿联酋", "UAE": "阿联酋",
}
USA_VALUES = {"美国", "AMERICA", "USA", "US", "UNITED STATES", "UNITED STATES OF AMERICA"}


def normalize_country(value):
    name = str(value).strip()
    if not name or name.lower() in ("nan", "none", "null"):
        return "未记录国家"
    return COUNTRY_NAMES.get(name.upper(), name)


def is_us_country(value):
    return str(value).strip().upper() in USA_VALUES


def _download(frame, filename, key):
    st.download_button("导出 CSV", frame.to_csv(index=False).encode("utf-8-sig"),
                       file_name=filename, mime="text/csv", key=key)


def _prepare(df):
    z = df.copy()
    z["国家"] = z["目的仓国家"].map(normalize_country)
    z["区域"] = z["目的仓物流区域"].fillna("").astype(str).str.strip()
    z.loc[z["区域"].isin(["", "nan", "None"]), "区域"] = "未记录区域"
    z["港后供应商"] = z["港后拖车行"].fillna("").astype(str).str.strip()
    z.loc[z["港后供应商"].isin(["", "nan", "None", "港后拖车测试"]), "港后供应商"] = "待分配/未记录"
    for field in ("ETA日期", "ATA日期", "LFD", "进口实际提箱时间", "实际送仓时间", "实际还柜日期"):
        z[field + "_dt"] = pd.to_datetime(z[field], errors="coerce", format="mixed")
    z["统计日期_dt"] = z["ETA日期_dt"].fillna(pd.to_datetime(z.get("目的港预计卸柜时间", pd.Series("", index=z.index)), errors="coerce", format="mixed"))
    z["已到港"] = pd.to_datetime(z["目的港/站卸柜日期"], errors="coerce", format="mixed").notna()
    z["已提柜"] = z["进口实际提箱时间_dt"].notna()
    z["已送仓"] = z["实际送仓时间_dt"].notna()
    z["已还空"] = z["实际还柜日期_dt"].notna()
    z["待提柜（已到港）"] = z["已到港"] & ~z["已提柜"]
    z["待送仓（已提柜）"] = z["已提柜"] & ~z["已送仓"]
    z["待还空（已送仓）"] = z["已送仓"] & ~z["已还空"]
    z["待分配"] = z["港后供应商"].eq("待分配/未记录")
    today = pd.Timestamp(date.today())
    lfd = z["LFD_dt"]
    z["LFD超期待核实"] = lfd.notna() & ~z["已提柜"] & (lfd < today)
    z["LFD三天内"] = lfd.notna() & ~z["已提柜"] & (lfd >= today) & (lfd < today + pd.Timedelta(days=3))
    z["缺少ETA"] = z["ETA日期_dt"].isna()
    return z


def _summary(z, by):
    keys = [by] if isinstance(by, str) else list(by)
    measures = ["已到港", "已提柜", "已送仓", "已还空", "待提柜（已到港）",
                "待送仓（已提柜）", "待还空（已送仓）", "待分配",
                "LFD超期待核实", "LFD三天内", "缺少ETA"]
    out = z.groupby(keys, dropna=False).agg(**{"总柜量": ("国家", "size"),
                        **{name: (name, "sum") for name in measures}}).reset_index()
    out["送仓率%"] = (100 * out["已送仓"] / out["总柜量"]).round(1)
    out["还空率%"] = (100 * out["已还空"] / out["总柜量"]).round(1)
    return out.sort_values("总柜量", ascending=False)


def _details(z, key):
    columns = ["国家", "区域", "箱号", "排柜单号", "目的仓", "港后供应商",
               "ETA日期", "ATA日期", "LFD", "进口实际提箱时间",
               "实际送仓时间", "实际还柜日期"]
    visible = z[[x for x in columns if x in z.columns]].copy()
    st.caption(f"匹配 {len(visible):,} 条货柜记录")
    st.dataframe(visible, use_container_width=True, hide_index=True, height=390)
    _download(visible, f"全球港后货柜明细_{key}.csv", f"global_details_{key}")


def show_global_overview(df):
    st.markdown("""<div style="background:linear-gradient(105deg,#092653,#134a88 80%,#ef5b20);
      border-radius:12px;padding:17px 24px;margin-bottom:12px;color:white">
      <div style="font-size:1.5rem;font-weight:750">🌍 全球港后运营总览</div>
      <div style="color:#dbe8fa;font-size:.9rem;margin-top:4px">
      国家管理 / 区域处理进度 / 港后供应商 / 异常预警</div></div>""", unsafe_allow_html=True)
    required = {"目的仓国家", "目的仓物流区域", "港后拖车行"}
    if not required.issubset(df.columns):
        st.error("缺少必要字段：" + "、".join(sorted(required - set(df.columns))))
        return
    data = _prepare(df)
    valid = data["统计日期_dt"].dropna()
    years = sorted(valid.dt.year.unique().astype(int).tolist(), reverse=True)
    f1, f2, f3 = st.columns([1, 1.5, 1.5])
    with f1:
        mode = st.selectbox("数据时间口径", ["全部历史记录", "按统计日期"], key="global_mode")
    with f2:
        if mode == "按统计日期" and years:
            yr = st.selectbox("ETA年份", years, index=years.index(2026) if 2026 in years else 0, key="global_year")
        else:
            yr = None
            st.caption("沿用左侧筛选；统计日期优先 ETA，缺失取预计卸柜时间")
    with f3:
        if yr is not None:
            dates = st.date_input("统计日期区间", (date(yr, 1, 1), date(yr, 12, 31)),
                                  key=f"global_dates_{yr}")
        else:
            dates = None
    if mode == "按统计日期":
        if not years:
            st.warning("无有效 ETA 日期，请使用全部历史记录模式。")
            return
        if not dates or len(dates) != 2:
            st.info("请选择完整的 ETA 起止日期。")
            return
        data = data[data["统计日期_dt"].between(pd.Timestamp(dates[0]),
            pd.Timestamp(dates[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))].copy()
    if data.empty:
        st.info("当前时间窗口内无货柜记录。")
        return
    countries = _summary(data, "国家")
    names = countries["国家"].tolist()
    country = st.selectbox("🌐 国家运营中心", ["全球全部"] + names, key="global_selected_country")
    z = data if country == "全球全部" else data[data["国家"].eq(country)]
    total = len(z)
    kpis = [("总柜量", total), ("区域数", len(z[["国家", "区域"]].drop_duplicates())),
            ("已到港/站", int(z["已到港"].sum())), ("已提柜", int(z["已提柜"].sum())),
            ("已送仓", int(z["已送仓"].sum())), ("已还空", int(z["已还空"].sum())),
            ("待分配", int(z["待分配"].sum())), ("LFD超期待核实", int(z["LFD超期待核实"].sum()))]
    for col, (label, value) in zip(st.columns(8), kpis):
        with col:
            st.caption(label)
            st.markdown(f"<div style='font-size:1.45rem;font-weight:750;color:#123765'>{value:,}</div>",
                        unsafe_allow_html=True)
    st.caption("柜量按「排柜单号」唯一业务记录统计，允许箱号重复。处理节点基于原始日期字段；"
               "无记录不等于现场未完成。区域使用「目的仓物流区域」原始值，不推断归属。")

    tab1, tab2, tab3, tab4 = st.tabs(["📊 国家运营对比", "🏭 区域处理工作台",
                                      "🚛 港后供应商", "⚠️ 异常与货柜明细"])
    with tab1:
        st.markdown("##### 国家货柜处理情况")
        st.dataframe(countries, hide_index=True, use_container_width=True,
                     column_config={"送仓率%": st.column_config.ProgressColumn(
                         "送仓率%", min_value=0, max_value=100, format="%.1f%%"),
                         "还空率%": st.column_config.ProgressColumn(
                         "还空率%", min_value=0, max_value=100, format="%.1f%%")})
        _download(countries, "全球国家运营进度.csv", "global_countries_v3")
        left, right = st.columns(2)
        with left:
            st.markdown("##### 国家柜量排名")
            st.bar_chart(countries.set_index("国家")["总柜量"].sort_values(),
                         horizontal=True, height=max(300, min(580, 33*len(countries))))
        with right:
            st.markdown("##### 国家送仓 / 还空量")
            st.bar_chart(countries.set_index("国家")[["已送仓", "已还空"]],
                         horizontal=True, height=max(300, min(580, 33*len(countries))))
    with tab2:
        st.markdown(f"##### {country} · 区域货柜处理矩阵")
        region_summary = _summary(z, ["国家", "区域"])
        st.dataframe(region_summary, hide_index=True, use_container_width=True,
                     column_config={"送仓率%": st.column_config.ProgressColumn(
                         "送仓率%", min_value=0, max_value=100, format="%.1f%%"),
                         "还空率%": st.column_config.ProgressColumn(
                         "还空率%", min_value=0, max_value=100, format="%.1f%%")})
        _download(region_summary, "国家区域货柜处理进度.csv", "global_region_v3")
        st.markdown("##### 区域待处理节点")
        chart = region_summary.copy()
        chart["国家 / 区域"] = chart["国家"] + " / " + chart["区域"]
        chart = chart.set_index("国家 / 区域")[["待提柜（已到港）",
                  "待送仓（已提柜）", "待还空（已送仓）"]]
        st.bar_chart(chart, horizontal=True, height=max(320, min(760, 30*len(chart))))
        st.caption("三种待处理节点可重叠或因里程碑缺失出现不一致，不能直接相加。")
    with tab3:
        st.markdown("##### 国家 / 区域 / 港后拖车商业务分配")
        supplier = z.groupby(["国家", "区域", "港后供应商"]).size().rename("柜量").reset_index()
        supplier = supplier.sort_values("柜量", ascending=False)
        st.dataframe(supplier, hide_index=True, use_container_width=True, height=460)
        _download(supplier, "全球港后供应商区域分配.csv", "global_suppliers_v3")
        st.markdown("##### 港后拖车商柜量")
        vendor_counts = z["港后供应商"].value_counts().head(15).sort_values()
        st.bar_chart(vendor_counts, horizontal=True, height=max(300, min(620, 32*len(vendor_counts))))
        st.caption("只读取「港后拖车行」；空白和「港后拖车测试」归为待分配。"
                   "字段有供应商名称不代表供应商已确认运力。")
    with tab4:
        st.markdown("##### 货柜处理状态与 LFD 预警")
        regions = sorted(z["区域"].unique().tolist())
        a, b, c = st.columns(3)
        with a:
            selected_region = st.selectbox("目的仓区域", ["全部区域"] + regions,
                                           key="global_detail_region_v3")
        scoped = z if selected_region == "全部区域" else z[z["区域"].eq(selected_region)]
        statuses = ["全部", "已到港", "已提柜", "已送仓", "已还空",
                    "待提柜（已到港）", "待送仓（已提柜）", "待还空（已送仓）",
                    "待分配", "LFD超期待核实", "LFD三天内", "缺少ETA"]
        with b:
            status = st.selectbox("货柜处理状态", statuses, key="global_detail_status_v3")
        with c:
            vendors = sorted(scoped["港后供应商"].unique().tolist())
            selected_vendor = st.selectbox("港后拖车商", ["全部供应商"] + vendors,
                                            key="global_detail_vendor_v3")
        if status != "全部":
            scoped = scoped[scoped[status]]
        if selected_vendor != "全部供应商":
            scoped = scoped[scoped["港后供应商"].eq(selected_vendor)]
        _details(scoped, "global_v3")
        st.caption("LFD为数据预警，需结合不同国家码头规则人工核实。"
                   "缺少提柜记录不等于确认未提柜。")
    st.caption("数据来自当前 SQLite 数据库。如仅显示美国，请由管理员先备份，"
               "再重新上传包含全球国家的完整源文件。")
