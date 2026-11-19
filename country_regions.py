"""Country and operating-region master data."""
import json
import pandas as pd
import streamlit as st
from db_backend import connect as db_connect, is_neon
from auth import is_admin

REGIONS = [
 ("US-NJ","新泽西","New Jersey","NJ"),
 ("US-LALB","洛杉矶／长滩","Los Angeles / Long Beach","LA/LB"),
 ("US-HOU","休斯顿","Houston","HOU"),
 ("US-ATL","亚特兰大","Atlanta","ATL"),
 ("US-CHI","芝加哥","Chicago","CHI"),
 ("US-SAV","萨凡纳","Savannah","SAV"),
]
COUNTRIES = [
 ("US","美国","United States",["美国","US","USA","AMERICA","UNITED STATES","UNITED STATES OF AMERICA"]),
 ("CA","加拿大","Canada",["加拿大","CA","CANADA"]),
 ("GB","英国","United Kingdom",["英国","UK","GB","GREAT BRITAIN","UNITED KINGDOM"]),
 ("DE","德国","Germany",["德国","DE","GERMANY"]),
 ("FR","法国","France",["法国","FR","FRANCE"]),
 ("IT","意大利","Italy",["意大利","IT","ITALY"]),
 ("ES","西班牙","Spain",["西班牙","ES","SPAIN"]),
 ("AU","澳大利亚","Australia",["澳大利亚","AU","AUSTRALIA"]),
 ("JP","日本","Japan",["日本","JP","JAPAN"]),
 ("MX","墨西哥","Mexico",["墨西哥","MX","MEXICO"]),
 ("NL","荷兰","Netherlands",["荷兰","NL","NETHERLANDS"]),
 ("PL","波兰","Poland",["波兰","PL","POLAND"]),
 ("BE","比利时","Belgium",["比利时","BE","BELGIUM"]),
 ("SG","新加坡","Singapore",["新加坡","SG","SINGAPORE"]),
 ("MY","马来西亚","Malaysia",["马来西亚","MY","MALAYSIA"]),
 ("TH","泰国","Thailand",["泰国","TH","THAILAND"]),
 ("AE","阿联酋","United Arab Emirates",["阿联酋","AE","UAE","UNITED ARAB EMIRATES"]),
 ("CZ","捷克","Czech Republic",["捷克","CZ","CZECH REPUBLIC","CZECHIA"]),
 ("CN","中国","China",["中国","CN","CHINA","PRC"]),
]
def _aliases(row):
    try:
        values=json.loads(row["aliases"] or "[]")
        return values if isinstance(values,list) else []
    except (ValueError,TypeError):
        return []

def _alias_index(conn):
    index={}
    for row in conn.execute("SELECT country_code,country_name,country_name_en,aliases FROM gtms_countries").fetchall():
        for alias in [row["country_code"],row["country_name"],row["country_name_en"]]+_aliases(row):
            key=_normalize(alias)
            if key:
                index[key]=row["country_code"]
    return index

def _add_alias(conn,code,alias):
    row=conn.execute("SELECT aliases FROM gtms_countries WHERE country_code=?",(code,)).fetchone()
    if row is None:
        raise ValueError("国家编码不存在")
    alias=_normalize(alias)
    index=_alias_index(conn)
    if alias in index and index[alias]!=code:
        raise ValueError("别名已属于另一个国家")
    values=sorted(set(_normalize(x) for x in _aliases(row))|{alias})
    conn.execute("UPDATE gtms_countries SET aliases=? WHERE country_code=?",
                 (json.dumps(values,ensure_ascii=False),code))

def _normalize(value):
    return str(value or "").strip().upper()
def _region_code(value):
    s=_normalize(value)
    for code,cn,en,abbr in REGIONS:
        keys={
            "US-NJ":("新泽西","NEW JERSEY","NJ"),
            "US-LALB":("洛杉矶","LOS ANGELES","LONG BEACH","LA/LB","美西CA"),
            "US-HOU":("休斯顿","HOUSTON","HOU","德州","TEXAS"),
            "US-ATL":("亚特兰大","ATLANTA","ATL","佐治亚"),
            "US-CHI":("芝加哥","CHICAGO","CHI","伊利诺伊"),
            "US-SAV":("萨凡纳","SAVANNAH","SAV"),
        }[code]
        if s in {_normalize(cn),_normalize(en),_normalize(abbr)} or any(k in s for k in keys):
            return code
    return None

