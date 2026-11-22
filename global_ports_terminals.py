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

def ensure_sqlite_v2(conn):
    """Create SQLite-compatible integer-key master tables without replacing data."""
    conn.execute("""CREATE TABLE IF NOT EXISTS gtms_ports_v2 (
        port_id INTEGER PRIMARY KEY, port_name TEXT NOT NULL,
        country_code TEXT NOT NULL DEFAULT '', unlocode TEXT NOT NULL DEFAULT '',
        canonical_port_id INTEGER, classification TEXT NOT NULL DEFAULT 'seaport_or_port_city',
        legacy_port_id TEXT NOT NULL DEFAULT '',
        state_code TEXT NOT NULL DEFAULT '', operating_region_code TEXT NOT NULL DEFAULT '')""")
    conn.execute("""CREATE TABLE IF NOT EXISTS gtms_terminals_v2 (
        terminal_id INTEGER PRIMARY KEY, terminal_name TEXT NOT NULL,
        port_id INTEGER NOT NULL, operator_name TEXT NOT NULL DEFAULT '',
        terminal_type TEXT NOT NULL DEFAULT 'container',
        source_url TEXT NOT NULL DEFAULT '',
        verification_status TEXT NOT NULL DEFAULT 'unverified',
        legacy_terminal_id TEXT NOT NULL DEFAULT '',
        state_code TEXT NOT NULL DEFAULT '', operating_region_code TEXT NOT NULL DEFAULT '')""")
    # Existing installations may have older v2 schemas: the upgrade below
    # adds the optional geographic columns without deleting any records.


def upgrade_v2_geography(conn):
    """Idempotent schema extension and PNCT association correction."""
    for table in ("gtms_ports_v2","gtms_terminals_v2"):
        cols=table_columns(conn,table)
        for field in ("state_code","operating_region_code"):
            if field not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {field} TEXT NOT NULL DEFAULT ''")
    for name,state,region in [("ATLANTA","GA","US-ATL"),("HOUSTON","TX","US-HOU"),("LONG BEACH","CA","US-LALB"),("LOS ANGELES","CA","US-LALB"),("SAVANNAH","GA","US-SAV"),("SEATTLE","WA","US-LALB"),("TACOMA","WA","US-LALB")]:
        conn.execute("UPDATE gtms_ports_v2 SET state_code=?,operating_region_code=? WHERE country_code='US' AND (UPPER(port_name)=? OR UPPER(port_name) LIKE ?) AND state_code=''",(state,region,name,name+",%"))
    # Always seed Port Newark and PNCT, including when neither exists in the imported CSV.
    port=conn.execute("SELECT port_id FROM gtms_ports_v2 WHERE UPPER(TRIM(port_name))='PORT NEWARK' AND country_code='US' LIMIT 1").fetchone()
    if port:
        pid=port["port_id"]
    else:
        pid=int(conn.execute("SELECT COALESCE(MAX(port_id),0)+1 AS n FROM gtms_ports_v2").fetchone()["n"])
        conn.execute("INSERT INTO gtms_ports_v2(port_id,port_name,country_code,unlocode,canonical_port_id,classification,legacy_port_id,state_code,operating_region_code) VALUES (?,?,?,?,?,?,?,?,?)",(pid,"PORT NEWARK","US","USNWK",pid,"seaport_or_port_city","gtms-system-port-newark","NJ","US-NJ"))
    conn.execute("UPDATE gtms_ports_v2 SET state_code='NJ',operating_region_code='US-NJ' WHERE port_id=?",(pid,))
    pnct=conn.execute("SELECT terminal_id FROM gtms_terminals_v2 WHERE UPPER(terminal_name) LIKE '%PORT NEWARK CONTAINER TERMINAL%' OR UPPER(TRIM(terminal_name))='PNCT'").fetchall()
    if not pnct:
        tid=int(conn.execute("SELECT COALESCE(MAX(terminal_id),0)+1 AS n FROM gtms_terminals_v2").fetchone()["n"])
        conn.execute("INSERT INTO gtms_terminals_v2(terminal_id,terminal_name,port_id,operator_name,terminal_type,source_url,verification_status,legacy_terminal_id,state_code,operating_region_code) VALUES (?,?,?,?,?,?,?,?,?,?)",(tid,"Port Newark Container Terminal (PNCT)",pid,"Port Newark Container Terminal","container","https://www.pnct.net/","official_source_reviewed","gtms-system-pnct","NJ","US-NJ"))
    else:
        for t in pnct:
            conn.execute("UPDATE gtms_terminals_v2 SET port_id=?,state_code='NJ',operating_region_code='US-NJ' WHERE terminal_id=?",(pid,t["terminal_id"]))
    for pattern in ("%MAHER%","%APM TERMINALS ELIZABETH%","%PORT LIBERTY BAYONNE%","%GCT BAYONNE%"):
        conn.execute("UPDATE gtms_terminals_v2 SET state_code='NJ',operating_region_code='US-NJ' WHERE UPPER(terminal_name) LIKE ? AND state_code=''",(pattern,))
    conn.execute("""UPDATE gtms_terminals_v2 SET
        state_code=(SELECT p.state_code FROM gtms_ports_v2 p WHERE p.port_id=gtms_terminals_v2.port_id),
        operating_region_code=(SELECT p.operating_region_code FROM gtms_ports_v2 p WHERE p.port_id=gtms_terminals_v2.port_id)
        WHERE state_code='' AND port_id IN (SELECT port_id FROM gtms_ports_v2 WHERE state_code<>'')""")


