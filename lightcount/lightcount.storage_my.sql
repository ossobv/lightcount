-- MySQL lightcount SQL create script

DROP TABLE IF EXISTS node_tbl;
CREATE TABLE node_tbl (
	node_id INT AUTO_INCREMENT NOT NULL,
	node_name VARCHAR(255) NOT NULL,
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
	node_id INT NOT NULL REFERENCES node_tbl (node_id),
	vlan_id INT NOT NULL,
	ip INT UNSIGNED NOT NULL,
	in_pps INT UNSIGNED NOT NULL, -- packets/second in
	in_bps BIGINT UNSIGNED NOT NULL, -- bytes/second in
	out_pps INT UNSIGNED NOT NULL, -- packets/second out
	out_bps BIGINT UNSIGNED NOT NULL, -- bytes/second out
	PRIMARY KEY (unixtime, node_id, vlan_id, ip),
	KEY (unixtime),
	KEY (node_id),
	KEY (vlan_id),
	KEY (ip)
);

DROP VIEW IF EXISTS sample_vw;
CREATE VIEW sample_vw AS
SELECT
	unixtime, FROM_UNIXTIME(unixtime) AS time,
	ip, INET_NTOA(ip) AS human_ip,
	vlan_id,
	in_pps, in_bps, out_pps, out_bps
FROM sample_tbl;
