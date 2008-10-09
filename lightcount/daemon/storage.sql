DROP TABLE IF EXISTS node_tbl;
CREATE TABLE node_tbl (
	node_id INT PRIMARY KEY AUTO_INCREMENT NOT NULL,
	node_name VARCHAR(255) NOT NULL
);

DROP TABLE IF EXISTS ip_range_tbl;
CREATE TABLE ip_range_tbl (
	ip_begin INT UNSIGNED NOT NULL,
	ip_end INT UNSIGNED NOT NULL,
	node_id INT NULL REFERENCES node_tbl (node_id),
	INDEX ip_range_idx (ip_begin, ip_end)
);
INSERT INTO ip_range_tbl VALUES (INET_ATON('0.0.0.0'), INET_ATON('255.255.255.255'), NULL);

DROP TABLE IF EXISTS count_tbl;
CREATE TABLE count_tbl (
	count_id INT PRIMARY KEY AUTO_INCREMENT NOT NULL,
	-- unixtime stores time when measurement begins (interval is defined in timer module)
	unixtime INT NOT NULL,
	node_id INT NOT NULL REFERENCES node_tbl (node_id),
	vlan_id INT NOT NULL,
	ip INT UNSIGNED NOT NULL,
	in_pps INT UNSIGNED NOT NULL, -- packets/second in
	in_bps BIGINT UNSIGNED NOT NULL, -- bytes/second in
	out_pps INT UNSIGNED NOT NULL, -- packets/second out
	out_bps BIGINT UNSIGNED NOT NULL -- bytes/second out
);
