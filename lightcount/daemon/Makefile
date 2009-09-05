# vim:ts=8:noet
#
# Makefile for the lightcount traffic daemon.
# By Walter Doekes, 2009.

ifeq ($(CFLAGS),)
    CFLAGS = -Wall
endif
ifeq ($(LDFLAGS),)
    LDFLAGS = -Wall -lpthread -lmysqlclient
endif

.PHONY: all clean \
	lightcount lightcount-nodebug lightcount-verbose \
	lightcount-test-output

all: lightcount lightcount-nodebug lightcount-verbose lightcount-test-output

clean:
	@rm -r bin

lightcount:
	APPNAME="$@" CPPFLAGS="$(CPPFLAGS)" \
	CFLAGS="$(CFLAGS) -g -O3" LDFLAGS="$(LDFLAGS) -g"
	MODULES="lightcount memory_simplehash sniff_packsock storage_my timer_nsleep util" \
	$(MAKE) bin/$@

lightcount-nodebug:
	APPNAME="$@" CPPFLAGS="$(CPPFLAGS) -DNDEBUG" \
	CFLAGS="$(CFLAGS) -O3" LDFLAGS="$(LDFLAGS) -O3" \
	MODULES="lightcount memory_simplehash sniff_packsock storage_my timer_nsleep util" \
	$(MAKE) bin/$@
	@strip bin/$@

lightcount-verbose:
	APPNAME="$@" CPPFLAGS="$(CPPFLAGS) -DDEBUG -DPRINT_EVERY_PACKET" \
	CFLAGS="$(CFLAGS) -g -O0" LDFLAGS="$(LDFLAGS) -g" \
	MODULES="lightcount memory_simplehash sniff_packsock storage_my timer_nsleep util" \
	$(MAKE) bin/$@

lightcount-test-output:
	APPNAME="$@" CPPFLAGS="$(CPPFLAGS) -DDEBUG -DINTERVAL_SECONDS=0" \
	CFLAGS="$(CFLAGS) -g -O0" LDFLAGS="$(LDFLAGS) -g" \
	MODULES="lightcount memory_testlive sniff_dummy storage_my timer_oneshot util" \
	$(MAKE) bin/$@


bin/.$(APPNAME)/%.o: %.c
	@mkdir -p $(dir $@)
	$(COMPILE.c) $< -o $@
bin/$(APPNAME): $(addprefix bin/.$(APPNAME)/, $(addsuffix .o, $(MODULES)))
	$(LINK.o) $^ -o $@
