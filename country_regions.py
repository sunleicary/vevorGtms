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
def show_country_regions(user, db):
    st.title("全球国家与业务区域管理")
    with db_connect(db) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS gtms_operating_regions (
            region_code TEXT PRIMARY KEY, country_code TEXT NOT NULL,
            country_name TEXT NOT NULL, region_name TEXT NOT NULL,
            region_name_en TEXT NOT NULL, abbreviation TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 99, enabled INTEGER NOT NULL DEFAULT 1)""")
        for i,(code,cn,en,abbr) in enumerate(REGIONS,1):
            conn.execute("""INSERT INTO gtms_operating_regions
                (region_code,country_code,country_name,region_name,region_name_en,abbreviation,sort_order)
                VALUES (?,?,?,?,?,?,?) ON CONFLICT (region_code) DO NOTHING""",
                (code,"US","美国",cn,en,abbr,i))
        rows=conn.execute("""SELECT region_code,country_code,country_name,region_name,
            region_name_en,abbreviation,sort_order,enabled FROM gtms_operating_regions
            ORDER BY country_code,sort_order,region_code""").fetchall()
    records=[dict(r) for r in rows]
    st.caption("美国六大港后运营区域；区域编码永久唯一，现有记录不会被初始化覆盖。")
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
