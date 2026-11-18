"""Streamlit supplier registry for pre-port and post-port drayage."""
import pandas as pd
import streamlit as st

from drayage_registry import STAGES, STATUSES, read_and_sync_registry, update_profile

COLUMNS = {
    "stage": "业务环节", "name": "供应商", "status": "档案状态",
    "contact": "联系人", "phone": "电话", "email": "邮箱", "notes": "备注",
    "updated_by": "更新人",
}


def show_drayage_suppliers(user):
    st.title("🚛 港前港后拖车供应商管理")
    st.caption("打开页面即从全部货柜记录同步供应商。港前和港后分别读取「港前拖车行」和「港后拖车行」。")
    try:
        profiles, assigned, imported, source_available = read_and_sync_registry()
    except Exception:
        st.error("供应商同步失败。请检查数据库连接、货柜表字段和建档权限。")
        return
    if not source_available:
        st.info("尚无货柜数据可供同步。")
    elif imported:
        st.success(f"本次新增 {imported} 个供应商档案。")

    for column, stage in zip(st.columns(2), STAGES):
        count = sum(entry_stage == stage for entry_stage, _ in assigned)
        column.metric(f"{stage} · 当前库供应商", count)

    stage_col, status_col, search_col = st.columns(3)
    stage = stage_col.selectbox("业务环节", ("全部", *STAGES))
    status = status_col.selectbox("档案状态", ("全部", *STATUSES))
    keyword = search_col.text_input("搜索供应商名称").strip().casefold()
    matched = [
        profile for profile in profiles
        if (stage == "全部" or profile["stage"] == stage)
        and (status == "全部" or profile["status"] == status)
        and keyword in profile["name"].casefold()
    ]
    if not matched:
        st.info("当前条件下没有供应商档案。")
        return
    view = pd.DataFrame(matched)[list(COLUMNS)].rename(columns=COLUMNS)
    view["当前库有分配记录"] = [
        "是" if (p["stage"], p["name"]) in assigned else "否" for p in matched
    ]
    st.dataframe(view, hide_index=True, use_container_width=True)
    export = view.map(
        lambda value: "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value
    )
    st.download_button("导出当前结果 CSV", export.to_csv(index=False).encode("utf-8-sig"),
                       file_name="港前港后拖车供应商.csv", mime="text/csv")

    if user["role"] == "管理员":
        edit_supplier(user, matched)


def edit_supplier(user, profiles):
    success = st.session_state.pop("drayage_profile_saved", False)
    if success:
        st.success("供应商档案已保存。")
    by_key = {(p["stage"], p["name"]): p for p in profiles}
    with st.expander("编辑供应商档案"):
        selected = st.selectbox("选择供应商", list(by_key),
                                format_func=lambda key: f"{key[0]}｜{key[1]}")
        profile = by_key[selected]
        with st.form(f"drayage_profile_{selected}_{profile['updated_at']}"):
            status = st.selectbox("档案状态", STATUSES, index=STATUSES.index(profile["status"]))
            contact = st.text_input("联系人", profile["contact"])
            phone = st.text_input("电话", profile["phone"])
            email = st.text_input("邮箱", profile["email"])
            notes = st.text_area("备注", profile["notes"])
            submitted = st.form_submit_button("保存档案", type="primary")
        if submitted:
            try:
                saved = update_profile(user, profile, status, contact, phone, email, notes)
            except Exception:
                st.error("档案保存失败。请检查数据库后重试。")
                return
            if not saved:
                st.warning("档案已被其他用户更新。请刷新后再编辑。")
                return
            st.session_state["drayage_profile_saved"] = True
            st.rerun()
