"""全美港后供应商总览：按 ETA 和目的仓区域统计，供应商只取港后拖车行。"""
from datetime import date
import pandas as pd
import streamlit as st

REGIONS = ["新泽西 NJ", "洛杉矶 LA/LB", "亚特兰大 ATL", "休斯顿 HOU", "芝加哥 CHI", "萨凡纳 SAV"]
REGION_SHORT = {"新泽西 NJ":"NJ", "洛杉矶 LA/LB":"LA", "亚特兰大 ATL":"ATL",
                "休斯顿 HOU":"HOU", "芝加哥 CHI":"CHI", "萨凡纳 SAV":"SAV"}
PALETTE = ["#ff641a", "#0875ed", "#00ad9d", "#8751d5", "#00a8eb", "#93a8be", "#e9b449"]

def show_supplier_overview(df, grid):
    st.markdown("""<style>
    .supplier-hero{background:linear-gradient(112deg,#092452,#06448d 72%,#f05b1c);
       color:white;padding:20px 26px;border-radius:14px;margin-bottom:12px}
    .supplier-hero h2{color:white;margin:0;font-size:1.65rem}
    .supplier-hero p{color:#d9eaff;margin:5px 0 0}
    .supplier-section{background:linear-gradient(90deg,#06265a,#0c559a);
       color:white;padding:9px 14px;border-radius:9px;font-weight:750;margin:12px 0}
    </style>""", unsafe_allow_html=True)
    st.markdown('<div class="supplier-hero"><h2>🚛 美国全美六大区域港后拖车业务需求与供应商分配分析</h2>'
                '<p>U.S. Six Regions · Post-Port Trucking Demand & Supplier Allocation</p></div>',
                unsafe_allow_html=True)
    years = sorted(df["ETA日期_dt"].dropna().dt.year.astype(int).unique().tolist(), reverse=True)
    if not years:
        st.warning("当前数据库缺少有效 ETA 日期，无法生成按 ETA 统计的供应商总览。")
        return
    default_year = 2026 if 2026 in years else years[0]
    a,b,c = st.columns([1,2,2])
    with a:
        year = st.selectbox("统计年份（ETA）", years, index=years.index(default_year), key="supplier_year")
    with b:
        date_range = st.date_input("ETA 统计区间", (date(year,1,1),date(year,12,31)),
                                   key=f"supplier_dates_{year}")
    with c:
        selected_regions = st.multiselect("统计区域", REGIONS, default=REGIONS, key="supplier_regions")
    if len(date_range)!=2:
        st.info("请选择开始和结束日期。")
        return
    z=df[df["区域"].isin(selected_regions) & df["ETA日期_dt"].between(
        pd.Timestamp(date_range[0]),pd.Timestamp(date_range[1])+pd.Timedelta(days=1)-pd.Timedelta(seconds=1))].copy()
    if z.empty:
        st.info("当前 ETA 区间及区域内暂无货柜数据。")
        return
    z["供应商"]=z["港后拖车行"].fillna("").astype(str).str.strip()
    z.loc[z["供应商"].isin(["", "nan", "None", "港后拖车测试"]), "供应商"] = "待分配/未记录"
    z["月份"]=z["ETA日期_dt"].dt.strftime("%Y-%m")
    total=len(z)
    pending=int(z["供应商"].eq("待分配/未记录").sum())
    allocated=total-pending
    monthly=z.groupby("月份").size()
    top_month=monthly.idxmax()
    stats=[("全年/区间总需求",f"{total:,} 柜"),
           ("已分配完成",f"{allocated:,} 柜",f"{allocated/total:.1%}"),
           ("待分配/未记录",f"{pending:,} 柜",f"{pending/total:.1%}"),
           ("日均需求",f"{total/max((date_range[1]-date_range[0]).days+1,1):.1f} 柜/天"),
           ("需求高峰月",top_month,f"{monthly.max():,} 柜"),
           ("覆盖区域",f"{z['区域'].nunique()} 个")]
    for col,stat in zip(st.columns(6),stats):
        col.metric(stat[0],stat[1],delta=stat[2] if len(stat)>2 else None,delta_color="off")
    st.caption(f"统计口径：ETA {date_range[0]} — {date_range[1]} · 排柜单号唯一业务记录 · 目的海外仓区域 · 港后拖车行；"
               "“港后拖车测试”归入待分配/未记录；已分配仅指有效供应商名称，不代表车队确认接单或运力。")

    st.markdown('<div class="supplier-section">📊 区域需求 · 月度趋势 · 供应商结构</div>',unsafe_allow_html=True)
    left,mid,right=st.columns([1,1.25,1],gap="medium")
    with left:
        with st.container(border=True):
            st.markdown("##### 六大区域业务需求")
            reg=z.groupby("区域").size().reindex(selected_regions,fill_value=0)
            st.bar_chart(reg.sort_values(),horizontal=True,height=290,x_label="柜量",y_label="区域")
    with mid:
        with st.container(border=True):
            st.markdown("##### 月度需求与分配趋势")
            month_table=pd.crosstab(z["月份"],z["供应商"].eq("待分配/未记录"))
            month_table=month_table.reindex(columns=[False,True],fill_value=0)
            month_table.columns=["已分配","待分配/未记录"]
            st.bar_chart(month_table,stack=True,height=290,x_label="ETA月份",y_label="柜量")
    with right:
        with st.container(border=True):
            st.markdown("##### 供应商整体分配结构")
            supplier_counts=z["供应商"].value_counts()
            top=supplier_counts.head(8)
            other=int(supplier_counts.iloc[8:].sum())
            if other: top=pd.concat([top,pd.Series({"其他供应商":other})])
            st.bar_chart(top.sort_values(),horizontal=True,height=290,x_label="柜量",y_label="供应商")

    st.markdown('<div class="supplier-section">📍 六大区域供应商分配详情</div>',unsafe_allow_html=True)
    for start in (0,3):
        cols=st.columns(3,gap="medium")
        for col,r in zip(cols,REGIONS[start:start+3]):
            with col:
                with st.container(border=True):
                    area=z[z["区域"].eq(r)]
                    n=len(area)
                    st.markdown(f"##### {r}")
                    st.metric("区域总需求",f"{n:,} 柜")
                    if not n:
                        st.caption("当前区间无数据")
                        continue
                    pending_r=int(area["供应商"].eq("待分配/未记录").sum())
                    st.progress((n-pending_r)/n,text=f"已分配 {(n-pending_r)/n:.1%} · 待分配 {pending_r:,} 柜")
                    share=area["供应商"].value_counts()
                    # Keep the six largest vendors visible and consolidate the remainder.
                    if len(share)>6:
                        share=pd.concat([share.iloc[:6],pd.Series({"其他供应商":int(share.iloc[6:].sum())})])
                    pie_data=pd.DataFrame({"供应商":share.index,"柜量":share.values})
                    pie_data["占比"]=pie_data["柜量"].div(n).mul(100).round(1)
                    pie_data["图上标签"]=pie_data.apply(
                        lambda row: f'{int(row["柜量"]):,}柜 / {row["占比"]:.1f}%', axis=1)
                    pie_spec={
                        "data":{"values":pie_data.to_dict("records")},
                        "width":"container",
                        "height":310,
                        "layer":[
                            {
                                "mark":{"type":"arc","outerRadius":100,"innerRadius":43},
                                "encoding":{
                                    "theta":{"field":"柜量","type":"quantitative","stack":True},
                                    "color":{"field":"供应商","type":"nominal",
                                             "scale":{"range":PALETTE},
                                             "legend":{"orient":"bottom","columns":2,"labelLimit":145}},
                                    "tooltip":[{"field":"供应商","type":"nominal"},
                                               {"field":"柜量","type":"quantitative","format":","},
                                               {"field":"占比","type":"quantitative","format":".1f","title":"占比 (%)"}]
                                }
                            },
                            {
                                "mark":{"type":"text","radius":124,"fontSize":11,"fontWeight":"bold",
                                        "color":"#092550"},
                                "encoding":{
                                    "theta":{"field":"柜量","type":"quantitative","stack":True},
                                    "text":{"field":"图上标签","type":"nominal"},
                                    "order":{"field":"供应商","type":"nominal"}
                                }
                            }
                        ],
                        "view":{"stroke":None}
                    }
                    st.vega_lite_chart(pie_spec,use_container_width=True,key=f"supplier_pie_{REGION_SHORT[r]}")

    st.markdown('<div class="supplier-section">📋 分配明细与业务查询</div>',unsafe_allow_html=True)
    t1,t2,t3=st.tabs(["区域汇总","供应商 × 区域","月度分配"])
    with t1:
        region_total=z.groupby("区域").size().rename("总需求")
        region_pending=z[z["供应商"].eq("待分配/未记录")].groupby("区域").size()
        report=pd.DataFrame({"总需求":region_total,"待分配/未记录":region_pending}).fillna(0).astype(int)
        report["已分配"]=report["总需求"]-report["待分配/未记录"]
        report["分配率"]=report["已分配"].div(report["总需求"]).mul(100).round(1)
        st.dataframe(report.reset_index(),hide_index=True,use_container_width=True)
    with t2:
        cross=pd.crosstab(z["供应商"],z["区域"])
        cross["合计"]=cross.sum(axis=1)
        st.dataframe(cross.sort_values("合计",ascending=False),use_container_width=True)
    with t3:
        m=pd.crosstab(z["月份"],z["供应商"].eq("待分配/未记录")).reindex(columns=[False,True],fill_value=0)
        m.columns=["已分配","待分配/未记录"]
        m["总需求"]=m.sum(axis=1)
        m["分配率(%)"]=(m["已分配"]/m["总需求"]*100).round(1)
        st.dataframe(m,use_container_width=True)

    st.markdown("#### 🔎 点击查看对应货柜记录")
    d1,d2=st.columns(2)
    with d1:
        r=st.selectbox("查询区域",["全部"]+selected_regions,key="supplier_detail_region")
    with d2:
        vendors=sorted(z["供应商"].unique().tolist())
        vendor=st.selectbox("查询港后拖车商",["全部"]+vendors,key="supplier_detail_vendor")
    subset=z.copy()
    if r!="全部": subset=subset[subset["区域"].eq(r)]
    if vendor!="全部": subset=subset[subset["供应商"].eq(vendor)]
    st.caption(f"匹配 {len(subset):,} 条货柜记录；可在下表查看和导出。")
    grid(subset,key="supplier_overview_detail")
    st.caption("说明：本页将港后拖车行为空或为“港后拖车测试”的记录归为“待分配/未记录”，"
               "无法识别供应商是否已确认产能。月度数据按 ETA 月份归属，不代表实际提柜月份。")
