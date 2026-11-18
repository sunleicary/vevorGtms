"""Five-column KPI summary calculated from imported workbook payloads.

Metric value is the supplier pass rate after excluding non-liable failures.\nDurations and standards must be numeric and expressed in matching units.
"""
import json
import math
import pandas as pd

METRICS = ("港后提柜及时率", "送仓准时率", "送仓时效", "提空及时率", "还柜及时率")
DURATION_FIELDS = {
    "送仓准时率": "送仓时效",
    "送仓时效": "送仓时效",
    "提空及时率": "提空时效",
    "还柜及时率": "还柜时效",
}
STANDARD_FIELD = "标准时效"
EXEMPT = "车队无责"

def _clean(value):
    return str(value if value is not None else "").strip()

def _number(value):
    raw = _clean(value).replace(",", "")
    if not raw:
        return None
    try:
        number = float(raw)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def summarize(raw):
    summary, warnings = [], []
    for metric in METRICS:
        part = raw.loc[raw["metric"].eq(metric)] if not raw.empty else pd.DataFrame()
        records = []
        for value in part["payload"] if not part.empty else []:
            try:
                records.append(value if isinstance(value, dict) else json.loads(value))
            except (TypeError, ValueError, json.JSONDecodeError):
                warnings.append(f"{metric}：存在无法解析的原始记录")
        total = len(records)
        failed, exempt = 0, 0
        unknown = 0
        for record in records:
            if metric == "港后提柜及时率":
                days = _number(record.get("超LFD天数"))
                if days is None:
                    unknown += 1
                    continue
                is_failed = days > 0
            else:
                actual_field = DURATION_FIELDS[metric]
                actual = _number(record.get(actual_field))
                standard_field = "时效标准" if metric == "送仓准时率" else STANDARD_FIELD
                standard = _number(record.get(standard_field))
                if actual is None or standard is None:
                    unknown += 1
                    continue
                is_failed = actual > standard
            if is_failed:
                failed += 1
                if _clean(record.get("运营判责")) == EXEMPT:
                    exempt += 1
        if unknown:
            warnings.append(f"{metric}：{unknown:,} 条记录的考核状态无法判定，指标值暂不计算")
        ratio = 1 - (failed - exempt) / total if total and not unknown else None
        summary.append({
            "指标": metric,
            "考核期间总记录数": total,
            "考核不达标记录数": failed,
            "供应商无责记录数": exempt,
            "指标值": f"{ratio:.2%}" if ratio is not None else "待核实",
        })
    return pd.DataFrame(summary), warnings
