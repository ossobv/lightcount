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
#include <sys/socket.h>
#include <netinet/in.h>
#include <net/if.h>
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <netpacket/packet.h> /* linux-specific: struct_ll and PF_PACKET */

/* Static constants (also found in linux/if_ether.h) */
#if BYTE_ORDER == LITTLE_ENDIAN
# define ETH_P_ALL 0x0300   /* all frames */
# define ETH_P_IP 0x0008    /* IP frames */
# define ETH_P_8021Q 0x0081 /* 802.1q vlan frames */
#elif BYTE_ORDER == BIG_ENDIAN
# define ETH_P_ALL 0x0003   /* all frames */
# define ETH_P_IP 0x0800    /* IP frames */
# define ETH_P_8021Q 0x8100 /* 802.1q vlan frames */
#endif


/* Ethernet header */
struct sniff_ether {
    uint8_t dest[6];	    /* destination host address */
    uint8_t source[6];	    /* source host address */
    uint16_t type;	    /* ETH_P_* type */
    uint16_t pcp_cfi_vid;   /* 3bit prio, 1bit format indic, 12bit vlan (0=no, fff=reserved) */
    uint16_t type2;	    /* encapsulated type */
};

/* IP header */
struct sniff_ip {
    uint8_t hl:4,	    /* header length */
	    ver:4;	    /* version */
    uint8_t  tos;	    /* type of service */
    uint16_t len;	    /* total length */
    uint16_t id;	    /* identification */
    uint16_t off;	    /* fragment offset field */
#define IP_RF 0x8000	    /* reserved fragment flag */
#define IP_DF 0x4000	    /* dont fragment flag */
#define IP_MF 0x2000	    /* more fragments flag */
#define IP_OFFMASK 0x1fff   /* mask for fragmenting bits */
    uint8_t  ttl;	    /* time to live */
    uint8_t  proto;	    /* protocol */
    uint16_t sum;	    /* checksum */
    uint32_t src;	    /* source address */
    uint32_t dst;	    /* dest address */
};

static void *sniff__memory[2];	    /* two locations to store counts in */
static void *sniff__memp;	    /* the "current" memory location */
static volatile int sniff__done;    /* whether we're done */


static void sniff__switch_memory(int signum);
static void sniff__loop_done(int signum);


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
    uint8_t datagram[ETHER_IP_SIZE];
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

    /* FIXME: Put the interfaces in promiscuous mode.. you must do this
     * by hand for now (/sbin/ip link set eth0 up promisc on). */

#ifndef NDEBUG
    fprintf(stderr, "sniff_loop: Starting loop (mem %p/%p).\n", sniff__memory[0], sniff__memory[1]);
#endif

    do {
	while (!sniff__done && (ret = recvfrom(
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
		memory_add(
		    sniff__memp,
		    ntohl(ipq->src),
		    ntohl(ipq->dst),
#if BYTE_ORDER == LITTLE_ENDIAN
		    ((uint8_t*)&ether->pcp_cfi_vid)[1] | ((((uint8_t*)&ether->pcp_cfi_vid)[0] & 0xf) << 8),
#elif BYTE_ORDER == BIG_ENDIAN
		    ether->pcp_cfi_vid & 0xfff,
#endif
		    ntohs(ipq->len) + 22
		);
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
