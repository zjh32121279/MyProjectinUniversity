#pragma once

#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>
#include <cstddef>

#pragma comment(lib, "ws2_32.lib")

#define RDT_SYN 0x01
#define RDT_ACK 0x02
#define RDT_FIN 0x04
#define RDT_RST 0x08
#define RDT_MSS 1400
#define RDT_MAX_SACK_BITS 32

#pragma pack(push, 1)
struct RDTHeader {
    uint32_t seq;      // sequence number (byte-based)
    uint32_t ack;      // ack number (next expected)
    uint16_t flags;    // SYN/ACK/FIN
    uint16_t checksum; // simple 16-bit checksum
    uint16_t wnd;      // receiver window (in segments)
    uint16_t len;      // data length
    uint32_t sack;     // selective-ack bitmap for next RDT_MAX_SACK_BITS packets
};
#pragma pack(pop)

static inline uint16_t rdt_checksum(const void* data, size_t len) {
    // simple 16-bit ones' complement checksum like in sample code
    const uint8_t* buf = (const uint8_t*)data;
    uint32_t sum = 0;
    size_t i = 0;
    while (i + 1 < len) {
        sum += (uint16_t)(buf[i] << 8 | buf[i + 1]);
        while (sum >> 16) {
            sum = (sum & 0xFFFF) + (sum >> 16);
        }
        i += 2;
    }
    if (i < len) { // odd
        sum += (uint16_t)(buf[i] << 8);
        while (sum >> 16) {
            sum = (sum & 0xFFFF) + (sum >> 16);
        }
    }
    sum = ~sum;
    return (uint16_t)(sum & 0xFFFF);
}

// utility: fill header checksum
static inline void fill_checksum(RDTHeader* h, const char* payload) {
    h->checksum = 0;
    // compute checksum over network-order header + payload
    RDTHeader tmp = *h;
    tmp.checksum = 0;
    // convert header to network order for checksum canonical form
    tmp.seq = htonl(tmp.seq);
    tmp.ack = htonl(tmp.ack);
    tmp.flags = htons(tmp.flags);
    tmp.checksum = htons(tmp.checksum);
    tmp.wnd = htons(tmp.wnd);
    tmp.len = htons(tmp.len);
    tmp.sack = htonl(tmp.sack);
    uint16_t cks = rdt_checksum(&tmp, sizeof(RDTHeader));
    if (h->len && payload) {
        size_t tot = sizeof(RDTHeader) + h->len;
        std::vector<char> buf(tot);
        memcpy(buf.data(), &tmp, sizeof(RDTHeader));
        memcpy(buf.data() + sizeof(RDTHeader), payload, h->len);
        cks = rdt_checksum(buf.data(), tot);
    }
    h->checksum = cks;
}

// convert header fields to/from network order
static inline void hdr_hton(RDTHeader* h) {
    h->seq = htonl(h->seq);
    h->ack = htonl(h->ack);
    h->flags = htons(h->flags);
    h->checksum = htons(h->checksum);
    h->wnd = htons(h->wnd);
    h->len = htons(h->len);
    h->sack = htonl(h->sack);
}

static inline void hdr_ntoh(RDTHeader* h) {
    h->seq = ntohl(h->seq);
    h->ack = ntohl(h->ack);
    h->flags = ntohs(h->flags);
    h->checksum = ntohs(h->checksum);
    h->wnd = ntohs(h->wnd);
    h->len = ntohs(h->len);
    h->sack = ntohl(h->sack);
}

// compute/verify checksum from raw network buffer
static inline bool verify_checksum_raw(const char* rawbuf, size_t rawlen) {
    if (!rawbuf || rawlen < sizeof(RDTHeader)) return false;
    // extract payload length (network order) from raw header
    uint16_t net_len;
    memcpy(&net_len, rawbuf + offsetof(RDTHeader, len), sizeof(uint16_t));
    size_t payload_len = ntohs(net_len);
    size_t tot = sizeof(RDTHeader) + payload_len;
    if (rawlen < tot) return false;
    // original checksum in network order
    uint16_t net_orig; memcpy(&net_orig, rawbuf + offsetof(RDTHeader, checksum), sizeof(uint16_t));
    uint16_t orig = ntohs(net_orig);

    // build temp buffer: copy raw header, zero checksum field, append payload
    std::vector<char> tmp(tot);
    memcpy(tmp.data(), rawbuf, sizeof(RDTHeader));
    tmp[offsetof(RDTHeader, checksum)] = 0;
    tmp[offsetof(RDTHeader, checksum) + 1] = 0;
    if (payload_len) memcpy(tmp.data() + sizeof(RDTHeader), rawbuf + sizeof(RDTHeader), payload_len);
    uint16_t cks = rdt_checksum(tmp.data(), tot);
    return cks == orig;
}

// convenience wrapper for compatibility
static inline bool verify_checksum(const RDTHeader* h, const char* payload) {
    // caller must ensure h points to raw bytes as received (network order)
    return verify_checksum_raw((const char*)h, sizeof(RDTHeader) + (h->len ? h->len : 0));
}

// convenience
static const int DEFAULT_RDT_PORT = 2333;

std::string LastWSAError() {
    int e = WSAGetLastError();
    char buf[256] = { 0 };
    FormatMessageA(FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS, NULL, e, 0, buf, sizeof(buf) - 1, NULL);
    return std::to_string(e) + ": " + std::string(buf);
}
