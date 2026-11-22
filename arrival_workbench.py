"""Arrival-centric read-only operating workbench."""
from datetime import date, timedelta
import pandas as pd
import streamlit as st

def build_arrivals(frame, today):
    z=frame.copy()
    def txt(col):
        return z.get(col,pd.Series("",index=z.index)).fillna("").astype(str).str.strip()
    def dt(col):
        return pd.to_datetime(txt(col),errors="coerce",format="mixed").dt.normalize()
    z["实际到港/站"]=dt("目的港/站卸柜日期")
    z["预计到港/站"]=dt("ETA日期").fillna(dt("目的港预计卸柜时间"))
    z["已提柜"]=dt("进口实际提箱时间").le(today)
    z["已送仓"]=dt("实际送仓时间").fillna(dt("实际到海外仓日期")).le(today)
    z["已还空"]=dt("实际还柜日期").le(today)
    region=txt("目的仓物流区域")
    country=txt("目的仓国家").str.casefold()
    us=country.isin(["美国","us","usa","united states","united states of america"])
    raw_port=txt("卸货港")
    chicago=us & region.str.contains("芝加哥|chicago|美中IL",case=False,regex=True)
    atlanta=us & region.str.contains("亚特兰大|atlanta|美南GA",case=False,regex=True) & ~region.str.contains("萨凡纳|savannah|SAV",case=False,regex=True)
    rail=chicago | atlanta
    z["原始卸货港"]=raw_port
    z["海运卸货港"]=raw_port.replace("","港口未记录")
    aliases=[
        ("洛杉矶/长滩港",r"洛杉矶|长滩|los[ _-]*angeles|long[ _-]*beach|\bUSLAX\b|\bUSLGB\b|\bLAX\b|\bLGB\b"),
        ("纽约/新泽西港",r"纽约|新泽西|new[ _-]*york|new[ _-]*jersey|newark|elizabeth|\bUSNYC\b|\bUSEWR\b"),
        ("休斯顿港",r"休斯顿|houston|\bUSHOU\b"),
        ("萨凡纳港",r"萨凡纳|savannah|\bUSSAV\b"),
    ]
    for label,pattern in aliases:
        mask=raw_port.str.contains(pattern,case=False,regex=True)
        z.loc[mask,"海运卸货港"]=label
    z["线路核对"]=""
    for mask, gateway in ((chicago,"洛杉矶/长滩港"),(atlanta,"萨凡纳港")):
        conflict=mask & raw_port.ne("") & z["海运卸货港"].ne(gateway)
        z.loc[conflict,"线路核对"]="原始卸货港与标准线路不一致，待核实"
        z.loc[mask & ~conflict,"海运卸货港"]=gateway
    z["铁路站口原始值"]=txt("铁路站口").replace("",pd.NA).fillna(txt("目的铁路站").replace("",pd.NA)).fillna("")
    z["运输类型"]="海运"
    z.loc[rail,"运输类型"]="铁路到站（区域口径）"
    z["港口/铁路站"]=z["海运卸货港"]
    z.loc[chicago,"港口/铁路站"]="芝加哥铁路站"
    z.loc[atlanta,"港口/铁路站"]="亚特兰大铁路站"
    z["海运船公司"]=txt("船公司")
    z["海运船名"]=txt("实际船名")
    z["海运航次"]=txt("实际航次")
    z["承运人"]=txt("船公司").replace("","未记录")
    z["班次"]=txt("实际船名")+" / "+txt("实际航次")
    z["班次可识别"]=txt("实际船名").ne("") & txt("实际航次").ne("")
    z.loc[rail,"承运人"]=txt("铁路公司").loc[rail].replace("","铁路承运人未记录")
    z.loc[rail,"班次"]=txt("铁路班次").loc[rail].replace("","铁路班次未记录")
    z.loc[rail,"班次可识别"]=txt("铁路班次").loc[rail].ne("") & txt("铁路公司").loc[rail].ne("")
    z.loc[~z["班次可识别"],"班次"]="班次未完整记录"
    # Coastal ETA is not a reliable rail ETA; use the destination unloading estimate or explicit station ETA.
    z.loc[rail,"预计到港/站"]=dt("预计到站时间").fillna(dt("目的港预计卸柜时间")).loc[rail]
    z["国家"]=txt("目的仓国家")
    actual=z[z["实际到港/站"].between(today-pd.Timedelta(days=14),today)].copy()
    future=z[z["实际到港/站"].isna() & z["预计到港/站"].between(today,today+pd.Timedelta(days=14))].copy()
    overdue=z[z["实际到港/站"].isna() & z["预计到港/站"].lt(today)].copy()
    missing=z[z["实际到港/站"].isna() & z["预计到港/站"].isna()].copy()
    return actual,future,overdue,missing

