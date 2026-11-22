"""Single-container detail view for the port operations dashboard."""
from datetime import date
import pandas as pd
import streamlit as st

def show_container_detail(data):
    st.subheader("📦 港后货柜详情")
    st.caption("逐柜查看 · 基于已导入业务数据，非实时码头/GPS状态")
    if data.empty:
        st.info("当前筛选条件下没有货柜。请调整左侧区域、拖车商或 ETA 范围。")
        return
    search = st.text_input("搜索箱号 / 排柜单号 / 提单号 / 船名", key="detail_search")
    matched = data
    if search.strip():
        fields = ["箱号", "排柜单号", "MB/L No.", "实际船名"]
        mask = data[fields].fillna("").astype(str).apply(
            lambda s: s.str.contains(search.strip(), case=False, regex=False)).any(axis=1)
        matched = data.loc[mask]
    if matched.empty:
        st.warning("未找到匹配货柜")
        return
    matched = matched.reset_index(drop=True)
    if st.session_state.get("detail_search_previous") != search:
        st.session_state.detail_position = 0
        st.session_state.detail_search_previous = search
    position = min(st.session_state.get("detail_position", 0), len(matched)-1)
    st.session_state.detail_position = position
    a,b,c,d = st.columns([1,1,2,3])
    if a.button("◀ 上一柜", disabled=position==0, key="detail_prev"):
        st.session_state.detail_position = position-1
        st.rerun()
    if b.button("下一柜 ▶", disabled=position>=len(matched)-1, key="detail_next"):
        st.session_state.detail_position = position+1
        st.rerun()
    options = list(range(len(matched)))
    chosen = c.selectbox("选择货柜", options, index=position,
        format_func=lambda i: f"{i+1}. {matched.iloc[i].get('柜号显示','') or matched.iloc[i].get('排柜单号','')}",
        key=f"detail_select_{search}_{position}")
    if chosen != position:
        st.session_state.detail_position = chosen
        st.rerun()
    d.caption(f"第 {position+1:,} / {len(matched):,} 柜（当前筛选结果）")
    row = matched.iloc[position]
    def val(field):
        v = row.get(field, "")
        return "—" if pd.isna(v) or str(v).strip() in ("", "nan", "NaT", "None") else str(v)
    st.markdown(f"### 🚢 {val('柜号显示')}  ·  {val('风险')}")
    metrics = [
        ("船公司", "船公司"), ("船名", "实际船名"), ("航次", "实际航次"),
        ("ETA", "ETA日期"), ("ATA", "ATA日期"), ("LFD", "LFD"),
        ("目的仓", "目的仓"), ("港后拖车商", "港后拖车行")]
    for i in range(0,len(metrics),4):
        cols = st.columns(4)
        for col,(label,field) in zip(cols,metrics[i:i+4]):
            col.metric(label,val(field))
    st.markdown("#### 海柜全生命周期运输追踪")
    region=val("目的仓物流区域")
    rail=any(x in region.casefold() for x in ("芝加哥","chicago","亚特兰大","atlanta"))
    events=[
        ("实际开船","ATD日期","ETDDATE"),
        ("实际抵达海港","卸货港ATA日期","卸货港ETA日期"),
    ]
    if rail:
        events.append(("铁路站场到站/卸柜","目的港/站卸柜日期","目的港预计卸柜时间"))
    events.extend([
        ("实际提柜","进口实际提箱时间",None),
        ("实际送仓","实际送仓时间","约仓时间"),
        ("实际还空","实际还柜日期","预计还柜时间"),
    ])
    def parsed(field):
        return pd.to_datetime(val(field),errors="coerce") if field else pd.NaT
    def shown(field):
        return val(field) if field and pd.notna(parsed(field)) else "未记录"
    items=[]
    previous=pd.NaT
    for i,(name,field,plan) in enumerate(events,1):
        if field=="实际送仓时间" and pd.isna(parsed(field)) and pd.notna(parsed("实际到海外仓日期")):
            field="实际到海外仓日期"
        actual=parsed(field)
        valid=pd.notna(actual) and actual.date()<=date.today()
        elapsed=None
        if valid and pd.notna(previous):
            elapsed=(actual.date()-previous.date()).days
        status="已记录" if valid else ("日期在未来，待核实" if pd.notna(actual) else "未记录")
        if elapsed is not None and elapsed<0:
            status="时间顺序异常，待核实"
        with st.container(border=True):
            left,right=st.columns([3,2])
            left.markdown(f"**{i}. {name}**")
            left.caption(f"字段：{field}")
            right.markdown(f"**{shown(field)}**")
            right.caption(status + (f" · 距上一阶段 {elapsed} 天" if elapsed is not None else ""))
            if plan:
                st.caption(f"计划/参考：{shown(plan)}（{plan}）")
        items.append({"运输阶段":name,"实际时间":shown(field),"来源字段":field,"计划/参考时间":shown(plan) if plan else "—","阶段耗时(天)":elapsed,"记录状态":status})
        previous=actual if valid else pd.NaT
    st.dataframe(pd.DataFrame(items),hide_index=True,use_container_width=True)
    if any(f not in row.index for f in ("ATD日期","卸货港ATA日期")):
        st.info("当前数据库尚未导入完整海运时间字段，请使用最新全量业务文件重新导入。缺失时间不会用预计日期代替。")
    st.caption("铁路站场按目的港/站卸柜日期统计，不代表已核实列车到站时刻；计划时间仅供参考。")
    groups = [
        ("📦 货柜基础信息", ["箱号","排柜单号","MB/L No.","目的仓物流区域","目的仓","目的仓国家","货代"]),
        ("🚢 港前运输信息", ["船公司","实际船名","实际航次","ETDDATE","ATD日期","卸货港ETA日期","卸货港ATA日期","ETA日期","ATA日期","卸货港","港前拖车行"]),
        ("⚓ 港后通关与放行", ["目的港/站卸柜日期","海关放行时间","清关完成时间","进口查验开始日期","进口查验完成日期","LFD"]),
        ("🚚 港后拖车送仓", ["港后拖车行","进口实际提箱时间","约仓时间","实际送仓时间","实际到海外仓日期"]),
        ("📭 还空信息", ["预计还柜时间","实际还柜日期","港后内部备注"])]
    for i in range(0,len(groups),2):
        cols = st.columns(2)
        for col,(heading,fields) in zip(cols,groups[i:i+2]):
            with col:
                with st.container(border=True):
                    st.markdown(f"**{heading}**")
                    st.dataframe(pd.DataFrame([{"字段":f,"数据":val(f)} for f in fields]),
                        hide_index=True,use_container_width=True)
    st.caption("注意：未记录不代表未发生；LFD风险基于Excel中的日期推算，不能代替码头实时核实。")
