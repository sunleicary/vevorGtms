import os
import sqlite3
from db_backend import connect as db_connect, is_neon
import sys
from lxml import etree

DB = os.path.join(os.path.dirname(__file__), "port_ops.db")
FIELDS = ["排柜单号","目的仓","实际送货仓","目的仓物流区域","目的仓国家","ATA日期","目的港/站卸柜日期", "目的港预计卸柜时间",
          "货代","清关行","港前拖车行","卸货港","卸货码头","目的港码头","码头","Terminal","目的地","船公司","实际船名","实际航次","ETA日期",
          "箱号","MB/L No.","港后拖车行","LFD","可提柜时间","海关放行时间","清关完成时间",
          "进口实际提箱时间","约仓时间","实际送仓时间","实际到海外仓日期",
          "实际还柜日期","预计还柜时间","进口查验开始日期","进口查验完成日期","港后内部备注","ATD日期","卸货港ETA日期","卸货港ATA日期","ETDDATE","ETA（计算）"]

def load(path):
    # Import into a temporary DB first; never destroy the existing database on failure.
    temp_db = DB + ".importing"
    if os.path.exists(temp_db):
        os.remove(temp_db)
    conn = sqlite3.connect(temp_db)
    try:
        columns = ",".join('"' + f + '" TEXT' for f in FIELDS)
        conn.execute("CREATE TABLE containers (id INTEGER PRIMARY KEY," + columns + ")")
        seen_orders = set()
        missing_orders = 0
        duplicate_orders = []
        cols = None
        batch = []
        count = 0
        insert = "INSERT INTO containers (" + ",".join('"' + f + '"' for f in FIELDS) + ") VALUES (" + ",".join("?" for _ in FIELDS) + ")"
        for _, el in etree.iterparse(path, events=("end",), tag="tr", html=True):
            cells = el.xpath("./th|./td")
            if cols is None:
                cols = ["".join(c.itertext()).strip() for c in cells]
                el.clear()
                continue
            if len(cells) == len(cols):
                values = ["".join(c.itertext()).strip() for c in cells]
                row = dict(zip(cols, values))
                if any(row.get(f, "").strip() for f in ("箱号", "排柜单号")):
                    order_no = row.get("排柜单号", "").strip()
                    if not order_no:
                        missing_orders += 1
                    elif order_no in seen_orders:
                        if len(duplicate_orders) < 10:
                            duplicate_orders.append(order_no)
                    else:
                        seen_orders.add(order_no)
                    batch.append(tuple((row.get("ETA（计算）") or row.get("ETA(计算)", "")) if f == "ETA（计算）" else row.get(f, "") for f in FIELDS))
                    count += 1
            if len(batch) >= 500:
                conn.executemany(insert, batch)
                batch = []
            el.clear()
            while el.getprevious() is not None:
                del el.getparent()[0]
        if batch:
            conn.executemany(insert, batch)
        duplicate_count = count - len(seen_orders) - missing_orders
        if missing_orders or duplicate_count:
            samples = ", ".join(duplicate_orders)
            raise ValueError(
                f"业务主键校验失败：排柜单号为空 {missing_orders} 行，"
                f"排柜单号重复 {duplicate_count} 行。重复样例：{samples}。"
                "导入已中止，原数据库保持不变。请核实原始业务记录。"
            )
        conn.execute('CREATE UNIQUE INDEX idx_order_no ON containers("排柜单号")')
        conn.execute('CREATE INDEX idx_container_no ON containers("箱号")')
        conn.execute('CREATE INDEX idx_region ON containers("目的仓物流区域")')
        conn.commit()
        if not count:
            raise ValueError("未发现有效货柜记录，请检查源文件格式及字段")
    except Exception:
        conn.close()
        os.remove(temp_db)
        raise
    conn.close()
    if is_neon():
        # Parse/validate fully before touching the existing production table.
        # The DELETE + INSERT are one transaction; errors restore the old dataset.
        from psycopg import sql
        try:
            with sqlite3.connect(temp_db) as source:
                source.row_factory = sqlite3.Row
                with db_connect(DB) as target:
                    for field in FIELDS:
                        quoted_field = '"' + field.replace('"', '""') + '"'
                        target.execute("ALTER TABLE containers ADD COLUMN IF NOT EXISTS " + quoted_field + " TEXT")
                    target.execute("DELETE FROM containers")
                    quoted = ", ".join('"' + c.replace('"', '""') + '"' for c in FIELDS)
                    statement = "INSERT INTO containers (id, " + quoted + ") VALUES (" + ",".join(["?"] * (len(FIELDS) + 1)) + ")"
                    cursor = source.execute("SELECT * FROM containers ORDER BY id")
                    while True:
                        chunk = cursor.fetchmany(500)
                        if not chunk:
                            break
                        target.executemany(statement, [tuple(row) for row in chunk])
        finally:
            if os.path.exists(temp_db):
                os.remove(temp_db)
    else:
        os.replace(temp_db, DB)
    print("Imported global records:", count)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python import_data.py source.xls")
    load(sys.argv[1])
