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
#include <signal.h>
#include <stdio.h>


void sniff_help() {
    printf(
	"/********************* module: sniff (dummy) **********************************/\n"
	"Sniff dummy does exactly nothing. It returns bogus data for initialization calls\n"
	"and it exits the main loop immediately. Use this in combination with the oneshot\n"
	"timer module to dump the memory to the storage engine immediately and once only.\n"
	"\n"
    );
}

int sniff_create_socket(char const *iface) {
    return 0;
}

void sniff_loop(int packet_socket, void *memory1, void *memory2) {
    /* Add signal handlers */
    util_signal_set(SIGUSR1, SIG_IGN);
}
