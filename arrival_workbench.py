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
    z["统计日期"]=dt("ETA日期").fillna(dt("目的港预计卸柜时间"))
    z["日期来源"]="ETA日期"
    z.loc[dt("ETA日期").isna(),"日期来源"]="目的港预计卸柜时间"
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
    z["最终港/站"]="其他/待核实"
    dest=txt("目的地")
    hits=pd.DataFrame({name:dest.str.contains(pattern,case=False,regex=True) for name,(_,_,pattern) in NODES.items()},index=z.index)
    for name in NODES:
        z.loc[hits[name]&hits.sum(axis=1).eq(1),"最终港/站"]=name
    return z

def show_arrival_workbench(frame, eta_range=None, eta_enabled=True):
    import pydeck as pdk
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
    flags=["已到港/站","已卸柜","已提柜","已送仓","已还空"]
    labels=list(NODES)+["其他/待核实"]
    summary=z.groupby("最终港/站").agg(总柜量=("排柜单号","size"),**{k:(k,"sum") for k in flags}).reindex(labels,fill_value=0)
    summary["未记录实际到港/站"]=summary["总柜量"]-summary["已到港/站"]
    cols=st.columns(4)
    for c,(name,val) in zip(cols,[("全美总柜量",len(z)),("六大港/站柜量",int(summary.loc[list(NODES),"总柜量"].sum())),("实际已到港/站",int(z["已到港/站"].sum())),("其他/待核实",int(summary.loc["其他/待核实","总柜量"]))]):
        c.metric(name,f"{val:,}")
    st.caption(f"ETA直接取值 {int(z['日期来源'].eq('ETA日期').sum()):,}；预计卸柜兜底 {int(z['日期来源'].eq('目的港预计卸柜时间').sum()):,}；筛选前缺有效日期 {int(all_rows['统计日期'].isna().sum()):,}。")
    st.subheader("美国六大港口与铁路站场运营地图")
    points=pd.DataFrame([dict(name=n,lat=lat,lon=lon,count=int(summary.loc[n,"总柜量"]),label=f"{n} {int(summary.loc[n,'总柜量']):,}柜",radius=14+min(26,int(summary.loc[n,"总柜量"])**0.5)) for n,(lat,lon,_) in NODES.items()])
    layers=[pdk.Layer("ScatterplotLayer",points,get_position="[lon, lat]",get_radius="radius",radius_units="pixels",get_fill_color=[235,105,40,175],pickable=True),pdk.Layer("TextLayer",points,get_position="[lon, lat]",get_text="label",get_size=14,get_color=[30,30,30],get_pixel_offset=[0,-35],pickable=False)]
    st.pydeck_chart(pdk.Deck(layers=layers,initial_view_state=pdk.ViewState(latitude=37.5,longitude=-96,zoom=3.3),map_style="light",tooltip={"text":"{name}: {count} 柜"}))
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
    st.subheader("船公司与航次")
    keys=[k for k in ["最终港/站","卸货港","船公司","实际船名","实际航次"] if k in detail]
    st.dataframe(detail.groupby(keys,dropna=False).size().reset_index(name="柜量"),hide_index=True,use_container_width=True)
    st.subheader("货柜明细")
    fields=[k for k in ["排柜单号","箱号","目的地","最终港/站","目的仓物流区域","统计日期","日期来源","ETA日期","卸货港ETA日期","实际海运到港","实际到港/站","实际卸柜","港后拖车行","LFD","进口实际提箱时间","实际送仓时间","实际还柜日期"] if k in detail]
    st.dataframe(detail[fields],hide_index=True,use_container_width=True)
    st.download_button("下载货柜明细 CSV",detail[fields].to_csv(index=False).encode("utf-8-sig"),"arrival_details.csv","text/csv")
