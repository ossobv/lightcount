-- MySQL lightcount SQL create script

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
