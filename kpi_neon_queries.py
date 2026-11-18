"""Server-side Neon KPI filters, five-metric aggregation, and paged details.

The existing SQLite path continues to use kpi_summary.summarize.
All SQL parameters are bound; the KPI rule is identical to kpi_summary.py.
"""
import pandas as pd
from db_backend import read_sql

US_COUNTRIES = ("美国", "US", "USA", "AMERICA", "UNITED STATES", "UNITED STATES OF AMERICA")
BASE = """month=? AND metric <> '台账'
    AND upper(btrim(coalesce(payload::jsonb ->> '目的仓国家',''))) = ANY(?)
    AND (metric <> '送仓时效'
         OR btrim(coalesce(payload::jsonb ->> '排柜单号','')) <> '')"""
# Bound list uses a PostgreSQL text[] parameter through psycopg.
def params(month):
    return (month, list(US_COUNTRIES))

def filters(supplier=None, region=None):
    where, args = "", []
    if supplier is not None:
        where += " AND btrim(coalesce(payload::jsonb ->> '港后拖车行','')) = ?"
        args.append(supplier)
    if region is not None:
        where += " AND btrim(coalesce(payload::jsonb ->> '目的仓物流区域','')) = ?"
        args.append(region)
    return where, args

def options(conn, month):
    suffix, extra = "", []
    field = "港后拖车行"
    query = f"""SELECT DISTINCT btrim(coalesce(payload::jsonb ->> '{field}','')) AS value
        FROM kpi_raw_rows_v2 WHERE {BASE} {suffix} ORDER BY value"""
    return read_sql(query, conn, params=params(month) + tuple(extra))["value"].tolist()

def region_options(conn, month, supplier=None):
    suffix, extra = filters(supplier=supplier)
    query = f"""SELECT DISTINCT btrim(coalesce(payload::jsonb ->> '目的仓物流区域','')) AS value
        FROM kpi_raw_rows_v2 WHERE {BASE} {suffix} ORDER BY value"""
    return read_sql(query, conn, params=params(month) + tuple(extra))["value"].tolist()

# Python's float parser accepts ordinary decimal/scientific strings after comma
# removal. The SQL expression intentionally treats malformed and nonfinite
# numbers as unknown. Keep the regex conservative and explicit.
# IMPORTANT: db_backend._translate replaces every '?' with '%s'.
# Keep '?' out of SQL regex literals to avoid accidental psycopg placeholders.
NUMERIC_RE = r'^[+-]{0,1}([0-9]+(\\.[0-9]*){0,1}|\\.[0-9]+)([eE][+-]{0,1}[0-9]+){0,1}$'
def number(field):
    clean = f"replace(btrim(coalesce(payload::jsonb ->> '{field}','')), ',', '')"
    return f"""(CASE WHEN {clean} ~ '{NUMERIC_RE}'
        THEN {clean}::double precision ELSE NULL END)"""

def summary(conn, month, supplier=None, region=None):
    suffix, extra = filters(supplier, region)
    lfd = number("超LFD天数")
    delivery = number("送仓时效")
    standard_punctual = number("时效标准")
    standard = number("标准时效")
    pickup_empty = number("提空时效")
    return_empty = number("还柜时效")
    sql = f"""
    WITH numeric_rows AS (
        SELECT metric,
            btrim(coalesce(payload::jsonb ->> '运营判责','')) AS liability,
            {lfd} AS lfd,
            {delivery} AS delivery,
            {standard_punctual} AS punctual_standard,
            {standard} AS standard,
            {pickup_empty} AS pickup_empty,
            {return_empty} AS return_empty
        FROM kpi_raw_rows_v2
        WHERE {BASE} {suffix}
    ), evaluated AS (
        SELECT metric, liability,
            CASE metric
                WHEN '港后提柜及时率' THEN lfd > 0
                WHEN '送仓准时率' THEN delivery > punctual_standard
                WHEN '送仓时效' THEN delivery > standard
                WHEN '提空及时率' THEN pickup_empty > standard
                WHEN '还柜及时率' THEN return_empty > standard
            END AS failed
        FROM numeric_rows
    )
    SELECT metric, count(*)::bigint AS total,
           count(*) FILTER (WHERE failed IS TRUE)::bigint AS failed,
           count(*) FILTER (WHERE failed IS TRUE AND liability='车队无责')::bigint AS exempt,
           count(*) FILTER (WHERE failed IS NULL)::bigint AS unknown
    FROM evaluated GROUP BY metric
    """
    rows = read_sql(sql, conn, params=params(month) + tuple(extra))
    from kpi_summary import METRICS
    grouped = {r["metric"]: r for r in rows.to_dict("records")}
    output, warnings = [], []
    for metric in METRICS:
        r = grouped.get(metric, {})
        total, failed, exempt, unknown = (int(r.get(k, 0)) for k in ("total", "failed", "exempt", "unknown"))
        ratio = 1 - (failed - exempt) / total if total and not unknown else None
        output.append({"指标": metric, "考核期间总记录数": total,
                       "考核不达标记录数": failed, "供应商无责记录数": exempt,
                       "指标值": f"{ratio:.2%}" if ratio is not None else "待核实"})
        if unknown:
            warnings.append(f"{metric}：{unknown:,} 条记录的考核状态无法判定，指标值暂不计算")
    return pd.DataFrame(output), warnings

