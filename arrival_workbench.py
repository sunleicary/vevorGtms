"""US destination-centric arrival monitoring; one ETA cohort for all views."""
from datetime import date
import pandas as pd
import streamlit as st

NODES = {
    "洛杉矶/长滩港": (33.75,-118.22,r"洛杉矶|长滩|los[ _-]*angeles|long[ _-]*beach|\bUSLAX\b|\bUSLGB\b|\bLAX\b|\bLGB\b"),
    "纽约/新泽西港": (40.68,-74.15,r"纽约|新泽西|new[ _-]*york|new[ _-]*jersey|newark|elizabeth|\bUSNYC\b|\bUSEWR\b|\bNYC\b"),
    "萨凡纳港": (32.13,-81.15,r"萨凡纳|savannah|\bUSSAV\b|\bSAV\b"),
    "休斯顿港": (29.73,-95.26,r"休斯顿|houston|\bUSHOU\b|\bHOU\b"),
    "芝加哥铁路站": (41.79,-87.72,r"芝加哥|chicago|\bUSCHI\b|\bCHI\b"),
    "亚特兰大铁路站": (33.75,-84.43,r"亚特兰大|atlanta|\bUSATL\b|\bATL\b"),
}

def build_arrivals(frame, today):
    z=frame.copy()
    def txt(col):
        return z.get(col,pd.Series("",index=z.index)).fillna("").astype(str).str.strip()
    def dt(col):
        return pd.to_datetime(txt(col),errors="coerce",format="mixed").dt.normalize()
    z=z.loc[txt("目的仓国家").str.casefold().isin(["美国","us","usa","america","united states","united states of america"])].copy()
    calc=dt("ETA（计算）").fillna(dt("ETA(计算)"))
    z["统计日期"]=dt("ETA日期").fillna(dt("目的港预计卸柜时间")).fillna(calc)
    z["日期来源"]="ETA日期"
    z.loc[dt("ETA日期").isna(),"日期来源"]="目的港预计卸柜时间"
    z.loc[dt("ETA日期").isna() & dt("目的港预计卸柜时间").isna(),"日期来源"]="ETA（计算）"
    z.loc[z["统计日期"].isna(),"日期来源"]="缺失"
    z["实际到港/站"]=dt("ATA日期")
    z["实际海运到港"]=dt("卸货港ATA日期")
    z["实际卸柜"]=dt("目的港/站卸柜日期")
    z["已到港/站"]=z["实际到港/站"].le(today)
    z["已卸柜"]=z["实际卸柜"].le(today)
    z["已提柜"]=dt("进口实际提箱时间").le(today)
    z["已送仓"]=dt("实际送仓时间").fillna(dt("实际到海外仓日期")).le(today)
    z["已还空"]=dt("实际还柜日期").le(today)
    z["逾期未记录到港"]=z["统计日期"].lt(today)&~z["已到港/站"]
    z["预计到港/站"]=z["统计日期"].ge(today)&~z["已到港/站"]
    z["缺少ETA且未记录到港"]=z["统计日期"].isna()&~z["已到港/站"]
    z["到港状态"]="已实际到港/站"
    z.loc[z["预计到港/站"],"到港状态"]="预计到港/站"
    z.loc[z["逾期未记录到港"],"到港状态"]="ETA已过，未记录到港"
    z.loc[z["缺少ETA且未记录到港"],"到港状态"]="缺少ETA"
    z["最终港/站"]="其他/待核实"
    dest=txt("目的地")
    hits=pd.DataFrame({name:dest.str.contains(pattern,case=False,regex=True) for name,(_,_,pattern) in NODES.items()},index=z.index)
    for name in NODES:
        z.loc[hits[name]&hits.sum(axis=1).eq(1),"最终港/站"]=name
    return z


