#!/bin/sh
# DUMP THE LIGHTCOUNT CSV DATA FOR THE PREVIOUS MONTH (ONCE!)
#
dumpdir=/srv/www/detool/data/csv
trafutildir="`dirname "$0"`/lightcount-trafutil"

last_month_short="`date -d '-1 month' '+%y%m'`"
last_month_long="`date -d '-1 month' '+%Y-%m-01'`"

fn="$dumpdir/osso_traffic.${last_month_short}amsterdamtz.csv"
if [ ! -e "$fn.bz2" ]; then
	"$trafutildir/trafutil.py" dump "$fn" -t month \
		-c "$trafutildir/lightcount.conf" \
		--begin-date "$last_month_long" --quiet
	nice bzip2 -9 "$fn"
fi

fn="$dumpdir/osso_traffic_sumip.${last_month_short}amsterdamtz.csv"
if [ ! -e "$fn.bz2" ]; then
	"$trafutildir/trafutil.py" sumip "$fn" -t month \
		-c "$trafutildir/lightcount.conf" \
		--begin-date "$last_month_long" --quiet
	nice bzip2 -9 "$fn"
fi
