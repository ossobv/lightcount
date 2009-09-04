# vim:ts=8:noet

ifeq ($(CFLAGS),)
    CFLAGS = -Wall
endif
ifeq ($(LDFLAGS),)
    LDFLAGS = -Wall -lpthread -lmysqlclient
endif
ifeq ($(RENAME),)
    RENAME = mv
endif

obj/%.o: %.c
	$(COMPILE.c) $< -o $@

.PHONY: lightcount lightcount-nodebug lightcount-verbose all clean

all: lightcount lightcount-nodebug lightcount-verbose

clean:
	$(RM) bin/* obj/*

lightcount:
	$(RM) obj/*
	CFLAGS="$(CFLAGS) -g -O3" \
	CPPFLAGS="$(CPPFLAGS)" \
	LDFLAGS="$(LDFLAGS) -g" \
	$(MAKE) bin/temp-default-lightcount
	$(RENAME) bin/temp-default-lightcount bin/lightcount

lightcount-nodebug:
	$(RM) obj/*
	CFLAGS="$(CFLAGS) -O3" \
	CPPFLAGS="$(CPPFLAGS) -DNDEBUG" \
	LDFLAGS="$(LDFLAGS)" \
	$(MAKE) bin/temp-default-lightcount
	$(RENAME) bin/temp-default-lightcount bin/lightcount-nodebug
	strip bin/lightcount-nodebug

lightcount-verbose:
	$(RM) obj/*
	CFLAGS="$(CFLAGS) -g -O0" \
	CPPFLAGS="$(CPPFLAGS) -DDEBUG -DPRINT_EVERY_PACKET" \
	LDFLAGS="$(LDFLAGS) -g" \
	$(MAKE) bin/temp-default-lightcount
	$(RENAME) bin/temp-default-lightcount bin/lightcount-verbose

bin/temp-default-lightcount: \
	obj/lightcount.o \
	obj/memory_simplehash.o \
	obj/sniff_packsock.o \
	obj/storage_my.o \
	obj/timer.o \
	obj/util.o
	$(LINK.o) -g $^ -o $@
