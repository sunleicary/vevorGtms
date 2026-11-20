"""Contract lane tariff management for post-port drayage tender workbooks."""
import json
import hashlib
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
from auth import is_admin
from db_backend import connect as db_connect

IDENTITY=["中标物流商","中标份额","大区","国家","线路名称","起始点","目的点"]
REQUIRED=["中标物流商","线路名称","起始点","目的点","卡车拖车费"]
def _parse(upload):
    frame=pd.read_excel(upload,sheet_name=0,dtype=object)
    frame=frame.loc[:,[c for c in frame.columns if isinstance(c,str) and c.strip()]]
    missing=[c for c in REQUIRED if c not in frame.columns]
    if missing:raise ValueError("缺少必要字段："+", ".join(missing))
    frame=frame.dropna(subset=["中标物流商","线路名称"]).copy()
    frame=frame.where(pd.notna(frame),None)
    return frame

def _key(record):
    raw=json.dumps([str(record.get(c) or "").strip() for c in
        ("中标物流商","大区","国家","线路名称","起始点","目的点")],ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _init(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS gtms_postport_contract_rates (
        rate_key TEXT PRIMARY KEY, supplier_name TEXT NOT NULL,
        bid_share TEXT NOT NULL DEFAULT '', region TEXT NOT NULL DEFAULT '',
        country TEXT NOT NULL DEFAULT '', lane_name TEXT NOT NULL,
        origin TEXT NOT NULL DEFAULT '', destination TEXT NOT NULL DEFAULT '',
        base_rate TEXT, charges_json TEXT NOT NULL DEFAULT '{}',
        remark TEXT NOT NULL DEFAULT '', source_file TEXT NOT NULL DEFAULT '',
        imported_at TEXT NOT NULL, updated_by TEXT NOT NULL DEFAULT '',
        effective_from TEXT NOT NULL DEFAULT '', effective_to TEXT NOT NULL DEFAULT '',
        enabled INTEGER NOT NULL DEFAULT 1
    )""")

def show_contract_rates(user,db):
    st.title("港后拖车行合同管理 · 线路报价")
    st.caption("以中标结果表建立供应商×线路报价台账；保留所有附加费原始字段，不自动推定合同生效期。")
    with db_connect(db) as conn:
        _init(conn)
        rates=[dict(r) for r in conn.execute("SELECT * FROM gtms_postport_contract_rates ORDER BY region,supplier_name,lane_name").fetchall()]
    if is_admin(user):
        with st.expander("导入中标结果 Excel / 更新合同报价",expanded=not rates):
            uploaded=st.file_uploader("上传美国港后拖车中标结果 .xlsx",type=["xlsx"],key="contract_tariff_upload")
            if uploaded is not None:
                try:
                    frame=_parse(uploaded)
                    st.write(f"识别 {len(frame)} 条报价，{frame['中标物流商'].nunique()} 家供应商")
                    st.dataframe(frame.head(15),hide_index=True,use_container_width=True)
                    st.warning("相同供应商+区域+线路+起终点的报价将更新；其他历史线路不删除。请确认文件为授权的最新版报价。")
                    confirm=st.checkbox("确认导入并更新报价",key="tariff_confirm")
                    if st.button("执行合同报价导入",disabled=not confirm,type="primary"):
                        stamp=datetime.now(timezone.utc).isoformat()
                        with db_connect(db) as conn:
                            _init(conn)
                            for _,line in frame.iterrows():
                                data={str(k):v for k,v in line.items()}
                                def value(k):
                                    v=data.get(k)
                                    return "" if v is None else str(v).strip()
                                extras={k:data[k] for k in data if k not in IDENTITY+["卡车拖车费","备注"] and data[k] is not None}
                                conn.execute("""INSERT INTO gtms_postport_contract_rates
                                    (rate_key,supplier_name,bid_share,region,country,lane_name,origin,destination,
                                     base_rate,charges_json,remark,source_file,imported_at,updated_by)
                                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                                    ON CONFLICT(rate_key) DO UPDATE SET bid_share=excluded.bid_share,
                                    base_rate=excluded.base_rate,charges_json=excluded.charges_json,
                                    remark=excluded.remark,source_file=excluded.source_file,
                                    imported_at=excluded.imported_at,updated_by=excluded.updated_by""",
                                    (_key(data),value("中标物流商"),value("中标份额"),value("大区"),
                                     value("国家"),value("线路名称"),value("起始点"),value("目的点"),
                                     value("卡车拖车费"),json.dumps(extras,ensure_ascii=False,default=str),
                                     value("备注"),uploaded.name,stamp,user.get("username","")))
                        st.success(f"已导入/更新 {len(frame)} 条线路报价。")
                        st.rerun()
                except Exception as exc:
                    st.error(f"报价文件解析或导入失败：{exc}")
    if not rates:
        st.info("当前数据库暂无合同报价。请管理员上传中标结果Excel并确认导入。")
        return
    a,b,c=st.columns(3)
    a.metric("线路报价",len(rates))
    b.metric("报价供应商",len({r["supplier_name"] for r in rates}))
    c.metric("线路名称",len({r["lane_name"] for r in rates}))
    suppliers=sorted({r["supplier_name"] for r in rates})
    regions=sorted({r["region"] for r in rates})
    x,y,z=st.columns(3)
    supplier=x.selectbox("物流商",["全部"]+suppliers)
    region=y.selectbox("大区",["全部"]+regions)
    keyword=z.text_input("线路 / 起点 / 目的点")
    matched=[r for r in rates if (supplier=="全部" or r["supplier_name"]==supplier)
        and (region=="全部" or r["region"]==region)
        and keyword.casefold() in (r["lane_name"]+" "+r["origin"]+" "+r["destination"]).casefold()]
    display=[]
    for r in matched:
        item={"报价ID":r["rate_key"][:12],"物流商":r["supplier_name"],
              "中标份额":r["bid_share"],"大区":r["region"],"国家":r["country"],
              "线路":r["lane_name"],"起点":r["origin"],"目的点":r["destination"],
              "卡车拖车费":r["base_rate"],"备注":r["remark"],
              "生效日":r["effective_from"],"截止日":r["effective_to"]}
        item.update(json.loads(r["charges_json"]))
        display.append(item)
    table=pd.DataFrame(display)
    st.dataframe(table,hide_index=True,use_container_width=True)
    st.download_button("导出当前合同线路报价",table.to_csv(index=False).encode("utf-8-sig"),
                       "postport_contract_rates.csv","text/csv")
    if is_admin(user) and matched:
        st.subheader("合同报价维护")
        keys={r["rate_key"]:r for r in matched}
        chosen=st.selectbox("选择线路报价",list(keys),format_func=lambda k:
                            f"{keys[k]['supplier_name']}｜{keys[k]['lane_name']}")
        selected=keys[chosen]
        with st.form("contract_rate_edit"):
            rate=st.text_input("卡车拖车费",selected["base_rate"] or "")
            start=st.text_input("生效日期 YYYY-MM-DD（可空）",selected["effective_from"])
            end=st.text_input("截止日期 YYYY-MM-DD（可空）",selected["effective_to"])
            enabled=st.checkbox("启用",value=bool(selected["enabled"]))
            save=st.form_submit_button("保存报价")
        if save:
            try:
                from datetime import date
                if start:date.fromisoformat(start)
                if end:date.fromisoformat(end)
                if start and end and start>end:raise ValueError("截止日期早于生效日期")
                if rate:float(rate)
                with db_connect(db) as conn:
                    conn.execute("""UPDATE gtms_postport_contract_rates SET base_rate=?,effective_from=?,
                        effective_to=?,enabled=?,updated_by=? WHERE rate_key=?""",
                        (rate.strip(),start.strip(),end.strip(),int(enabled),user.get("username",""),chosen))
                st.success("报价已更新")
                st.rerun()
            except ValueError as exc:
                st.error(f"报价或日期格式不正确：{exc}")
