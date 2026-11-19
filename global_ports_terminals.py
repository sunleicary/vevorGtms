"""Global ports and terminals master data, shared by pre-port and post-port operations."""
import hashlib
import re
import pandas as pd
import streamlit as st
from db_backend import connect as db_connect, is_neon
from auth import is_admin
from country_regions import _alias_index, _initialize as initialize_countries

PORT_FIELDS = ("起运港","装货港","出运港","出口港","始发港","卸货港","目的港","到达港","进口港","港口","Port of Loading","POL","Port of Discharge","POD")
PRE_PORT_FIELDS = {"起运港","装货港","出运港","出口港","始发港","Port of Loading","POL"}
POST_PORT_FIELDS = {"卸货港","目的港","到达港","进口港","Port of Discharge","POD"}
TERMINAL_FIELDS = ("卸货码头","目的港码头","装货码头","起运港码头","码头","Terminal")
PRE_TERMINAL_FIELDS = {"装货码头","起运港码头"}
POST_TERMINAL_FIELDS = {"卸货码头","目的港码头"}
EMPTY = {"","NAN","NONE","NULL","N/A","未记录","未知","-","--"}

def clean(value):
    value=str(value or "").strip()
    return "" if value.upper() in EMPTY else value

def uid(kind, name, port=""):
    return hashlib.sha256((kind+"|"+port.casefold()+"|"+name.casefold()).encode("utf-8")).hexdigest()[:24]

def table_columns(conn, name):
    if is_neon():
        rows=conn.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=?",(name,)).fetchall()
        return {r["column_name"] for r in rows}
    return {r["name"] for r in conn.execute("PRAGMA table_info("+name+")").fetchall()}

