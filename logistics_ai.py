"""Natural-language reporting copilot: constrained plans, never model-generated SQL."""
import json
import os
import re
import urllib.request
from datetime import date, timedelta
import pandas as pd
import streamlit as st
from db_backend import connect as db_connect, read_sql

DIMENSIONS={"区域":"区域","港后拖车商":"港后拖车行","供应商":"港后拖车行","船公司":"船公司",
            "船名":"实际船名","目的仓":"目的仓物流区域","国家":"目的仓国家"}
DATE_COLUMNS={"ETA":"ETA日期","LFD":"LFD","ATA":"ATA日期"}
REGIONS={"洛杉矶":"洛杉矶","长滩":"洛杉矶","新泽西":"新泽西","休斯顿":"休斯顿",
         "芝加哥":"芝加哥","亚特兰大":"亚特兰大","萨凡纳":"萨凡纳"}
ALLOWED_GROUPS={"区域","港后拖车行","船公司","实际船名","目的仓物流区域","目的仓国家","周","日"}
def _clean(v):
    return str(v).strip() if pd.notna(v) else ""

def _local_plan(question, suppliers):
    q=question.strip()
    metric="柜量"
    if any(x in q for x in ("LFD","超期","到期","预警")):metric="LFD风险"
    group="区域"
    if "按周" in q or "每周" in q or "周度" in q:group="周"
    elif "按日" in q or "每天" in q:group="日"
    else:
        for word,field in DIMENSIONS.items():
            if any(x in q for x in ("按"+word,"各"+word,word+"分布",word+"排名",word+"对比")):
                group=field
                break
    date_field="LFD" if metric=="LFD风险" else "ETA日期"
    start=end=None
    today=date.today()
    if "未来7天" in q or "未来七天" in q:
        start=today.isoformat();end=(today+timedelta(days=7)).isoformat()
    elif "今天" in q:
        start=end=today.isoformat()
    elif "本周" in q:
        start=(today-timedelta(days=today.weekday())).isoformat()
        end=(date.fromisoformat(start)+timedelta(days=6)).isoformat()
    elif "本月" in q:
        start=today.replace(day=1).isoformat()
        end=(today.replace(day=28)+timedelta(days=4)).replace(day=1).__sub__(timedelta(days=1)).isoformat()
    # Explicit year is mandatory for numeric date ranges to avoid ambiguous results.
    matches=re.findall(r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})",q)
    if len(matches)>=2:
        start=date(*map(int,matches[0])).isoformat()
        end=date(*map(int,matches[1])).isoformat()
    elif len(matches)==1:
        start=end=date(*map(int,matches[0])).isoformat()
    region=next((v for k,v in REGIONS.items() if k in q),None)
    supplier=next((s for s in sorted(suppliers,key=len,reverse=True) if s and s.casefold() in q.casefold()),None)
    return {"metric":metric,"group":group,"date_field":date_field,"start":start,"end":end,
            "region":region,"supplier":supplier}

