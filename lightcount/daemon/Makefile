CFLAGS = -Wall -g
LDFLAGS = -Wall -g -lpthread -lmysqlclient
OBJS = lightcount.o memory.o sniff.o storage.o timer.o util.o

%.oS: %.c
	$(COMPILE.c) -DPRINT_EVERY_PACKET $< -o $@
%.slow: %.oS
	$(LINK.o) -g0 -O3 $^ -o $@
%.o3: %.c
	$(COMPILE.c) -g0 -DNDEBUG -O3 $< -o $@
%.fast: %.o3
	$(LINK.o) -g0 -O3 $^ -o $@

.PHONY: all clean
all: lightcount lightcount.fast lightcount.slow
clean:
	rm -f $(OBJS) $(OBJS:.o=.o3) $(OBJS:.o=.oS) lightcount lightcount.fast lightcount.slow

lightcount: $(OBJS)
lightcount.fast: $(OBJS:.o=.o3)
lightcount.slow: $(OBJS:.o=.oS)