def render_schematic(summary):
    """Static geographic image background and live overlay cards; no map service."""
    import html
    outline = "M38,24 L370,24 L380,28 L412,34 L451,32 L494,49 L508,62 L526,89 L515,107 L565,98 L568,89 L590,89 L614,72 L654,72 L681,43 L699,47 L699,64 L708,74 L671,88 L662,104 L672,112 L625,123 L613,145 L606,139 L600,165 L603,185 L596,194 L563,210 L536,235 L536,252 L551,289 L547,310 L538,310 L518,277 L520,269 L508,253 L491,256 L475,247 L437,250 L439,262 L421,262 L393,255 L376,258 L346,278 L343,292 L346,302 L324,296 L300,259 L282,255 L275,264 L265,261 L252,244 L234,231 L213,231 L213,236 L180,236 L135,219 L107,222 L90,204 L65,197 L19,128 L21,108 L18,99 L25,66 L16,34 L35,36 L41,47 L44,44 Z"
    positions = {
        "洛杉矶/长滩港": ("2%", "46%", False),
        "纽约/新泽西港": ("77%", "7%", False),
        "萨凡纳港": ("77%", "67%", False),
        "休斯顿港": ("29%", "71%", False),
        "芝加哥铁路站": ("48%", "7%", True),
        "亚特兰大铁路站": ("54%", "43%", True),
    }
    cards=[]
    for name,(left,top,rail) in positions.items():
        total=int(summary.loc[name,"总柜量"])
        arrived=int(summary.loc[name,"已到港/站"])
        cards.append(
            f'<div class="gtms-map-card" style="left:{left};top:{top};border-top-color:{"#2877b8" if rail else "#d97736"}">'
            f'<div class="gtms-map-name">{html.escape(name)}</div>'
            f'<div>总柜量 <b>{total:,}</b></div>'
            f'<div class="gtms-map-arrived">已到 <b>{arrived:,}</b></div>'
            f'<div class="gtms-map-transit">在途 <b>{total-arrived:,}</b></div></div>'
        )
    svg=f'<svg viewBox="0 0 730 340" preserveAspectRatio="xMidYMid meet" role="img" aria-label="美国本土地理背景" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="gtmsLand" x1="0" x2="0" y1="0" y2="1"><stop stop-color="#e4ebf0"/><stop offset="1" stop-color="#d2dee8"/></linearGradient></defs><path d="{outline}" fill="url(#gtmsLand)" stroke="#a3b6c6" stroke-width="1.4" transform="translate(0 8)"/></svg>'
    st.markdown(
        '<style>'
        '.gtms-static-map{position:relative;width:100%;height:340px;overflow:hidden;border:1px solid #d8e3ec;border-radius:8px;background:linear-gradient(155deg,#f8fbfd,#edf4f9)}'
        '.gtms-static-map svg{position:absolute;inset:0;width:100%;height:100%}'
        '.gtms-map-card{position:absolute;box-sizing:border-box;width:21%;padding:7px 9px;border:1px solid #d7e1e9;border-top:3px solid;background:rgba(255,255,255,.96);border-radius:6px;box-shadow:0 2px 8px rgba(27,54,77,.09);font-size:14px;line-height:1.35;color:#34485d}'
        '.gtms-map-name{font-weight:700;color:#17365a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}'
        '.gtms-map-card>div:not(:first-child){display:flex;justify-content:space-between;gap:4px}'
        '.gtms-map-arrived{color:#16814b}.gtms-map-transit{color:#b66b1f}'
        '</style><div class="gtms-static-map">'+svg+''.join(cards)+'</div>',
        unsafe_allow_html=True,
    )
    st.caption("静态美国地理背景 · 数字来自当前筛选数据 · 橙色为海运港口，蓝色为铁路站场。")



