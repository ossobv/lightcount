/* vim: set ts=8 sw=4 sts=4 noet: */
/*======================================================================
Copyright (C) 2008,2009 OSSO B.V. <walter+lightcount@osso.nl>
This file is part of LightCount.

LightCount is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

LightCount is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with LightCount.  If not, see <http://www.gnu.org/licenses/>.
======================================================================*/

#include "lightcount.h"
#include <mysql/mysql.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Settings */
#define DONT_STORE_ZERO_ENTRIES 1	    /* delete all entries with all values zero */
#define USE_DAEMON_IP_FILTER 1		    /* filter IP addresses daemon-side */
#define USE_PREPARED_STATEMENTS 1	    /* use MySQL prepared statements */
#define BUFSIZE 2048			    /* all sprintfs below are calculated to fit in this */


static char const *storage__config_file;    /* configuration file name */
static MYSQL *storage__mysql;		    /* gets reinitialized every write */
static int storage__node_id;		    /* may vary per write */
static uint32_t storage__unixtime_begin;    /* varies per write */
static uint32_t storage__interval;	    /* may vary per write */
static uint32_t storage__intervald2;	    /* interval divided by two */

#ifdef USE_DAEMON_IP_FILTER
static uint32_t *storage__ipfilter_rbegin;  /* ip ranges to filter [from, to, from, to, ...] */
static uint32_t *storage__ipfilter_rend;    /* end of ip ranges to filter */
#endif /* !USE_DAEMON_IP_FILTER */

#ifdef USE_PREPARED_STATEMENTS
static MYSQL_STMT *storage__mysqlps;	    /* prepared statement handle */
static MYSQL_BIND storage__mysqlbind[8];    /* prepared statement bind handles */
static uint32_t storage__mysqldataip;	    /* prepared statement data container for ip */
static struct ipcount_t storage__mysqldata; /* prepared statement data container for rest */
#endif /* USE_PREPARED_STATEMENTS */

static char storage__conf_host[256];	    /* db hostname/ip */
static int storage__conf_port;		    /* db port */
static char storage__conf_user[256];	    /* db username */
static char storage__conf_pass[256];	    /* db password */
static char storage__conf_dbase[256];	    /* db database */


static int storage__db_connect();
static void storage__db_disconnect();
static int storage__db_get_node_id(char const *safe_node_name);
static int storage__read_config(char const *config_file);
static void storage__rtrim(char *io);
static void storage__write_ip(uint32_t ip, struct ipcount_t const *ipcount);

#ifdef USE_DAEMON_IP_FILTER
static int storage__ipfilter_begin();
static void storage__ipfilter_end();
static int storage__ipfilter_in_range(uint32_t ip);
#endif /* USE_DAEMON_IP_FILTER */

#ifndef USE_PREPARED_STATEMENTS
static void storage__write_record_sql(uint32_t unixtime, int node_id, uint16_t vlan, uint32_t ip,
        uint32_t in_pps, uint64_t in_bps, uint32_t out_pps, uint64_t out_bps);
#endif /* !USE_PREPARED_STATEMENTS */

#ifdef USE_PREPARED_STATEMENTS
static int storage__db_prepstmt_begin();
static void storage__db_prepstmt_end();
static void storage__write_record_prepstmt(uint16_t vlan, uint32_t ip,
        uint32_t in_pps, uint64_t in_bps, uint32_t out_pps, uint64_t out_bps);
#endif /* USE_PREPARED_STATEMENTS */



