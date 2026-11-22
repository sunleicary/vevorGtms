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
    today=pd.Timestamp(date.today())
    def parsed(field):
        return pd.to_datetime(val(field),errors="coerce") if field else pd.NaT
    def valid(field):
        d=parsed(field)
        return pd.notna(d) and d.date()<=today.date()
    def shown(field):
        return val(field) if field and pd.notna(parsed(field)) else "未记录"
    region=val("目的仓物流区域").casefold()
    rail=any(x in region for x in ("芝加哥","chicago","亚特兰大","atlanta"))
    delivery="实际送仓时间"
    if pd.isna(parsed(delivery)) and pd.notna(parsed("实际到海外仓日期")):
        delivery="实际到海外仓日期"
    events=[("发船","ATD日期","ETDDATE"),("抵达海运港口","卸货港ATA日期","卸货港ETA日期")]
    if rail:
        events.append(("抵达铁路站场","ATA日期","ETA日期"))
    events.extend([("目的港/站卸柜","目的港/站卸柜日期","目的港预计卸柜时间"),("提柜","进口实际提箱时间",None),("送仓",delivery,"约仓时间"),("还空","实际还柜日期",None)])
    def deadline_status(actual,limit):
        due=parsed(limit)
        if pd.isna(due):
            return "缺少截止日期，无法判断"
        end=parsed(actual).date() if valid(actual) else today.date()
        delta=(end-due.date()).days
        if delta>0:
            return f"超期 {delta} 天" if valid(actual) else f"已过截止日 {delta} 天，未记录完成"
        if valid(actual):
            return "未超期"
        return "今日截止" if delta==0 else f"距截止日 {-delta} 天"
    pickup_status=deadline_status("进口实际提箱时间","LFD")
    return_status=deadline_status("实际还柜日期","预计还柜时间")
    completed=sum(valid(field) for _,field,_ in events)
    first=parsed("ATD日期")
    last=parsed("实际还柜日期") if valid("实际还柜日期") else today
    duration=(last.date()-first.date()).days if valid("ATD日期") else None
    cols=st.columns(3)
    cols[0].metric("已记录运输节点",f"{completed}/{len(events)}")
    cols[1].metric("自发船累计天数",f"{duration} 天" if duration is not None and duration>=0 else "待核实")
    cols[2].metric("提柜LFD状态",pickup_status)
    st.progress(completed/len(events))
    st.caption("进度为有效实际日期记录比例，不代表实时运输进度。")
    st.write("还空截止日状态："+return_status)
    previous=pd.NaT
    for i,(name,field,plan) in enumerate(events,1):
        actual=parsed(field)
        done=valid(field)
        planned=parsed(plan)
        elapsed=(actual.date()-previous.date()).days if done and pd.notna(previous) else None
        status="🟢 已记录" if done else "⚪ 未记录"
        if not done and pd.notna(actual):
            status="🟠 实际日期在未来，待核实"
        elif not done and pd.notna(planned):
            status="🔵 预计到达/完成" if planned.date()>=today.date() else "🟠 计划日期已过，未记录完成"
        if elapsed is not None and elapsed<0:
            status="🔴 时间顺序异常"
        with st.container(border=True):
            left,right=st.columns([3,2])
            left.markdown(f"**{i:02d} · {name}**")
            left.caption(status)
            right.markdown(f"**{shown(field)}**")
            right.caption("实际日期 · "+field)
            if plan:
                st.caption(f"计划日期：{shown(plan)} · {plan}")
            if elapsed is not None and elapsed>=0:
                st.caption(f"距上一节点 {elapsed} 天")
            if field in ("进口实际提箱时间","实际还柜日期"):
                limit="LFD" if field=="进口实际提箱时间" else "预计还柜时间"
                risk=pickup_status if limit=="LFD" else return_status
                msg=f"截止日期：{shown(limit)} · {risk}"
                if "超期" in risk and risk!="未超期" or "已过截止日" in risk:
                    st.error(msg)
                elif risk=="未超期":
                    st.success(msg)
                else:
                    st.warning(msg)
        previous=actual if done else pd.NaT
    st.caption("铁路到站采用ATA日期，卸柜采用目的港/站卸柜日期；海运到港采用卸货港ATA日期。还空截止日按系统现有预计还柜时间口径，超期为日历天差，不代表确认罚金。")
    if any(f not in row.index for f in ("ATD日期","卸货港ATA日期")):
        st.info("请重新导入全量源表以补齐海运日期字段。")
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
