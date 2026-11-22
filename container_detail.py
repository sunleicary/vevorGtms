"""Single-container detail view for the port operations dashboard."""
from datetime import date
from html import escape
import pandas as pd
import streamlit as st

def show_container_detail(data):
    st.markdown('<div style="font-size:20px;font-weight:700;line-height:1.4">港后货柜详情</div>',unsafe_allow_html=True)
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
    st.markdown(f'<div style="font-size:18px;font-weight:700;line-height:1.4;margin:4px 0 10px">货柜 {escape(val("柜号显示"))} <span style="font-size:11px;font-weight:500;color:#64748b"> · {escape(val("风险"))}</span></div>',unsafe_allow_html=True)
    metrics=[("船公司","船公司"),("船名","实际船名"),("航次","实际航次"),("最终ETA","ETA日期"),("最终ATA","ATA日期"),("提柜LFD","LFD"),("可提柜时间","可提柜时间"),("目的仓","目的仓"),("港后拖车商","港后拖车行")]
    cells=[]
    for label,field in metrics:
        cells.append(f'<div style="min-width:0;padding:9px 12px"><div style="font-size:11px;color:#64748b;margin-bottom:3px">{label}</div><div style="font-size:14px;color:#17324d;font-weight:600;overflow-wrap:anywhere;line-height:1.4">{escape(val(field))}</div></div>')
    st.markdown('<div style="background:#f8fafc;border:1px solid #dbe3ec;border-radius:9px;display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:2px;padding:4px">'+''.join(cells)+'</div>',unsafe_allow_html=True)
    st.markdown('<div style="font-size:14px;font-weight:700;margin:12px 0 4px">海柜全生命周期运输追踪</div>',unsafe_allow_html=True)
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
    events.extend([("目的港/站卸柜","目的港/站卸柜日期","目的港预计卸柜时间"),("可提柜","可提柜时间",None),("提柜","进口实际提箱时间",None),("送仓",delivery,"约仓时间"),("还空","实际还柜日期",None)])
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
    tracked=[field for _,field,_ in events if field!="可提柜时间" or pd.notna(parsed(field))]
    completed=sum(valid(field) for field in tracked)
    first=parsed("ATD日期")
    last=parsed("实际还柜日期") if valid("实际还柜日期") else today
    duration=(last.date()-first.date()).days if valid("ATD日期") else None
    icons=["M3 14 L12 10 L21 14 L18 19 H6 Z M7 12 V5 H17 V12 M12 5 V1 M2 22 Q5 19 8 22 T14 22 T22 22","M12 7 V22 M5 11 H19 M2 15 Q2 22 12 22 Q22 22 22 15 M9 4 A3 3 0 1 0 15 4 A3 3 0 1 0 9 4","M5 2 H19 V19 H5 Z M5 11 H19 M9 19 L5 23 M15 19 L19 23 M12 3 V11 M8 15 H10 M14 15 H16","M2 4 H22 V20 H2 Z M7 5 V19 M12 5 V19 M17 5 V19","M1 5 H15 V18 H1 Z M15 10 H20 L23 14 V18 H15 M3 19 A3 3 0 1 0 9 19 A3 3 0 1 0 3 19 M16 19 A3 3 0 1 0 22 19 A3 3 0 1 0 16 19","M2 9 L12 2 L22 9 V22 H2 Z M7 22 V12 H17 V22 M7 15 H17 M7 18 H17","M3 10 A9 9 0 1 1 5 19 M3 3 V10 H10 M8 13 L11 16 L17 9"]
    cards=[]
    records=[]
    previous=pd.NaT
    for i,(name,field,plan) in enumerate(events):
        actual=parsed(field)
        done=valid(field)
        planned=parsed(plan)
        elapsed=(actual.date()-previous.date()).days if done and pd.notna(previous) else None
        color="#15803d" if done else "#94a3b8"
        status="已记录" if done else "未记录"
        if not done and pd.notna(actual):
            color,status="#b45309","实际日期异常"
        elif not done and pd.notna(planned):
            color,status=("#2563eb","预计完成") if planned.date()>=today.date() else ("#b45309","计划已过")
        if field=="可提柜时间" and not done:
            status="待确认" if pd.isna(actual) else "日期待核实"
        if elapsed is not None and elapsed<0:
            color,status="#dc2626","顺序异常"
        limit="LFD" if field=="进口实际提箱时间" else "预计还柜时间" if field=="实际还柜日期" else None
        risk=deadline_status(field,limit) if limit else ""
        if risk and (risk.startswith("超期") or risk.startswith("已过截止日")):
            color,status="#dc2626","超期"
        icon="M4 12 L10 18 L21 5 M3 3 H15 M3 3 V21 H21 V13" if field=="可提柜时间" else icons[{"ATD日期":0,"卸货港ATA日期":1,"ATA日期":2,"目的港/站卸柜日期":3,"进口实际提箱时间":4,"实际还柜日期":6}.get(field,5)]
        short={"抵达海运港口":"海运到港","抵达铁路站场":"铁路到站","目的港/站卸柜":"卸柜"}.get(name,name)
        actual_text=actual.strftime("%Y-%m-%d") if pd.notna(actual) else "—"
        plan_text=planned.strftime("%Y-%m-%d") if pd.notna(planned) else "—"
        note=f"截止 {shown(limit)[:10]}" if limit else f"计划 {plan_text}" if plan else ""
        gap=f"间隔 {elapsed} 天" if elapsed is not None and elapsed>=0 else ""
        cards.append(f'<div style="flex:1;min-width:112px;text-align:center;position:relative;z-index:1;padding:0 3px"><div style="width:36px;height:36px;margin:auto;background:#fff;border:1.5px solid {color};border-radius:50%;display:flex;align-items:center;justify-content:center;color:{color}"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="{icon}"/></svg></div><div style="font-size:12px;font-weight:700;margin-top:6px;color:#17324d">{short}</div><div style="font-size:12px;font-weight:600;color:{color};margin-top:5px">{actual_text}</div><div style="font-size:11px;color:{color};margin-top:3px">{status}</div><div style="font-size:10px;color:#64748b;margin-top:5px">{escape(note)}</div><div style="font-size:10px;color:#64748b">{gap}</div></div>')
        records.append({"节点":name,"实际时间":shown(field),"实际来源":field,"计划时间":shown(plan) if plan else "—","截止日期":shown(limit) if limit else "—","状态":status,"超期判断":risk,"阶段耗时（天）":elapsed})
        if field!="可提柜时间" or done:
            previous=actual if done else pd.NaT
    st.markdown('<div style="background:#f8fafc;border:1px solid #dbe3ec;border-top:3px solid #f97316;border-radius:12px;padding:14px 10px 12px;overflow-x:auto"><div style="display:flex;position:relative;min-width:'+str(len(events)*118)+'px"><div style="position:absolute;left:7%;right:7%;top:18px;height:1px;background:#cbd5e1"></div>'+''.join(cards)+'</div></div>',unsafe_allow_html=True)
    stats=[("节点记录",f"{completed}/{len(tracked)}"),("累计耗时",f"{duration} 天" if duration is not None and duration>=0 else "待核实"),("提柜LFD",shown("LFD")),("提柜时效",pickup_status),("还空截止",return_status)]
    cards2=[]
    for label,value in stats:
        color="#dc2626" if value.startswith(("超期","已过截止日")) else "#15803d" if value=="未超期" else "#17324d"
        cards2.append(f'<div style="padding:8px 12px;min-width:0"><div style="font-size:11px;color:#64748b">{label}</div><div style="font-size:14px;font-weight:600;color:{color};margin-top:3px;overflow-wrap:anywhere">{escape(value)}</div></div>')
    st.markdown('<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(135px,1fr));gap:4px;background:#f8fafc;border:1px solid #dbe3ec;border-radius:8px">'+''.join(cards2)+'</div>',unsafe_allow_html=True)
    st.caption("可提柜时间仅显示已记录的码头/铁路站场可提柜时间；缺失时待确认，不用卸柜或清关日期推算。无可提柜记录时不计入节点完成率。")
    st.caption("绿色：已记录 ｜ 蓝色：预计 ｜ 橙色：需核实 ｜ 红色：超期/异常 ｜ 灰色：未记录")
    with st.expander("展开完整节点日期及超期明细"):
        st.dataframe(pd.DataFrame(records),hide_index=True,use_container_width=True)
    st.caption("铁路到站采用ATA日期，卸柜采用目的港/站卸柜日期；海运到港采用卸货港ATA日期。还空截止日按系统现有预计还柜时间口径，超期为日历天差，不代表确认罚金。")
    if any(f not in row.index for f in ("ATD日期","卸货港ATA日期")):
        st.info("请重新导入全量源表以补齐海运日期字段。")
    groups = [
        ("货柜基础信息", ["箱号","排柜单号","MB/L No.","目的仓物流区域","目的仓","目的仓国家"]),
        ("港前运输信息", ["货代","港前拖车行","ETDDATE"]),
        ("港后 · 海运及铁路运输信息", ["船公司","实际船名","实际航次","ATD日期","卸货港","卸货港ETA日期","卸货港ATA日期","目的地","ETA日期","ATA日期"]),
        ("港后 · 清关与提柜信息", ["目的港预计卸柜时间","目的港/站卸柜日期","海关放行时间","清关完成时间","进口查验开始日期","进口查验完成日期","可提柜时间","LFD","进口实际提箱时间"]),
        ("港后 · 拖车送仓信息", ["港后拖车行","约仓时间","实际送仓时间","实际到海外仓日期"]),
        ("港后 · 还空信息", ["预计还柜时间","实际还柜日期","港后内部备注"])]
    for i in range(0,len(groups),2):
        cols = st.columns(2)
        for col,(heading,fields) in zip(cols,groups[i:i+2]):
            with col:
                with st.container(border=True):
                    st.markdown(f'<div style="font-size:14px;font-weight:600">{escape(heading)}</div>',unsafe_allow_html=True)
                    st.markdown('<div style="font-size:12px;line-height:1.5">'+''.join(f'<div style="display:grid;grid-template-columns:minmax(100px,40%) 1fr;gap:8px;padding:5px 0;border-bottom:1px solid rgba(148,163,184,.22)"><span style="color:#64748b">{escape(f)}</span><span style="overflow-wrap:anywhere">{escape(val(f))}</span></div>' for f in fields)+'</div>',unsafe_allow_html=True)
    st.caption("注意：未记录不代表未发生；LFD风险基于Excel中的日期推算，不能代替码头实时核实。")
