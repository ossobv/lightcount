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
#include <assert.h>
#include <stdio.h>


static void storage__write_ip(uint32_t ip, struct ipcount_t const *ipcount);


void storage_help() {
    printf(
	"/********************* module: storage (console) ******************************/\n"
	"This is a dummy storage module. Use this to test the rest of the program when\n"
	"you don't have or want a database.\n"
	"\n"
    );
}

int storage_open(char const *config_file) {
    printf("Initializing storage: config_file=\"%s\"\n", config_file);
    return 0;
}

void storage_close() {
    printf("Finishing storage!\n");
}

void storage_write(uint32_t unixtime_begin, uint32_t interval, void *memory) {
    printf("Storage output: unixtime_begin=%" SCNu32 ", interval=%" SCNu32 ", memory=%p\n",
	    unixtime_begin, interval, memory);
    memory_enum(memory, &storage__write_ip);
}

static void storage__write_ip(uint32_t ip, struct ipcount_t const *ipcount) {
    printf(
	" * %s\tvlan_id=%" SCNu32 "\t"
	"in_pps=%" SCNu32 "\tin_bps=%" SCNu64 "\tout_pps=%" SCNu32 "\tout_bps=%" SCNu64 "\n",
	util_inet_htoa(ip), ipcount->vlan,\
	ipcount->packets_in, ipcount->u.bytes_in, ipcount->packets_out, ipcount->bytes_out
    );
}
