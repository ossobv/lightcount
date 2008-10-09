/* vim: set ts=8 sw=4 sts=4 noet: 
========================================================================
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
========================================================================
*/
#include <sys/types.h>
#include <inttypes.h>

/*----------------------------------------------------------------------------*
 | Program: lightcount                                                        |
 |                                                                            |
 | The program is divided in a couple of modules that could be replaced by    |
 | different implementations. These modules must implement the functions      |
 | listed below. For every module a remark is made about which other module   |
 | functions it calls.                                                        |
 |                                                                            |
 | The `*_help` functions provide implementation specific information.        |
 | Everything is assumed to be single-threaded and non-reentrant, except for  |
 | the timer that uses a thread to call `storage_write` at a specified        |
 | interval.                                                                  |
 *----------------------------------------------------------------------------*/

/* The all-important counter struct. Only the `memory` module uses this, but
 * its callback receives it as well, so it's listed here. */
struct ipcount_t;
struct ipcount_t {
    union {
	struct ipcount_t *more_memory;
	uint64_t bytes_in;
    } u;
    uint64_t bytes_out;
    uint32_t packets_in;
    uint32_t packets_out;
    uint16_t ip_high;
    uint16_t vlan;
    uint32_t is_used:1,
	is_reserved:31;
};

/* The `memory_enum` callback type. Gets a 32-bits IP address and an ipcount_t
 * struct as arguments. */
typedef void (*memory_enum_cb)(uint32_t, struct ipcount_t const*);


/*----------------------------------------------------------------------------*
 | Module: lightcount                                                         |
 |                                                                            |
 | Does the user interface.                                                   |
 |                                                                            |
 | Calls: any of the functions listed here (from the main thread)             |
 *----------------------------------------------------------------------------*/
void lightcount_help(); /* show help */


/*----------------------------------------------------------------------------*
 | Module: memory                                                             |
 |                                                                            |
 | Handles storage of intermittent values (packet/byte counts) before they    |
 | are averaged.                                                              |
 |                                                                            |
 | Calls: (nothing)                                                           |
 *----------------------------------------------------------------------------*/
void memory_help(); /* show info */
void *memory_alloc(); /* create memory to pass around */
void memory_reset(void *memory); /* reset the memory to be reused */
void memory_free(void *memory); /* free the memory */
void memory_add(void *memory, uint32_t src, uint32_t dst, uint16_t vlan,
		uint16_t len); /* store intermittent values */
void memory_enum(void *memory, memory_enum_cb cb); /* read values */


/*----------------------------------------------------------------------------*
 | Module: sniff                                                              |
 |                                                                            |
 | Does the sniffing of the ethernet packets. As `sniff_loop` is the main     |
 | (foreground) loop, it listens for the quit signals: HUP, INT, TERM and     |
 | QUIT.                                                                      |
 |                                                                            |
 | Calls: `memory_add`                                                        |
 *----------------------------------------------------------------------------*/
void sniff_help(); /* show info */
int sniff_create_socket(char const *iface); /* create a packet socket */
void sniff_close_socket(int packet_socket); /* close the packet socket */
void sniff_loop(int packet_socket, void *memory1, void *memory2); /* run */


/*----------------------------------------------------------------------------*
 | Module: storage                                                            |
 |                                                                            |
 | Stores the packet/byte count averages. You must call `storage_open` and    |
 | `storage_close` while single-threaded. A config file name must be passed   |
 | to `storage_open` that can be used to read settings like (1) which IP      |
 | addresses to store/ignore or (2) to which database to connect.             |
 |                                                                            |
 | Calls: (nothing)                                                           |
 *----------------------------------------------------------------------------*/
void storage_help();
int storage_open(char const *config_file);
void storage_close();
void storage_write(uint32_t unixtime_begin, uint32_t interval, void *memory);


/*----------------------------------------------------------------------------*
 | Module: timer                                                              |
 |                                                                            |
 | Runs a thread that wakes up every interval. When waking up, it raises      |
 | SIGUSR1 to signal `sniff_loop` to begin writing to a different buffer so   |
 | it can safely give the current buffer to `storage_write` for processing.   |
 |                                                                            |
 | Calls: `storage_write` (from a thread)                                     |
 *----------------------------------------------------------------------------*/
void timer_help();
int timer_loop_bg(void *memory1, void *memory2);
void timer_loop_stop();


/*----------------------------------------------------------------------------*
 | Utility functions that are not module specific.                            |
 *----------------------------------------------------------------------------*/
void util_get_safe_node_name(char *dst, size_t len);
int util_signal_set(int signum, void (*handler)(int));
char *util_inet_htoa(uint32_t ip4);
#if !(_BSD_SOURCE || _XOPEN_SOURCE >= 500)
int usleep(unsigned usecs);
#endif /* !(_BSD_SOURCE || _XOPEN_SOURCE >= 500) */
