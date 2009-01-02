CFLAGS = -Wall -g
LDFLAGS = -Wall -g -lpthread -lmysqlclient
BINS = bin/lightcount bin/lightcount.fast bin/lightcount.slow
OBJS = obj/lightcount.o obj/memory.o obj/sniff_packsock.o obj/storage_my.o obj/timer.o obj/util.o

obj/%.o: %.c
	$(COMPILE.c) -DDEBUG $< -o $@
bin/%: obj/%.o
	$(LINK.o) -g0 -O3 $^ -o $@
obj/%.oS: %.c
	$(COMPILE.c) -DPRINT_EVERY_PACKET $< -o $@
bin/%.slow: obj/%.oS
	$(LINK.o) -g0 -O3 $^ -o $@
obj/%.o3: %.c
	$(COMPILE.c) -g0 -DNDEBUG -O3 $< -o $@
bin/%.fast: obj/%.o3
	$(LINK.o) -g0 -O3 $^ -o $@

.PHONY: all clean
all: $(BINS)
clean:
	rm -f $(OBJS) $(OBJS:.o=.o3) $(OBJS:.o=.oS) $(BINS)

bin/lightcount: $(OBJS)
bin/lightcount.fast: $(OBJS:.o=.o3)
bin/lightcount.slow: $(OBJS:.o=.oS)
