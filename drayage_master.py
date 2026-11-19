"""Port-side drayage master: stage-specific source mappings and guarded CRUD."""
import pandas as pd
import streamlit as st
from auth import is_admin
from db_backend import connect as db_connect, is_neon

STAGES=("港前","港后")
SOURCES=(("港前","港前拖车行"),("港后","港后拖车行"))

def _columns(conn,table):
    if is_neon():
        return {r["column_name"] for r in conn.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=?",(table,)).fetchall()}
    return {r["name"] for r in conn.execute("PRAGMA table_info("+table+")").fetchall()}

def initialize(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS gtms_drayage_suppliers (
        supplier_id BIGINT PRIMARY KEY, stage TEXT NOT NULL CHECK(stage IN ('港前','港后')),
        supplier_name TEXT NOT NULL, supplier_code TEXT NOT NULL DEFAULT '',
        country_code TEXT NOT NULL DEFAULT '', state_code TEXT NOT NULL DEFAULT '',
        operating_region_code TEXT NOT NULL DEFAULT '', contact_name TEXT NOT NULL DEFAULT '',
        phone TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT '待核实', notes TEXT NOT NULL DEFAULT '',
        created_from_business INTEGER NOT NULL DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS gtms_drayage_supplier_sources (
        stage TEXT NOT NULL, source_name TEXT NOT NULL, supplier_id BIGINT NOT NULL,
        record_count BIGINT NOT NULL DEFAULT 0, PRIMARY KEY(stage,source_name),
        FOREIGN KEY(supplier_id) REFERENCES gtms_drayage_suppliers(supplier_id)
    )""")
    available=_columns(conn,"containers")
    found=[(stage,col) for stage,col in SOURCES if col in available]
    known={(r["stage"],r["supplier_name"].casefold()):r["supplier_id"] for r in conn.execute("SELECT supplier_id,stage,supplier_name FROM gtms_drayage_suppliers").fetchall()}
    mapping={(r["stage"],r["source_name"]):r["supplier_id"] for r in conn.execute("SELECT stage,source_name,supplier_id FROM gtms_drayage_supplier_sources").fetchall()}
    next_id=int(conn.execute("SELECT COALESCE(MAX(supplier_id),0)+1 AS n FROM gtms_drayage_suppliers").fetchone()["n"])
    added=0
    for stage,col in found:
        quoted='"'+col.replace('"','""')+'"'
        rows=conn.execute(f"SELECT TRIM({quoted}) AS name,COUNT(*) AS cnt FROM containers WHERE {quoted} IS NOT NULL AND TRIM({quoted})<>'' GROUP BY TRIM({quoted})").fetchall()
        seen=set()
        for row in rows:
            name=str(row["name"]).strip()
            seen.add(name)
            sid=mapping.get((stage,name)) or known.get((stage,name.casefold()))
            if sid is None:
                sid=next_id
                next_id+=1
                conn.execute("INSERT INTO gtms_drayage_suppliers(supplier_id,stage,supplier_name,created_from_business) VALUES (?,?,?,1)",(sid,stage,name))
                known[(stage,name.casefold())]=sid
                added+=1
            conn.execute("""INSERT INTO gtms_drayage_supplier_sources(stage,source_name,supplier_id,record_count)
                VALUES (?,?,?,?) ON CONFLICT(stage,source_name) DO UPDATE SET record_count=excluded.record_count""",(stage,name,sid,int(row["cnt"])))
        for old in conn.execute("SELECT source_name FROM gtms_drayage_supplier_sources WHERE stage=?",(stage,)).fetchall():
            if old["source_name"] not in seen:
                conn.execute("UPDATE gtms_drayage_supplier_sources SET record_count=0 WHERE stage=? AND source_name=?",(stage,old["source_name"]))
    return found,added

def show_drayage_master(user,db):
    st.title("港前港后拖车行主数据管理")
    st.caption("港前和港后严格按不同字段初始化 · 整数 supplier_id · 增加 / 修改 / 删除 / 查询")
    with db_connect(db) as conn:
        found,added=initialize(conn)
        records=[dict(r) for r in conn.execute("""SELECT d.*,COALESCE((SELECT SUM(s.record_count) FROM gtms_drayage_supplier_sources s WHERE s.supplier_id=d.supplier_id),0) AS container_count FROM gtms_drayage_suppliers d ORDER BY d.stage,d.supplier_id""").fetchall()]
        sources=[dict(r) for r in conn.execute("SELECT stage,source_name,supplier_id,record_count FROM gtms_drayage_supplier_sources ORDER BY stage,record_count DESC").fetchall()]
    a,b,c=st.columns(3)
    a.metric("港前供应商",sum(r["stage"]=="港前" for r in records))
    b.metric("港后供应商",sum(r["stage"]=="港后" for r in records))
    c.metric("本次新增",added)
    if len(found)<2:
        st.warning("业务表未同时包含「港前拖车行」与「港后拖车行」，缺失字段的供应商无法自动同步。")
    tab1,tab2=st.tabs(["查询主数据","业务来源映射"])
    with tab1:
        stage=st.selectbox("业务环节",["全部",*STAGES])
        query=st.text_input("搜索名称、代码、区域、联系人")
        filtered=[r for r in records if (stage=="全部" or r["stage"]==stage) and query.casefold() in " ".join(str(r.get(k,"")) for k in ("supplier_name","supplier_code","country_code","state_code","operating_region_code","contact_name")).casefold()]
        st.dataframe(pd.DataFrame(filtered),hide_index=True,use_container_width=True)
        st.download_button("导出全部拖车行",pd.DataFrame(records).to_csv(index=False).encode("utf-8-sig"),"gtms_drayage_suppliers.csv","text/csv")
    with tab2:
        st.dataframe(pd.DataFrame(sources),hide_index=True,use_container_width=True)
        st.download_button("导出全部来源映射",pd.DataFrame(sources).to_csv(index=False).encode("utf-8-sig"),"gtms_drayage_supplier_sources.csv","text/csv")
    if not is_admin(user):return
    st.subheader("增加 / 修改")
    options={str(r["supplier_id"]):r for r in records}
    choice=st.selectbox("选择供应商",["新增",*options],format_func=lambda k:"新增拖车行" if k=="新增" else f"{options[k]['stage']} · {options[k]['supplier_name']} ({k})")
    current=options.get(choice,{})
    with st.form("drayage_master_edit"):
        stage_value=st.selectbox("业务环节",STAGES,index=STAGES.index(current.get("stage","港前")),disabled=choice!="新增")
        name=st.text_input("供应商名称",current.get("supplier_name",""))
        code=st.text_input("供应商代码",current.get("supplier_code",""))
        country=st.text_input("国家代码",current.get("country_code",""))
        state=st.text_input("州/省代码",current.get("state_code",""))
        region=st.text_input("运营区域",current.get("operating_region_code",""))
        contact=st.text_input("联系人",current.get("contact_name",""))
        phone=st.text_input("电话",current.get("phone",""))
        email=st.text_input("邮箱",current.get("email",""))
        status=st.selectbox("状态",["待核实","启用","停用"],index=["待核实","启用","停用"].index(current.get("status","待核实")))
        notes=st.text_area("备注",current.get("notes",""))
        save=st.form_submit_button("保存")
    if save:
        if not name.strip():
            st.error("名称不能为空")
            return
        values=(name.strip(),code.strip(),country.strip().upper(),state.strip().upper(),region.strip().upper(),contact.strip(),phone.strip(),email.strip(),status,notes.strip())
        with db_connect(db) as conn:
            if choice=="新增":
                sid=int(conn.execute("SELECT COALESCE(MAX(supplier_id),0)+1 AS n FROM gtms_drayage_suppliers").fetchone()["n"])
                conn.execute("""INSERT INTO gtms_drayage_suppliers(supplier_id,stage,supplier_name,supplier_code,country_code,state_code,operating_region_code,contact_name,phone,email,status,notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",(sid,stage_value,*values))
            else:
                conn.execute("""UPDATE gtms_drayage_suppliers SET supplier_name=?,supplier_code=?,country_code=?,state_code=?,operating_region_code=?,contact_name=?,phone=?,email=?,status=?,notes=? WHERE supplier_id=?""",(*values,int(choice)))
        st.success("保存成功")
        st.rerun()
    st.subheader("删除")
    if not options:return
    target=st.selectbox("选择删除对象",list(options),format_func=lambda k:f"{options[k]['stage']} · {options[k]['supplier_name']}",key="drayage_master_delete")
    with st.form("drayage_master_delete_confirm"):
        confirm=st.checkbox("确认永久删除此供应商")
        delete=st.form_submit_button("删除")
    if delete:
        if not confirm:
            st.error("请确认删除")
            return
        with db_connect(db) as conn:
            refs=conn.execute("SELECT COUNT(*) AS n FROM gtms_drayage_supplier_sources WHERE supplier_id=?",(int(target),)).fetchone()["n"]
            if refs:
                st.error("存在业务来源关联，禁止删除；请先调整映射或停用。")
                return
            conn.execute("DELETE FROM gtms_drayage_suppliers WHERE supplier_id=?",(int(target),))
        st.success("删除成功")
        st.rerun()
