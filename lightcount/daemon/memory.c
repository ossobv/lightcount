/* vim: set ts=8 sw=4 sts=4 noet: */
#include "lightcount.h"
#include <assert.h>
#include <malloc.h>
#include <stdio.h>
#include <string.h>

/* See helptext below. I don't know what reasonable numbers are, but:
 * 16 <= HASHBITS <= 32 is a must! And having 6 buckets should be a good
 * number, so we use 7 as default. (We get even numbers with BUCKETS+1.) */
#define HASHBITS 18
#define BUCKETS 7


static void memory__add_one(void *memory, u_int32_t ip, u_int16_t vlan, u_int16_t len, int is_output);
#ifdef PRINT_EVERY_PACKET
static void memory__dump_ipcount(u_int32_t ip, struct ipcount_t *ipc);
#endif

void memory_help() {
    printf(
        "/********************* module: memory (simple_hash) ***************************/\n"
	"#define HASHBITS %" SCNu32 "\n"
	"#define BUCKETS %" SCNu32 "\n"
	"\n"
	"The memory uses %" SCNu32 " low order bits as hash and %" SCNu32 " buckets of %" SCNu32 " byte sized\n"
	"information about an IP. That means that we'll use _two_ buffers of:\n"
	"(2**BITS)*(BUCKETS+1)*sizeof(ipcount_t) == %" SCNu64 "MB ram. Plus an optional %" SCNu64 "kB\n"
	"more per bucket overrun.\n"
	"\n",
	(u_int32_t)HASHBITS, (u_int32_t)BUCKETS,
	(u_int32_t)HASHBITS, (u_int32_t)BUCKETS, (u_int32_t)sizeof(struct ipcount_t),
	(u_int64_t)(1 << HASHBITS) * (BUCKETS + 1) * sizeof(struct ipcount_t) / 1024 / 1024,
	(u_int64_t)(1 << (32 - HASHBITS)) * sizeof(struct ipcount_t) / 1024
    );
    if (HASHBITS < 16 || HASHBITS > 32) {
	fprintf(stderr, "WARNING: HASHBITS has the insane value of %" SCNu32 "!\n\n", (u_int32_t)HASHBITS);
    }
    if (BUCKETS <= 1 || BUCKETS > 511) {
	fprintf(stderr, "WARNING: BUCKETS has the insane value of %" SCNu32 "!\n\n", (u_int32_t)BUCKETS);
    }
}

void *memory_alloc() {
    assert(sizeof(struct ipcount_t) / 8 * 8 == sizeof(struct ipcount_t)); /* proper alignment */
    return calloc(sizeof(struct ipcount_t), (1 << HASHBITS) * (BUCKETS + 1));
}

void memory_reset(void *memory) {
    struct ipcount_t *mem = memory;
    int ip_low;
    for (ip_low = 0; ip_low < (1 << HASHBITS); ++ip_low, mem += (BUCKETS + 1)) {
	if (mem[BUCKETS].u.more_memory != NULL) {
	    free(mem[BUCKETS].u.more_memory);
	}
    }
    memset(memory, 0, (1 << HASHBITS) * (BUCKETS + 1) * sizeof(struct ipcount_t));
}

void memory_free(void *memory) {
    memory_reset(memory);
    free(memory);
}

void memory_add(void *memory, u_int32_t src, u_int32_t dst, u_int16_t vlan, u_int16_t len) {
#if PRINT_EVERY_PACKET
    fprintf(stderr, "memory_add: 0x%08" PRIx32 " > 0x%08" PRIx32 " (len=%" SCNu16 ",vlan=%" SCNu16 ").\n", src, dst, len, vlan);
#endif
    memory__add_one(memory, src, vlan, len, 1); /* src == output */
    memory__add_one(memory, dst, vlan, len, 0); /* dst == input */
}

