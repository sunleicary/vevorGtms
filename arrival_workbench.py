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
    """Static, responsive SVG; no basemap, network requests or map controls."""
    layout = [
        ("洛杉矶/长滩港","LA / LB",102,213,8,249,143),
        ("纽约/新泽西港","NY / NJ",531,150,510,38,142),
        ("萨凡纳港","SAV",459,253,510,278,142),
        ("休斯顿港","HOU",328,283,233,328,146),
        ("芝加哥铁路站","CHI",381,153,277,4,153),
        ("亚特兰大铁路站","ATL",431,232,345,196,150),
    ]
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 660 405" role="img" aria-label="美国六大港口及铁路站场柜量示意图" style="width:100%;height:auto;display:block;font-family:Arial,Microsoft YaHei,sans-serif">',
             '<rect width="660" height="405" rx="10" fill="#10243e"/>',
             '<path d="M65 46 L122 60 L170 65 L218 69 L270 72 L306 73 L322 87 L350 77 L375 86 L388 108 L405 98 L419 113 L435 104 L452 128 L470 119 L484 99 L514 96 L537 72 L557 78 L562 105 L548 120 L532 126 L535 149 L517 166 L508 189 L490 204 L480 229 L461 248 L474 273 L491 303 L481 319 L466 311 L447 276 L425 257 L398 261 L379 250 L362 273 L340 271 L326 306 L317 338 L295 327 L280 300 L254 280 L229 286 L212 260 L183 251 L159 235 L128 230 L111 209 L91 198 L80 167 L64 144 L51 112 L58 86 Z" fill="#253e58" stroke="#607a96" stroke-width="1.5" transform="translate(10 20)"/>']
    for name,code,x,y,bx,by,w in layout:
        color = "#38bdf8" if code in ("CHI","ATL") else "#ff9a54"
        parts.append(f'<path d="M{x} {y} L{bx+w/2} {by+32}" stroke="{color}" stroke-width="1.3" stroke-dasharray="3 3" fill="none"/><circle cx="{x}" cy="{y}" r="11" fill="{color}" opacity=".2"/><circle cx="{x}" cy="{y}" r="4.5" fill="{color}" stroke="white"/>')
    for name,code,x,y,bx,by,w in layout:
        color = "#38bdf8" if code in ("CHI","ATL") else "#ff9a54"
        count = int(summary.loc[name,"总柜量"])
        parts.append(f'<rect x="{bx}" y="{by}" width="{w}" height="65" rx="7" fill="#10243e" stroke="{color}"/><text x="{bx+10}" y="{by+19}" font-size="13" fill="#e2e8f0" font-weight="600">{name}</text><text x="{bx+10}" y="{by+48}" font-size="25" fill="{color}" font-weight="bold">{count:,}</text><text x="{bx+w-9}" y="{by+48}" text-anchor="end" font-size="10" fill="#b5c8df">{code} · 柜</text>')
    parts.append('</svg>')
    st.markdown('<div style="max-width:1050px;margin:auto">'+''.join(parts)+'</div>',unsafe_allow_html=True)
    st.caption("橙色：海运港群 ｜ 蓝色：铁路站场 ｜ 示意位置，非精确地理坐标。其他目的地单独统计。")
    st.caption("点击下方区域按钮，切换每日趋势及货柜明细。")
    for col,name in zip(st.columns(6),NODES):
        if col.button(name, key="arrival_map_"+name, use_container_width=True):
            st.session_state["arrival_destination_filter"]=name



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

