"""VevorTMS 智能运营中心。当前为基于导入数据的规则辅助分析，不执行外部AI调用。"""
from datetime import date
import pandas as pd
import streamlit as st

def vendors(df):
    x=df.copy()
    x["港后拖车行"]=x["港后拖车行"].fillna("").astype(str).str.strip()
    return x[x["港后拖车行"].ne("") & ~x["港后拖车行"].isin(["nan","None"])]

def dt(df,col):
    return pd.to_datetime(df[col],errors="coerce") if col in df else pd.Series(pd.NaT,index=df.index)

def export(df,key,name):
    st.download_button("导出全部结果CSV",df.to_csv(index=False).encode("utf-8-sig"),file_name=name,mime="text/csv",key=key)

def show_intelligent_lfd(df):
    st.title("🚨 智能LFD预警与自动催办")
    st.caption("根据已导入数据预警，非实时码头信息；催办内容仅供复制，不会自动发送。")
    x=vendors(df)
    if x.empty:
        st.info("暂无已分配港后拖车商的海柜。");return
    regions=sorted(x["区域"].dropna().unique())
    region=st.selectbox("区域",["全部"]+list(regions),key="int_lfd_region")
    if region!="全部":x=x[x["区域"].eq(region)]
    supplier=st.selectbox("港后拖车商",["全部"]+sorted(x["港后拖车行"].unique()),key="int_lfd_supplier")
    if supplier!="全部":x=x[x["港后拖车行"].eq(supplier)]
    lfd=dt(x,"LFD").dt.normalize()
    pickup=dt(x,"进口实际提箱时间")
    days=(lfd-pd.Timestamp(date.today())).dt.days
    x=x.copy()
    x["距LFD天数"]=days
    x["预警"]="正常或已提柜"
    pending=pickup.isna()
    x.loc[pending & lfd.isna(),"预警"]="缺少LFD"
    x.loc[pending & days.lt(0),"预警"]="超期待核实"
    x.loc[pending & days.eq(0),"预警"]="今日到期"
    x.loc[pending & days.eq(1),"预警"]="未来24-48小时"
    x.loc[pending & days.between(2,3),"预警"]="未来48-72小时"
    risk=x[x["预警"].ne("正常或已提柜")].copy()
    labels=["超期待核实","今日到期","未来24-48小时","未来48-72小时","缺少LFD"]
    for col,label in zip(st.columns(5),labels):
        col.metric(label,int(risk["预警"].eq(label).sum()))
    risk["_priority"]=risk["预警"].map({v:i for i,v in enumerate(labels)})
    risk=risk.sort_values(["_priority","距LFD天数"],na_position="last")
    columns=[c for c in ["排柜单号","箱号","区域","港后拖车行","LFD","距LFD天数","预警"] if c in risk]
    st.dataframe(risk[columns],hide_index=True,use_container_width=True)
    export(risk[columns],"int_lfd_csv","智能LFD预警.csv")
    if not risk.empty:
        order=st.selectbox("生成催办内容（排柜单号）",risk["排柜单号"].astype(str).tolist(),key="int_lfd_order")
        row=risk.loc[risk["排柜单号"].astype(str).eq(order)].iloc[0]
        st.text_area("催办内容",f"您好，请核实海柜 {row.get('箱号','')}（排柜单号 {order}），LFD：{row.get('LFD','')}，风险：{row['预警']}。请反馈码头状态、预约和提柜计划，谢谢。",height=110)

