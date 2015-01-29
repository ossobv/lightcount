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
#include <stdlib.h>
#include <unistd.h>


int main(int argc, char const *const *argv) {
    int socket = -1;
    void *memory[2];

    /* User wants help? */
    if (argc == 2 && argv[1][0] == '-' && argv[1][1] == 'h' && argv[1][2] == '\0') {
	lightcount_help();
	sniff_help();
	memory_help();
	timer_help();
	storage_help();
	return 0;
    }

    /* Try initialization */
    if (argc != 3 || (socket = sniff_create_socket(argv[1])) < 0 || storage_open(argv[2]) != 0) {
	if (socket >= 0)
	    close(socket);
	fprintf(stderr, "lightcount: Initialization failed or bad command line options. See -h for help.\n");
	return 0;
    }

    /* Initialize memory */
    memory[0] = memory_alloc();
    memory[1] = memory_alloc();
    assert(memory[0] != NULL && memory[1] != NULL);

    /* Initialize updater thread */
    timer_loop_bg(memory[0], memory[1]);

    /* Start the main loop (ends on INT/HUP/TERM/QUIT or error) */
    sniff_loop(socket, memory[0], memory[1]);

    /* Finish updater thread */
    timer_loop_stop();

    /* Finish/close open stuff */
    memory_free(memory[0]);
    memory_free(memory[1]);
    storage_close();
    close(socket);
    return 0;
}

void lightcount_help() {
    printf(
	"Usage: lightcount IFACE CONFIGFILE\n"
	"Captures IP traffic on the specified interface and stores the average packet\n"
	"and length counts.\n"
	"\n"
    );
}