void storage_help() {
    printf(
	"/********************* module: storage (mysql) ********************************/\n"
	"#%s DONT_STORE_ZERO_ENTRIES\n"
	"#%s USE_DAEMON_IP_FILTER\n"
	"#%s USE_PREPARED_STATEMENTS\n"
	"\n"
	"Stores average values in the MySQL database as specified in the supplied\n"
	"configuration file. This file gets reloaded on every write, so you can switch\n"
	"databases on the fly if you wish.\n"
	"\n"
	"The configuration file must look like:\n"
	"  storage_host=HOSTNAME\n"
	"  storage_port=PORT\n"
	"  storage_user=USERNAME\n"
	"  storage_pass=PASSWORD\n"
	"  storage_dbase=DATABASE\n"
	"\n"
	"Only counts for IP addresses that are listed in the `ip_range_tbl` table are\n"
	"stored. Those ranges can be specified on a `node_id` basis if desired. See\n"
	"the storage.sql CREATE script for more information.\n"
	"\n"
	"When DONT_STORE_ZERO_ENTRIES is defined, no values with all zeroes are stored.\n"
	"For calculation purposes no value is the same as all zeroes anyway. But if\n"
	"you're interested in seeing whether there has been _any_ traffic at all, you'll\n"
	"want to undefine it.\n"
	"\n"
	"Define or undefine USE_DAEMON_IP_FILTER to select whether you want to do the\n"
	"filtering of the IP addresses in ip_range_tbl by the daemon or by the SQL\n"
	"server respectively. Filtering by SQL is probably only better if you have\n"
	"really many or very large IP ranges (covering 10+ percent of the entire IP\n"
	"space).\n"
	"\n"
	"You can define or undefine USE_PREPARED_STATEMENTS to enable/disable use of\n"
	"MySQL prepared statements. Using them is recommended as it reduces the amount of\n"
	"traffic sent to the server and the server only has to parse the query once.\n"
	"\n",
#ifdef DONT_STORE_ZERO_ENTRIES
	"define",
#else /* !DONT_STORE_ZERO_ENTRIES */
	"undef",
#endif /* !DONT_STORE_ZERO_ENTRIES */
#ifdef USE_DAEMON_IP_FILTER
	"define",
#else /* !USE_DAEMON_IP_FILTER */
	"undef",
#endif /* !USE_DAEMON_IP_FILTER */
#ifdef USE_PREPARED_STATEMENTS
	"define"
#else /* !USE_PREPARED_STATEMENTS */
	"undef"
#endif /* !USE_PREPARED_STATEMENTS */
    );
}

int storage_open(char const *config_file) {
    storage__config_file = config_file;
    /* Read config file once as a test */
    if (storage__read_config(storage__config_file) != 0) {
	fprintf(stderr, "storage_open: Failed to open configuration file.\n");
	return -1;
    }
    /* Init mysql lib */
    if (mysql_library_init(-1, NULL, NULL) != 0) {
	fprintf(stderr, "mysql_library_init: Failed to initialize.\n");
	return -1;
    }
    return 0;
}

void storage_close() {
    /* Finish mysql lib */
    mysql_library_end();
}

void storage_write(uint32_t unixtime_begin, uint32_t interval, void *memory) {
    char buf[BUFSIZE];

    /* Connect to database */
    if (storage__db_connect() != 0)
	return;

    /* Store values to use when running `memory_enum`. */
    storage__unixtime_begin = unixtime_begin;
    storage__interval = interval;
    storage__intervald2 = interval >> 1;
    util_get_safe_node_name(buf, 256); /* 256 < BUFSIZE */
    storage__node_id = storage__db_get_node_id(buf);
    if (storage__node_id == -1) {
	storage__db_disconnect();
	return;
    }

#ifdef USE_DAEMON_IP_FILTER
    /* Get IP addresses to filter */
    if (storage__ipfilter_begin() != 0) {
	storage__db_disconnect();
	return;
    }
#endif /* USE_DAEMON_IP_FILTER */

#ifdef USE_PREPARED_STATEMENTS
    /* Prepare MyMSQL prepared statement */
    if (storage__db_prepstmt_begin() != 0) {
	storage__db_disconnect();
	return;
    }
#endif /* USE_PREPARED_STATEMENTS */
    
    /* Finally! Insert data! */
    memory_enum(memory, &storage__write_ip);

#ifdef USE_PREPARED_STATEMENTS
    /* Free MyMSQL prepared statement */
    storage__db_prepstmt_end();
#endif /* USE_PREPARED_STATEMENTS */

#ifdef USE_DAEMON_IP_FILTER
    /* Free IP filter memory */
    storage__ipfilter_end();
#endif /* USE_DAEMON_IP_FILTER */

    /* Disconnect */
    storage__db_disconnect();
}