def show_global_ports_terminals(user, db):
    st.title("全球港口与码头管理")
    st.caption("SQLite 整数主键港口及码头主数据；自动建表，不覆盖既有记录。")
    with db_connect(db) as conn:
        if is_neon():
            exists=conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() AND table_name IN ('gtms_ports_v2','gtms_terminals_v2')").fetchall()
            available={r["table_name"] for r in exists}
        else:
            available={r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('gtms_ports_v2','gtms_terminals_v2')").fetchall()}
        if not is_neon():
            ensure_sqlite_v2(conn)
        elif len(available)!=2:
            st.warning("当前 PostgreSQL 缺少整数主键港口及码头主数据表。")
            return
        upgrade_v2_geography(conn)
        ports=[dict(r) for r in conn.execute("SELECT * FROM gtms_ports_v2 ORDER BY port_id").fetchall()]
        terminals=[dict(r) for r in conn.execute("SELECT * FROM gtms_terminals_v2 ORDER BY terminal_id").fetchall()]
    c1,c2,c3=st.columns(3)
    c1.metric("港口记录",len(ports))
    c2.metric("码头记录",len(terminals))
    c3.metric("标准港口",len({p["canonical_port_id"] for p in ports}))
    ptab,ttab,stab=st.tabs(["港口主数据","码头主数据","数据完整性"])
    with ptab:
        st.dataframe(pd.DataFrame(ports),hide_index=True,use_container_width=True)
        if ports:
            st.download_button("导出港口CSV",pd.DataFrame(ports).to_csv(index=False).encode("utf-8-sig"),"gtms_ports_v2.csv","text/csv")
    with ttab:
        port_names={p["port_id"]:p["port_name"] for p in ports}
        display=[{**t,"所属港口":port_names.get(t["port_id"],"未找到")} for t in terminals]
        st.dataframe(pd.DataFrame(display),hide_index=True,use_container_width=True)
        if terminals:
            st.download_button("导出码头CSV",pd.DataFrame(terminals).to_csv(index=False).encode("utf-8-sig"),"gtms_terminals_v2.csv","text/csv")
    with stab:
        orphans=[t for t in terminals if t["port_id"] not in {p["port_id"] for p in ports}]
        pending=[t for t in terminals if t["verification_status"] not in ("official_source_reviewed","verified")]
        st.write(f"码头关联异常：{len(orphans)}；待进一步核验：{len(pending)}")
        if pending:
            st.dataframe(pd.DataFrame(pending),hide_index=True,use_container_width=True)
    if not is_admin(user):
        return
    st.subheader("主数据标准操作：增加 / 修改 / 删除 / 查询")
    st.caption("上方表格支持查询与导出；下方支持增加、修改及安全删除。")
    kind=st.radio("对象",["港口","码头"],horizontal=True)
    records=ports if kind=="港口" else terminals
    id_field="port_id" if kind=="港口" else "terminal_id"
    choices={str(r[id_field]):r for r in records}
    selection=st.selectbox("选择记录",["新增"]+list(choices),format_func=lambda x:"新增" if x=="新增" else f"{x} · {choices[x]['port_name' if kind=='港口' else 'terminal_name']}")
    current=choices.get(selection,{})
    with st.form("v2_master_edit"):
        name=st.text_input("名称",current.get("port_name",current.get("terminal_name","")))
        if kind=="港口":
            country=st.text_input("国家代码",current.get("country_code",""))
            locode=st.text_input("UN/LOCODE",current.get("unlocode",""))
            classification=st.text_input("分类",current.get("classification","seaport_or_port_city"))
            state=st.text_input("州/省代码",current.get("state_code",""))
            region=st.text_input("运营区域",current.get("operating_region_code",""))
        else:
            port_options={p["port_id"]:p["port_name"] for p in ports}
            if not port_options:
                st.warning("请先建立港口")
                return
            keys=list(port_options)
            selected_port=st.selectbox("所属港口",keys,index=keys.index(current["port_id"]) if current.get("port_id") in keys else 0,format_func=lambda x:f"{x} · {port_options[x]}")
            state=st.text_input("州/省代码",current.get("state_code",""))
            region=st.text_input("运营区域",current.get("operating_region_code",""))
            operator=st.text_input("运营商",current.get("operator_name",""))
            terminal_type=st.text_input("码头类型",current.get("terminal_type","container"))
            source_url=st.text_input("核验来源",current.get("source_url",""))
            verification=st.selectbox("核验状态",["unverified","official_source_reviewed","verified"],index=["unverified","official_source_reviewed","verified"].index(current.get("verification_status","unverified")) if current.get("verification_status","unverified") in ["unverified","official_source_reviewed","verified"] else 0)
        submitted=st.form_submit_button("保存")
    if submitted:
        name=clean(name)
        if not name:
            st.error("名称不能为空")
            return
        if kind=="港口" and (len(country.strip())!=2 or not country.strip().isalpha()):
            st.error("国家代码必须为两位英文字母")
            return
        with db_connect(db) as conn:
            if selection=="新增":
                next_id=int(conn.execute(f"SELECT COALESCE(MAX({id_field}),0)+1 AS next_id FROM gtms_{'ports' if kind=='港口' else 'terminals'}_v2").fetchone()["next_id"])
            else:
                next_id=int(selection)
            if kind=="港口":
                if selection=="新增":
                    conn.execute("INSERT INTO gtms_ports_v2(port_id,port_name,country_code,unlocode,canonical_port_id,classification,legacy_port_id,state_code,operating_region_code) VALUES (?,?,?,?,?,?,?,?,?)",(next_id,name,country.upper().strip(),locode.upper().strip(),next_id,classification,"manual-"+str(next_id),state.upper().strip(),region.upper().strip()))
                else:
                    conn.execute("UPDATE gtms_ports_v2 SET port_name=?,country_code=?,unlocode=?,classification=?,state_code=?,operating_region_code=? WHERE port_id=?",(name,country.upper().strip(),locode.upper().strip(),classification,state.upper().strip(),region.upper().strip(),next_id))
            else:
                if selection=="新增":
                    conn.execute("INSERT INTO gtms_terminals_v2(terminal_id,terminal_name,port_id,operator_name,terminal_type,source_url,verification_status,legacy_terminal_id,state_code,operating_region_code) VALUES (?,?,?,?,?,?,?,?,?,?)",(next_id,name,selected_port,operator,terminal_type,source_url,verification,"manual-"+str(next_id),state.upper().strip(),region.upper().strip()))
                else:
                    conn.execute("UPDATE gtms_terminals_v2 SET terminal_name=?,port_id=?,operator_name=?,terminal_type=?,source_url=?,verification_status=?,state_code=?,operating_region_code=? WHERE terminal_id=?",(name,selected_port,operator,terminal_type,source_url,verification,state.upper().strip(),region.upper().strip(),next_id))
        st.success("保存成功")
        st.rerun()

    st.divider()
    st.subheader("删除主数据")
    if selection=="新增":
        st.caption("请选择现有记录后执行删除。")
        return
    with st.form("delete_port_terminal_v2"):
        confirm=st.checkbox("确认永久删除所选记录")
        delete=st.form_submit_button("删除所选记录")
    if delete:
        if not confirm:
            st.error("请先勾选删除确认")
            return
        with db_connect(db) as conn:
            if kind=="港口":
                refs=conn.execute("SELECT COUNT(*) AS n FROM gtms_terminals_v2 WHERE port_id=?",(int(selection),)).fetchone()["n"]
                canonical=conn.execute("SELECT COUNT(*) AS n FROM gtms_ports_v2 WHERE canonical_port_id=? AND port_id<>?",(int(selection),int(selection))).fetchone()["n"]
                if refs or canonical:
                    st.error(f"禁止删除：关联码头 {refs} 条，关联港口别名 {canonical} 条。请先处理关联关系。")
                    return
                conn.execute("DELETE FROM gtms_ports_v2 WHERE port_id=?",(int(selection),))
            else:
                conn.execute("DELETE FROM gtms_terminals_v2 WHERE terminal_id=?",(int(selection),))
        st.success("删除成功")
        st.rerun()