def show_vessel_schedule(rows, today):
    st.subheader("船舶到港与铁路到站计划")
    st.caption("按目的仓物流区域统计，沿用左侧ETA、区域及港后拖车商筛选；不受上方最终港/站下钻影响。海运到港日期可能在统计窗口之外。")
    v=rows.copy()
    def clean(field):
        return v.get(field,pd.Series("",index=v.index)).fillna("").astype(str).str.strip().replace("", "未记录")
    for field in ["目的仓物流区域","卸货港","船公司","实际船名","实际航次"]:
        v[field]=clean(field)
    regions=v["目的仓物流区域"]
    selected=st.selectbox("目的地海外仓区域",["全部海外仓区域"]+sorted(regions.unique().tolist()),key="vessel_warehouse_region")
    if selected!="全部海外仓区域":
        v=v.loc[regions.eq(selected)].copy()
    rail=v["目的仓物流区域"].str.contains(r"芝加哥|亚特兰大|chicago|atlanta",case=False,regex=True)
    date_fields=["卸货港ETA日期","卸货港ATA日期","目的港预计卸柜时间","目的港/站卸柜日期"]
    for field in date_fields:
        parsed=pd.to_datetime(v.get(field,pd.Series("",index=v.index)),errors="coerce",format="mixed").dt.normalize()
        v[field]=parsed.dt.strftime("%Y-%m-%d").fillna("未记录")
        if field in date_fields[2:]:
            v.loc[~rail,field]="不适用"
    v["海运到港状态"]="未记录实际到港"
    v.loc[pd.to_datetime(v["卸货港ATA日期"],errors="coerce").le(today),"海运到港状态"]="已实际到港"
    keys=["目的仓物流区域","船公司","实际船名","实际航次","卸货港"]+date_fields+["海运到港状态"]
    schedule=v.groupby(keys,dropna=False)["排柜单号"].nunique().reset_index(name="柜量")
    schedule["_sort"]=pd.to_datetime(schedule["卸货港ETA日期"],errors="coerce")
    schedule["_actual_sort"]=pd.to_datetime(schedule["卸货港ATA日期"],errors="coerce")
    schedule=schedule.sort_values(["目的仓物流区域","_sort","_actual_sort","船公司","实际船名","实际航次"],na_position="last").drop(columns=["_sort","_actual_sort"])
    st.metric("当前海外仓区域业务柜量",f"{v['排柜单号'].nunique():,}")
    st.caption("同一船名、航次、卸货港及日期组合汇总；日期不同则分行，避免用单一日期覆盖不同货柜。缺少船名、航次或港口的记录保留为未记录。")
    st.dataframe(schedule,hide_index=True,use_container_width=True)
    st.download_button("下载船舶到港与铁路到站计划 CSV",schedule.to_csv(index=False).encode("utf-8-sig"),"vessel_arrival_schedule.csv","text/csv")
    with st.expander("查看船舶对应货柜明细"):
        fields=["排柜单号","箱号"]+keys+["目的地","港后拖车行","统计日期"]
        st.dataframe(v[[k for k in fields if k in v]],hide_index=True,use_container_width=True)
        st.download_button("下载船舶货柜明细 CSV",v[[k for k in fields if k in v]].to_csv(index=False).encode("utf-8-sig"),"vessel_container_details.csv","text/csv")

def build_vessel_alerts(rows, today, tolerance=1):
    keys=["船公司","实际船名","实际航次","卸货港"]
    v=rows.copy()
    for k in keys:
        v[k]=v.get(k,pd.Series("",index=v.index)).fillna("").astype(str).str.strip().str.upper()
    valid=v[keys].apply(lambda c: ~c.isin(["","NAN","NONE","未记录","-"])).all(axis=1)
    missing_identity=int((~valid).sum())
    v=v.loc[valid].copy()
    v["_eta"]=pd.to_datetime(v.get("卸货港ETA日期",pd.Series("",index=v.index)),errors="coerce",format="mixed").dt.normalize()
    v["_ata"]=pd.to_datetime(v.get("卸货港ATA日期",pd.Series("",index=v.index)),errors="coerce",format="mixed").dt.normalize()
    result=[]
    for identity,g in v.groupby(keys):
        etas=g["_eta"].dropna().unique()
        atas=g.loc[g["_ata"].le(today),"_ata"].dropna().unique()
        eta=pd.Timestamp(etas[0]) if len(etas)==1 else pd.NaT
        ata=pd.Timestamp(atas[0]) if len(atas)==1 else pd.NaT
        days=None
        if len(etas)!=1 or len(atas)>1 or g["_ata"].gt(today).any():
            status="数据待核实"
        else:
            days=( (ata if pd.notna(ata) else today)-eta).days
            status=("延误到港" if days>tolerance else "正常到港") if pd.notna(ata) else ("逾期未确认到港" if days>tolerance else "计划到港")
        result.append(dict(zip(keys,identity)) | {"计划到港ETA":eta,"实际到港ATA":ata,"到港偏差天数":days,"涉及柜量":g["排柜单号"].nunique(),"船舶状态":status})
    return pd.DataFrame(result,columns=keys+["计划到港ETA","实际到港ATA","到港偏差天数","涉及柜量","船舶状态"]),missing_identity


def vessel_port_groups(vessels):
    port_groups=[
        ("洛杉矶/长滩港",NODES["洛杉矶/长滩港"][2]),
        ("纽约/新泽西港",NODES["纽约/新泽西港"][2]),
        ("萨凡纳港",NODES["萨凡纳港"][2]),
        ("休斯顿港",NODES["休斯顿港"][2]),
    ]
    port_names=vessels["卸货港"].fillna("").astype(str)
    assigned=pd.Series(False,index=vessels.index)
    groups=[]
    for name,pattern in port_groups:
        mask=port_names.str.contains(pattern,case=False,regex=True)&~assigned
        groups.append((name,mask))
        assigned |= mask
    groups.append(("其他卸货港",~assigned))
    return groups