static int storage__db_connect() {
    /* Read config file to get database connect config */
    storage__read_config(storage__config_file); /* ignore return value */
    /* Connect to database */
    if ((storage__mysql = mysql_init(NULL)) == NULL
	    || mysql_real_connect(storage__mysql, storage__conf_host,
				  storage__conf_user, storage__conf_pass,
				  storage__conf_dbase, storage__conf_port,
				  NULL, 0) == NULL) {
	if (storage__mysql != NULL)
	    mysql_close(storage__mysql);
	fprintf(stderr, "mysql_init/mysql_real_connect: %s\n", mysql_error(storage__mysql));
	return -1;
    }
    return 0;
}

static void storage__db_disconnect() {
    if (storage__mysql != NULL) {
	mysql_close(storage__mysql);
	storage__mysql = NULL;
    }
}

static int storage__db_get_node_id(char const *safe_node_name) {
    char buf[BUFSIZE];
    int ret;
    MYSQL_RES *mysql_res;
    MYSQL_ROW mysql_row;

    sprintf(buf, "SELECT node_id FROM node_tbl WHERE node_name = '%s'", safe_node_name);
    if (mysql_query(storage__mysql, buf)) {
	fprintf(stderr, "mysql_query: %s\n", mysql_error(storage__mysql));
	return -1;
    }

    if ((mysql_res = mysql_store_result(storage__mysql)) == NULL) {
	fprintf(stderr, "mysql_query: %s\n", mysql_error(storage__mysql));
	return -1;
    }

    if (mysql_num_rows(mysql_res) >= 1) {
	assert(mysql_num_rows(mysql_res) == 1);
	mysql_row = mysql_fetch_row(mysql_res);
	ret = atoi(mysql_row[0]);
	assert(ret > 0);
    } else {
	sprintf(buf, "INSERT INTO node_tbl (node_name) VALUES ('%s')", safe_node_name);
	if (mysql_query(storage__mysql, buf)) {
	    fprintf(stderr, "mysql_query: %s\n", mysql_error(storage__mysql));
	    ret = -1;
	} else {
	    ret = mysql_insert_id(storage__mysql);
	    assert(ret > 0);
	}
    }

    mysql_free_result(mysql_res);
    return ret;
}

static int storage__read_config(char const *config_file) {
    FILE *fp;
    char buf[BUFSIZE];

    /* Set all sorts of defaults and null-terminate */
    storage__conf_host[sizeof(storage__conf_host)-1] = '\0';
    strncpy(storage__conf_host, "localhost", sizeof(storage__conf_host) - 1);
    storage__conf_port = 3306;
    storage__conf_user[sizeof(storage__conf_user)-1] = '\0';
    strncpy(storage__conf_user, "root", sizeof(storage__conf_user) - 1);
    storage__conf_pass[sizeof(storage__conf_pass)-1] = '\0';
    strncpy(storage__conf_pass, "", sizeof(storage__conf_pass) - 1);
    storage__conf_dbase[sizeof(storage__conf_dbase)-1] = '\0';
    strncpy(storage__conf_dbase, "", sizeof(storage__conf_dbase) - 1);

    /* Open file to find user values */
    if ((fp = fopen(config_file, "r")) == NULL) {
	perror("fopen");
	fprintf(stderr, "storage__read_config: Using defaults: mysql://%s@%s:%d/%s.\n",
		storage__conf_user, storage__conf_host, storage__conf_port, storage__conf_dbase);
	return -1;
    }

    /* Read through file */
    while (!feof(fp) && !ferror(fp)) {
	if (fgets(buf, BUFSIZE, fp) != NULL) {
#define check(b, c, d) \
    if (strncmp(b, c, sizeof(c) - 1) == 0) { \
	strncpy(d, b + sizeof(c) - 1, sizeof(d) - 1); \
	storage__rtrim(d); \
    } else
	    check(buf, "storage_host=", storage__conf_host)
	    check(buf, "storage_user=", storage__conf_user)
	    check(buf, "storage_pass=", storage__conf_pass)
	    check(buf, "storage_dbase=", storage__conf_dbase)
#undef check
	    if (strncmp(buf, "storage_port=", 13) == 0)
		storage__conf_port = atoi(buf + 13);
	}
    }
    fclose(fp);

#ifndef NDEBUG
    fprintf(stderr, "storage__read_config: Using these values: mysql://%s:%s@%s:%d/%s.\n",
	storage__conf_user, "XXXXXX",
	storage__conf_host, storage__conf_port, storage__conf_dbase);
#endif
    return 0;
}