def show_arrival_workbench(frame, eta_range=None, eta_enabled=True):
    today=pd.Timestamp(date.today())
    all_rows=build_arrivals(frame,today)
    st.title("港口与铁路到站动态监控中心")
    if eta_enabled:
        if eta_range is None:
            eta_range=((today-pd.Timedelta(days=14)).date(),(today+pd.Timedelta(days=14)).date())
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
    st.caption("按目的地归属最终港/站，洛杉矶与长滩合并。美国业务按排柜单号去重后的数据；非实时码头状态。")
    flags=["已到港/站","预计到港/站","逾期未记录到港","缺少ETA且未记录到港","已卸柜","已提柜","已送仓","已还空"]
    labels=list(NODES)+["其他/待核实"]
    summary=z.groupby("最终港/站").agg(总柜量=("排柜单号","size"),**{k:(k,"sum") for k in flags}).reindex(labels,fill_value=0)
    missing=all_rows[all_rows["缺少ETA且未记录到港"]].copy()
    summary["未记录实际到港/站"]=summary["总柜量"]-summary["已到港/站"]
    if eta_enabled:
        summary["缺少ETA（窗口外单列）"]=missing.groupby("最终港/站").size().reindex(labels,fill_value=0)
        summary=summary.drop(columns="缺少ETA且未记录到港")
    cols=st.columns(4)
    for c,(name,val) in zip(cols,[("全美总柜量",len(z)),("六大港/站柜量",int(summary.loc[list(NODES),"总柜量"].sum())),("实际已到港/站",int(z["已到港/站"].sum())),("其他/待核实",int(summary.loc["其他/待核实","总柜量"]))]):
        c.metric(name,f"{val:,}")
    st.caption(f"ETA直接取值 {int(z['日期来源'].eq('ETA日期').sum()):,}；预计卸柜兜底 {int(z['日期来源'].eq('目的港预计卸柜时间').sum()):,}；ETA（计算）兜底 {int(z['日期来源'].eq('ETA（计算）').sum()):,}；筛选前缺有效日期 {int(all_rows['统计日期'].isna().sum()):,}。")
    st.subheader("到港状态分类")
    status_cols=st.columns(4)
    for c,(label,value) in zip(status_cols,[("已实际到港/站",z["已到港/站"].sum()),("预计到港/站",z["预计到港/站"].sum()),("ETA已过未记录到港",z["逾期未记录到港"].sum()),("缺少ETA（未记录到港）",len(missing))]):
        c.metric(label,f"{int(value):,}")
    st.caption("前三项受ETA筛选限制。缺少ETA且未记录到港按当前区域和港后拖车商筛选，不受日期窗口限制；启用ETA窗口时不计入地图及窗口总柜量。ETA今天到期仍列为预计到港，逾期仅表示需核实。")
    st.subheader("美国六大港口与铁路站场运营地图")
    render_schematic(summary)
    st.dataframe(summary.reset_index(),hide_index=True,use_container_width=True)
    st.subheader("每日到港/站业务量趋势")
    chosen=st.selectbox("最终港/站下钻",["全美国","六大港/站"]+labels,key="arrival_destination_filter")
    detail=z if chosen=="全美国" else z[z["最终港/站"].isin(list(NODES))] if chosen=="六大港/站" else z[z["最终港/站"].eq(chosen)]
    days=pd.date_range(start,end)
    daily=detail.groupby("统计日期").size().reindex(days,fill_value=0).rename("ETA柜量").to_frame()
    daily["已到港/站（按ETA归组）"]=detail[detail["已到港/站"]].groupby("统计日期").size().reindex(days,fill_value=0)
    st.bar_chart(daily[["ETA柜量"]])
    st.caption("每日业务量按ETA归组，不代表实际当天到港或可提柜。实际到港状态按ATA判断。")
    table=z.groupby(["统计日期","最终港/站"]).size().unstack(fill_value=0).reindex(index=days,columns=labels,fill_value=0)
    table["全美"]=table.sum(axis=1)
    table.index.name="ETA统计日期"
    st.dataframe(table.reset_index(),hide_index=True,use_container_width=True)
    st.download_button("下载每日柜量 CSV",table.to_csv().encode("utf-8-sig"),"daily_arrivals.csv","text/csv")
    st.subheader("实际到达趋势（同一ETA业务范围）")
    actual=detail.loc[detail["已到港/站"]].groupby("实际到港/站").size()
    if not actual.empty:
        st.bar_chart(actual.rename("实际到港/站柜量"))
    show_vessel_schedule(z,today)
    st.subheader("货柜明细")
    selected_status=st.selectbox("到港状态筛选",["全部（当前ETA范围）","已实际到港/站","预计到港/站","ETA已过，未记录到港","缺少ETA"],key="arrival_status_filter")
    if selected_status=="缺少ETA":
        detail=missing if chosen=="全美国" else missing[missing["最终港/站"].isin(list(NODES))] if chosen=="六大港/站" else missing[missing["最终港/站"].eq(chosen)]
        st.caption("缺少ETA明细不受日期窗口限制。")
    elif selected_status!="全部（当前ETA范围）":
        detail=detail[detail["到港状态"].eq(selected_status)]
    fields=[k for k in ["排柜单号","箱号","目的地","最终港/站","目的仓物流区域","统计日期","日期来源","到港状态","ETA日期","目的港预计卸柜时间","ETA（计算）","卸货港ETA日期","实际海运到港","实际到港/站","实际卸柜","港后拖车行","LFD","进口实际提箱时间","实际送仓时间","实际还柜日期"] if k in detail]
    st.dataframe(detail[fields],hide_index=True,use_container_width=True)
    st.download_button("下载货柜明细 CSV",detail[fields].to_csv(index=False).encode("utf-8-sig"),"arrival_details.csv","text/csv")
