"""Customs broker master data, with evidence-based initialization from business fields."""
import pandas as pd
import streamlit as st
from db_backend import connect as db_connect, is_neon
from auth import is_admin

BROKER_FIELDS=("清关行","清关代理","报关行","报关代理","Customs Broker","Customs Broker Name","customs_broker","broker_name","Broker")

def columns(conn,table):
    if is_neon():
        return {r["column_name"] for r in conn.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=?",(table,)).fetchall()}
    return {r["name"] for r in conn.execute("PRAGMA table_info("+table+")").fetchall()}

def exists(conn,table):
    if is_neon():
        return bool(conn.execute("SELECT 1 FROM information_schema.tables WHERE table_schema=current_schema() AND table_name=?",(table,)).fetchone())
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone())

def initialize(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS gtms_customs_brokers (
        broker_id BIGINT PRIMARY KEY,
        broker_name TEXT NOT NULL,
        broker_code TEXT NOT NULL DEFAULT '',
        country_code TEXT NOT NULL DEFAULT '',
        state_code TEXT NOT NULL DEFAULT '',
        operating_region_code TEXT NOT NULL DEFAULT '',
        contact_name TEXT NOT NULL DEFAULT '',
        email TEXT NOT NULL DEFAULT '',
        phone TEXT NOT NULL DEFAULT '',
        aliases TEXT NOT NULL DEFAULT '',
        enabled INTEGER NOT NULL DEFAULT 1,
        notes TEXT NOT NULL DEFAULT '',
        created_from_business INTEGER NOT NULL DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS gtms_customs_broker_sources (
        source_field TEXT NOT NULL,
        source_name TEXT NOT NULL,
        broker_id BIGINT NOT NULL,
        record_count BIGINT NOT NULL DEFAULT 0,
        PRIMARY KEY(source_field,source_name),
        FOREIGN KEY(broker_id) REFERENCES gtms_customs_brokers(broker_id)
    )""")
    if not exists(conn,"containers"):
        return [],0
    available=columns(conn,"containers")
    matched=[field for field in BROKER_FIELDS if field in available]
    known={str(r["broker_name"]).casefold():r["broker_id"] for r in conn.execute("SELECT broker_id,broker_name FROM gtms_customs_brokers").fetchall()}
    source_map={(r["source_field"],r["source_name"]):r["broker_id"] for r in conn.execute("SELECT source_field,source_name,broker_id FROM gtms_customs_broker_sources").fetchall()}
    next_id=int(conn.execute("SELECT COALESCE(MAX(broker_id),0)+1 AS n FROM gtms_customs_brokers").fetchone()["n"])
    added=0
    for field in matched:
        quoted='"'+field.replace('"','""')+'"'
        rows=conn.execute(f"SELECT TRIM({quoted}) AS name,COUNT(*) AS cnt FROM containers WHERE {quoted} IS NOT NULL AND TRIM({quoted})<>'' GROUP BY TRIM({quoted})").fetchall()
        seen=set()
        for row in rows:
            name=str(row["name"]).strip()
            if name.casefold() in ("nan","null","none","n/a","未知","-","--"):
                continue
            seen.add(name)
            cid=source_map.get((field,name)) or known.get(name.casefold())
            if cid is None:
                cid=next_id
                next_id+=1
                conn.execute("INSERT INTO gtms_customs_brokers(broker_id,broker_name,created_from_business) VALUES (?,?,1)",(cid,name))
                known[name.casefold()]=cid
                added+=1
            conn.execute("""INSERT INTO gtms_customs_broker_sources(source_field,source_name,broker_id,record_count)
                VALUES (?,?,?,?) ON CONFLICT(source_field,source_name)
                DO UPDATE SET record_count=excluded.record_count""",(field,name,cid,int(row["cnt"])))
        for old in conn.execute("SELECT source_name FROM gtms_customs_broker_sources WHERE source_field=?",(field,)).fetchall():
            if old["source_name"] not in seen:
                conn.execute("UPDATE gtms_customs_broker_sources SET record_count=0 WHERE source_field=? AND source_name=?",(field,old["source_name"]))
    return matched,added

def show_customs_brokers(user,db):
    st.title("清关行管理")
    st.caption("清关行主数据 · 整数 broker_id · 增加 / 修改 / 删除 / 查询")
    with db_connect(db) as conn:
        matched,added=initialize(conn)
        records=[dict(r) for r in conn.execute("""SELECT b.*,COALESCE((SELECT SUM(s.record_count) FROM gtms_customs_broker_sources s WHERE s.broker_id=b.broker_id),0) AS business_count
            FROM gtms_customs_brokers b ORDER BY b.broker_id""").fetchall()]
        sources=[dict(r) for r in conn.execute("SELECT source_field,source_name,broker_id,record_count FROM gtms_customs_broker_sources ORDER BY record_count DESC").fetchall()]
    a,b,c=st.columns(3)
    a.metric("清关行数量",len(records))
    b.metric("业务来源名称",len(sources))
    c.metric("本次新增",added)
    if not matched:
        st.warning("业务表中未找到明确的清关行字段。不会把「货代」自动认定为清关行；请手工新增，或在业务导入表中提供「清关行」字段。")
    else:
        st.caption("识别到的清关行字段："+", ".join(matched))
    tab1,tab2=st.tabs(["查询主数据","业务来源映射"])
    with tab1:
        query=st.text_input("按名称、代码、国家、区域查询")
        filtered=[r for r in records if query.casefold() in " ".join(str(r.get(k,"")) for k in ("broker_name","broker_code","country_code","state_code","operating_region_code","aliases")).casefold()]
        st.dataframe(pd.DataFrame(filtered),hide_index=True,use_container_width=True)
        st.download_button("导出全部清关行",pd.DataFrame(records).to_csv(index=False).encode("utf-8-sig"),"gtms_customs_brokers.csv","text/csv")
    with tab2:
        st.dataframe(pd.DataFrame(sources),hide_index=True,use_container_width=True)
        st.download_button("导出来源映射",pd.DataFrame(sources).to_csv(index=False).encode("utf-8-sig"),"gtms_customs_broker_sources.csv","text/csv")
    if not is_admin(user):
        return
    st.subheader("增加 / 修改")
    options={str(r["broker_id"]):r for r in records}
    choice=st.selectbox("选择记录",["新增"]+list(options),format_func=lambda k:"新增清关行" if k=="新增" else f"{k} · {options[k]['broker_name']}")
    current=options.get(choice,{})
    with st.form("broker_edit"):
        name=st.text_input("清关行名称",current.get("broker_name",""))
        code=st.text_input("清关行代码",current.get("broker_code",""))
        country=st.text_input("国家代码",current.get("country_code",""))
        state=st.text_input("州/省代码",current.get("state_code",""))
        region=st.text_input("运营区域",current.get("operating_region_code",""))
        contact=st.text_input("联系人",current.get("contact_name",""))
        email=st.text_input("邮箱",current.get("email",""))
        phone=st.text_input("电话",current.get("phone",""))
        aliases=st.text_input("别名",current.get("aliases",""))
        enabled=st.checkbox("启用",value=bool(current.get("enabled",1)))
        notes=st.text_area("备注",current.get("notes",""))
        save=st.form_submit_button("保存")
    if save:
        if not name.strip():
            st.error("名称不能为空")
            return
        values=(name.strip(),code.strip(),country.strip().upper(),state.strip().upper(),region.strip().upper(),contact.strip(),email.strip(),phone.strip(),aliases.strip(),int(enabled),notes.strip())
        with db_connect(db) as conn:
            if choice=="新增":
                new_id=int(conn.execute("SELECT COALESCE(MAX(broker_id),0)+1 AS n FROM gtms_customs_brokers").fetchone()["n"])
                conn.execute("""INSERT INTO gtms_customs_brokers
                    (broker_id,broker_name,broker_code,country_code,state_code,operating_region_code,contact_name,email,phone,aliases,enabled,notes)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",(new_id,)+values)
            else:
                conn.execute("""UPDATE gtms_customs_brokers SET broker_name=?,broker_code=?,country_code=?,state_code=?,operating_region_code=?,
                    contact_name=?,email=?,phone=?,aliases=?,enabled=?,notes=? WHERE broker_id=?""",values+(int(choice),))
        st.success("保存成功")
        st.rerun()
    st.subheader("删除")
    if not options:
        return
    target=st.selectbox("选择删除对象",list(options),format_func=lambda k:f"{k} · {options[k]['broker_name']}",key="broker_delete")
    with st.form("broker_delete_form"):
        confirmed=st.checkbox("确认永久删除此清关行")
        delete=st.form_submit_button("删除")
    if delete:
        if not confirmed:
            st.error("请确认删除")
            return
        with db_connect(db) as conn:
            count=conn.execute("SELECT COUNT(*) AS n FROM gtms_customs_broker_sources WHERE broker_id=?",(int(target),)).fetchone()["n"]
            if count:
                st.error("该清关行存在业务来源关联，禁止删除。请先调整映射。")
                return
            conn.execute("DELETE FROM gtms_customs_brokers WHERE broker_id=?",(int(target),))
        st.success("删除成功")
        st.rerun()