static void storage__rtrim(char *io) {
    char *p = io + strlen(io);
    while (--p && p >= io && *p <= ' ')
	*p = '\0';
}

static void storage__write_ip(uint32_t ip, struct ipcount_t const *ipcount) {
    uint32_t rnd_packets_in = (ipcount->packets_in + storage__intervald2) / storage__interval;
    uint64_t rnd_bytes_in = (ipcount->u.bytes_in + storage__intervald2) / storage__interval;
    uint32_t rnd_packets_out = (ipcount->packets_out + storage__intervald2) / storage__interval;
    uint64_t rnd_bytes_out = (ipcount->bytes_out + storage__intervald2) / storage__interval;

#ifdef DONT_STORE_ZERO_ENTRIES
    if (rnd_packets_in != 0 || rnd_bytes_in != 0 || rnd_packets_out != 0 || rnd_bytes_out != 0)
#endif /* DONT_STORE_ZERO_ENTRIES */
    {
#   ifdef USE_DAEMON_IP_FILTER 
	if (storage__ipfilter_in_range(ip) != 0)
#   endif /* !USE_DAEMON_IP_FILTER */
	{
#       ifdef USE_PREPARED_STATEMENTS
	    storage__write_record_prepstmt(ipcount->vlan, ip,
		    rnd_packets_in, rnd_bytes_in, rnd_packets_out, rnd_bytes_out);
#       else /* !USE_PREPARED_STATEMENTS */
	    storage__write_record_sql(storage__unixtime_begin, storage__node_id, ipcount->vlan, ip,
		    rnd_packets_in, rnd_bytes_in, rnd_packets_out, rnd_bytes_out);
        #endif
	}
    }
}


#ifdef USE_DAEMON_IP_FILTER
static int storage__ipfilter_begin() {
    char buf[BUFSIZE];
    MYSQL_RES *res;
    unsigned long rows;
    MYSQL_ROW row;
    int ret;

    /* Get an ordered list of the ip ranges. */
    sprintf(
	buf,
	"SELECT ip_begin, ip_end FROM ip_range_tbl "
	"WHERE node_id IS NULL OR node_id = %d "
	"ORDER BY ip_begin, ip_end",
	storage__node_id
    );
    if (mysql_query(storage__mysql, buf)) {
	fprintf(stderr, "mysql_query: %s\n", mysql_error(storage__mysql));
	return -1;
    }
    /* Store result gets all results immediately. This way we get the num_rows
     * before looping over all results (and it could possibly reduce latency,
     * on the other hand it uses a bit more memory to store all results
     * temporarily). */
    if ((res = mysql_store_result(storage__mysql)) == NULL) {
	fprintf(stderr, "mysql_store_result: %s\n", mysql_error(storage__mysql));
	return -1;
    }
    rows = (long)mysql_num_rows(res);
    if ((storage__ipfilter_rbegin = (uint32_t*)malloc(2 * rows * sizeof(uint32_t))) == NULL) {
	fprintf(stderr, "malloc failed for daemon side ip filter (tried to get %d bytes)\n",
		(int)(2 * rows * sizeof(uint32_t)));
	mysql_free_result(res);
	return -1;
    }

    /* Fetch row data */
    storage__ipfilter_rend = storage__ipfilter_rbegin;
    while ((row = mysql_fetch_row(res)) != NULL) {
	assert(row[0] != NULL && row[1] != NULL);
	/* The results are passed a strings, yuck */
	*storage__ipfilter_rend++ = (uint32_t)atol(row[0]);
	*storage__ipfilter_rend++ = (uint32_t)atol(row[1]);
    }
    ret = (int)mysql_errno(storage__mysql); /* fetch_row returns NULL for both error and eof */
    assert(storage__ipfilter_rend - storage__ipfilter_rbegin == 2 * rows);

    /* Clean up */
    mysql_free_result(res);
    return ret;
}

static void storage__ipfilter_end() {
    free(storage__ipfilter_rbegin);
}

