--
-- MySQL lightcount SQL create script
-- (see maintenance tips below)
--

DROP TABLE IF EXISTS node_tbl;
CREATE TABLE node_tbl (
	node_id TINYINT UNSIGNED AUTO_INCREMENT NOT NULL,
	node_name VARCHAR(255) NOT NULL,
	-- Set the expect_data_interval to non-NULL to check if you're still
	-- getting input from this node. This defines how long there may be no
	-- new data for this node before a warning is sent (see contrib
	-- cron.hourly lightcountheartbeat for a checking method).
	expect_data_interval INT UNSIGNED NULL DEFAULT NULL, -- seconds
	PRIMARY KEY (node_id),
	KEY (node_name)
);

DROP TABLE IF EXISTS ip_range_tbl;
CREATE TABLE ip_range_tbl (
	ip_begin INT UNSIGNED NOT NULL,
	ip_end INT UNSIGNED NOT NULL,
	node_id INT NULL REFERENCES node_tbl (node_id),
	KEY (ip_begin, ip_end),
	KEY (node_id)
);
INSERT INTO ip_range_tbl VALUES (INET_ATON('0.0.0.0'), INET_ATON('255.255.255.255'), NULL);

DROP TABLE IF EXISTS sample_tbl;
CREATE TABLE sample_tbl (
	-- unixtime holds measurement-start-time (interval is defined in timer module)
	unixtime INT NOT NULL,
	node_id TINYINT UNSIGNED NOT NULL REFERENCES node_tbl (node_id),
	vlan_id SMALLINT UNSIGNED NOT NULL,
	ip INT UNSIGNED NOT NULL,
	in_pps SMALLINT UNSIGNED NOT NULL, -- packets/second in
	in_bps INT UNSIGNED NOT NULL, -- bytes/second in
	out_pps SMALLINT UNSIGNED NOT NULL, -- packets/second out
	out_bps INT UNSIGNED NOT NULL, -- bytes/second out
	PRIMARY KEY (unixtime, node_id, vlan_id, ip),
	KEY (node_id),
	KEY (vlan_id),
	KEY (ip)
);

DROP VIEW IF EXISTS ip_range_vw;
CREATE VIEW ip_range_vw AS
SELECT
	ip_begin, INET_NTOA(ip_begin) AS human_ip_begin,
	ip_end, INET_NTOA(ip_end) AS human_ip_end,
	ip_range_tbl.node_id, node_name
FROM ip_range_tbl LEFT JOIN node_tbl USING (node_id);

DROP VIEW IF EXISTS sample_vw;
CREATE VIEW sample_vw AS
SELECT
	unixtime, FROM_UNIXTIME(unixtime) AS time,
	sample_tbl.node_id, node_name,
	ip, INET_NTOA(ip) AS human_ip,
	vlan_id,
	in_pps, in_bps, out_pps, out_bps
FROM sample_tbl LEFT JOIN node_tbl USING (node_id);


--
-- Maintenance tip #1
-- CREATING A WRITE ONLY ACCOUNT FOR THE DAEMON
--

-- CREATE USER 'traffic_w'@'%' IDENTIFIED BY 'somepassword';
-- GRANT SELECT ON ip_range_tbl TO 'traffic_w'@'%';
-- GRANT SELECT, INSERT ON node_tbl TO 'traffic_w'@'%';
-- GRANT INSERT ON sample_tblTO 'traffic_w'@'%';


--
-- Maintenance tip #2
-- REMOVING RECORDS THAT ARE NOT IN ip_range_tbl FROM sample_tbl
--

-- SELECT * FROM sample_tbl s
-- LEFT JOIN ip_range_tbl t ON t.node_id IS NULL
--     AND t.ip_begin <= s.ip AND s.ip <= t.ip_end
-- WHERE s.unixtime >= 1249884000 AND s.unixtime < 1249884000 + 28800
--     AND t.ip_begin IS NULL;
--
-- +------------+---------+---------+------------+--------+--------+---------+---------+----------+--------+---------+
-- | unixtime   | node_id | vlan_id | ip         | in_pps | in_bps | out_pps | out_bps | ip_begin | ip_end | node_id |
-- +------------+---------+---------+------------+--------+--------+---------+---------+----------+--------+---------+
-- | 1249902960 |       1 |       0 |  174393876 |      0 |     20 |       0 |      31 |     NULL |   NULL |    NULL | 
-- | 1249902960 |       1 |       0 |  174393886 |      0 |      0 |       0 |       9 |     NULL |   NULL |    NULL | 
-- ...
-- | 1249902990 |       1 |       0 | 1607978050 |      0 |     43 |       0 |      72 |     NULL |   NULL |    NULL | 
-- | 1249902990 |       1 |       0 | 3758096385 |      0 |     43 |       0 |       0 |     NULL |   NULL |    NULL | 
-- +------------+---------+---------+------------+--------+--------+---------+---------+----------+--------+---------+
-- 18 rows in set (1.01 sec)
-- 
-- DELETE FROM s USING sample_tbl s
-- LEFT JOIN ip_range_tbl t ON t.node_id IS NULL
--     AND t.ip_begin <= s.ip AND s.ip <= t.ip_end
-- WHERE s.unixtime >= 1249884000 AND s.unixtime < 1249884000 + 28800
--     AND t.ip_begin is null;
--
-- Query OK, 18 rows affected (1.48 sec)
