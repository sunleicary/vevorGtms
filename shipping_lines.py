"""Shipping line master data seeded from the actual containers.船公司 column."""
import re
import pandas as pd
import streamlit as st
from db_backend import connect as db_connect, is_neon
from auth import is_admin

def _cols(conn, table):
    if is_neon():
        return {r["column_name"] for r in conn.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=?",(table,)).fetchall()}
    return {r["name"] for r in conn.execute("PRAGMA table_info("+table+")").fetchall()}

def _exists(conn, table):
    if is_neon():
        return bool(conn.execute("SELECT 1 FROM information_schema.tables WHERE table_schema=current_schema() AND table_name=?",(table,)).fetchone())
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone())

def initialize(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS gtms_shipping_lines (
        carrier_id BIGINT PRIMARY KEY,
        carrier_name TEXT NOT NULL,
        carrier_code TEXT NOT NULL DEFAULT '',
        aliases TEXT NOT NULL DEFAULT '',
        enabled INTEGER NOT NULL DEFAULT 1,
        notes TEXT NOT NULL DEFAULT '',
        source_field TEXT NOT NULL DEFAULT '船公司',
        created_from_business INTEGER NOT NULL DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS gtms_shipping_line_sources (
        source_name TEXT PRIMARY KEY,
        carrier_id BIGINT NOT NULL,
        record_count BIGINT NOT NULL DEFAULT 0,
        FOREIGN KEY(carrier_id) REFERENCES gtms_shipping_lines(carrier_id)
    )""")
    if not _exists(conn,"containers") or "船公司" not in _cols(conn,"containers"):
        return 0, 0
    rows=conn.execute('SELECT TRIM("船公司") AS name,COUNT(*) AS cnt FROM containers WHERE "船公司" IS NOT NULL AND TRIM("船公司")<>\'\' GROUP BY TRIM("船公司") ORDER BY TRIM("船公司")').fetchall()
    existing={str(r["source_name"]).casefold():r["carrier_id"] for r in conn.execute("SELECT source_name,carrier_id FROM gtms_shipping_line_sources").fetchall()}
    known={str(r["carrier_name"]).casefold():r["carrier_id"] for r in conn.execute("SELECT carrier_id,carrier_name FROM gtms_shipping_lines").fetchall()}
    next_id=int(conn.execute("SELECT COALESCE(MAX(carrier_id),0)+1 AS n FROM gtms_shipping_lines").fetchone()["n"])
    added=0
    for row in rows:
        name=str(row["name"]).strip()
        if not name: continue
        key=name.casefold()
        cid=existing.get(key) or known.get(key)
        if cid is None:
            cid=next_id
            next_id+=1
            conn.execute("INSERT INTO gtms_shipping_lines(carrier_id,carrier_name,created_from_business) VALUES (?,?,1)",(cid,name))
            known[key]=cid
            added+=1
        conn.execute("""INSERT INTO gtms_shipping_line_sources(source_name,carrier_id,record_count)
            VALUES (?,?,?) ON CONFLICT(source_name) DO UPDATE SET record_count=excluded.record_count""",
            (name,cid,int(row["cnt"])))
    # Refresh counts when the business dataset is replaced, without deleting historical carriers.
    current={str(r["name"]).casefold() for r in rows}
    for source in conn.execute("SELECT source_name FROM gtms_shipping_line_sources").fetchall():
        if str(source["source_name"]).casefold() not in current:
            conn.execute("UPDATE gtms_shipping_line_sources SET record_count=0 WHERE source_name=?",(source["source_name"],))
    return added,len(rows)

def show_shipping_lines(user, db):
    st.title("船司管理")
    st.caption("基于业务数据字段「船公司」自动初始化；使用整数 carrier_id。名称未核实前不自动合并不同拼写。")
    with db_connect(db) as conn:
        added,source_count=initialize(conn)
        lines=[dict(r) for r in conn.execute("""SELECT l.*,
            COALESCE((SELECT SUM(s.record_count) FROM gtms_shipping_line_sources s WHERE s.carrier_id=l.carrier_id),0) AS container_count
            FROM gtms_shipping_lines l ORDER BY l.carrier_id""").fetchall()]
        sources=[dict(r) for r in conn.execute("""SELECT s.source_name,s.carrier_id,l.carrier_name,s.record_count
            FROM gtms_shipping_line_sources s JOIN gtms_shipping_lines l ON l.carrier_id=s.carrier_id
            ORDER BY s.record_count DESC,s.source_name""").fetchall()]
    a,b,c=st.columns(3)
    a.metric("船司主数据",len(lines))
    b.metric("业务原始名称",source_count)
    c.metric("本次新增船司",added)
    tab1,tab2=st.tabs(["船司主数据","业务来源与名称映射"])
    with tab1:
        query=st.text_input("搜索船司名称/代码")
        visible=[r for r in lines if query.casefold() in (str(r["carrier_name"])+" "+str(r["carrier_code"])+" "+str(r["aliases"])).casefold()]
        st.dataframe(pd.DataFrame(visible),hide_index=True,use_container_width=True)
        st.download_button("导出全部船司 CSV",pd.DataFrame(lines).to_csv(index=False).encode("utf-8-sig"),"gtms_shipping_lines.csv","text/csv")
    with tab2:
        st.dataframe(pd.DataFrame(sources),hide_index=True,use_container_width=True)
        st.download_button("导出原始名称映射 CSV",pd.DataFrame(sources).to_csv(index=False).encode("utf-8-sig"),"gtms_shipping_line_sources.csv","text/csv")
    if not is_admin(user): return
    st.subheader("主数据标准操作：增加 / 修改 / 删除 / 查询")
    st.caption("查询与导出在上方；新增和修改在下方。删除操作需要二次确认，已有业务来源关联的船司不可直接删除。")
    options={str(r["carrier_id"]):r for r in lines}
    choice=st.selectbox("选择船司",["新增"]+list(options),format_func=lambda k:"新增船司" if k=="新增" else f"{k} · {options[k]['carrier_name']}")
    current=options.get(choice,{})
    with st.form("shipping_line_edit"):
        name=st.text_input("标准名称",current.get("carrier_name",""))
        code=st.text_input("船司代码",current.get("carrier_code",""))
        aliases=st.text_input("别名（逗号分隔）",current.get("aliases",""))
        enabled=st.checkbox("启用",value=bool(current.get("enabled",1)))
        notes=st.text_area("备注",value=current.get("notes",""))
        save=st.form_submit_button("保存")
    if save:
        name=name.strip()
        if not name:
            st.error("船司名称不能为空")
            return
        with db_connect(db) as conn:
            if choice=="新增":
                cid=int(conn.execute("SELECT COALESCE(MAX(carrier_id),0)+1 AS n FROM gtms_shipping_lines").fetchone()["n"])
                conn.execute("INSERT INTO gtms_shipping_lines(carrier_id,carrier_name,carrier_code,aliases,enabled,notes) VALUES (?,?,?,?,?,?)",(cid,name,code.strip().upper(),aliases.strip(),int(enabled),notes.strip()))
            else:
                conn.execute("UPDATE gtms_shipping_lines SET carrier_name=?,carrier_code=?,aliases=?,enabled=?,notes=? WHERE carrier_id=?",(name,code.strip().upper(),aliases.strip(),int(enabled),notes.strip(),int(choice)))
        st.success("保存成功")
        st.rerun()

    st.divider()
    st.subheader("删除船司")
    if not options:
        st.info("暂无可删除的船司")
        return
    delete_key=st.selectbox("选择要删除的船司",list(options),format_func=lambda k:f"{k} · {options[k]['carrier_name']}",key="delete_shipping_line")
    with st.form("delete_shipping_line_form"):
        confirmed=st.checkbox("我确认删除此船司主数据（不可撤销）")
        delete=st.form_submit_button("删除",type="secondary")
    if delete:
        if not confirmed:
            st.error("请先确认删除")
            return
        with db_connect(db) as conn:
            linked=conn.execute("SELECT COUNT(*) AS n FROM gtms_shipping_line_sources WHERE carrier_id=?",(int(delete_key),)).fetchone()["n"]
            if linked:
                st.error(f"该船司存在 {linked} 条业务名称映射，请先调整映射，不能直接删除。")
                return
            conn.execute("DELETE FROM gtms_shipping_lines WHERE carrier_id=?",(int(delete_key),))
        st.success("删除成功")
        st.rerun()
