"""Import warehouse addresses from the supplied multi-sheet address directory."""
import io
import pandas as pd
import streamlit as st
from auth import is_admin
from db_backend import connect as db_connect
from warehouses import initialize

SHEETS=("美国26年","加拿大26年","使用中","弃用","26年美国淘汰","26年加拿大淘汰")
ARCHIVED={"弃用","26年美国淘汰","26年加拿大淘汰"}
HEADERS=("国家","区域","仓库名称","仓库地址","GLC线路是否存在","运营管理系统是否已启用","备注",
         "海外仓状态","海外仓入库状态")

def parse_directory(data):
    workbook=pd.ExcelFile(io.BytesIO(data))
    result=[]
    for priority,sheet in enumerate(SHEETS):
        if sheet not in workbook.sheet_names:continue
        frame=pd.read_excel(workbook,sheet_name=sheet,dtype=str)
        if len(frame.columns)<4:continue
        # Source has mixed labels and multiline headers; positions 0-8 are stable.
        for _,row in frame.iterrows():
            values=["" if pd.isna(row.iloc[i]) else str(row.iloc[i]).strip()
                    for i in range(min(9,len(row)))]
            values+=[""]*(9-len(values))
            if not values[2]:continue
            entry=dict(zip(HEADERS,values))
            entry["来源工作表"]=sheet
            entry["优先级"]=priority
            result.append(entry)
    return result

def show_address_import(user,db):
    if not is_admin(user):return
    with st.expander("从海外仓地址大全导入仓库详细地址",expanded=False):
        st.caption("按仓库名称精确匹配；2026年清单优先。弃用/淘汰仓库不会自动启用或覆盖现役地址。")
        uploaded=st.file_uploader("上传海外仓地址大全 .xlsx",type=["xlsx"],key="warehouse_address_upload")
        if not uploaded:return
        try:items=parse_directory(uploaded.getvalue())
        except Exception as exc:
            st.error(f"地址文件读取失败：{exc}")
            return
        with db_connect(db) as conn:
            initialize(conn)
            current=[dict(r) for r in conn.execute("SELECT * FROM gtms_warehouses").fetchall()]
        by_name={r["warehouse_name"].strip().casefold():r for r in current}
        best={}
        for item in items:
            key=item["仓库名称"].casefold()
            if key not in best:best[key]=item
        review=[]
        for item in best.values():
            old=by_name.get(item["仓库名称"].casefold())
            archived=item["来源工作表"] in ARCHIVED or any(
                x in item["海外仓状态"] for x in ("已关仓","虚拟仓"))
            old_address=(old or {}).get("address","") or ""
            new_address=item["仓库地址"]
            if archived:action="历史档案（不自动更新）"
            elif not old:action="未匹配主数据"
            elif not new_address:action="地址为空（跳过）"
            elif old_address.strip() and old_address.strip()!=new_address.strip():action="地址冲突（人工确认）"
            elif old_address.strip()==new_address.strip():action="地址一致"
            else:action="可补充地址"
            review.append({"仓库名称":item["仓库名称"],"来源":item["来源工作表"],
                           "处理建议":action,"现有地址":old_address,"文件地址":new_address,
                           "国家":item["国家"],"区域":item["区域"],
                           "GLC线路":item["GLC线路是否存在"],
                           "仓库状态":item["海外仓状态"],
                           "入库状态":item["海外仓入库状态"],
                           "备注":item["备注"]})
        result=pd.DataFrame(review)
        st.metric("源文件地址记录",len(items))
        st.metric("去重仓库名称",len(best))
        st.dataframe(result,hide_index=True,use_container_width=True)
        st.download_button("导出地址匹配与冲突核对表",result.to_csv(index=False).encode("utf-8-sig"),
                           "warehouse_address_review.csv","text/csv",key="warehouse_address_review_download")
        st.caption("仅自动补充原主数据中地址为空的现役仓库。冲突、弃用和未匹配仓库需人工核对。")
        approve=st.checkbox("确认仅写入匹配成功且地址为空的现役仓库",key="warehouse_address_approve")
        if st.button("执行安全地址补充",disabled=not approve,key="warehouse_address_apply"):
            count=0
            with db_connect(db) as conn:
                for item in review:
                    if item["处理建议"]!="可补充地址":continue
                    source=best[item["仓库名称"].casefold()]
                    current_record=by_name[item["仓库名称"].casefold()]
                    result_update=conn.execute("""UPDATE gtms_warehouses SET address=?,
                        notes=CASE WHEN notes='' THEN ? ELSE notes END
                        WHERE warehouse_id=? AND TRIM(address)=''""",
                        (source["仓库地址"],
                         "地址来源："+source["来源工作表"]+"；GLC线路："+source["GLC线路是否存在"]+
                         "；原始备注："+source["备注"],current_record["warehouse_id"]))
                    count+=max(0,result_update.rowcount)
            st.success(f"已补充 {count} 个仓库地址；其余保留核对，不覆盖。")
            st.rerun()
