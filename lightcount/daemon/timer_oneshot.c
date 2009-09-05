/* vim: set ts=8 sw=4 sts=4 noet: */
/*======================================================================
Copyright (C) 2009 OSSO B.V. <walter+lightcount@osso.nl>
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
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <time.h>
#include <unistd.h>

/* Settings */
#ifndef LISTEN_SECONDS
#   define LISTEN_SECONDS 300		/* how long to listen for data */
#endif /* LISTEN_SECONDS */
#ifndef FAKE_INTERVAL_SECONDS
#   define FAKE_INTERVAL_SECONDS LISTEN_SECONDS /* how long we've supposedly listened */
#endif /* FAKE_INTERVAL_SECONDS */


static pthread_t timer__thread;
static void *timer__memory[2];		/* memory to store in non-volatile space */
static void *timer__memp;		/* memory that's currently written to */
static volatile int timer__done;	/* whether we're done */


static void *timer__run(void *thread_arg);


void timer_help() {
    printf(
	"/********************* module: timer (oneshot) ********************************/\n"
	"#define LISTEN_SECONDS %" SCNu32 "\n"
	"#define FAKE_INTERVAL_SECONDS %" SCNu32 "\n"
	"\n"
	"Sleeps until the specified interval of %.2f minutes have passed and wakes up\n"
	"to tell the storage engine to write averages. After waking the storage engine\n"
	"it exits.\n"
	"\n"
	"This differs from the n_sleep timer in that it (1) does not align the times, it\n"
	"just waits the specified amount of time once and (2) can tell the storage engine\n"
	"that the interval was FAKE_INTERVAL_SECONDS long.\n"
	"\n"
	"Combine this with a data generating memory module, set LISTEN_SECONDS to 0 and\n"
	"FAKE_INTERVAL_SECONDS to some reasonable value to do timing tests of the storage\n"
	"engine.\n"
	"\n",
	(uint32_t)LISTEN_SECONDS, (uint32_t)FAKE_INTERVAL_SECONDS,
	(float)LISTEN_SECONDS / 60
    );
}

int timer_loop_bg(void *memory1, void *memory2) {
    pthread_attr_t attr;
    assert(LISTEN_SECONDS >= 0);
    assert(((FAKE_INTERVAL_SECONDS >> 1) << 1) == FAKE_INTERVAL_SECONDS);
    
    /* Set internal config */
    timer__memory[0] = memory1;
    timer__memory[1] = memory2;
    timer__memp = memory1; /* sniff_loop writes to memory1 first */
    timer__done = 0;

    /* We want default pthread attributes */
    if (pthread_attr_init(&attr) != 0) {
	perror("pthread_attr_init");
	return -1;
    }
    
    /* Run thread */
    if (pthread_create(&timer__thread, &attr, &timer__run, NULL) != 0) {
	perror("pthread_create");
	return -1;
    }
#ifndef NDEBUG
    fprintf(stderr, "timer_loop_bg: Thread %p started.\n", (void*)timer__thread);
#endif
    return 0;
}

void timer_loop_stop() {
    void *ret;

    /* Tell our thread that it is time */
    timer__done = 1; /* a raise SIGALRM would be nice.. but sleep doesn't wake up */

    /* Get its exit status */
    if (pthread_join(timer__thread, &ret) != 0)
	perror("pthread_join");
#ifndef NDEBUG
    fprintf(stderr, "timer_loop_stop: Thread %p joined.\n", (void*)timer__thread);
#endif
}

/* The timers job is to run storage function after after INTERVAL_SECONDS time. */
static void *timer__run(void *thread_arg) {
    int sleep_seconds = (int)LISTEN_SECONDS;

#ifndef NDEBUG
    fprintf(stderr, "timer__run: Thread started.\n");
#endif

#if LISTEN_SECONDS == 0
    /* Yield once so the other thread gets to initialize its signal handlers */
    sleep(1);
#endif /* LISTEN_SECONDS == 0 */

#ifndef NDEBUG
    fprintf(stderr, "timer__run: Sleep planned for %i seconds.\n", sleep_seconds);
#endif

    /* Count down once */
    while (!timer__done && sleep_seconds) {
	sleep(1);
	sleep_seconds -= 1;
    }

    /* Poke other thread to switch memory */
    raise(SIGUSR1);
    sleep(1); /* wait a second to let other thread finish switching memory */

    /* Delegate the actual writing to storage. */
    storage_write(time(NULL), FAKE_INTERVAL_SECONDS, timer__memp);

    /* Reset memory (not needed really, but consistent with a looping timer) */
    memory_reset(timer__memp);
    
#ifndef NDEBUG
    fprintf(stderr, "timer__run: Thread done.\n");
#endif
    return 0;
}