def _initialize(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS gtms_countries (
        country_code TEXT PRIMARY KEY, country_name TEXT NOT NULL,
        country_name_en TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
        aliases TEXT NOT NULL DEFAULT '[]')""")
    columns=[r["name"] for r in conn.execute("PRAGMA table_info(gtms_countries)").fetchall()] if not is_neon() else [
        r["column_name"] for r in conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='gtms_countries'").fetchall()]
    if "aliases" not in columns:
        conn.execute("ALTER TABLE gtms_countries ADD COLUMN aliases TEXT NOT NULL DEFAULT '[]'")
    # Legacy candidates are computed live from containers; no persisted table.
    conn.execute("DROP TABLE IF EXISTS gtms_country_candidates")
    conn.execute("""CREATE TABLE IF NOT EXISTS gtms_region_source_values (
        country_raw TEXT NOT NULL, region_raw TEXT NOT NULL,
        country_code TEXT, region_code TEXT, record_count INTEGER NOT NULL,
        PRIMARY KEY (country_raw,region_raw))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS gtms_operating_regions (
        region_code TEXT PRIMARY KEY, country_code TEXT NOT NULL,
        country_name TEXT NOT NULL, region_name TEXT NOT NULL,
        region_name_en TEXT NOT NULL, abbreviation TEXT NOT NULL,
        sort_order INTEGER NOT NULL DEFAULT 99, enabled INTEGER NOT NULL DEFAULT 1)""")
    for code,cn,en,aliases in COUNTRIES:
        conn.execute("""INSERT INTO gtms_countries
            (country_code,country_name,country_name_en,aliases)
            VALUES (?,?,?,?) ON CONFLICT(country_code) DO NOTHING""",
            (code,cn,en,json.dumps(sorted(set(_normalize(x) for x in aliases)),ensure_ascii=False)))
    # One-time migration: preserve manually mapped aliases from the former table.
    legacy_exists=(conn.execute("SELECT 1 FROM information_schema.tables WHERE table_name='gtms_country_aliases'").fetchone()
        if is_neon() else conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='gtms_country_aliases'").fetchone())
    if legacy_exists:
        for row in conn.execute("SELECT alias,country_code FROM gtms_country_aliases").fetchall():
            if conn.execute("SELECT 1 FROM gtms_countries WHERE country_code=?",(row["country_code"],)).fetchone():
                _add_alias(conn,row["country_code"],row["alias"])
        conn.execute("DROP TABLE gtms_country_aliases")
    for code,country,country_name,cn,en,abbr in [
        ("CZ-01","CZ","捷克","捷克","Czech Republic","CZ"),
        ("CN-EAST","CN","中国","华东","East China","EAST"),
    ]:
        conn.execute("""INSERT INTO gtms_operating_regions
            (region_code,country_code,country_name,region_name,region_name_en,abbreviation,sort_order)
            VALUES (?,?,?,?,?,?,99) ON CONFLICT(region_code) DO NOTHING""",
            (code,country,country_name,cn,en,abbr))
    # Remove obsolete Seattle master record after consolidating it into LA/LB.
    conn.execute("DELETE FROM gtms_operating_regions WHERE region_code=?", ("US-SEA",))
    for i,(code,cn,en,abbr) in enumerate(REGIONS,1):
        conn.execute("""INSERT INTO gtms_operating_regions
            (region_code,country_code,country_name,region_name,region_name_en,abbreviation,sort_order)
            VALUES (?,?,?,?,?,?,?) ON CONFLICT(region_code) DO NOTHING""",(code,"US","美国",cn,en,abbr,i))

    # A country-level default region is allowed only if no subregion exists.
    # Remove obsolete defaults when explicit regions exist (notably US).
    for row in conn.execute("SELECT country_code,country_name,country_name_en FROM gtms_countries").fetchall():
        code=row["country_code"]
        has_subregion=conn.execute(
            "SELECT 1 FROM gtms_operating_regions WHERE country_code=? AND region_code<>? LIMIT 1",
            (code,code)).fetchone()
        if has_subregion:
            conn.execute("DELETE FROM gtms_operating_regions WHERE region_code=? AND country_code=?",
                         (code,code))
        else:
            conn.execute("""INSERT INTO gtms_operating_regions
                (region_code,country_code,country_name,region_name,region_name_en,abbreviation,sort_order)
                VALUES (?,?,?,?,?,?,?) ON CONFLICT(region_code) DO NOTHING""",
                (code,code,row["country_name"],row["country_name"],row["country_name_en"],code,0))

def _resolve_region(conn, country, raw_region):
    """Resolve against master regions, preserving conflicts for review."""
    if not country:
        return None
    raw=_normalize(raw_region)
    rows=conn.execute(
        "SELECT region_code,region_name,region_name_en,abbreviation FROM gtms_operating_regions WHERE country_code=? AND enabled=1",
        (country,)).fetchall()
    by_code={r["region_code"]:r for r in rows}
    if country=="US":
        if "西雅图" in raw or "SEATTLE" in raw:
            return "US-LALB" if "US-LALB" in by_code else None
        matched=_region_code(raw_region)
        return matched if matched in by_code else None
    for r in rows:
        if raw and raw in {_normalize(r[k]) for k in ("region_code","region_name","region_name_en","abbreviation")}:
            return r["region_code"]
    # A country with a single country-level region needs no further subdivision.
    if country in by_code and len(rows)==1:
        return country
    if not raw and len(rows)==1:
        return rows[0]["region_code"]
    return None

def _sync_existing(conn):
    # Read existing source values; do not rewrite the container business table.
    try:
        source=conn.execute('''SELECT COALESCE("目的仓国家",'') AS country_raw,
            COALESCE("目的仓物流区域",'') AS region_raw, COUNT(*) AS cnt
            FROM containers GROUP BY 1,2''').fetchall()
    except Exception as exc:
        if "no such table" in str(exc).lower() or "does not exist" in str(exc).lower():
            return 0
        raise
    aliases=_alias_index(conn)
    conn.execute("DELETE FROM gtms_region_source_values")
    for row in source:
        raw_country=str(row["country_raw"] or "").strip()
        raw_region=str(row["region_raw"] or "").strip()
        country=aliases.get(_normalize(raw_country))
        region=_resolve_region(conn,country,raw_region)
        # Explicit country-specific "other" bucket in source mappings.
        # Do not create an additional US operating-region master record.
        if country=="US" and _normalize(raw_region) in {
            "美国-TIKTOK抖音官方仓","美国-其他"
        }:
            region="US-OTHER"
        if country=="CZ" and _normalize(raw_region) in {
            "欧洲-西班牙","欧洲-法国","欧洲-意大利"
        }:
            region="CZ-OTHER"
        # Country-specific source labels that correspond to existing subregions.
        if country=="CZ" and raw_region=="欧洲-捷克":
            region="CZ-01"
        if country=="CN" and raw_region=="中国-华东":
            region="CN-EAST"
        conn.execute("""INSERT INTO gtms_region_source_values
            (country_raw,region_raw,country_code,region_code,record_count)
            VALUES (?,?,?,?,?)""",(raw_country,raw_region,country,region,int(row["cnt"])))
    return len(source)

def show_country_regions(user, db):
    st.title("全球国家与业务区域管理")
    with db_connect(db) as conn:
        _initialize(conn)
        # Always refresh derived mappings so imported containers and aliases are reflected.
        count=_sync_existing(conn)
        if st.button("同步现有业务国家与区域", disabled=not is_admin(user)):
            st.success(f"已同步 {count} 组源数据国家/区域组合；原始货柜记录未修改。")
        rows=conn.execute("""SELECT region_code,country_code,country_name,region_name,
            region_name_en,abbreviation,sort_order,enabled FROM gtms_operating_regions
            ORDER BY country_code,sort_order,region_code""").fetchall()
        countries=conn.execute("SELECT * FROM gtms_countries ORDER BY country_code").fetchall()
        source=conn.execute("SELECT * FROM gtms_region_source_values ORDER BY record_count DESC").fetchall()
    records=[dict(r) for r in rows]
    st.caption("主数据与原始业务数据分开存储；国家采用 ISO 两位编码，美国区域采用 US- 前缀。")
    st.subheader("国家主数据")
    st.dataframe(pd.DataFrame([{**dict(x),"aliases":"、".join(_aliases(x))} for x in countries]),hide_index=True,use_container_width=True)
    st.subheader("现有数据中未识别的国家名称")
    alias_lookup={}
    for item in countries:
        for name in [item["country_code"],item["country_name"],item["country_name_en"]]+_aliases(item):
            alias_lookup[_normalize(name)]=item["country_code"]
    candidate_counts={}
    for item in source:
        raw=str(item["country_raw"] or "").strip()
        if raw and _normalize(raw) not in alias_lookup:
            candidate_counts[raw]=candidate_counts.get(raw,0)+int(item["record_count"])
    pending=[{"country_raw":raw,"record_count":count,"status":"待确认"}
             for raw,count in sorted(candidate_counts.items(),key=lambda pair:-pair[1])]
    if pending:
        st.warning(f"发现 {len(pending)} 个未识别的原始国家名称，已实时识别，等待管理员确认国家编码。")
        st.dataframe(pd.DataFrame(pending),hide_index=True,use_container_width=True)
        if is_admin(user):
            with st.form("resolve_country"):
                raw=st.selectbox("选择原始国家名称", [r["country_raw"] for r in pending])
                target=st.selectbox("映射到标准国家", [r["country_code"]+" · "+r["country_name"] for r in countries])
                resolve=st.form_submit_button("确认国家映射并重新同步")
            if resolve:
                code=target.split(" · ",1)[0]
                with db_connect(db) as conn:
                    _add_alias(conn,code,raw)
                    _sync_existing(conn)
                st.success("国家映射已保存。")
                st.rerun()
    else:
        st.success("当前已同步的国家名称均能匹配标准国家主数据。")
    st.subheader("现有业务国家与区域映射")
    source_records=[dict(x) for x in source]
    if source_records:
        st.metric("已同步原始国家/区域组合",len(source_records))
        st.dataframe(pd.DataFrame(source_records),hide_index=True,use_container_width=True)
        missing=[x for x in source_records if not x["country_code"] or not x["region_code"]]
        if missing:
            st.warning(f"有 {len(missing)} 组国家或业务区域需要核对（下表列出具体原因）。")
            issues=[{**x,"问题原因":("国家未识别" if not x["country_code"] else "区域未匹配到该国家的运营区域")} for x in missing]
            st.dataframe(pd.DataFrame(issues),hide_index=True,use_container_width=True)
            st.download_button("导出待核对组合 CSV",
                pd.DataFrame(issues).to_csv(index=False).encode("utf-8-sig"),
                file_name="gtms_unresolved_country_regions.csv",mime="text/csv")
        else:
            st.success("所有现有业务国家与区域组合均已匹配。")
        st.download_button("导出原始国家区域映射",pd.DataFrame(source_records).to_csv(index=False).encode("utf-8-sig"),file_name="gtms_country_region_mapping.csv",mime="text/csv")
    else:
        st.info("尚未同步现有货柜业务的国家与区域，请点击上方同步按钮。")
    st.subheader("运营区域主数据")
    st.dataframe(pd.DataFrame(records).rename(columns={
        "region_code":"区域编码","country_code":"国家代码","country_name":"国家",
        "region_name":"中文名称","region_name_en":"英文名称","abbreviation":"简称",
        "sort_order":"排序","enabled":"启用"}),hide_index=True,use_container_width=True)
    st.download_button("导出全部区域 CSV",pd.DataFrame(records).to_csv(index=False).encode("utf-8-sig"),
                       file_name="gtms_regions.csv",mime="text/csv")
    if not is_admin(user):
        return
    selected=st.selectbox("编辑区域",["新增区域"]+[r["region_code"] for r in records])
    old=next((r for r in records if r["region_code"]==selected),{})
    with st.form("edit_region"):
        code=st.text_input("区域编码",old.get("region_code",""),disabled=bool(old))
        country=st.text_input("国家代码",old.get("country_code","US"))
        country_name=st.text_input("国家名称",old.get("country_name","美国"))
        cn=st.text_input("区域中文名",old.get("region_name",""))
        en=st.text_input("区域英文名",old.get("region_name_en",""))
        abbr=st.text_input("简称",old.get("abbreviation",""))
        order=st.number_input("排序",min_value=1,value=int(old.get("sort_order",99)))
        enabled=st.checkbox("启用",value=bool(old.get("enabled",1)))
        submit=st.form_submit_button("保存区域")
    if submit:
        code,country,country_name,cn,en,abbr=[x.strip() for x in (code,country,country_name,cn,en,abbr)]
        country=country.upper()
        if not all((code,country,country_name,cn,en,abbr)) or len(country)!=2 or not country.isalpha():
            st.error("请完整填写区域信息，并使用两位国家代码。")
        elif not code.startswith(country+"-") or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-/" for c in code):
            st.error("区域编码必须采用大写国家代码-区域简称格式。")
        else:
            try:
                with db_connect(db) as conn:
                    if old:
                        conn.execute("""UPDATE gtms_operating_regions SET country_code=?,country_name=?,
                            region_name=?,region_name_en=?,abbreviation=?,sort_order=?,enabled=?
                            WHERE region_code=?""",
                            (country,country_name,cn,en,abbr,int(order),int(enabled),code))
                    else:
                        conn.execute("""INSERT INTO gtms_operating_regions
                            (region_code,country_code,country_name,region_name,region_name_en,
                            abbreviation,sort_order,enabled) VALUES (?,?,?,?,?,?,?,?)""",
                            (code,country,country_name,cn,en,abbr,int(order),int(enabled)))
                st.success("保存成功")
                st.rerun()
            except Exception as exc:
                st.error("保存失败，请检查编码是否重复或数据库连接。")
                st.caption(type(exc).__name__)