void memory_enum(void *memory, memory_enum_cb cb) {
    int ip_low = 0;
    struct ipcount_t *mem = memory;

    for (ip_low = 0; ip_low < (1 << HASHBITS); ++ip_low, mem += (BUCKETS + 1)) {
	int i;
	for (i = 0; i < BUCKETS && mem[i].is_used; ++i) { /* See 0.0.*.* assumption above. */
#if PRINT_EVERY_PACKET
	    memory__dump_ipcount(ip_low | (mem[i].ip_high << HASHBITS), &mem[i]);
#endif
	    cb(ip_low | (mem[i].ip_high << HASHBITS), &mem[i]);
	}
	if (i == BUCKETS && mem[BUCKETS].u.more_memory != NULL) {
	    struct ipcount_t *more_mem = mem[BUCKETS].u.more_memory;
	    while (more_mem->is_used) {
#if PRINT_EVERY_PACKET
		memory__dump_ipcount(ip_low | (more_mem->ip_high << HASHBITS), more_mem);
#endif
		cb(ip_low | (more_mem->ip_high << HASHBITS), more_mem);
		++more_mem;
	    }
	}
    }
}
	    

#define memory__add_one_first(iso, m, ih, v, l) \
    m->is_used = 1; \
    m->ip_high = ih; \
    m->vlan = v; \
    if (iso) { \
	m->packets_out = (u_int32_t)1; \
	m->bytes_out = (u_int64_t)l; \
    } else { \
	m->packets_in = (u_int32_t)1; \
	m->u.bytes_in = (u_int64_t)l; \
    }

#define memory__add_one_subsequent(iso, m, l) \
    if (iso) { \
	m->packets_out += (u_int32_t)1; \
	m->bytes_out += (u_int64_t)l; \
    } else { \
	m->packets_in += (u_int32_t)1; \
	m->u.bytes_in += (u_int64_t)l; \
    }

static void memory__add_one(void *memory, u_int32_t ip, u_int16_t vlan, u_int16_t len, int is_output) {
    int i;
    struct ipcount_t *mem = (struct ipcount_t*)memory + ((ip & ((1 << HASHBITS) - 1)) * (BUCKETS + 1));
    u_int16_t ip_high = ip >> HASHBITS;

    for (i = 0; i < BUCKETS; ++i, ++mem) {
	if (!mem->is_used) {
	    assert(mem->packets_in == 0 && mem->packets_out == 0);
	    assert(mem->u.bytes_in == 0 && mem->bytes_out == 0);
	    assert(mem->vlan == 0 && mem->ip_high == 0);
	    memory__add_one_first(is_output, mem, ip_high, vlan, len);
	    return;
	} else if (mem->ip_high == ip_high && mem->vlan == vlan) {
	    memory__add_one_subsequent(is_output, mem, len);
	    return;
	}
    }
    /* We haven't returned.. memory must be full. We use BUCKET+1 to store a pointer to more memory. */
    if (mem->u.more_memory == NULL) {
#ifndef NDEBUG
        fprintf(stderr, "memory_add_one: Buckets are full for IP 0x%08" PRIx32 ". Alloc'ing %" SCNu64 " bytes mem.\n",
		ip, (u_int64_t)sizeof(struct ipcount_t) * (1 << (32 - HASHBITS)));
#endif
	mem->u.more_memory = calloc(sizeof(struct ipcount_t), 1 << (32 - HASHBITS));
	if (mem->u.more_memory == NULL) {
	    fprintf(stderr, "memory_add_one: Error! Couldn't allocate more memory! Skipping count.\n");
	    return;
	}
    }
    mem = mem->u.more_memory;
    for (i = 0; i < (1 << (32 - HASHBITS)); ++i, ++mem) {
	if (!mem->is_used) {
	    assert(mem->packets_in == 0 && mem->packets_out == 0);
	    assert(mem->u.bytes_in == 0 && mem->bytes_out == 0);
	    assert(mem->vlan == 0 && mem->ip_high == 0);
	    memory__add_one_first(is_output, mem, ip_high, vlan, len);
	    return;
	} else if (mem->ip_high == ip_high && mem->vlan == vlan) {
	    memory__add_one_subsequent(is_output, mem, len);
	    return;
	}
    }
    /* We can't be here. We've allocated enough memory. */
    assert(0);
}

#ifdef PRINT_EVERY_PACKET
static void memory__dump_ipcount(u_int32_t ip, struct ipcount_t *mem) {
    fprintf(stderr, "memory__dump_ipcount: (IP 0x%08" PRIx32 ") pi %" SCNu32 " po %" SCNu32 " bi %" SCNu64 " bo %" SCNu64
	    " iph 0x%" PRIx16 " vl %" SCNu16 "\n",
	    ip, mem->packets_in, mem->packets_out, mem->u.bytes_in, mem->bytes_out, mem->ip_high, mem->vlan);
}
#endif