def initialize(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS gtms_global_ports (
        port_id TEXT PRIMARY KEY, port_name TEXT NOT NULL,
        country_code TEXT NOT NULL DEFAULT '', unlocode TEXT NOT NULL DEFAULT '',
        enabled INTEGER NOT NULL DEFAULT 1, notes TEXT NOT NULL DEFAULT '')""")
    conn.execute("""CREATE TABLE IF NOT EXISTS gtms_global_terminals (
        terminal_id TEXT PRIMARY KEY, terminal_name TEXT NOT NULL,
        port_id TEXT NOT NULL DEFAULT '', enabled INTEGER NOT NULL DEFAULT 1,
        notes TEXT NOT NULL DEFAULT '')""")
    conn.execute("""CREATE TABLE IF NOT EXISTS gtms_port_terminal_sources (
        source_id TEXT PRIMARY KEY, entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL, source_field TEXT NOT NULL,
        business_side TEXT NOT NULL, record_count INTEGER NOT NULL DEFAULT 0)""")

def _side(field, kind, columns):
    if kind=="port":
        if field in PRE_PORT_FIELDS: return "港前"
        if field in POST_PORT_FIELDS: return "港后"
    else:
        if field in PRE_TERMINAL_FIELDS: return "港前"
        if field in POST_TERMINAL_FIELDS: return "港后"
    # Shared columns have no reliable business-side attribution.
    return "未区分"

# Curated exact port-name aliases; avoid substring guesses (e.g. Portland).
PORT_COUNTRY_NAMES = {
 "US": "LOS ANGELES|LONG BEACH|LA/LB|NEW YORK|NEW JERSEY|SAVANNAH|HOUSTON|CHARLESTON|NORFOLK|BALTIMORE|MIAMI|OAKLAND|SEATTLE|TACOMA|JACKSONVILLE|MOBILE|NEW ORLEANS|BOSTON|PHILADELPHIA|WILMINGTON NC|洛杉矶|长滩|纽约|新泽西|萨凡纳|休斯顿|查尔斯顿|诺福克|巴尔的摩|迈阿密|奥克兰|西雅图|塔科马",
 "CN": "SHANGHAI|NINGBO|NINGBO ZHOUSHAN|SHENZHEN|YANTIAN|SHEKOU|QINGDAO|TIANJIN|XINGANG|XIAMEN|GUANGZHOU|NANSHA|DALIAN|LIANYUNGANG|FUZHOU|RIZHAO|上海|宁波|舟山|深圳|盐田|蛇口|青岛|天津|新港|厦门|广州|南沙|大连|连云港|福州|日照",
 "NL": "ROTTERDAM|AMSTERDAM|鹿特丹|阿姆斯特丹",
 "DE": "HAMBURG|BREMERHAVEN|BREMEN|WILHELMSHAVEN|汉堡|不来梅港",
 "BE": "ANTWERP|ANTWERPEN|ZEEBRUGGE|安特卫普|泽布吕赫",
 "GB": "FELIXSTOWE|SOUTHAMPTON|LONDON GATEWAY|LIVERPOOL|IMMINGHAM|费利克斯托|南安普顿|利物浦",
 "FR": "LE HAVRE|MARSEILLE|FOS SUR MER|DUNKIRK|勒阿弗尔|马赛|敦刻尔克",
 "ES": "VALENCIA|BARCELONA|ALGECIRAS|BILBAO|瓦伦西亚|巴塞罗那|阿尔赫西拉斯",
 "IT": "GENOA|GENOVA|LA SPEZIA|TRIESTE|NAPLES|GIOIA TAURO|热那亚|拉斯佩齐亚|的里雅斯特|那不勒斯",
 "PL": "GDANSK|GDYNIA|格但斯克|格丁尼亚",
 "CZ": "PRAGUE|PRAHA|布拉格",
 "CA": "VANCOUVER|PRINCE RUPERT|MONTREAL|HALIFAX|温哥华|鲁珀特王子港|蒙特利尔|哈利法克斯",
 "MX": "MANZANILLO|LAZARO CARDENAS|VERACRUZ|ALTAMIRA|曼萨尼约|拉萨罗卡德纳斯|韦拉克鲁斯",
 "JP": "TOKYO|YOKOHAMA|OSAKA|KOBE|NAGOYA|HAKATA|东京|横滨|大阪|神户|名古屋",
 "SG": "SINGAPORE|新加坡",
 "MY": "PORT KLANG|KLANG|TANJUNG PELEPAS|PENANG|巴生港|丹绒帕拉帕斯|槟城",
 "TH": "LAEM CHABANG|BANGKOK|林查班|曼谷",
 "AE": "JEBEL ALI|KHALIFA PORT|迪拜杰贝阿里|杰贝阿里|哈利法港",
 "AU": "SYDNEY|MELBOURNE|BRISBANE|FREMANTLE|ADELAIDE|悉尼|墨尔本|布里斯班|弗里曼特尔",
}
PORT_COUNTRY_LOOKUP = {alias.strip().upper(): code for code,names in PORT_COUNTRY_NAMES.items() for alias in names.split("|")}

def name_country(name):
    import re
    value=clean(name).upper()
    suffix=re.search(r",\\s*([A-Z]{2})\\s*$", value)
    if suffix and suffix.group(1) in PORT_COUNTRY_NAMES:
        return suffix.group(1)
    value=re.sub(r"^(PORT OF|PORT|港口)\\s+", "", value).strip()
    value=re.sub(r"\\s+(PORT|港)$", "", value).strip()
    # ISO UN/LOCODE format, if explicitly supplied in a recognizable form.
    match=re.fullmatch(r"([A-Z]{2})[- ]?([A-Z]{3})",value)
    if match and match.group(1) in PORT_COUNTRY_NAMES:
        return match.group(1)
    return PORT_COUNTRY_LOOKUP.get(value)

def infer_port_countries(conn, cols, port_fields):
    """Destination warehouse country is authoritative for discharge ports only."""
    initialize_countries(conn)
    aliases=_alias_index(conn)
    discharge={}
    pre_ids=set()
    if "目的仓国家" in cols:
        for field in port_fields:
            if field not in POST_PORT_FIELDS and field not in PRE_PORT_FIELDS:
                continue
            if field in POST_PORT_FIELDS:
                query='SELECT "'+field+'" AS port_raw,"目的仓国家" AS country_raw FROM containers GROUP BY "'+field+'","目的仓国家"'
                for row in conn.execute(query).fetchall():
                    name=clean(row["port_raw"])
                    if name:
                        code=aliases.get(str(row["country_raw"] or "").strip().upper())
                        if code:
                            discharge.setdefault(uid("port",name),set()).add(code)
            else:
                for row in conn.execute('SELECT DISTINCT "'+field+'" AS port_raw FROM containers').fetchall():
                    name=clean(row["port_raw"])
                    if name:
                        pre_ids.add(uid("port",name))
    else:
        for field in port_fields:
            if field in PRE_PORT_FIELDS:
                for row in conn.execute('SELECT DISTINCT "'+field+'" AS port_raw FROM containers').fetchall():
                    name=clean(row["port_raw"])
                    if name:
                        pre_ids.add(uid("port",name))
    updated=0
    unresolved=0
    conflicts=0
    for port in conn.execute("SELECT port_id,port_name,country_code FROM gtms_global_ports").fetchall():
        pid=port["port_id"]
        countries=discharge.get(pid,set())
        if len(countries)>1:
            conflicts+=1
            continue
        # When a name appears in both origin and discharge fields, do not
        # blindly apply the destination rule if it contradicts its geography.
        geographic=name_country(port["port_name"])
        if countries:
            destination=next(iter(countries))
            if pid in pre_ids and geographic and geographic!=destination:
                conflicts+=1
                continue
            code=destination
        else:
            code=geographic
        if code and port["country_code"]!=code:
            conn.execute("UPDATE gtms_global_ports SET country_code=? WHERE port_id=?",(code,pid))
            updated+=1
        elif not code and not port["country_code"]:
            unresolved+=1
    return updated,conflicts,unresolved

def sync(conn):
    cols=table_columns(conn,"containers")
    if not cols:
        return 0,0
    port_fields=[x for x in PORT_FIELDS if x in cols]
    terminal_fields=[x for x in TERMINAL_FIELDS if x in cols]
    ports_added=set()
    terminals_added=set()
    # Preserve manually edited master attributes and existing records.
    for field in port_fields:
        rows=conn.execute('SELECT "'+field+'" AS raw,COUNT(*) AS cnt FROM containers GROUP BY "'+field+'"').fetchall()
        for row in rows:
            name=clean(row["raw"])
            if not name: continue
            pid=uid("port",name)
            conn.execute("INSERT INTO gtms_global_ports(port_id,port_name) VALUES (?,?) ON CONFLICT(port_id) DO NOTHING",(pid,name))
            side=_side(field,"port",cols)
            sid=uid("source","port|"+pid+"|"+field+"|"+side)
            conn.execute("""INSERT INTO gtms_port_terminal_sources
                (source_id,entity_type,entity_id,source_field,business_side,record_count)
                VALUES (?,?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET record_count=excluded.record_count""",
                (sid,"port",pid,field,side,int(row["cnt"])))
            ports_added.add(pid)
    # Only associate terminals with ports when a clear matching-side port column exists.
    preferred={
        "卸货码头":("卸货港","目的港"),"目的港码头":("目的港","卸货港"),
        "装货码头":("装货港","起运港"),"起运港码头":("起运港","装货港"),
    }
    for field in terminal_fields:
        port_field=next((p for p in preferred.get(field,()) if p in cols),None)
        if port_field:
            query='SELECT "'+field+'" AS raw,"'+port_field+'" AS port_raw,COUNT(*) AS cnt FROM containers GROUP BY "'+field+'","'+port_field+'"'
        else:
            query='SELECT "'+field+'" AS raw,COUNT(*) AS cnt FROM containers GROUP BY "'+field+'"'
        for row in conn.execute(query).fetchall():
            name=clean(row["raw"])
            if not name: continue
            port_name=clean(row["port_raw"]) if port_field else ""
            pid=uid("port",port_name) if port_name else ""
            tid=uid("terminal",name,port_name)
            conn.execute("""INSERT INTO gtms_global_terminals(terminal_id,terminal_name,port_id)
                VALUES (?,?,?) ON CONFLICT(terminal_id) DO NOTHING""",(tid,name,pid))
            side=_side(field,"terminal",cols)
            sid=uid("source","terminal|"+tid+"|"+field+"|"+side)
            conn.execute("""INSERT INTO gtms_port_terminal_sources
                (source_id,entity_type,entity_id,source_field,business_side,record_count)
                VALUES (?,?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET record_count=excluded.record_count""",
                (sid,"terminal",tid,field,side,int(row["cnt"])))
            terminals_added.add(tid)
    updated,conflicts,unresolved=infer_port_countries(conn,cols,port_fields)
    return len(ports_added),len(terminals_added),updated,conflicts,unresolved

def show_global_ports_terminals(user, db):
    st.title("全球港口与码头管理")
    st.caption("港前港后共用主数据；仅依据实际存在的业务字段初始化。卸货港国家以业务表的目的仓国家为准；港前起运港按港口名称识别；来源冲突保留待核对。")
    with db_connect(db) as conn:
        initialize(conn)
        try:
            counts=sync(conn)
        except Exception as exc:
            st.error("业务港口与码头同步失败，请检查数据库字段。")
            st.caption(type(exc).__name__)
            return
        ports=[dict(x) for x in conn.execute("SELECT * FROM gtms_global_ports ORDER BY port_name").fetchall()]
        terminals=[dict(x) for x in conn.execute("SELECT * FROM gtms_global_terminals ORDER BY terminal_name").fetchall()]
        sources=[dict(x) for x in conn.execute("SELECT * FROM gtms_port_terminal_sources ORDER BY entity_type,business_side,source_field").fetchall()]
    a,b,c=st.columns(3)
    a.metric("港口",len(ports))
    b.metric("码头",len(terminals))
    c.metric("本次发现的港口/码头",str(counts[0])+" / "+str(counts[1]))
    st.caption(f"国家代码更新 {counts[2]} 条；来源国家冲突 {counts[3]} 条；仍未识别 {counts[4]} 条。卸货港按目的仓国家确定，港前起运港按名称识别。")
    st.caption("同步只补充缺失的主数据并刷新来源计数，不覆盖人工编辑字段。")
    tab1,tab2,tab3=st.tabs(["港口主数据","码头主数据","业务来源与统计"])
    with tab1:
        st.dataframe(pd.DataFrame(ports),hide_index=True,use_container_width=True)
        if ports:
            st.download_button("导出港口 CSV",pd.DataFrame(ports).to_csv(index=False).encode("utf-8-sig"),file_name="gtms_ports.csv",mime="text/csv")
    with tab2:
        st.dataframe(pd.DataFrame(terminals),hide_index=True,use_container_width=True)
        if terminals:
            st.download_button("导出码头 CSV",pd.DataFrame(terminals).to_csv(index=False).encode("utf-8-sig"),file_name="gtms_terminals.csv",mime="text/csv")
    with tab3:
        st.dataframe(pd.DataFrame(sources),hide_index=True,use_container_width=True)
        st.info("来源字段不等同于实际业务环节。共享字段标为“未区分”，不根据拖车供应商名称推断港前/港后。")
    if not is_admin(user):
        return
    st.subheader("主数据维护")
    entity=st.radio("维护对象",["港口","码头"],horizontal=True)
    records=ports if entity=="港口" else terminals
    options={r["port_id"] if entity=="港口" else r["terminal_id"]:r for r in records}
    selected=st.selectbox("选择记录",["新增"]+list(options),format_func=lambda x:"新增" if x=="新增" else (options[x]["port_name"] if entity=="港口" else options[x]["terminal_name"])+" · "+x[:8])
    old=options.get(selected,{})
    with st.form("port_terminal_editor"):
        name=st.text_input("名称",old.get("port_name",old.get("terminal_name","")))
        if entity=="港口":
            country=st.text_input("国家 ISO 两位编码（待确认可留空）",old.get("country_code",""))
            unlocode=st.text_input("UN/LOCODE（待确认可留空）",old.get("unlocode",""))
        else:
            port_options={"":"待确认/未关联"}|{p["port_id"]:p["port_name"] for p in ports}
            port_id=st.selectbox("所属港口",list(port_options),index=list(port_options).index(old.get("port_id","")) if old.get("port_id","") in port_options else 0,format_func=lambda x:port_options[x])
        notes=st.text_area("备注",value=old.get("notes",""))
        enabled=st.checkbox("启用",value=bool(old.get("enabled",1)))
        save=st.form_submit_button("保存")
    if save:
        name=clean(name)
        if not name:
            st.error("名称不能为空")
            return
        if entity=="港口" and (country.strip() and (len(country.strip())!=2 or not country.strip().isalpha())):
            st.error("国家编码必须为两位字母")
            return
        with db_connect(db) as conn:
            if entity=="港口":
                if old:
                    conn.execute("UPDATE gtms_global_ports SET port_name=?,country_code=?,unlocode=?,notes=?,enabled=? WHERE port_id=?",(name,country.strip().upper(),unlocode.strip().upper(),notes,int(enabled),selected))
                else:
                    conn.execute("INSERT INTO gtms_global_ports(port_id,port_name,country_code,unlocode,notes,enabled) VALUES (?,?,?,?,?,?) ON CONFLICT(port_id) DO NOTHING",(uid("port",name),name,country.strip().upper(),unlocode.strip().upper(),notes,int(enabled)))
            else:
                if old:
                    conn.execute("UPDATE gtms_global_terminals SET terminal_name=?,port_id=?,notes=?,enabled=? WHERE terminal_id=?",(name,port_id,notes,int(enabled),selected))
                else:
                    conn.execute("INSERT INTO gtms_global_terminals(terminal_id,terminal_name,port_id,notes,enabled) VALUES (?,?,?,?,?) ON CONFLICT(terminal_id) DO NOTHING",(uid("terminal",name,port_id),name,port_id,notes,int(enabled)))
        st.success("保存成功")
        st.rerun()
