"""Monthly KPI workbook import matching the October 2026 service-provider assessment workbook."""
from io import BytesIO
import pandas as pd
import streamlit as st

SHEETS = {
    "港后提柜及时率": ("是否及时", {"及时"}, {"不及时", "否", "超时"}),
    "送仓准时率": ("是否准时", {"准时"}, {"不准时"}),
    "送仓时效": ("是否超时", {"否", "未超时"}, {"是", "超时"}),
    "提空及时率": ("是否超时", {"否", "未超时"}, {"是", "超时"}),
    "还柜及时率": ("是否超时", {"否", "未超时"}, {"是", "超时"}),
}
def _read_sheet(book, sheet):
    # The workbook uses a title/instruction row above the real headers.
    frame = pd.read_excel(book, sheet_name=sheet, header=1, dtype=str).fillna("")
    frame.columns = [str(c).strip() for c in frame.columns]
    return frame

def show_monthly_kpi():
    st.title("📊 月度港后拖车商 KPI 考核（原始考核表格式）")
    st.caption("支持2026年10月KPI工作簿格式：港后提柜及时率、送仓准时率、送仓时效、提空及时率、还柜及时率。"
               "按排柜单号唯一计数，箱号允许重复；供应商只取港后拖车行。")
    uploaded = st.file_uploader("上传国际物流服务商KPI月度工作簿 (.xlsx)", type=["xlsx"], key="monthly_kpi_file")
    if uploaded is None:
        st.info("请上传月度KPI工作簿。文件仅在本次会话内分析，不写入公开GitHub或业务数据库。")
        return
    try:
        book = pd.ExcelFile(BytesIO(uploaded.getvalue()))
        missing = [name for name in SHEETS if name not in book.sheet_names]
        if missing:
            st.error("缺少工作表：" + "、".join(missing))
            return
        tables = []
        for sheet, (status_col, pass_values, fail_values) in SHEETS.items():
            frame = _read_sheet(book, sheet)
            required = {"排柜单号", "目的仓国家", "目的仓物流区域", "港后拖车行", status_col}
            if not required.issubset(frame.columns):
                st.warning(f"{sheet} 缺少字段：" + "、".join(sorted(required - set(frame.columns))))
                continue
            frame = frame[frame["目的仓国家"].astype(str).str.strip().str.upper().isin(
                ["美国", "AMERICA", "USA", "US", "UNITED STATES", "UNITED STATES OF AMERICA"])].copy()
            frame["排柜单号"] = frame["排柜单号"].astype(str).str.strip()
            frame["港后拖车行"] = frame["港后拖车行"].astype(str).str.strip()
            frame = frame[frame["排柜单号"].ne("") & frame["港后拖车行"].ne("") &
                          ~frame["港后拖车行"].isin(["港后拖车测试", "nan", "None"])].copy()
            frame["重复业务单"] = frame.duplicated("排柜单号", keep=False)
            frame["考核结果"] = frame[status_col].astype(str).str.strip().map(
                lambda v: "达标" if v in pass_values else ("不达标" if v in fail_values else "待核实"))
            frame["考核项目"] = sheet
            frame["来源状态"] = frame[status_col]
            keep = ["考核项目", "月份", "排柜单号", "箱号", "目的仓物流区域",
                    "港后拖车行", "考核结果", "来源状态", "重复业务单"]
            for col in keep:
                if col not in frame.columns:
                    frame[col] = ""
            # Conflicting duplicate business rows must not be silently scored.
            conflicts = frame.groupby("排柜单号")["考核结果"].transform("nunique").gt(1)
            frame.loc[conflicts, "考核结果"] = "待核实"
            frame = frame.drop_duplicates("排柜单号", keep="last")
            tables.append(frame[keep])
        if not tables:
            st.error("未找到可统计的美国港后拖车业务。")
            return
        detail = pd.concat(tables, ignore_index=True)
        regions = sorted(detail["目的仓物流区域"].unique().tolist())
        suppliers = sorted(detail["港后拖车行"].unique().tolist())
        c1, c2, c3 = st.columns(3)
        with c1:
            selected_region = st.selectbox("目的仓物流区域", ["全部区域"] + regions, key="monthly_kpi_region")
        with c2:
            selected_supplier = st.selectbox("港后拖车商", ["全部供应商"] + suppliers, key="monthly_kpi_supplier")
        with c3:
            months = sorted(detail["月份"].astype(str).unique().tolist())
            selected_month = st.selectbox("考核月份", ["全部月份"] + months, key="monthly_kpi_month")
        if selected_region != "全部区域":
            detail = detail[detail["目的仓物流区域"].eq(selected_region)]
        if selected_supplier != "全部供应商":
            detail = detail[detail["港后拖车行"].eq(selected_supplier)]
        if selected_month != "全部月份":
            detail = detail[detail["月份"].astype(str).eq(selected_month)]
        st.warning("仅识别工作簿明确标注的达标/不达标状态。'？'、空白、公式错误及其他状态计为待核实，"
                   "不参与得分分母。重复排柜单号有冲突时不自动判定。")
        st.metric("覆盖业务单", f"{detail['排柜单号'].nunique():,}")
        counts = detail.groupby(["港后拖车行", "考核项目", "考核结果"]).size().unstack(fill_value=0)
        for status in ["达标", "不达标", "待核实"]:
            if status not in counts.columns:
                counts[status] = 0
        counts["有效样本"] = counts["达标"] + counts["不达标"]
        counts["KPI得分%"] = (100 * counts["达标"] / counts["有效样本"].replace(0, float("nan"))).round(2)
        score = counts.reset_index().sort_values(["港后拖车行", "考核项目"])
        st.markdown("### 各港后供应商 × KPI 得分")
        st.dataframe(score, hide_index=True, use_container_width=True)
        st.download_button("导出KPI评分汇总 CSV", score.to_csv(index=False).encode("utf-8-sig"),
                           file_name="港后拖车商月度KPI评分.csv", mime="text/csv", key="monthly_kpi_scores_csv")
        pivot = score.pivot(index="港后拖车行", columns="考核项目", values="KPI得分%")
        pivot["已评分指标数"] = pivot.notna().sum(axis=1)
        pivot["五项等权参考分%"] = pivot.drop(columns="已评分指标数").mean(axis=1).round(2)
        pivot.loc[pivot["已评分指标数"].lt(len(SHEETS)), "五项等权参考分%"] = float("nan")
        st.markdown("### 供应商横向对比（仅五项有原始考核工作表的指标）")
        st.dataframe(pivot.reset_index(), hide_index=True, use_container_width=True)
        st.caption("五项等权参考分不是合同规定的正式加权总分；文件返回及时率、系统数据准确性仍需补充证据。")
        st.markdown("### 逐单考核与待核实明细")
        show_only = st.checkbox("只显示不达标及待核实", value=True, key="monthly_kpi_only_issues")
        visible = detail[detail["考核结果"].ne("达标")] if show_only else detail
        st.dataframe(visible, hide_index=True, use_container_width=True, height=430)
        st.download_button("导出逐单考核明细 CSV", visible.to_csv(index=False).encode("utf-8-sig"),
                           file_name="港后拖车商月度KPI逐单明细.csv", mime="text/csv", key="monthly_kpi_detail_csv")
    except Exception as exc:
        st.error(f"工作簿读取或计算失败：{exc}")