def detail_page(conn, month, metric, supplier=None, region=None, limit=100, offset=0):
    """Read only one page. Count is supplied by the already computed KPI summary."""
    suffix, extra = filters(supplier, region)
    where = f"{BASE} {suffix} AND metric=?"
    arguments = params(month) + tuple(extra) + (metric,)
    return read_sql(f"""SELECT source_row, payload FROM kpi_raw_rows_v2
        WHERE {where} ORDER BY source_row LIMIT ? OFFSET ?""",
        conn, params=arguments + (min(max(int(limit), 1), 100), max(int(offset), 0)))

def number(field):
    clean = f"replace(btrim(coalesce(payload::jsonb ->> '{field}','')), ',', '')"
    return f"""(CASE WHEN {clean} ~ '{NUMERIC_RE}'
        THEN {clean}::double precision ELSE NULL END)"""

def summary(conn, month, supplier=None, region=None):
    suffix, extra = filters(supplier, region)
    lfd = number("超LFD天数")
    delivery = number("送仓时效")
    standard_punctual = number("时效标准")
    standard = number("标准时效")
    pickup_empty = number("提空时效")
    return_empty = number("还柜时效")
    sql = f"""
    WITH numeric_rows AS (
        SELECT metric,
            btrim(coalesce(payload::jsonb ->> '运营判责','')) AS liability,
            {lfd} AS lfd,
            {delivery} AS delivery,
            {standard_punctual} AS punctual_standard,
            {standard} AS standard,
            {pickup_empty} AS pickup_empty,
            {return_empty} AS return_empty
        FROM kpi_raw_rows_v2
        WHERE {BASE} {suffix}
    ), evaluated AS (
        SELECT metric, liability,
            CASE metric
                WHEN '港后提柜及时率' THEN lfd > 0
                WHEN '送仓准时率' THEN delivery > punctual_standard
                WHEN '送仓时效' THEN delivery > standard
                WHEN '提空及时率' THEN pickup_empty > standard
                WHEN '还柜及时率' THEN return_empty > standard
            END AS failed
        FROM numeric_rows
    )
    SELECT metric, count(*)::bigint AS total,
           count(*) FILTER (WHERE failed IS TRUE)::bigint AS failed,
           count(*) FILTER (WHERE failed IS TRUE AND liability='车队无责')::bigint AS exempt,
           count(*) FILTER (WHERE failed IS NULL)::bigint AS unknown
    FROM evaluated GROUP BY metric
    """
    rows = read_sql(sql, conn, params=params(month) + tuple(extra))
    from kpi_summary import METRICS
    grouped = {r["metric"]: r for r in rows.to_dict("records")}
    output, warnings = [], []
    for metric in METRICS:
        r = grouped.get(metric, {})
        total, failed, exempt, unknown = (int(r.get(k, 0)) for k in ("total", "failed", "exempt", "unknown"))
        ratio = 1 - (failed - exempt) / total if total and not unknown else None
        output.append({"指标": metric, "考核期间总记录数": total,
                       "考核不达标记录数": failed, "供应商无责记录数": exempt,
                       "指标值": f"{ratio:.2%}" if ratio is not None else "待核实"})
        if unknown:
            warnings.append(f"{metric}：{unknown:,} 条记录的考核状态无法判定，指标值暂不计算")
    return pd.DataFrame(output), warnings

def detail_page(conn, month, metric, supplier=None, region=None, limit=100, offset=0):
    """Read only one page. Count is supplied by the already computed KPI summary."""
    suffix, extra = filters(supplier, region)
    where = f"{BASE} {suffix} AND metric=?"
    arguments = params(month) + tuple(extra) + (metric,)
    return read_sql(f"""SELECT source_row, payload FROM kpi_raw_rows_v2
        WHERE {where} ORDER BY source_row LIMIT ? OFFSET ?""",
        conn, params=arguments + (min(max(int(limit), 1), 100), max(int(offset), 0)))

def all_details(conn, month, metric, supplier=None, region=None):
    """Return every detail row matching the selected US KPI filters."""
    suffix, extra = filters(supplier, region)
    where = f"{BASE} {suffix} AND metric=?"
    arguments = params(month) + tuple(extra) + (metric,)
    return read_sql(f"""SELECT source_row, payload FROM kpi_raw_rows_v2
        WHERE {where} ORDER BY source_row""", conn, params=arguments)
