-- Snapshot from uploaded 全量数据表 (2).xls, 2026-11-19. Safe, repeatable seed.
BEGIN;
CREATE TABLE IF NOT EXISTS gtms_customs_brokers (
 broker_id BIGINT PRIMARY KEY, broker_name TEXT NOT NULL, broker_code TEXT NOT NULL DEFAULT '',
 country_code TEXT NOT NULL DEFAULT '', state_code TEXT NOT NULL DEFAULT '',
 operating_region_code TEXT NOT NULL DEFAULT '', contact_name TEXT NOT NULL DEFAULT '',
 email TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '', aliases TEXT NOT NULL DEFAULT '',
 enabled INTEGER NOT NULL DEFAULT 1, notes TEXT NOT NULL DEFAULT '',
 created_from_business INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS gtms_customs_broker_sources (
 source_field TEXT NOT NULL, source_name TEXT NOT NULL, broker_id BIGINT NOT NULL,
 record_count BIGINT NOT NULL DEFAULT 0, PRIMARY KEY(source_field,source_name),
 FOREIGN KEY(broker_id) REFERENCES gtms_customs_brokers(broker_id)
);
CREATE TEMP TABLE seed_brokers (source_id BIGINT, name TEXT, cnt BIGINT) ON COMMIT DROP;
INSERT INTO seed_brokers VALUES
(1,'HONGKONG YONGLONG',10932),
(2,'一八',7106),
(3,'RHENUS',6653),
(4,'GUANGUANTONG',3035),
(5,'乔达',2347),
(6,'海程邦达',2341),
(7,'REISHI INTERNATIONAL GROUP LIMITED',1433),
(8,'Russell A Farrow Limited',499),
(9,'testqingguan',379),
(10,'Toll Global Forwarding (Beijing) Co., Ltd. Ningbo Branch',193),
(11,'CHR',177),
(12,'优备艾佳',173),
(13,'深圳云翔',136),
(14,'盈和',85),
(15,'海祥',52),
(16,'融汇',47),
(17,'艾姆勒',30),
(18,'易联鑫达',26),
(19,'B2B业务',6),
(20,'B2C业务',4),
(21,'安达迅',2),
(22,'AAJD',1);
-- Use existing broker ID when an exact name is already registered.
INSERT INTO gtms_customs_brokers (broker_id,broker_name,created_from_business,notes)
SELECT (SELECT COALESCE(MAX(broker_id),0) FROM gtms_customs_brokers)+
 ROW_NUMBER() OVER (ORDER BY s.source_id),s.name,1,'2026-11-19 上传文件初始化；待核验'
FROM seed_brokers s
WHERE NOT EXISTS (SELECT 1 FROM gtms_customs_brokers b WHERE LOWER(b.broker_name)=LOWER(s.name))
ON CONFLICT(broker_id) DO NOTHING;
INSERT INTO gtms_customs_broker_sources(source_field,source_name,broker_id,record_count)
SELECT '清关行',s.name,b.broker_id,s.cnt FROM seed_brokers s
JOIN gtms_customs_brokers b ON LOWER(b.broker_name)=LOWER(s.name)
ON CONFLICT(source_field,source_name) DO UPDATE
SET broker_id=excluded.broker_id,record_count=excluded.record_count;
COMMIT;
