/* vim: set ts=8 sw=4 sts=4 noet: */
#include "lightcount.h"
#include <sys/time.h>
#include <pthread.h>
#include <setjmp.h>
#include <signal.h>
#include <stdio.h>
#include <time.h>
#include <unistd.h>

/* Settings */
#define INTERVAL_SECONDS 300	/* run the storage engine every N seconds */


static pthread_t timer__thread;
static void *timer__memory[2];		/* memory to store in non-volatile space */
static void *timer__memp;		/* memory that's currently written to */
static int timer__done;			/* whether we're done */


static void *timer__run(void *thread_arg);

void timer_help() {
    printf(
	"/********************* module: timer (n_sleep) ********************************/\n"
	"#define INTERVAL_SECONDS %" SCNu32 "\n"
	"\n"
	"Sleeps until the specified interval of %.2f minutes have passed and wakes up\n"
	"to tell the storage engine to write averages.\n"
	"\n",
	(u_int32_t)INTERVAL_SECONDS, (float)INTERVAL_SECONDS / 60
    );
}

int timer_loop_bg(void *memory1, void *memory2) {
    pthread_attr_t attr;
    
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

/* The timers job is to run storage function after after every INTERVAL_SECONDS time. */
static void *timer__run(void *thread_arg) {
    struct timeval current_time; /* current time is in UTC */
    int first_run_skipped = 0; /* do not store the first run because the interval is wrong */
    int sleep_useconds;

#ifndef NDEBUG
    fprintf(stderr, "timer__run: Thread started.\n");
#endif

    while (1) {
	/* Get current time */
	if (gettimeofday(&current_time, NULL) != 0) {
	    perror("gettimeofday");
	    return (void*)-1;
	}
    
	/* Calculate how long to sleep */
	sleep_useconds = 1000000 * (INTERVAL_SECONDS - (current_time.tv_sec % INTERVAL_SECONDS)) - current_time.tv_usec;
#ifndef NDEBUG
	fprintf(stderr, "timer__run: Current time is %i (%02i:%02i:%02i.%06i), sleep planned for %i useconds.\n",
		(int)current_time.tv_sec,
		(int)(current_time.tv_sec / 3600) % 24, (int)(current_time.tv_sec / 60) % 60, (int)current_time.tv_sec % 60,
		(int)current_time.tv_usec, sleep_useconds);
#endif

	/* Sleep won't EINTR on SIGALRM, use a crappy loop instead */
	while (!timer__done && (sleep_useconds -= 1000000) > 999999)
	    sleep(1);
	if (timer__done)
	    break;
	usleep(sleep_useconds % 1000000); /* some systems do not like usleep to sleep too long */
#ifndef NDEBUG
	fprintf(stderr, "timer__run: Awake!\n");
#endif

	/* Poke other thread to switch memory */
	raise(SIGUSR1);
	sleep(1); /* wait a second to let other thread finish switching memory */

	if (first_run_skipped) {
	    /* Delegate the actual writing to storage.
	     * Round the unixtime_begin down to 3 seconds because we might be off a bit
	     * mostly because of the crappy loop above. */
	    storage_write(current_time.tv_sec - (current_time.tv_sec % 3), INTERVAL_SECONDS, timer__memp);
	} else {
	    /* On first run, we started too late in the interval. Ignore those counts. */
	    first_run_skipped = 1;
	}

	/* Reset mem for next run */
	memory_reset(timer__memp);
	if (timer__memp == timer__memory[0])
	    timer__memp = timer__memory[1];
	else
	    timer__memp = timer__memory[0];
    }
    
#ifndef NDEBUG
    fprintf(stderr, "timer__run: Thread done.\n");
#endif
    return 0;
}
