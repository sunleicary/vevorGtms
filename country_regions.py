"""Country and operating-region master data."""
import pandas as pd
import streamlit as st
from db_backend import connect as db_connect
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
]
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
        country_name_en TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS gtms_country_aliases (
        alias TEXT PRIMARY KEY, country_code TEXT NOT NULL)""")
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
        conn.execute("INSERT INTO gtms_countries(country_code,country_name,country_name_en) VALUES (?,?,?) ON CONFLICT(country_code) DO NOTHING",(code,cn,en))
        for alias in aliases:
            conn.execute("INSERT INTO gtms_country_aliases(alias,country_code) VALUES (?,?) ON CONFLICT(alias) DO NOTHING",(_normalize(alias),code))
    for i,(code,cn,en,abbr) in enumerate(REGIONS,1):
        conn.execute("""INSERT INTO gtms_operating_regions
            (region_code,country_code,country_name,region_name,region_name_en,abbreviation,sort_order)
            VALUES (?,?,?,?,?,?,?) ON CONFLICT(region_code) DO NOTHING""",(code,"US","美国",cn,en,abbr,i))

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
    aliases={r["alias"]:r["country_code"] for r in conn.execute("SELECT alias,country_code FROM gtms_country_aliases").fetchall()}
    conn.execute("DELETE FROM gtms_region_source_values")
    for row in source:
        raw_country=str(row["country_raw"] or "").strip()
        raw_region=str(row["region_raw"] or "").strip()
        country=aliases.get(_normalize(raw_country))
        region=_region_code(raw_region) if country=="US" else None
        conn.execute("""INSERT INTO gtms_region_source_values
            (country_raw,region_raw,country_code,region_code,record_count)
            VALUES (?,?,?,?,?)""",(raw_country,raw_region,country,region,int(row["cnt"])))
    return len(source)

def show_country_regions(user, db):
    st.title("全球国家与业务区域管理")
    with db_connect(db) as conn:
        _initialize(conn)
        initialized=conn.execute("SELECT COUNT(*) FROM gtms_region_source_values").fetchone()[0]
        if not initialized:
            _sync_existing(conn)
        if st.button("同步现有业务国家与区域", disabled=not is_admin(user)):
            count=_sync_existing(conn)
            st.success(f"已同步 {count} 组源数据国家/区域组合；原始货柜记录未修改。")
        rows=conn.execute("""SELECT region_code,country_code,country_name,region_name,
            region_name_en,abbreviation,sort_order,enabled FROM gtms_operating_regions
            ORDER BY country_code,sort_order,region_code""").fetchall()
        countries=conn.execute("SELECT * FROM gtms_countries ORDER BY country_code").fetchall()
        source=conn.execute("SELECT * FROM gtms_region_source_values ORDER BY record_count DESC").fetchall()
    records=[dict(r) for r in rows]
    st.caption("主数据与原始业务数据分开存储；国家采用 ISO 两位编码，美国区域采用 US- 前缀。")
    st.subheader("国家主数据")
    st.dataframe(pd.DataFrame([dict(x) for x in countries]),hide_index=True,use_container_width=True)
    st.subheader("现有业务国家与区域映射")
    source_records=[dict(x) for x in source]
    if source_records:
        st.metric("已同步原始国家/区域组合",len(source_records))
        st.dataframe(pd.DataFrame(source_records),hide_index=True,use_container_width=True)
        missing=[x for x in source_records if not x["country_code"] or (x["country_code"]=="US" and not x["region_code"])]
        if missing:
            st.warning(f"有 {len(missing)} 组国家或美国区域尚未识别，请核对源数据。")
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
