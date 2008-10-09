/* vim: set ts=8 sw=4 sts=4 noet: */
/* NOTE: Raise SIGUSR1 when you want it to switch memory.
 * NOTE: Its your job to put the interfaces in promiscuous mode. */
#include "lightcount.h"
#include <sys/socket.h>
#include <netinet/in.h>
#include <netpacket/packet.h>
#include <net/if.h>
#include <assert.h>
#include <endian.h>
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

/* Static constants (also found in linux/if_ether.h) */
#if __BYTE_ORDER == __LITTLE_ENDIAN
# define ETH_P_ALL 0x0300   /* all frames */
# define ETH_P_IP 0x0008    /* IP frames */
# define ETH_P_8021Q 0x0081 /* 802.1q vlan frames */
#elif __BYTE_ORDER == __BIG_ENDIAN
# define ETH_P_ALL 0x0003   /* all frames */
# define ETH_P_IP 0x0800    /* IP frames */
# define ETH_P_8021Q 0x8100 /* 802.1q vlan frames */
#endif


/* Ethernet header */
struct sniff_ether {
    u_int8_t dest[6];       /* destination host address */
    u_int8_t source[6];     /* source host address */
    u_int16_t type;         /* ETH_P_* type */
    u_int16_t pcp:3,	    /* priority code point (for 8021q) */
	     cfi:1,	    /* canonical format indicator */
	     vid:12;	    /* vlan identifier (0=no, fff=reserved) */
    u_int16_t type2;	    /* encapsulated type */
};

/* IP header */
struct sniff_ip {
    u_int8_t hl:4,	    /* header length */
	     ver:4;	    /* version */
    u_int8_t  tos;	    /* type of service */
    u_int16_t len;	    /* total length */
    u_int16_t id;	    /* identification */
    u_int16_t off;	    /* fragment offset field */
#define IP_RF 0x8000        /* reserved fragment flag */
#define IP_DF 0x4000        /* dont fragment flag */
#define IP_MF 0x2000        /* more fragments flag */
#define IP_OFFMASK 0x1fff   /* mask for fragmenting bits */
    u_int8_t  ttl;	    /* time to live */
    u_int8_t  proto;	    /* protocol */
    u_int16_t sum;	    /* checksum */
    u_int32_t src;	    /* source address */
    u_int32_t dst;	    /* dest address */
};

static void *sniff__memory[2];	/* two locations to store counts in */
static void *sniff__memp;	/* the "current" memory location */
static int sniff__done;		/* whether we're done */


static void sniff__switch_memory(int signum);
static void sniff__loop_done(int signum);
#if 0
static void sniff__test_memory_enum(u_int32_t ip, struct ipcount_t const *ipcount);
#endif


void sniff_help() {
    printf(
	"/********************* module: sniff (packet_socket) **************************/\n"
	"Sniff uses a packet socket to listen for all inbound and outbound packets.\n"
	"Specify the interface name as IFACE or 'any' if you want to listen on all\n"
	"interfaces.\n"
	"\n"
	"Internally, we listen on the ETH_P_ALL SOCK_RAW protocol for packets with\n"
	"an ETH_P_IP or ETH_P_8021Q ethernet type. (In 802.1q packets we examine only\n"
	"IP packets. Double tagged packets are ignored.) The packet count, length\n"
	"(including ethernet frame) and destination is recorded.\n"
	"\n"
	"Note one: packets from localhost to localhost are seen twice. We seem them\n"
	"once outbound and once inbound. And, as both source and destination is\n"
	"counted, you should expect a multiplication of four. You should expect a\n"
	"similar multiplication on machines doing NAT.\n"
	"\n"
	"Note two: if you want to see VLANs, your kernel must not process them. The\n"
	"Linux kernels on which this is tested use something called hardware VLAN\n"
	"acceleration. This mangles the ethernet frames to look like regular IP\n"
	"containing frames. Unload the 8021q module to be sure.\n"
	"\n"
	"Note three: if you want to capture packets not intended for your host -- a\n"
	"common setup is to mirror all traffic to a host that only runs the lightcount\n"
	"daemon -- you need to manually set the interfaces in promiscuous mode.\n"
	"\n"
    );
}

int sniff_create_socket(char const *iface) {
    /* We could use ETH_P_IP here instead of ETH_P_ALL but we'd miss out on
     * (1) locally generated packets and (2) 802.1q packets. */
    int raw_socket = socket(PF_PACKET, SOCK_RAW, ETH_P_ALL);
    if (raw_socket >= 0) {
	if (strcmp(iface, "any") != 0) {
	    int ifindex = if_nametoindex(iface);
	    if (ifindex != 0) {
		struct sockaddr_ll saddr_ll;
		saddr_ll.sll_family = AF_PACKET;
		saddr_ll.sll_protocol = ETH_P_ALL;
		saddr_ll.sll_ifindex = if_nametoindex(iface);
		if (bind(raw_socket, (struct sockaddr*)&saddr_ll, sizeof(struct sockaddr_ll)) != 0)
		    perror("bind");
	    } else {
		fprintf(stderr, "if_nametoindex: No such interface found, perhaps you want 'any' (all)?\n");
		close(raw_socket);
		return -1;
	    }
	}
    } else {
	perror("socket");
	fprintf(stderr, "socket: Are you root? You need CAP_NET_RAW powers.\n");
    }
    return raw_socket;
}

