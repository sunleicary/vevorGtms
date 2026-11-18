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
    st.markdown("#### 🚦 货柜物流节点")
    events = [
        ("预计到港 ETA","ETA日期"),
        ("实际到港 ATA","ATA日期"),
        ("卸船","目的港/站卸柜日期"),
        ("海关放行/清关完成","清关完成时间"),
        ("可提柜（无独立字段）",None),
        ("实际提柜","进口实际提箱时间"),
        ("实际送仓","实际送仓时间"),
        ("实际还空","实际还柜日期")]
    items = []
    for name,field in events:
        value = val(field) if field else "暂无数据"
        items.append({"节点":name,"时间":value,"记录状态":"有记录" if value not in ("—","暂无数据") else "待核实"})
    st.dataframe(pd.DataFrame(items),hide_index=True,use_container_width=True)
    groups = [
        ("📦 货柜基础信息", ["箱号","排柜单号","MB/L No.","目的仓物流区域","目的仓","目的仓国家","货代"]),
        ("🚢 港前运输信息", ["船公司","实际船名","实际航次","ETA日期","ATA日期","卸货港","港前拖车行"]),
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