def _ai_plan(question,suppliers):
    key=os.environ.get("OPENAI_API_KEY","")
    try:
        if not key:key=str(st.secrets.get("OPENAI_API_KEY",""))
    except Exception:pass
    if not key:return None,"未配置在线模型密钥，使用本地规则理解。"
    model=os.environ.get("GTMS_AI_MODEL","gpt-4.1-mini")
    try:
        model=str(st.secrets.get("GTMS_AI_MODEL",model))
    except Exception:pass
    schema={"type":"object","additionalProperties":False,"properties":{
        "metric":{"type":"string","enum":["柜量","LFD风险"]},
        "group":{"type":"string","enum":sorted(ALLOWED_GROUPS)},
        "date_field":{"type":"string","enum":["ETA日期","LFD","ATA日期"]},
        "start":{"type":["string","null"]},"end":{"type":["string","null"]},
        "region":{"type":["string","null"]},"supplier":{"type":["string","null"]}},
        "required":["metric","group","date_field","start","end","region","supplier"]}
    payload={"model":model,"messages":[
        {"role":"system","content":"你是物流报表意图解析器。只输出指定JSON。不得编造数据。日期YYYY-MM-DD，未明确日期用null；仅按港后拖车行筛选供应商；只使用用户明确要求的区域、供应商。当前日期："+date.today().isoformat()+"。已知港后拖车商："+json.dumps(suppliers[:150],ensure_ascii=False)},
        {"role":"user","content":question}],
        "response_format":{"type":"json_schema","json_schema":{"name":"gtms_report_plan","strict":True,"schema":schema}}}
    req=urllib.request.Request("https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode(),headers={"Authorization":"Bearer "+key,
        "Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=20) as response:
            parsed=json.loads(json.loads(response.read())["choices"][0]["message"]["content"])
        return parsed,"在线AI已解析意图；统计仍由受控分析引擎执行。"
    except Exception:
        return None,"在线AI暂不可用，已回退到本地规则理解。"

def _validate_plan(plan, suppliers):
    if plan.get("metric") not in ("柜量","LFD风险"):raise ValueError("不支持的指标")
    if plan.get("group") not in ALLOWED_GROUPS:raise ValueError("不支持的分组维度")
    if plan.get("date_field") not in DATE_COLUMNS.values():raise ValueError("不支持的日期字段")
    for key in ("start","end"):
        if plan.get(key):plan[key]=date.fromisoformat(plan[key]).isoformat()
    if plan.get("start") and plan.get("end") and plan["start"]>plan["end"]:
        raise ValueError("起始日期不能晚于结束日期")
    if plan.get("region") and plan["region"] not in REGIONS.values():raise ValueError("区域不在允许范围")
    if plan.get("supplier") and plan["supplier"] not in suppliers:raise ValueError("供应商不存在于港后拖车行字段")
    return plan

def _region(value):
    v=_clean(value).lower()
    mapping={"新泽西":["新泽西","new jersey","-nj","nj-"],
        "洛杉矶":["洛杉矶","美西ca","los angeles","long beach"],
        "休斯顿":["休斯顿","houston","德州","texas"],
        "芝加哥":["芝加哥","chicago","伊利诺伊"],
        "亚特兰大":["亚特兰大","atlanta","佐治亚"],
        "萨凡纳":["萨凡纳","savannah"]}
    return next((k for k,terms in mapping.items() if any(t in v for t in terms)),"其他区域")

def _data():
    with db_connect(os.environ.get("GTMS_DB_PATH","")) as conn:
        return read_sql("SELECT * FROM containers",conn)

def show_logistics_ai(user,db):
    st.title("🤖 物流AI助理")
    st.caption("自然语言动态报表 · 数据源：GTMS containers · 只读分析，不执行AI生成SQL")
    with db_connect(db) as conn:
        df=read_sql("SELECT * FROM containers",conn)
    if df.empty:
        st.info("数据库尚无业务记录。")
        return
    if "排柜单号" in df:
        df=df.drop_duplicates(subset=["排柜单号"],keep="last")
    if "目的仓国家" in df:
        country=df["目的仓国家"].fillna("").astype(str).str.strip().str.lower()
        df=df[country.isin(["美国","usa","us","united states","united states of america"])]
    df=df.copy()
    df["区域"]=df.get("目的仓物流区域",pd.Series("",index=df.index)).map(_region)
    suppliers=sorted(set(df.get("港后拖车行",pd.Series("",index=df.index)).dropna().astype(str).str.strip())-{"","nan"})
    if "gtms_ai_messages" not in st.session_state:st.session_state["gtms_ai_messages"]=[]
    for m in st.session_state["gtms_ai_messages"][-8:]:
        with st.chat_message(m["role"]):st.write(m["content"])
    examples=["2026年11月1日至2026年12月31日按区域统计港后柜量",
              "未来7天LFD到期未提柜的货柜，按区域统计",
              "按港后拖车商对比柜量","按周统计港后柜量"]
    with st.expander("示例提问"):
        for i,example in enumerate(examples):
            if st.button(example,key=f"ai_example_{i}"):st.session_state["gtms_ai_question"]=example
    question=st.chat_input("例如：2026年11月1日至2026年12月31日按区域统计港后柜量")
    if not question:question=st.session_state.pop("gtms_ai_question",None)
    if not question:return
    st.session_state["gtms_ai_messages"].append({"role":"user","content":question})
    with st.chat_message("user"):st.write(question)
    with st.chat_message("assistant"):
        try:
            plan,note=_ai_plan(question,suppliers)
            if plan is None:plan=_local_plan(question,suppliers)
            plan=_validate_plan(plan,suppliers)
            filtered=df.copy()
            if plan["region"]:filtered=filtered[filtered["区域"]==plan["region"]]
            if plan["supplier"]:
                filtered=filtered[filtered["港后拖车行"].fillna("").astype(str).str.strip()==plan["supplier"]]
            col=plan["date_field"]
            if col not in filtered:raise ValueError(f"业务表中缺少日期字段：{col}")
            dt=pd.to_datetime(filtered[col],errors="coerce")
            if plan["start"]:filtered=filtered[dt>=pd.Timestamp(plan["start"])]
            dt=pd.to_datetime(filtered[col],errors="coerce")
            if plan["end"]:filtered=filtered[dt<pd.Timestamp(plan["end"])+pd.Timedelta(days=1)]
            if plan["metric"]=="LFD风险":
                if "进口实际提箱时间" not in filtered:raise ValueError("缺少实际提箱时间字段")
                picked=pd.to_datetime(filtered["进口实际提箱时间"],errors="coerce")
                filtered=filtered[picked.isna()].copy()
            group=plan["group"]
            if group=="周":
                filtered["统计分组"]=pd.to_datetime(filtered[col],errors="coerce").dt.to_period("W-SUN").astype(str)
            elif group=="日":
                filtered["统计分组"]=pd.to_datetime(filtered[col],errors="coerce").dt.strftime("%Y-%m-%d")
            else:
                if group not in filtered:raise ValueError(f"业务表缺少维度：{group}")
                filtered["统计分组"]=filtered[group].fillna("未填写").astype(str).str.strip().replace("","未填写")
            summary=filtered.groupby("统计分组",dropna=False).size().reset_index(name="柜量").sort_values("柜量",ascending=False)
            if group in ("周","日"):summary=summary.sort_values("统计分组")
            summary=summary.rename(columns={"统计分组":group})
            st.metric("符合条件的货柜数",f"{len(filtered):,}")
            st.caption(f"口径：{plan['metric']}｜日期字段：{col}｜范围：{plan['start'] or '不限'} ~ {plan['end'] or '不限'}｜分组：{group}｜区域：{plan['region'] or '全部'}｜港后拖车商：{plan['supplier'] or '全部'}")
            st.caption(note)
            if summary.empty:st.info("当前筛选条件下没有符合条件的记录。")
            else:
                st.bar_chart(summary.set_index(group)["柜量"])
                st.dataframe(summary,hide_index=True,use_container_width=True)
            st.download_button("下载统计报表 CSV",summary.to_csv(index=False).encode("utf-8-sig"),
                               "gtms_ai_report.csv","text/csv",key="gtms_ai_summary_"+str(len(st.session_state["gtms_ai_messages"])))
            detail_cols=[x for x in ("排柜单号","箱号","目的仓物流区域","港后拖车行","ETA日期","LFD","进口实际提箱时间") if x in filtered]
            with st.expander("查看明细与导出"):
                st.dataframe(filtered[detail_cols],hide_index=True,use_container_width=True)
                st.download_button("下载明细 CSV",filtered[detail_cols].to_csv(index=False).encode("utf-8-sig"),
                                   "gtms_ai_detail.csv","text/csv",key="gtms_ai_detail_"+str(len(st.session_state["gtms_ai_messages"])))
            response=f"已生成{plan['metric']}报表，共{len(filtered):,}柜，按{group}统计。"
            st.session_state["gtms_ai_messages"].append({"role":"assistant","content":response})
        except Exception as exc:
            st.error(f"无法生成报表：{exc}。请明确日期范围或更换统计维度。")
