#!/bin/sh
# PRUNE THE LIGHTCOUNT sample_tbl TABLE BY DELETING RECORDS OF MORE THAN TWO
# MONTHS OLD. RUN THIS EVERY 15 MINUTES. (THE lightcount-dumpcsv.sh SCRIPT
# SHOULD HAVE MADE CSV BACKUPS OF THIS DATA.)
#
mydb=osso_traffic_db2

myuser="`sed -ne 's/^ *user *= *\(.*\) *$/\1/p' /etc/mysql/debian.cnf | head -n1`"
mypass="`sed -ne 's/^ *password *= *\(.*\) *$/\1/p' /etc/mysql/debian.cnf | head -n1`"
mysql="mysql -u$myuser -p$mypass $mydb"

last_month="`date -d '-2 month' '+%s'`"
stmt="DELETE FROM sample_tbl WHERE unixtime < $last_month LIMIT 10000";
echo "$stmt" | $mysql

# It's possible that you'll want to OPTIMIZE TABLE every now and
# then. But be aware: aborting the optimize table statement, yields
# an unusable DB.
#
# mysql> optimize table sample_tbl;
# +-----------------------------+----------+----------+----------+
# | Table                       | Op       | Msg_type | Msg_text |
# +-----------------------------+----------+----------+----------+
# | osso_traffic_db2.sample_tbl | optimize | status   | OK       | 
# +-----------------------------+----------+----------+----------+
# 1 row in set (1 min 29.56 sec)
#
#
# When the table is unusable:
# osso-www:~# mysqlrepair --databases osso_traffic_db2 -uroot -p
# Enter password: 
# osso_traffic_db2.ip_range_tbl                      OK
# osso_traffic_db2.node_tbl                          OK
# osso_traffic_db2.sample_tbl
# warning  : Number of rows changed from 29195 to 35646977
# status   : OK
#
# This takes around 4 minutes.
