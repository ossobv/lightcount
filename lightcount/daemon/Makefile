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
	lightcount lightcount-nodebug lightcount-verbose

all: lightcount lightcount-nodebug lightcount-verbose

clean:
	@rm -r bin

lightcount:
	APPNAME="$@" \
	MODULES="lightcount memory_simplehash sniff_packsock storage_my timer util" \
	CPPFLAGS="$(CPPFLAGS)" \
	CFLAGS="$(CFLAGS) -g -O3" \
	LDFLAGS="$(LDFLAGS) -g" \
	$(MAKE) bin/$@

lightcount-nodebug:
	APPNAME="$@" \
	MODULES="lightcount memory_simplehash sniff_packsock storage_my timer util" \
	CPPFLAGS="$(CPPFLAGS) -DNDEBUG" \
	CFLAGS="$(CFLAGS) -O3" \
	LDFLAGS="$(LDFLAGS)" \
	$(MAKE) bin/$@
	@strip bin/$@

lightcount-verbose:
	APPNAME="$@" \
	MODULES="lightcount memory_simplehash sniff_packsock storage_my timer util" \
	CPPFLAGS="$(CPPFLAGS) -DDEBUG -DPRINT_EVERY_PACKET" \
	CFLAGS="$(CFLAGS) -g -O0" \
	LDFLAGS="$(LDFLAGS) -g" \
	$(MAKE) bin/$@


bin/.$(APPNAME)/%.o: %.c
	@mkdir -p $(dir $@)
	$(COMPILE.c) $< -o $@
bin/$(APPNAME): $(addprefix bin/.$(APPNAME)/, $(addsuffix .o, $(MODULES)))
	$(LINK.o) $^ -o $@
