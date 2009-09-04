#!/bin/sh
# MAKE AN SQL DUMP OF THE TWO NON-sample_tbl TABLES FOR EVERY DAY OF THE WEEK
#
dumpdir="`dirname "$0"`/lightcount-dumps"
mydb=osso_traffic_db2

myuser="`sed -ne 's/^ *user *= *\(.*\) *$/\1/p' /etc/mysql/debian.cnf | head -n1`"
mypass="`sed -ne 's/^ *password *= *\(.*\) *$/\1/p' /etc/mysql/debian.cnf | head -n1`"
mysqldump="mysqldump -u$myuser -p$mypass --skip-extended-insert --skip-lock-tables $mydb"

curday="`date +%a | tr '[[:upper:]]' '[[:lower:]]'`"
for tbl in ip_range_tbl node_tbl; do
	$mysqldump "$tbl" > "$dumpdir/$tbl.weekday-$curday.sql"
done
