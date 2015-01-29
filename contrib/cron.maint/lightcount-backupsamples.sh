#!/bin/sh
# DUMP LIGHTCOUNT CSV DATA FOR THE CURRENT WEEK, STORES AT MOST 7 COPIES
#
dumpdir="`dirname "$0"`/lightcount-dumps"
trafutildir="`dirname "$0"`/lightcount-trafutil"

prefix="$dumpdir/sample_tbl.week`date +%V`"
for x in `seq 7`; do
	if [ ! -r "$prefix-$x.csv.bz2" ] ; then
		fn="$prefix-$x.csv"
		break
	fi
done

if [ -z "$fn" ]; then
	echo "$0: Already 7 files for this week?" >&2
	exit 1
fi

"$trafutildir/trafutil.py" dump "$fn" -t week -c "$trafutildir/lightcount.conf" --quiet
nice bzip2 -9 "$fn"