static int storage__ipfilter_in_range(uint32_t ip) {
    uint32_t *pos;
    /* We could optimize this by using a binary search.. it is an ordered
     * list after all. */
    for (pos = storage__ipfilter_rbegin; pos != storage__ipfilter_rend; pos += 2) {
	if (pos[0] <= ip && ip <= pos[1])
	    return 1;
    }
    return 0;
}
#endif /* USE_DAEMON_IP_FILTER */


#ifndef USE_PREPARED_STATEMENTS
static void storage__write_record_sql(uint32_t unixtime, int node_id, uint16_t vlan, uint32_t ip,
        uint32_t in_pps, uint64_t in_bps, uint32_t out_pps, uint64_t out_bps) {
    char buf[BUFSIZE];

    /* After a failure, we won't try again this run */
    if (storage__mysql == NULL)
	return;

    /* Include SELECT that checks whether IP is in range */
    sprintf(
	buf,
	"INSERT INTO sample_tbl (unixtime,node_id,vlan_id,ip,in_pps,in_bps,out_pps,out_bps) "
	"SELECT "
	    "%" SCNu32 ",%d,%" SCNu16 ",%" SCNu32 ","
	    "%" SCNu32 ",%" SCNu64 ",%" SCNu32 ",%" SCNu64 " "
	"FROM DUAL WHERE EXISTS ("
	    "SELECT ip_begin FROM ip_range_tbl "
	    "WHERE ip_begin <= %" SCNu32 " AND %" SCNu32 " <= ip_end"
	    " AND (node_id IS NULL OR node_id = %d)"
	")",
	storage__unixtime_begin, node_id, vlan, ip, in_pps, in_bps, out_pps, out_bps,
	ip, ip, node_id
    ); /* 240 bytes + 11 args * len("18446744073709551615") way smaller than BUFSIZE */
    if (mysql_query(storage__mysql, buf)) {
	fprintf(stderr, "mysql_query: %s\n", mysql_error(storage__mysql));
	storage__db_disconnect();
	return;
    }
#   ifdef PRINT_EVERY_PACKET
    if (mysql_affected_rows(storage__mysql) >= 1) {
	assert(mysql_affected_rows(storage__mysql) == 1);
	fprintf(stderr, "storage__write_ip: %s\n", buf);
    }
#   endif /* PRINT_EVERY_PACKET */
}
#endif /* !USE_PREPARED_STATEMENTS */