void sniff_loop(int packet_socket, void *memory1, void *memory2) {
#define ETHER_IP_SIZE (sizeof(struct sniff_ether) + sizeof(struct sniff_ip))
    ssize_t ret;
    struct sockaddr_ll saddr_ll;
    unsigned saddr_ll_size = sizeof(struct sockaddr_ll);
    u_int8_t datagram[ETHER_IP_SIZE];
    struct sniff_ether *ether = (struct sniff_ether*)datagram;
    struct sniff_ip *ip = (struct sniff_ip*)(datagram + 14);
    struct sniff_ip *ipq = (struct sniff_ip*)(datagram + 18);

    /* Set memory and other globals */
    sniff__memory[0] = memory1;
    sniff__memory[1] = memory2;
    sniff__memp = sniff__memory[0];
    sniff__done = 0;

    /* Add signal handlers */
    util_signal_set(SIGUSR1, sniff__switch_memory);
    util_signal_set(SIGINT, sniff__loop_done);
    util_signal_set(SIGHUP, sniff__loop_done);
    util_signal_set(SIGQUIT, sniff__loop_done);
    util_signal_set(SIGTERM, sniff__loop_done);

#ifndef NDEBUG
    fprintf(stderr, "sniff_loop: Starting loop (mem %p/%p).\n", sniff__memory[0], sniff__memory[1]);
#endif

    do {
	while ((ret = recvfrom(
	    packet_socket,
	    datagram,
	    ETHER_IP_SIZE,
	    0,
	    (struct sockaddr*)&saddr_ll,
	    &saddr_ll_size
	)) > 0) {
	    /* Process only ETH_P_IP/ETH_P_8021Q packets.
	     * Make sure we count the ethernet frame lengths as well (18 resp. 22 bytes). */
	    if (ether->type == ETH_P_IP) {
		memory_add(sniff__memp, ntohl(ip->src), ntohl(ip->dst), 0, ntohs(ip->len) + 18);
	    } else if (ether->type == ETH_P_8021Q && ether->type2 == ETH_P_IP) {
#if __BYTE_ORDER == __LITTLE_ENDIAN
		memory_add(sniff__memp, ntohl(ipq->src), ntohl(ipq->dst), ntohs(ether->vid << 4), ntohs(ipq->len) + 22);
#elif __BYTE_ORDER == __BIG_ENDIAN
		memory_add(sniff__memp, ntohl(ipq->src), ntohl(ipq->dst), ntohs(ether->vid), ntohs(ipq->len) + 22);
#else
		assert(0);
#endif
	    }
    	}
    } while (errno == EINTR && !sniff__done);
    /* Check errors */
    if (!sniff__done)
        perror("recvfrom");
#ifndef NDEBUG
    else
	fprintf(stderr, "sniff_loop: Ended loop at user/system request.\n");
#endif

    /* Remove signal handlers */
    util_signal_set(SIGUSR1, SIG_IGN);
    util_signal_set(SIGINT, SIG_IGN);
    util_signal_set(SIGHUP, SIG_IGN);
    util_signal_set(SIGQUIT, SIG_IGN);
    util_signal_set(SIGTERM, SIG_IGN);
#undef ETHER_IP_SIZE
}

static void sniff__switch_memory(int signum) {
#if 0
    fprintf(stderr, "sniff__switch_memory: Listing memory %p:\n", sniff__memp);
    memory_enum(sniff__memp, &sniff__test_memory_enum);
#endif
    if (sniff__memp == sniff__memory[0])
	sniff__memp = sniff__memory[1];
    else
	sniff__memp = sniff__memory[0];
#ifndef NDEBUG
    fprintf(stderr, "sniff__switch_memory: Using memory %p.\n", sniff__memp);
#endif
}

static void sniff__loop_done(int signum) {
    sniff__done = 1;
}

#if 0
static void sniff__test_memory_enum(u_int32_t ip, struct ipcount_t const *ipcount) {
    u_int8_t *ip8 = (u_int8_t*)&ip;
    fprintf(stderr, " * %" SCNu8 ".%" SCNu8 ".%" SCNu8 ".%" SCNu8
	    " pktIO %" SCNu32 "/%" SCNu32 " bytesIO %" SCNu64 "/%" SCNu64 " vlan# %" SCNu16 "\n",
#if __BYTE_ORDER == __LITTLE_ENDIAN
       	    ip8[3], ip8[2], ip8[1], ip8[0],
#elif __BYTE_ORDER == __BIG_ENDIAN
       	    ip8[0], ip8[1], ip8[2], ip8[3],
#else
	    0, 0, 0, 0,
#endif
	    ipcount->packets_in, ipcount->packets_out, ipcount->bytes_in, ipcount->bytes_out,
	    ipcount->vlan);
}
#endif
