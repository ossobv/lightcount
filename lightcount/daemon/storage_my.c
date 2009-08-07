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

#define DONT_STORE_ZERO_ENTRIES 1	    /* delete all entries with all values zero */
#define BUFSIZE 2048			    /* all sprintfs below are calculated to fit in this */

static char const *storage__config_file;    /* configuration file name */
static MYSQL *storage__mysql;		    /* gets reinitialized every write */
static int storage__node_id;		    /* may vary per write */
static uint32_t storage__unixtime_begin;    /* varies per write */
static uint32_t storage__interval;	    /* may vary per write */

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


void storage_help() {
    printf(
	"/********************* module: storage (mysql) ********************************/\n"
	"#%s DONT_STORE_ZERO_ENTRIES\n"
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
	"\n",
#ifdef DONT_STORE_ZERO_ENTRIES
	"define"
#else /* !DONT_STORE_ZERO_ENTRIES */
	"undef"
#endif
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
    util_get_safe_node_name(buf, 256); /* 256 < BUFSIZE */
    storage__node_id = storage__db_get_node_id(buf);
    if (storage__node_id == -1) {
	storage__db_disconnect();
	return;
    }
    
    /* Finally! Insert data! */
    memory_enum(memory, &storage__write_ip);

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
    mysql_close(storage__mysql);
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
	fprintf(stderr, "storage__read_config: Using defaults: mysql://%s@%s:%i/%s.\n",
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
    fprintf(stderr, "storage__read_config: Using these values: mysql://%s:%s@%s:%i/%s.\n",
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
    char buf[BUFSIZE];

    /* Include select that checks whether IP is in range */
    sprintf(
	buf,
	"INSERT INTO sample_tbl (unixtime,node_id,vlan_id,ip,in_pps,in_bps,out_pps,out_bps) "
	"SELECT "
	    "%" SCNu32 ",%i,%" SCNu16 ",%" SCNu32 ","
	    "ROUND(%" SCNu32 "/%" SCNu32 "),ROUND(%" SCNu64 "/%" SCNu32 "),"
	    "ROUND(%" SCNu32 "/%" SCNu32 "),ROUND(%" SCNu64 "/%" SCNu32 ") "
	"FROM DUAL WHERE EXISTS ("
	    "SELECT ip_begin FROM ip_range_tbl "
	    "WHERE ip_begin <= %" SCNu32 " AND %" SCNu32 " <= ip_end"
	    " AND (node_id IS NULL OR node_id = %i)"
#ifdef DONT_STORE_ZERO_ENTRIES
	    " AND (ROUND(%" SCNu32 "/%" SCNu32 ")<>0 OR ROUND(%" SCNu64 "/%" SCNu32 ")<>0"
	    " OR ROUND(%" SCNu32 "/%" SCNu32 ")<>0 OR ROUND(%" SCNu64 "/%" SCNu32 ")<>0)"
#endif /* DONT_STORE_ZERO_ENTRIES */
	")",
	storage__unixtime_begin, storage__node_id, ipcount->vlan, ip,
	ipcount->packets_in, storage__interval, ipcount->u.bytes_in, storage__interval,
	ipcount->packets_out, storage__interval, ipcount->bytes_out, storage__interval,
	ip, ip, storage__node_id
#ifdef DONT_STORE_ZERO_ENTRIES
	, ipcount->packets_in, storage__interval, ipcount->u.bytes_in, storage__interval,
	ipcount->packets_out, storage__interval, ipcount->bytes_out, storage__interval
#endif /* DONT_STORE_ZERO_ENTRIES */
    ); /* 23 args * len("18446744073709551615") is still only 460 */
    if (mysql_query(storage__mysql, buf)) {
	fprintf(stderr, "mysql_query: %s\n", mysql_error(storage__mysql));
	return;
    }
#ifdef PRINT_EVERY_PACKET
    if (mysql_affected_rows(storage__mysql) >= 1) {
	assert(mysql_affected_rows(storage__mysql) == 1);
        fprintf(stderr, "storage__write_ip: %s\n", buf);
    }
#endif
}
