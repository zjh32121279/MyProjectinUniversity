// MD5.h
// MD5 Message Digest Algorithm Header

#ifndef MD5_HEADER_H
#define MD5_HEADER_H

#include <stdint.h>
#include <string>

using namespace std;

/* ================================================================
 * Four Constants — MD5 Initialization Vectors
 * ================================================================
 * Per RFC 1321, stored in little-endian byte order.
 * Byte layout in memory (low → high address):
 *   A: 01 23 45 67
 *   B: 89 AB CD EF
 *   C: FE DC BA 98
 *   D: 76 54 32 10
 * ================================================================ */
#define MD5_INIT_A  0x67452301UL
#define MD5_INIT_B  0xEFCDAB89UL
#define MD5_INIT_C  0x98BADCFEUL
#define MD5_INIT_D  0x10325476UL

/* MD5 block size in bits */
#define MD5_BLOCK_BITS  512
/* MD5 block size in bytes */
#define MD5_BLOCK_SIZE  64
/* MD5 digest size in bytes */
#define MD5_DIGEST_SIZE 16
/* MD5 hex string length (excluding null terminator) */
#define MD5_HEX_SIZE    32

/* ================================================================
 * Bitwise Operation Helper Macros
 * ================================================================
 * C/C++ built-in operators: & | ^ ~ << >> — no extra header needed.
 * The only missing piece is circular left-shift: ROTATE_LEFT.
 *
 * The expression (x << n) | (x >> (32-n)) is recognized by GCC/Clang
 * and compiled to a single ROL instruction, so no builtin is needed.
 * ================================================================ */
#define ROTATE_LEFT(x, n)  \
    (((uint32_t)(x) << (n)) | ((uint32_t)(x) >> ((32 - (n)) & 31)))

/* ================================================================
 * MD5 Four-Round Nonlinear Functions
 * ================================================================ */
#define MD5_F(X, Y, Z)  (((X) & (Y)) | ((~(X)) & (Z)))
#define MD5_G(X, Y, Z)  (((X) & (Z)) | ((Y) & (~(Z))))
#define MD5_H(X, Y, Z)  ((X) ^ (Y) ^ (Z))
#define MD5_I(X, Y, Z)  ((Y) ^ ((X) | (~(Z))))

/* ================================================================
 * MD5 Context Structure
 * ================================================================ */
typedef struct {
    uint32_t A;             /* Register A — init to MD5_INIT_A */
    uint32_t B;             /* Register B — init to MD5_INIT_B */
    uint32_t C;             /* Register C — init to MD5_INIT_C */
    uint32_t D;             /* Register D — init to MD5_INIT_D */
    uint32_t count[2];      /* Original message length in bits (64-bit) */
    uint8_t  buffer[64];    /* 512-bit message block buffer */
    uint8_t  digest[16];    /* Final 128-bit digest output */
} MD5_CTX;

// ===== Layer 1: Basic Conversion Functions =====

// Convert 16-byte digest to 32-char hex string
string digestToHexString(const uint8_t digest[MD5_DIGEST_SIZE]);

// Decode 64-byte block into 16 little-endian 32-bit words X[0..15]
void decodeToUint32(const uint8_t block[MD5_BLOCK_SIZE], uint32_t output[16]);

// Encode 4 registers into 16-byte array in little-endian
void encodeFromUint32(const uint32_t state[4], uint8_t output[MD5_DIGEST_SIZE]);

// ===== Layer 2: MD5 Core Transform =====

// Perform MD5 transform on a single 512-bit block (64-step main loop)
void md5Transform(MD5_CTX *ctx, const uint8_t block[MD5_BLOCK_SIZE]);

// ===== Layer 3: MD5 Three-Step Interface — Init / Update / Final =====

// Step 1: Initialize MD5 context with the four initial vectors
void md5Init(MD5_CTX *ctx);

// Step 2: Feed data in, processing full blocks as they become available
void md5Update(MD5_CTX *ctx, const uint8_t *data, size_t dataLen);

// Step 3: Apply padding + append length + process final block(s) → output digest
void md5Final(MD5_CTX *ctx);

// ===== Layer 4: High-Level Interface =====

// Compute MD5 for an arbitrary-length string, returns 32-char hex string
string md5String(const string &input);

// Compute MD5 for a file of any size, returns 32-char hex string
string md5File(const string &filePath);

// ===== Layer 5: CLI & Verification Functions =====

// Print test cases against RFC 1321 standard test vectors
void md5PrintTestCases();

// Print help information (-h option)
void md5PrintHelp();

// Compute and print MD5 for the given file (-c option)
void md5ComputeFile(const string &filePath);

// Verify file integrity via manual MD5 input (-v option)
void md5ValidateByManualInput(const string &filePath);

// Verify file integrity by reading MD5 from a .md5 file (-f option)
void md5ValidateByFile(const string &filePath, const string &md5FilePath);

#endif /* MD5_HEADER_H */
