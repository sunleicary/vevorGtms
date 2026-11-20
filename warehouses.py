"""Warehouse master data; source of truth is containers.实际送货仓."""
import pandas as pd
import streamlit as st
from db_backend import connect as db_connect, is_neon
from auth import is_admin

def _has_column(conn,table,col):
    if is_neon():
        return bool(conn.execute("SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=? AND column_name=?",(table,col)).fetchone())
    return any(r["name"]==col for r in conn.execute("PRAGMA table_info("+table+")").fetchall())

def initialize(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS gtms_warehouses (
      warehouse_id BIGINT PRIMARY KEY, warehouse_name TEXT NOT NULL,
      warehouse_code TEXT NOT NULL DEFAULT '', country_code TEXT NOT NULL DEFAULT '',
      state_code TEXT NOT NULL DEFAULT '', operating_region_code TEXT NOT NULL DEFAULT '',
      address TEXT NOT NULL DEFAULT '', operator_name TEXT NOT NULL DEFAULT '',
      contact_name TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '',
      email TEXT NOT NULL DEFAULT '', enabled INTEGER NOT NULL DEFAULT 1,
      notes TEXT NOT NULL DEFAULT '', created_from_business INTEGER NOT NULL DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS gtms_warehouse_sources (
      source_name TEXT PRIMARY KEY, warehouse_id BIGINT NOT NULL,
      record_count BIGINT NOT NULL DEFAULT 0,
      FOREIGN KEY(warehouse_id) REFERENCES gtms_warehouses(warehouse_id)
    )""")
    if not _has_column(conn,"containers","实际送货仓"):
        return False,0
    rows=conn.execute('SELECT TRIM("实际送货仓") AS name, COUNT(*) AS cnt FROM containers WHERE "实际送货仓" IS NOT NULL AND TRIM("实际送货仓")<>\'\' GROUP BY TRIM("实际送货仓") ORDER BY TRIM("实际送货仓")').fetchall()
    known={r["warehouse_name"].casefold():r["warehouse_id"] for r in conn.execute("SELECT warehouse_id,warehouse_name FROM gtms_warehouses").fetchall()}
    mapping={r["source_name"]:r["warehouse_id"] for r in conn.execute("SELECT source_name,warehouse_id FROM gtms_warehouse_sources").fetchall()}
    next_id=int(conn.execute("SELECT COALESCE(MAX(warehouse_id),0)+1 AS n FROM gtms_warehouses").fetchone()["n"])
    added=0
    for r in rows:
        name=r["name"]
        wid=mapping.get(name) or known.get(name.casefold())
        if wid is None:
            wid=next_id
            next_id+=1
            conn.execute("INSERT INTO gtms_warehouses(warehouse_id,warehouse_name,created_from_business) VALUES (?,?,1)",(wid,name))
            known[name.casefold()]=wid
            added+=1
        conn.execute("""INSERT INTO gtms_warehouse_sources(source_name,warehouse_id,record_count) VALUES (?,?,?)
          ON CONFLICT(source_name) DO UPDATE SET record_count=excluded.record_count""",(name,wid,int(r["cnt"])))
    current={r["name"] for r in rows}
    for r in conn.execute("SELECT source_name FROM gtms_warehouse_sources").fetchall():
        if r["source_name"] not in current:
            conn.execute("UPDATE gtms_warehouse_sources SET record_count=0 WHERE source_name=?",(r["source_name"],))
    return True,added

def show_warehouses(user,db):
    st.title("海外仓主数据管理")
    st.caption("数据来源：实际送货仓 · 自动初始化 · 增加 / 修改 / 删除 / 查询")
    with db_connect(db) as conn:
        has_source,added=initialize(conn)
        records=[dict(r) for r in conn.execute("""SELECT w.*,COALESCE((SELECT SUM(s.record_count) FROM gtms_warehouse_sources s WHERE s.warehouse_id=w.warehouse_id),0) AS container_count
            FROM gtms_warehouses w ORDER BY w.warehouse_id""").fetchall()]
        sources=[dict(r) for r in conn.execute("SELECT source_name,warehouse_id,record_count FROM gtms_warehouse_sources ORDER BY record_count DESC").fetchall()]
    a,b,c=st.columns(3)
    a.metric("仓库主数据",len(records))
    b.metric("业务仓库名称",len(sources))
    c.metric("本次新增",added)
    if not has_source:
        st.warning("当前 containers 表缺少「实际送货仓」字段。请先导入包含该字段的完整业务数据，或执行仓库初始化 SQL。")
    tab1,tab2=st.tabs(["查询仓库","原始名称与业务量"])
    with tab1:
        search=st.text_input("查询仓库名称、代码、国家、州、区域或运营商")
        filtered=[r for r in records if search.casefold() in " ".join(str(r.get(k,"")) for k in ("warehouse_name","warehouse_code","country_code","state_code","operating_region_code","operator_name")).casefold()]
        st.dataframe(pd.DataFrame(filtered),hide_index=True,use_container_width=True)
        st.download_button("导出全部仓库",pd.DataFrame(records).to_csv(index=False).encode("utf-8-sig"),"gtms_warehouses.csv","text/csv")
    with tab2:
        st.dataframe(pd.DataFrame(sources),hide_index=True,use_container_width=True)
        st.download_button("导出仓库来源",pd.DataFrame(sources).to_csv(index=False).encode("utf-8-sig"),"gtms_warehouse_sources.csv","text/csv")
    if not is_admin(user):return
    from warehouse_addresses import show_address_import
    show_address_import(user,db)
    st.subheader("增加 / 修改")
    options={str(r["warehouse_id"]):r for r in records}
    selected=st.selectbox("选择仓库",["新增"]+list(options),format_func=lambda k:"新增仓库" if k=="新增" else f"{k} · {options[k]['warehouse_name']}")
    current=options.get(selected,{})
    fields=[("warehouse_name","仓库名称"),("warehouse_code","仓库代码"),("country_code","国家代码"),("state_code","州/省代码"),("operating_region_code","运营区域"),("address","仓库地址"),("operator_name","运营商"),("contact_name","联系人"),("phone","联系电话"),("email","邮箱"),("notes","备注")]
    with st.form("warehouse_editor"):
        values={k:st.text_input(label,str(current.get(k,""))) for k,label in fields}
        enabled=st.checkbox("启用",bool(current.get("enabled",1)))
        save=st.form_submit_button("保存")
    if save:
        if not values["warehouse_name"].strip():
            st.error("仓库名称不能为空")
            return
        keys=[k for k,_ in fields]
        data=[values[k].strip().upper() if k in ("country_code","state_code","operating_region_code") else values[k].strip() for k in keys]+[int(enabled)]
        with db_connect(db) as conn:
            if selected=="新增":
                wid=int(conn.execute("SELECT COALESCE(MAX(warehouse_id),0)+1 AS n FROM gtms_warehouses").fetchone()["n"])
                cols=",".join(keys+["enabled"])
                placeholders=",".join(["?"]*(len(keys)+2))
                conn.execute(f"INSERT INTO gtms_warehouses(warehouse_id,{cols}) VALUES ({placeholders})",(wid,*data))
            else:
                setters=",".join(k+"=?" for k in keys+["enabled"])
                conn.execute(f"UPDATE gtms_warehouses SET {setters} WHERE warehouse_id=?",(*data,int(selected)))
        st.success("保存成功")
        st.rerun()
    st.subheader("删除")
    if not options:return
    target=st.selectbox("选择删除仓库",list(options),format_func=lambda k:f"{k} · {options[k]['warehouse_name']}",key="delete_warehouse")
    with st.form("warehouse_delete"):
        confirm=st.checkbox("确认永久删除仓库")
        delete=st.form_submit_button("删除")
    if delete:
        if not confirm:
            st.error("请先确认删除")
            return
        with db_connect(db) as conn:
            refs=conn.execute("SELECT COUNT(*) AS n FROM gtms_warehouse_sources WHERE warehouse_id=?",(int(target),)).fetchone()["n"]
            if refs:
                st.error("该仓库已关联业务来源，禁止直接删除；可以先停用。")
                return
            conn.execute("DELETE FROM gtms_warehouses WHERE warehouse_id=?",(int(target),))
        st.success("删除成功")
        st.rerun()
