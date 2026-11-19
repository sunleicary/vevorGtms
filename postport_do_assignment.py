"""Post-port drayage Delivery Order (DO) assignment register."""
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
from auth import is_admin
from db_backend import connect as db_connect

STATUSES=("待分配","已分配待确认","供应商已确认","供应商拒绝","已取消")

def show_do_assignment(user, db, containers):
    st.title("港后拖车商DO分配")
    st.caption("DO分配记录独立保存；原始「港后拖车行」仅作为建议供应商，不等于已确认DO。")
    with db_connect(db) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS gtms_postport_do_assignments (
            order_no TEXT PRIMARY KEY, container_no TEXT NOT NULL DEFAULT '',
            supplier_name TEXT NOT NULL, status TEXT NOT NULL DEFAULT '已分配待确认',
            assigned_at TEXT NOT NULL, assigned_by TEXT NOT NULL DEFAULT '',
            confirmed_at TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT ''
        )""")
        assignments=[dict(r) for r in conn.execute("SELECT * FROM gtms_postport_do_assignments").fetchall()]
    existing={str(r["order_no"]):r for r in assignments}
    base=containers.copy()
    if "排柜单号" not in base:
        st.warning("业务数据缺少排柜单号，无法进行DO分配。")
        return
    base["排柜单号"]=base["排柜单号"].fillna("").astype(str).str.strip()
    base=base[base["排柜单号"].ne("")].drop_duplicates("排柜单号",keep="last")
    for col in ("箱号","港后拖车行","目的仓物流区域","ETA日期","LFD"):
        if col not in base:base[col]=""
    view=base[["排柜单号","箱号","港后拖车行","目的仓物流区域","ETA日期","LFD"]].copy()
    view["DO分配供应商"]=view["排柜单号"].map(lambda k:existing.get(k,{}).get("supplier_name",""))
    view["DO状态"]=view["排柜单号"].map(lambda k:existing.get(k,{}).get("status","待分配"))
    view["分配时间"]=view["排柜单号"].map(lambda k:existing.get(k,{}).get("assigned_at",""))
    a,b,c=st.columns(3)
    a.metric("业务货柜",len(view))
    b.metric("已创建DO分配",sum(v["status"]!="已取消" for v in existing.values()))
    c.metric("待分配",int(view["DO状态"].eq("待分配").sum()))
    statuses=st.multiselect("DO状态筛选",STATUSES,default=list(STATUSES))
    query=st.text_input("搜索排柜单号、箱号或拖车商")
    filtered=view[view["DO状态"].isin(statuses)]
    if query:
        mask=filtered.astype(str).apply(lambda c:c.str.contains(query,case=False,regex=False)).any(axis=1)
        filtered=filtered[mask]
    st.dataframe(filtered,hide_index=True,use_container_width=True)
    st.download_button("导出DO分配台账",filtered.to_csv(index=False).encode("utf-8-sig"),"postport_do_assignments.csv","text/csv")
    if not is_admin(user) and user.get("role")!="港后运营人员":
        return
    st.subheader("批量DO分配")
    st.caption("仅对未分配柜号建立DO；已分配、已确认、已取消的记录不会被批量覆盖。")
    pending=view[view["DO状态"].eq("待分配")].copy()
    if pending.empty:
        st.info("当前筛选范围没有待分配货柜。")
    else:
        region_values=sorted(pending["目的仓物流区域"].fillna("").astype(str).unique().tolist())
        selected_regions=st.multiselect("批量分配 · 运营区域",region_values,key="do_bulk_regions")
        if selected_regions:
            pending=pending[pending["目的仓物流区域"].fillna("").astype(str).isin(selected_regions)]
        eta_dates=pd.to_datetime(pending["ETA日期"],errors="coerce",format="mixed")
        valid_eta=eta_dates.dropna()
        use_eta=st.checkbox("按ETA日期筛选",key="do_bulk_eta_enabled")
        if use_eta and not valid_eta.empty:
            start_date,end_date=valid_eta.min().date(),valid_eta.max().date()
            chosen_dates=st.date_input("批量分配 · ETA范围",value=(start_date,end_date),
                                       min_value=start_date,max_value=end_date,key="do_bulk_eta")
            if len(chosen_dates)==2:
                pending=pending[eta_dates.dt.date.between(*chosen_dates)]
            else:
                pending=pending.iloc[0:0]
        elif use_eta:
            st.warning("没有有效ETA日期。")
            pending=pending.iloc[0:0]
        bulk_query=st.text_input("批量分配 · 搜索柜号/排柜单号",key="do_bulk_search")
        if bulk_query:
            pending=pending[pending[["排柜单号","箱号"]].astype(str).apply(
                lambda c:c.str.contains(bulk_query,case=False,regex=False)).any(axis=1)]
        st.caption(f"可选择 {len(pending):,} 柜；勾选后先预览再确认。")
        selection=pending.copy()
        selection.insert(0,"选择",False)
        edited=st.data_editor(selection,hide_index=True,use_container_width=True,
                              disabled=[c for c in selection.columns if c!="选择"],
                              key="do_bulk_editor")
        chosen=edited[edited["选择"]].copy()
        st.write(f"已选择 **{len(chosen):,}** 柜")
        supplier_names=sorted(set(view["港后拖车行"].dropna().astype(str).str.strip())-{""})
        with db_connect(db) as conn:
            try:
                master=conn.execute("SELECT supplier_name FROM gtms_drayage_suppliers WHERE stage='港后' AND status<>'停用'").fetchall()
                supplier_names=sorted(set(supplier_names)|{r["supplier_name"] for r in master})
            except Exception:
                pass
        with st.form("do_bulk_confirm"):
            target_supplier=st.selectbox("批量分配给港后拖车商",["请选择"]+supplier_names)
            bulk_notes=st.text_area("批量分配备注")
            acknowledge=st.checkbox("已核对所选柜号与港后拖车商，确认批量创建DO分配")
            preview=st.form_submit_button("预览批量分配")
        if preview:
            if not len(chosen) or target_supplier=="请选择" or not acknowledge:
                st.error("请先选择货柜、指定供应商并确认。")
            else:
                st.session_state["do_bulk_preview"]={
                    "orders":chosen["排柜单号"].tolist(),
                    "supplier":target_supplier,"notes":bulk_notes,
                }
        prepared=st.session_state.get("do_bulk_preview")
        if prepared:
            ids=set(chosen["排柜单号"])
            if (set(prepared["orders"])!=ids or prepared["supplier"]!=target_supplier
                    or prepared["notes"]!=bulk_notes):
                st.session_state.pop("do_bulk_preview",None)
            else:
                st.warning(f"即将为 {len(ids)} 柜分配给「{target_supplier}」，状态为「已分配待确认」。")
                if st.button("最终确认并保存批量DO",type="primary",key="do_bulk_commit"):
                    now=datetime.now(timezone.utc).isoformat()
                    rows=chosen[["排柜单号","箱号"]].to_dict("records")
                    saved=0
                    with db_connect(db) as conn:
                        for item in rows:
                            # No upsert: never overwrite existing assignments, even if changed by another user.
                            result=conn.execute("""INSERT INTO gtms_postport_do_assignments
                                (order_no,container_no,supplier_name,status,assigned_at,assigned_by,confirmed_at,notes)
                                VALUES (?,?,?,'已分配待确认',?,?,'',?)
                                ON CONFLICT(order_no) DO NOTHING""",
                                (item["排柜单号"],str(item["箱号"]),target_supplier,now,
                                 user.get("username",""),bulk_notes.strip()))
                            saved+=max(0,result.rowcount)
                    st.session_state.pop("do_bulk_preview",None)
                    st.success(f"成功创建 {saved} 条DO分配；{len(rows)-saved} 条已有记录未覆盖。")
                    st.rerun()
    st.divider()
    st.subheader("新增 / 修改 DO分配")
    if view.empty:return
    order=st.selectbox("选择排柜单号",view["排柜单号"].tolist())
    source=view.loc[view["排柜单号"].eq(order)].iloc[0]
    old=existing.get(order,{})
    suggested=str(source["港后拖车行"] or "").strip()
    supplier_names=sorted(set(view["港后拖车行"].dropna().astype(str).str.strip())-{""})
    initial=old.get("supplier_name") or suggested
    if initial and initial not in supplier_names:supplier_names.append(initial)
    with st.form("do_assignment_edit"):
        supplier=st.selectbox("港后拖车商",["请选择"]+supplier_names,index=(["请选择"]+supplier_names).index(initial) if initial else 0)
        status=st.selectbox("DO状态",STATUSES[1:],index=list(STATUSES[1:]).index(old.get("status","已分配待确认")) if old.get("status","已分配待确认") in STATUSES[1:] else 0)
        notes=st.text_area("分配说明",old.get("notes",""))
        save=st.form_submit_button("保存DO分配")
    if save:
        if supplier=="请选择":
            st.error("请选择港后拖车商")
            return
        now=datetime.now(timezone.utc).isoformat()
        confirmed=now if status=="供应商已确认" and old.get("status")!="供应商已确认" else old.get("confirmed_at","")
        if status!="供应商已确认":confirmed=""
        with db_connect(db) as conn:
            conn.execute("""INSERT INTO gtms_postport_do_assignments
              (order_no,container_no,supplier_name,status,assigned_at,assigned_by,confirmed_at,notes)
              VALUES (?,?,?,?,?,?,?,?)
              ON CONFLICT(order_no) DO UPDATE SET supplier_name=excluded.supplier_name,
              status=excluded.status,assigned_at=excluded.assigned_at,
              assigned_by=excluded.assigned_by,confirmed_at=excluded.confirmed_at,notes=excluded.notes""",
              (order,str(source["箱号"]),supplier,status,now,user.get("username",""),confirmed,notes.strip()))
        st.success("DO分配已保存")
        st.rerun()
    st.caption("「供应商已确认」应在收到实际确认后由运营人员记录；当前页面不向供应商自动发送DO。")