def show_ai_fee_review(df):
    st.title("🧾 AI异常费用审核")
    st.caption("规则辅助审核原型，尚未连接AI模型、合同价格或费用数据库；不自动审批。")
    file=st.file_uploader("上传异常费用明细CSV或XLSX",type=["csv","xlsx"],key="int_fee_upload")
    if file is None:
        st.info("请提供：排柜单号、费用类型、费用金额；建议另有费用说明、凭证链接、港后拖车行。")
        return
    try:
        fees=pd.read_csv(file) if file.name.lower().endswith(".csv") else pd.read_excel(file)
    except Exception as exc:
        st.error(f"无法读取文件：{exc}");return
    required={"排柜单号","费用类型","费用金额"}
    if not required.issubset(fees.columns):
        st.error("缺少字段："+", ".join(sorted(required-set(fees.columns))));return
    fees=fees.copy()
    fees["费用金额"]=pd.to_numeric(fees["费用金额"],errors="coerce")
    def check(row):
        issues=[]
        if pd.isna(row["费用金额"]) or row["费用金额"]<0:issues.append("金额无效")
        for field in ["费用说明","凭证链接"]:
            value=row.get(field,"")
            if pd.isna(value) or not str(value).strip():issues.append("缺少"+field)
        return "；".join(issues) if issues else "待核对合同与实际事件"
    fees["审核提示"]=fees.apply(check,axis=1)
    st.metric("待核对记录",len(fees))
    st.dataframe(fees,hide_index=True,use_container_width=True)
    export(fees,"int_fee_csv","异常费用辅助审核.csv")
    st.warning("所有费用必须人工核对合同、事件与原始凭证；提示不代表批准或拒付。")

def show_supplier_capacity(df):
    st.title("📈 供应商绩效与产能管理")
    st.caption("仅按港后拖车行统计。产能值由用户手工填写，不代表车队已确认。")
    x=vendors(df)
    if x.empty:
        st.info("暂无港后供应商数据。");return
    regions=sorted(x["区域"].dropna().unique())
    region=st.selectbox("区域",["全部"]+list(regions),key="int_capacity_region")
    if region!="全部":x=x[x["区域"].eq(region)]
    period=st.date_input("ETA区间",(date.today()-pd.Timedelta(days=30),date.today()+pd.Timedelta(days=60)),key="int_capacity_eta")
    if isinstance(period,(tuple,list)) and len(period)==2:
        eta=dt(x,"ETA日期")
        x=x[eta.between(pd.Timestamp(period[0]),pd.Timestamp(period[1])+pd.Timedelta(days=1)-pd.Timedelta(seconds=1))]
    x=x.copy()
    pickup=dt(x,"进口实际提箱时间").dt.normalize()
    lfd=dt(x,"LFD").dt.normalize()
    x["已提柜"]=pickup.notna()
    x["及时提柜"]=pickup.notna() & lfd.notna() & pickup.le(lfd)
    summary=x.groupby("港后拖车行").agg(分配柜量=("港后拖车行","size"),已提柜=("已提柜","sum"),及时提柜=("及时提柜","sum")).reset_index()
    summary["提柜及时率(%)"]=(summary["及时提柜"]/summary["已提柜"].replace(0,float("nan"))*100).round(1)
    st.caption("及时率=有LFD且按时提柜数/已提柜数；缺失LFD的记录需补充。")
    st.dataframe(summary,hide_index=True,use_container_width=True)
    if not summary.empty:st.bar_chart(summary.set_index("港后拖车行")["分配柜量"])
    st.markdown("#### 产能对比")
    capacity=summary[["港后拖车行","分配柜量"]].copy()
    capacity["承诺产能(柜)"]=0
    edited=st.data_editor(capacity,hide_index=True,use_container_width=True,disabled=["港后拖车行","分配柜量"],key="int_capacity_editor")
    edited["承诺产能(柜)"]=pd.to_numeric(edited["承诺产能(柜)"],errors="coerce").fillna(0).clip(lower=0)
    edited["产能缺口(柜)"]=(edited["分配柜量"]-edited["承诺产能(柜)"]).clip(lower=0)
    st.dataframe(edited,hide_index=True,use_container_width=True)
    export(summary.merge(edited[["港后拖车行","承诺产能(柜)","产能缺口(柜)"]],on="港后拖车行"),"int_capacity_csv","供应商绩效产能.csv")