#ifdef USE_PREPARED_STATEMENTS
static int storage__db_prepstmt_begin() {
    char buf[BUFSIZE];

    if ((storage__mysqlps = mysql_stmt_init(storage__mysql)) == NULL) {
	fprintf(stderr, "mysql_stmt_init: %s\n", mysql_error(storage__mysql));
	return -1;
    }

#ifdef USE_DAEMON_IP_FILTER
    /* Simple INSERT statement */
    sprintf(buf, 
	"INSERT INTO sample_tbl (unixtime,node_id,vlan_id,ip,in_pps,in_bps,out_pps,out_bps) "
	"VALUES (%" SCNu32 ",%d,?,?,?,?,?,?)",
	storage__unixtime_begin, storage__node_id
    );
#else /* !USE_DAEMON_IP_FILTER */
    /* Include SELECT that checks whether IP is in range */
    sprintf(buf, 
	"INSERT INTO sample_tbl (unixtime,node_id,vlan_id,ip,in_pps,in_bps,out_pps,out_bps) "
	"SELECT %" SCNu32 ",%d,?,?,?,?,?,? "
	"FROM DUAL WHERE EXISTS ("
	    "SELECT ip_begin FROM ip_range_tbl "
	    "WHERE ip_begin <= ? AND ? <= ip_end"
	    " AND (node_id IS NULL OR node_id = %d)"
	")",
	storage__unixtime_begin, storage__node_id, storage__node_id
    ); /* 240 bytes + 3 args is way smaller than BUFSIZE */
#endif /* !USE_DAEMON_IP_FILTER */

    if (mysql_stmt_prepare(storage__mysqlps, buf, strlen(buf)) != 0) {
	fprintf(stderr, "mysql_stmt_prepare: %s\n", mysql_stmt_error(storage__mysqlps));
	(void)mysql_stmt_close(storage__mysqlps);
	return -1;
    }

#ifdef USE_DAEMON_IP_FILTER
    assert(mysql_stmt_param_count(storage__mysqlps) == 6);
#else /* !USE_DAEMON_IP_FILTER */
    assert(mysql_stmt_param_count(storage__mysqlps) == 8);
#endif /* !USE_DAEMON_IP_FILTER */

    /* Initialize bind values */
    memset(storage__mysqlbind, 0, sizeof(storage__mysqlbind));
    storage__mysqlbind[0].buffer_type = MYSQL_TYPE_SHORT;
    storage__mysqlbind[0].buffer = (char*)&storage__mysqldata.vlan;
    storage__mysqlbind[1].buffer_type = MYSQL_TYPE_LONG; 
    storage__mysqlbind[1].buffer = (char*)&storage__mysqldataip;
    storage__mysqlbind[2].buffer_type = MYSQL_TYPE_LONG;
    storage__mysqlbind[2].buffer = (char*)&storage__mysqldata.packets_in;
    storage__mysqlbind[3].buffer_type = MYSQL_TYPE_LONGLONG;
    storage__mysqlbind[3].buffer = (char*)&storage__mysqldata.u.bytes_in;
    storage__mysqlbind[4].buffer_type = MYSQL_TYPE_LONG;
    storage__mysqlbind[4].buffer = (char*)&storage__mysqldata.packets_out;
    storage__mysqlbind[5].buffer_type = MYSQL_TYPE_LONGLONG;
    storage__mysqlbind[5].buffer = (char*)&storage__mysqldata.bytes_out;
    storage__mysqlbind[0].is_unsigned = storage__mysqlbind[1].is_unsigned
	    = storage__mysqlbind[2].is_unsigned = storage__mysqlbind[3].is_unsigned
	    = storage__mysqlbind[4].is_unsigned = storage__mysqlbind[5].is_unsigned
	    = (my_bool)-1;

#ifndef USE_DAEMON_IP_FILTER
    storage__mysqlbind[6].buffer_type = MYSQL_TYPE_LONG; 
    storage__mysqlbind[6].buffer = (char*)&storage__mysqldataip;
    storage__mysqlbind[7].buffer_type = MYSQL_TYPE_LONG; 
    storage__mysqlbind[7].buffer = (char*)&storage__mysqldataip;
    storage__mysqlbind[6].is_unsigned = storage__mysqlbind[7].is_unsigned = (my_bool)-1;
#endif /* !USE_DAEMON_IP_FILTER */

    if (mysql_stmt_bind_param(storage__mysqlps, storage__mysqlbind) != 0) {
	fprintf(stderr, "mysql_stmt_bind: %s\n", mysql_stmt_error(storage__mysqlps));
	(void)mysql_stmt_close(storage__mysqlps);
	return -1;
    }

    return 0;
}

static void storage__db_prepstmt_end() {
    if (storage__mysqlps != NULL) {
	(void)mysql_stmt_close(storage__mysqlps);
	storage__mysqlps = NULL;
    }
}

static void storage__write_record_prepstmt(uint16_t vlan, uint32_t ip,
        uint32_t in_pps, uint64_t in_bps, uint32_t out_pps, uint64_t out_bps) {
    /* After a failure, we won't try again this run */
    if (storage__mysqlps == NULL)
	return;

    /* Set values in the locations that the prepared statement will be looking at */
    storage__mysqldata.vlan = vlan;
    storage__mysqldataip = ip;
    storage__mysqldata.packets_in = in_pps;
    storage__mysqldata.u.bytes_in = in_bps;
    storage__mysqldata.packets_out = out_pps;
    storage__mysqldata.bytes_out = out_bps;

    if (mysql_stmt_execute(storage__mysqlps) != 0) {
	fprintf(stderr, "mysql_stmt_execute: %s\n", mysql_stmt_error(storage__mysqlps));
	storage__db_prepstmt_end();
	return;
    }
#   ifdef PRINT_EVERY_PACKET
    if (mysql_stmt_affected_rows(storage__mysqlps) >= 1) {
	assert(mysql_stmt_affected_rows(storage__mysqlps) == 1);
	fprintf(stderr, "storage__write_ip: Data stored for IP %" SCNu32 "\n", ip);
    }
#   endif /* PRINT_EVERY_PACKET */
}
#endif /* USE_PREPARED_STATEMENTS */