def build_carrier_share(rows):
    carriers = rows.get("船公司", pd.Series("", index=rows.index, dtype="object"))
    carriers = carriers.fillna("").astype(str).str.strip().str.upper()
    missing = carriers.isin(["", "NAN", "NONE", "NULL", "N/A", "-", "未记录"])
    share = carriers.mask(missing, "未记录").value_counts().rename_axis("航司").reset_index(name="柜量")
    share["占比"] = share["柜量"].div(len(rows)) * 100
    return share.sort_values(["柜量", "航司"], ascending=[False, True]).reset_index(drop=True)


def default_arrival_eta_range(today):
    today = pd.Timestamp(today)
    return (
        (today - pd.Timedelta(weeks=2)).date(),
        (today + pd.DateOffset(months=2)).date(),
    )


def show_arrival_workbench(frame, eta_range=None, eta_enabled=True):
    today=pd.Timestamp(date.today())
    all_rows=build_arrivals(frame,today)
    st.markdown("""<style>
[data-testid="stMain"]:has(.arrival-page-title) {font-size:14px}
[data-testid="stMain"]:has(.arrival-page-title) :is(h1,h2,h3,h4,h5,h6,p,label,button,[role="tab"],[data-baseweb="select"],[data-baseweb="select"] span,[data-testid="stMetricValue"],[data-testid="stMetricValue"] div,[data-testid="stMetricLabel"] p,[data-testid="stCaptionContainer"] p) {font-size:14px!important;line-height:1.5!important}
[data-testid="stMain"]:has(.arrival-page-title) .arrival-page-title {font-size:20px!important;font-weight:700;line-height:1.45;color:inherit;margin:0 0 4px}
[data-testid="stMain"]:has(.arrival-page-title) [data-testid="stMetricValue"] {font-weight:700!important;min-height:22px!important}
[data-testid="stMain"]:has(.arrival-page-title) [data-testid="stMetricLabel"] {min-height:22px!important}
[data-testid="stMain"]:has(.arrival-page-title) [data-testid="stMetric"] {padding:8px 10px!important;border-radius:6px!important}
[data-testid="stMain"]:has(.arrival-page-title) [data-testid="stVerticalBlock"] {gap:.5rem!important}
[data-testid="stMain"]:has(.arrival-page-title) [data-testid="stTabs"] button {padding:6px 12px!important}
[data-testid="stMain"]:has(.arrival-page-title) [data-testid="stCaptionContainer"] p {opacity:.85}
</style><div class="arrival-page-title">港口与铁路到站动态监控中心</div>""",unsafe_allow_html=True)
    if eta_enabled:
        if eta_range is None:
            eta_range = default_arrival_eta_range(today)
        if len(eta_range)!=2:
            st.info("请选择完整的 ETA 起止日期。")
            return
        start,end=map(pd.Timestamp,eta_range)
        z=all_rows[all_rows["统计日期"].between(start,end)].copy()
    else:
        z=all_rows.copy()
        valid=z["统计日期"].dropna()
        start,end=(valid.min(),valid.max()) if not valid.empty else (today,today)
    st.caption(f"ETA统计窗口：{start.date()} 至 {end.date()}（含起止日）" if eta_enabled else "ETA不限（含缺失日期记录）")
    flags=["已到港/站","预计到港/站","逾期未记录到港","缺少ETA且未记录到港","已卸柜","已提柜","已送仓","已还空"]
    labels=list(NODES)+["其他/待核实"]
    summary=z.groupby("最终港/站").agg(总柜量=("排柜单号","size"),**{k:(k,"sum") for k in flags}).reindex(labels,fill_value=0)
    missing=all_rows[all_rows["缺少ETA且未记录到港"]].copy()
    summary["未记录实际到港/站"]=summary["总柜量"]-summary["已到港/站"]
    if eta_enabled:
        summary["缺少ETA（窗口外单列）"]=missing.groupby("最终港/站").size().reindex(labels,fill_value=0)
        summary=summary.drop(columns="缺少ETA且未记录到港")
    arrived=int(z["已到港/站"].sum())
    vessels,missing_identity=build_vessel_alerts(z,today)
    vessel_risk=vessels[vessels["船舶状态"].isin(["延误到港","逾期未确认到港"])]
    cols=st.columns(5)
    for c,(name,val) in zip(cols,[("全美总柜量",f"{len(z):,}"),("已到港/站",f"{arrived:,}"),("在途柜量",f"{len(z)-arrived:,}"),("船舶异常航次",f"{len(vessel_risk):,}"),("ETA已过待核实",f"{int(z['逾期未记录到港'].sum()):,}")]):
        c.metric(name,val,help="按船司、船名、航次、卸货港去重；海运ATA或当前日期超过卸货港ETA一天。缺失或冲突日期单列待核实。" if name=="船舶异常航次" else None)
    groups = vessel_port_groups(vessels)
    left,right=st.columns([2,1])
    with left:
        with st.container(border=True):
            st.markdown("#### 美国港口与铁路站场")
            render_schematic(summary)
    with right:
        with st.container(border=True):
            st.markdown("#### 美国港口船舶到港监控")
            confirmed=vessels["实际到港ATA"].notna() & vessels["船舶状态"].ne("数据待核实")
            pending=vessels["船舶状态"].isin(["计划到港","逾期未确认到港"])
            total=len(vessels)
            done=int(confirmed.sum())
            waiting=int(pending.sum())
            for c,(label,value) in zip(st.columns(3),[("总航次",total),("已到港",done),("待到港",waiting)]):
                c.metric(label,f"{value:,}")
            regional=[]
            for name,mask in groups:
                n=int(mask.sum())
                d=int((mask&confirmed).sum())
                w=int((mask&pending).sum())
                abnormal=int((mask & vessels["船舶状态"].isin(["延误到港","逾期未确认到港"])).sum())
                regional.append({"港口区域":name.replace("港","") if name!="其他卸货港" else "其他港口","总航次":n,"已到":d,"待到":w,"待核实":n-d-w,"异常":abnormal})
            regional.append({"港口区域":"合计","总航次":total,"已到":done,"待到":waiting,"待核实":total-done-waiting,"异常":len(vessel_risk)})
            region_table=pd.DataFrame(regional)
            styled=region_table.style.set_properties(subset=["已到"],**{"color":"#15803d"}).set_properties(subset=["待到"],**{"color":"#b7791f"}).set_properties(subset=["异常"],**{"color":"#ba3c43"})
            st.dataframe(styled,hide_index=True,use_container_width=True,height=248)
            st.caption(f"按海运卸货港及挂靠航次统计；缺少船舶识别字段 {missing_identity} 柜。详情见「船舶与航次」。")
    with st.expander("节点统计与日期口径"):
        st.dataframe(summary.reset_index(),hide_index=True,use_container_width=True)
        st.caption("在途含ETA已过但未记录到达的货柜；启用ETA筛选时，缺少ETA记录不计入地图总量。")
    region_options = {
        "🇺🇸 全美总览": None,
        "🗽 新泽西 NJ": "纽约/新泽西港",
        "🛳️ 萨凡纳 SAV": "萨凡纳港",
        "⚓ 洛杉矶 LA/LB": "洛杉矶/长滩港",
        "🚛 休斯顿 HOU": "休斯顿港",
        "🚆 芝加哥 CHI": "芝加哥铁路站",
        "🏭 亚特兰大 ATL": "亚特兰大铁路站",
    }
    st.markdown("""
<style>
.st-key-arrival_analysis_region [role="radiogroup"] {
    flex-wrap: wrap;
    gap: .5rem;
    border-bottom: 1px solid rgba(128,128,128,.25);
}
.st-key-arrival_analysis_region [role="radiogroup"] label {
    margin: 0;
    padding: .45rem .35rem;
    border-bottom: 2px solid transparent;
}
.st-key-arrival_analysis_region [role="radiogroup"] label:has(input:checked) {
    color: #d93242;
    border-bottom-color: #d93242;
}
.st-key-arrival_analysis_region label:has(input:checked) p {color: #d93242}
</style>
""", unsafe_allow_html=True)
    region = st.radio(
        "分析区域", list(region_options), horizontal=True,
        label_visibility="collapsed", key="arrival_analysis_region",
    )
    node = region_options[region]
    carrier_rows = z
    if node is not None:
        carrier_rows = z.loc[z["最终港/站"].eq(node)]
        vessels, missing_identity = build_vessel_alerts(carrier_rows, today)
        vessel_risk = vessels[vessels["船舶状态"].isin(["延误到港", "逾期未确认到港"])]
        groups = vessel_port_groups(vessels)
        confirmed = vessels["实际到港ATA"].notna() & vessels["船舶状态"].ne("数据待核实")
        pending = vessels["船舶状态"].isin(["计划到港", "逾期未确认到港"])
    tab_plan, tab_vessel, tab_actual, tab_risk, tab_carrier = st.tabs(
        ["每日到港计划", "船舶与航次", "实际到港趋势", "异常监控", "航司占比"]
    )
    with tab_plan:
        planned = vessels.loc[vessels["计划到港ETA"].notna()]
        if planned.empty:
            st.info("当前范围无有效船舶计划日期。")
        else:
            daily=planned.groupby("计划到港ETA").size().rename("计划到港航次")
            st.bar_chart(daily,height=240)
            st.dataframe(daily.reset_index(),hide_index=True,use_container_width=True)
        st.caption("按海运卸货港ETA及去重挂靠航次统计；统计范围沿用上方区域和侧栏筛选。")
    with tab_vessel:
        st.markdown("#### 单日集中到港监控")
        concentrated=[]
        for name,mask in groups:
            # Other ports are not one geographic port: count each separately.
            subset=vessels.loc[mask & pending & vessels["计划到港ETA"].ge(today)]
            if name=="其他卸货港":
                daily=subset.groupby(["计划到港ETA","卸货港"]).size()
                entries=[(day,port,int(n)) for (day,port),n in daily.items()]
            else:
                daily=subset.groupby("计划到港ETA").size()
                entries=[(day,name,int(n)) for day,n in daily.items()]
            for day,port,n in entries:
                if n>=2:
                    concentrated.append({"预计到港日期":day.strftime("%Y-%m-%d"),"港口区域":port,"预计航次":n,"集中到港预警":"红色预警" if n>=3 else "黄色预警"})
        if concentrated:
            alerts=pd.DataFrame(concentrated).sort_values(["预计到港日期","预计航次","港口区域"],ascending=[True,False,True]).reset_index(drop=True)
            styled=alerts.style.map(lambda v:"color:#ba3c43;font-weight:600" if v=="红色预警" else "color:#b7791f;font-weight:600",subset=["集中到港预警"])
            st.dataframe(styled,hide_index=True,use_container_width=True)
        else:
            st.success("当前统计周期内无单日多船集中到港预警")
        st.caption("按当前ETA筛选货柜范围、海运卸货港及卸货港ETA统计未确认到港的未来航次；单日2航次黄色，3航次及以上红色。日期待核实及已过原计划ETA的航次见异常监控。")
    with tab_actual:
        st.markdown("#### 船舶实际到港趋势")
        actual=vessels.loc[confirmed].groupby("实际到港ATA").size().rename("实际到港航次")
        if not actual.empty:
            st.bar_chart(actual,height=240)
            st.dataframe(actual.reset_index(),hide_index=True,use_container_width=True)
        else:
            st.info("当前范围无已确认到港航次。")
    with tab_risk:
        st.markdown("#### 船舶到港异常航次")
        st.caption(f"异常 {len(vessel_risk)} 航次 · 涉及 {int(vessel_risk['涉及柜量'].sum())} 柜 · 日期待核实 {int(vessels['船舶状态'].eq('数据待核实').sum())} 航次 · 缺少船舶识别字段 {missing_identity} 柜")
        st.dataframe(vessel_risk,hide_index=True,use_container_width=True)
        with st.expander("全部船舶到港状态（含数据待核实）"):
            st.dataframe(vessels,hide_index=True,use_container_width=True)
        st.download_button("下载异常航次 CSV",vessel_risk.to_csv(index=False).encode("utf-8-sig"),"vessel_alerts.csv","text/csv")
    with tab_carrier:
        if carrier_rows.empty:
            st.info("当前筛选范围内无货柜记录。")
        else:
            carrier_share = build_carrier_share(carrier_rows)
            st.caption(f"统计范围共 {len(carrier_rows):,} 柜。按货柜记录的「船公司」统计，未记录航司的货柜也计入总柜量。")
            st.dataframe(
                carrier_share,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "占比": st.column_config.ProgressColumn(
                        "占比", min_value=0, max_value=100, format="%.1f%%"
                    ),
                },
            )
