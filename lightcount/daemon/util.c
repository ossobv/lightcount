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
#include "endian.h"
#include <sys/utsname.h>
#include <assert.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>

/* Includes for select(2) when usleep(3) is unavailable */
#if !(_BSD_SOURCE || _XOPEN_SOURCE >= 500)
# include <sys/time.h>
# include <sys/types.h>
# include <unistd.h>
#endif /* !(_BSD_SOURCE || _XOPEN_SOURCE >= 500) */


/* Fix non-bsd signal(2) behaviour when sigaction(2) is unavailable */
#if !(__USE_POSIX || __USE_BSD)
# ifndef _NSIG
#  define _NSIG 65
# endif
typedef void (*sighandler_t)(int);
static sighandler_t util__sighandlers[_NSIG];
void util__signal_helper(int signum) {
    util__sighandlers[signum](signum);
    if (signal(signum, util__signal_helper) == SIG_ERR)
	perror("signal");
}
#endif /* !(__USE_POSIX || __USE_BSD) */

void util_get_safe_node_name(char *dst, size_t len) {
    struct utsname uname_info;
    char *p;
    assert(len >= 2);
    dst[len-1] = '\0';

    /* Get hostname from uname */
    if (uname(&uname_info) != 0) {
	perror("uname");
	strncpy(dst, "uname_2_failed", len - 1);
	return;
    }
    strncpy(dst, uname_info.nodename, len - 1);
#ifdef _GNU_SOURCE
    if (strlen(dst) + strlen(dst) + 1 < len - 1) {
	strcat(dst, ".");
	strcat(dst, uname_info.domainname);
    }
#endif /* _GNU_SOURCE */

    /* Junk all funny characters in node_name */
    p = dst;
    while (*p != '\0') {
	if (!(*p == '-' || *p == '_' || *p == '.'
		|| (*p >= '0' && *p <= '9')
		|| (*p >= 'A' && *p <= 'Z')
		|| (*p >= 'a' && *p <= 'z'))) {
	    *p = '_';
	}
	++p;
    }
}

int util_signal_set(int signum, void (*handler)(int)) {
#ifdef __USE_POSIX
    int ret;
    struct sigaction action;
    action.sa_handler = handler;
    sigemptyset(&action.sa_mask);
    action.sa_flags = 0;
    if ((ret = sigaction(signum, &action, NULL)) != 0) {
	perror("sigaction");
        return -1;
    }
#else
# ifndef __USE_BSD
    if (handler != SIG_IGN && handler != SIG_DFL) {
	assert(signum < _NSIG);
	util__sighandlers[signum] = handler;
	handler = &util__signal_helper;
    }
# endif /* !__USE_BSD */
    if (signal(signum, handler) == SIG_ERR) {
	perror("signal");
	return -1;
    }
#endif /* !__USE_POSIX && !__USE_BSD */
    return 0;
}

char *util_inet_htoa(uint32_t ip4) {
    static char static_buf[16];
    uint8_t const *ip48 = (uint8_t const*)&ip4;
    static_buf[15] = '\0';
    sprintf(
	static_buf,
	"%" SCNu8 ".%" SCNu8 ".%" SCNu8 ".%" SCNu8,
#if BYTE_ORDER == LITTLE_ENDIAN
        ip48[3], ip48[2], ip48[1], ip48[0]
#elif BYTE_ORDER == BIG_ENDIAN
	ip48[0], ip48[1], ip48[2], ip48[3]
#endif
    );
    return static_buf;
}

#if !(_BSD_SOURCE || _XOPEN_SOURCE >= 500)
int usleep(unsigned usec) {
    struct timeval timeout;
    timeout.tv_sec = usec / 1000000;
    timeout.tv_usec = usec;
    if (select(0, NULL, NULL, NULL, &timeout) == 0)
	return 0;
    return -1;
}
#endif /* !(_BSD_SOURCE || _XOPEN_SOURCE >= 500) */