def summarize(z, actual):
    day="实际到港/站" if actual else "预计到港/站"
    keys=["国家","运输类型","港口/铁路站","海运卸货港","承运人","班次","班次可识别",day]
    x=z.groupby(keys,dropna=False).agg(业务柜量=("排柜单号","size"),已提柜=("已提柜","sum"),已送仓=("已送仓","sum"),已还空=("已还空","sum")).reset_index()
    if actual:
        x["待送仓"]=x["业务柜量"]-x["已送仓"]
        x["送仓率"]=(100*x["已送仓"]/x["业务柜量"]).round(1)
    else:
        x=x[keys+["业务柜量"]]
    return x.sort_values([day,"港口/铁路站","承运人","班次"])

def show_arrival_workbench(frame):
    today=pd.Timestamp(date.today())
    actual,future,overdue,missing=build_arrivals(frame,today)
    st.title("港口与铁路到站动态监控中心")
    st.caption(f"实际到港/站：{(today-pd.Timedelta(days=14)).date()} 至 {today.date()} ｜ 预计：{today.date()} 至 {(today+pd.Timedelta(days=14)).date()}。独立滚动窗口，沿用左侧区域与供应商，不受左侧ETA筛选截断。")
    st.warning("仅统计本企业业务柜（排柜单号），不是整船载箱量。铁路站口、铁路承运人、铁路班次缺失时不推断；铁路到站预测使用目的港预计卸柜时间或明确到站时间，不使用海运ETA。")
    locations=sorted(set(pd.concat([actual,future,overdue,missing])["港口/铁路站"]))
    selected=st.multiselect("港口 / 铁路站（不选表示全部）",locations,key="arrival_location_normalized")
    if selected:
        actual,future,overdue,missing=[x[x["港口/铁路站"].isin(selected)] for x in (actual,future,overdue,missing)]
    st.caption("芝加哥与亚特兰大按最终铁路站归类；海运卸货港单独保留。原始线路冲突标记待核实。")
    a,b,c,d,e=st.columns(5)
    a.metric("近两周实际到港/站",len(actual))
    b.metric("已送仓",int(actual["已送仓"].sum()))
    c.metric("到港待送仓",int((~actual["已送仓"]).sum()))
    d.metric("未来两周预计到港/站",len(future))
    e.metric("逾期未记录到港/站",len(overdue))
    combined=pd.concat([actual.assign(类别="实际到港/站"),future.assign(类别="预计到港/站")])
    if not combined.empty:
        st.subheader("港口 / 铁路站柜量对比")
        st.bar_chart(combined.groupby(["港口/铁路站","类别"]).size().unstack(fill_value=0))
    for i,(tab,z,is_actual) in enumerate(zip(st.tabs(["近两周实际到港/站","未来两周预计到港/站","逾期及缺失日期"]),[actual,future,overdue],[True,False,False])):
        with tab:
            if i==2:
                st.caption(f"预计日期早于今天且未记录实际到港：{len(overdue)}柜；缺少有效预计日期：{len(missing)}柜。")
                z=pd.concat([overdue.assign(异常="预计日期已过"),missing.assign(异常="缺少预计日期")])
            else:
                report=summarize(z,is_actual)
                known=z[z["班次可识别"]]
                count=known[["国家","港口/铁路站","承运人","班次"]].drop_duplicates().shape[0]
                st.caption(f"可识别航次/班次组合：{count}；无法识别班次的业务柜：{len(z)-len(known)}。日期分组可能因同一航次分批卸柜产生多行。")
                st.dataframe(report,hide_index=True,use_container_width=True)
                st.download_button("下载航次统计 CSV",report.to_csv(index=False).encode("utf-8-sig"),f"arrival_summary_{i}.csv","text/csv",key=f"arrival_summary_{i}")
                day="实际到港/站" if is_actual else "预计到港/站"
                if not z.empty:
                    st.bar_chart(z.groupby(day).size())
                groups=list(z.groupby(["港口/铁路站","承运人","班次"],dropna=False).groups)
                chosen=st.selectbox("选择航次查看货柜明细", [None]+groups,format_func=lambda x:"全部" if x is None else " | ".join(map(str,x)),key=f"arrival_voyage_{i}")
                if chosen is not None:
                    z=z[(z["港口/铁路站"]==chosen[0]) & (z["承运人"]==chosen[1]) & (z["班次"]==chosen[2])]
            fields=[k for k in ["排柜单号","箱号","港口/铁路站","海运卸货港","原始卸货港","铁路站口原始值","线路核对","海运船公司","海运船名","海运航次","承运人","班次","实际到港/站","预计到港/站","港后拖车行","实际送货仓","目的仓","进口实际提箱时间","实际送仓时间","实际到海外仓日期","实际还柜日期","LFD","异常"] if k in z]
            st.dataframe(z[fields],hide_index=True,use_container_width=True)
            st.download_button("下载货柜明细 CSV",z[fields].to_csv(index=False).encode("utf-8-sig"),f"arrival_detail_{i}.csv","text/csv",key=f"arrival_detail_{i}")
