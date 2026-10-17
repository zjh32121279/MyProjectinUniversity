// MD5.cpp
// MD5 Message Digest Algorithm Implementation

#include "MD5.h"
#include <iostream>
#include <iomanip>
#include <fstream>
#include <cstring>
#include <cctype>
#include <sstream>

using namespace std;

/* ================================================================
 * Predefined Constants for MD5
 * ================================================================ */

// T-table: 64 constants, T[i] = floor(2^32 * |sin(i+1)|)
static const uint32_t T[64] = {
    0xd76aa478, 0xe8c7b756, 0x242070db, 0xc1bdceee,
    0xf57c0faf, 0x4787c62a, 0xa8304613, 0xfd469501,
    0x698098d8, 0x8b44f7af, 0xffff5bb1, 0x895cd7be,
    0x6b901122, 0xfd987193, 0xa679438e, 0x49b40821,
    0xf61e2562, 0xc040b340, 0x265e5a51, 0xe9b6c7aa,
    0xd62f105d, 0x02441453, 0xd8a1e681, 0xe7d3fbc8,
    0x21e1cde6, 0xc33707d6, 0xf4d50d87, 0x455a14ed,
    0xa9e3e905, 0xfcefa3f8, 0x676f02d9, 0x8d2a4c8a,
    0xfffa3942, 0x8771f681, 0x6d9d6122, 0xfde5380c,
    0xa4beea44, 0x4bdecfa9, 0xf6bb4b60, 0xbebfbc70,
    0x289b7ec6, 0xeaa127fa, 0xd4ef3085, 0x04881d05,
    0xd9d4d039, 0xe6db99e5, 0x1fa27cf8, 0xc4ac5665,
    0xf4292244, 0x432aff97, 0xab9423a7, 0xfc93a039,
    0x655b59c3, 0x8f0ccc92, 0xffeff47d, 0x85845dd1,
    0x6fa87e4f, 0xfe2ce6e0, 0xa3014314, 0x4e0811a1,
    0xf7537e82, 0xbd3af235, 0x2ad7d2bb, 0xeb86d391
};

// Shift amounts per step (s-table)
static const uint32_t S[64] = {
    7, 12, 17, 22,   7, 12, 17, 22,   7, 12, 17, 22,   7, 12, 17, 22,
    5,  9, 14, 20,   5,  9, 14, 20,   5,  9, 14, 20,   5,  9, 14, 20,
    4, 11, 16, 23,   4, 11, 16, 23,   4, 11, 16, 23,   4, 11, 16, 23,
    6, 10, 15, 21,   6, 10, 15, 21,   6, 10, 15, 21,   6, 10, 15, 21
};

/* ================================================================
 * Layer 1: Basic Conversion Functions
 * ================================================================ */

// ----------------------------------------------------------------
// digestToHexString
// Convert 16-byte digest to a 32-character hexadecimal string.
// ----------------------------------------------------------------
string digestToHexString(const uint8_t digest[MD5_DIGEST_SIZE]) {
    ostringstream oss;
    for (int i = 0; i < MD5_DIGEST_SIZE; i++) {
        oss << hex << setw(2) << setfill('0') << (int)digest[i];
    }
    return oss.str();
}

// ----------------------------------------------------------------
// decodeToUint32
// Decode a 64-byte block into 16 little-endian 32-bit words.
// Each group of 4 consecutive bytes forms one uint32_t (low byte first).
// ----------------------------------------------------------------
void decodeToUint32(const uint8_t block[MD5_BLOCK_SIZE], uint32_t output[16]) {
    for (int i = 0, j = 0; j < MD5_BLOCK_SIZE; i++, j += 4) {
        output[i] =  (uint32_t)block[j]
                   | ((uint32_t)block[j + 1] << 8)
                   | ((uint32_t)block[j + 2] << 16)
                   | ((uint32_t)block[j + 3] << 24);
    }
}

// ----------------------------------------------------------------
// encodeFromUint32
// Encode 4 registers into a 16-byte array in little-endian order.
// Low byte stored at low address.
// ----------------------------------------------------------------
void encodeFromUint32(const uint32_t state[4], uint8_t output[MD5_DIGEST_SIZE]) {
    for (int i = 0, j = 0; j < MD5_DIGEST_SIZE; i++, j += 4) {
        output[j]      = (uint8_t)( state[i]        & 0xFF);
        output[j + 1]  = (uint8_t)((state[i] >>  8) & 0xFF);
        output[j + 2]  = (uint8_t)((state[i] >> 16) & 0xFF);
        output[j + 3]  = (uint8_t)((state[i] >> 24) & 0xFF);
    }
}

/* ================================================================
 * Layer 2: MD5 Core Transform — 64-step computation on one 512-bit block
 * ================================================================ */

// ----------------------------------------------------------------
// md5Transform
// Perform the MD5 core transform on a single 512-bit message block.
// Processing:
//   1. Decode 64-byte block into 16 32-bit words X[0..15]
//   2. Save current register values
//   3. Round 1 — F function, 16 steps, X indices sequential
//   4. Round 2 — G function, 16 steps, X indices = (5*i+1)%16
//   5. Round 3 — H function, 16 steps, X indices = (3*i+5)%16
//   6. Round 4 — I function, 16 steps, X indices = (7*i)%16
//   7. Accumulate results back into ctx registers
// ----------------------------------------------------------------
void md5Transform(MD5_CTX *ctx, const uint8_t block[MD5_BLOCK_SIZE]) {
    // ---- Step 1: Decode 64-byte block into 16 32-bit words ----
    uint32_t X[16];
    decodeToUint32(block, X);

    // ---- Step 2: Save current register values ----
    uint32_t a = ctx->A;
    uint32_t b = ctx->B;
    uint32_t c = ctx->C;
    uint32_t d = ctx->D;

    // Local STEP macro: performs one step then rotates registers rightward
    #define STEP(f, a, b, c, d, k, i, s) \
        do { \
            (a) += f((b), (c), (d)) + X[(k)] + T[(i)]; \
            (a)  = ROTATE_LEFT((a), (s)); \
            (a) += (b); \
        } while (0)

    // ---- Step 3: Round 1 — F function, X indices = i (sequential) ----
    STEP(MD5_F, a, b, c, d,  0,  0,  7);
    STEP(MD5_F, d, a, b, c,  1,  1, 12);
    STEP(MD5_F, c, d, a, b,  2,  2, 17);
    STEP(MD5_F, b, c, d, a,  3,  3, 22);
    STEP(MD5_F, a, b, c, d,  4,  4,  7);
    STEP(MD5_F, d, a, b, c,  5,  5, 12);
    STEP(MD5_F, c, d, a, b,  6,  6, 17);
    STEP(MD5_F, b, c, d, a,  7,  7, 22);
    STEP(MD5_F, a, b, c, d,  8,  8,  7);
    STEP(MD5_F, d, a, b, c,  9,  9, 12);
    STEP(MD5_F, c, d, a, b, 10, 10, 17);
    STEP(MD5_F, b, c, d, a, 11, 11, 22);
    STEP(MD5_F, a, b, c, d, 12, 12,  7);
    STEP(MD5_F, d, a, b, c, 13, 13, 12);
    STEP(MD5_F, c, d, a, b, 14, 14, 17);
    STEP(MD5_F, b, c, d, a, 15, 15, 22);

    // ---- Step 4: Round 2 — G function, X indices = (5*i+1)%16 ----
    STEP(MD5_G, a, b, c, d,  1, 16,  5);
    STEP(MD5_G, d, a, b, c,  6, 17,  9);
    STEP(MD5_G, c, d, a, b, 11, 18, 14);
    STEP(MD5_G, b, c, d, a,  0, 19, 20);
    STEP(MD5_G, a, b, c, d,  5, 20,  5);
    STEP(MD5_G, d, a, b, c, 10, 21,  9);
    STEP(MD5_G, c, d, a, b, 15, 22, 14);
    STEP(MD5_G, b, c, d, a,  4, 23, 20);
    STEP(MD5_G, a, b, c, d,  9, 24,  5);
    STEP(MD5_G, d, a, b, c, 14, 25,  9);
    STEP(MD5_G, c, d, a, b,  3, 26, 14);
    STEP(MD5_G, b, c, d, a,  8, 27, 20);
    STEP(MD5_G, a, b, c, d, 13, 28,  5);
    STEP(MD5_G, d, a, b, c,  2, 29,  9);
    STEP(MD5_G, c, d, a, b,  7, 30, 14);
    STEP(MD5_G, b, c, d, a, 12, 31, 20);

    // ---- Step 5: Round 3 — H function, X indices = (3*i+5)%16 ----
    STEP(MD5_H, a, b, c, d,  5, 32,  4);
    STEP(MD5_H, d, a, b, c,  8, 33, 11);
    STEP(MD5_H, c, d, a, b, 11, 34, 16);
    STEP(MD5_H, b, c, d, a, 14, 35, 23);
    STEP(MD5_H, a, b, c, d,  1, 36,  4);
    STEP(MD5_H, d, a, b, c,  4, 37, 11);
    STEP(MD5_H, c, d, a, b,  7, 38, 16);
    STEP(MD5_H, b, c, d, a, 10, 39, 23);
    STEP(MD5_H, a, b, c, d, 13, 40,  4);
    STEP(MD5_H, d, a, b, c,  0, 41, 11);
    STEP(MD5_H, c, d, a, b,  3, 42, 16);
    STEP(MD5_H, b, c, d, a,  6, 43, 23);
    STEP(MD5_H, a, b, c, d,  9, 44,  4);
    STEP(MD5_H, d, a, b, c, 12, 45, 11);
    STEP(MD5_H, c, d, a, b, 15, 46, 16);
    STEP(MD5_H, b, c, d, a,  2, 47, 23);

    // ---- Step 6: Round 4 — I function, X indices = (7*i)%16 ----
    STEP(MD5_I, a, b, c, d,  0, 48,  6);
    STEP(MD5_I, d, a, b, c,  7, 49, 10);
    STEP(MD5_I, c, d, a, b, 14, 50, 15);
    STEP(MD5_I, b, c, d, a,  5, 51, 21);
    STEP(MD5_I, a, b, c, d, 12, 52,  6);
    STEP(MD5_I, d, a, b, c,  3, 53, 10);
    STEP(MD5_I, c, d, a, b, 10, 54, 15);
    STEP(MD5_I, b, c, d, a,  1, 55, 21);
    STEP(MD5_I, a, b, c, d,  8, 56,  6);
    STEP(MD5_I, d, a, b, c, 15, 57, 10);
    STEP(MD5_I, c, d, a, b,  6, 58, 15);
    STEP(MD5_I, b, c, d, a, 13, 59, 21);
    STEP(MD5_I, a, b, c, d,  4, 60,  6);
    STEP(MD5_I, d, a, b, c, 11, 61, 10);
    STEP(MD5_I, c, d, a, b,  2, 62, 15);
    STEP(MD5_I, b, c, d, a,  9, 63, 21);

    #undef STEP

    // ---- Step 7: Accumulate results back into context registers ----
    ctx->A += a;
    ctx->B += b;
    ctx->C += c;
    ctx->D += d;
}

/* ================================================================
 * Layer 3: MD5 Three-Step Interface — Init → Update → Final
 * ================================================================ */

// ----------------------------------------------------------------
// md5Init
// Step 1: Initialize MD5 context.
// Set A/B/C/D to RFC 1321 initial vectors, zero the bit counter.
// ----------------------------------------------------------------
void md5Init(MD5_CTX *ctx) {
    // 1. Set the four initialization vectors
    ctx->A = MD5_INIT_A;
    ctx->B = MD5_INIT_B;
    ctx->C = MD5_INIT_C;
    ctx->D = MD5_INIT_D;

    // 2. Clear the message bit-length counter
    ctx->count[0] = 0;
    ctx->count[1] = 0;
}

// ----------------------------------------------------------------
// md5Update
// Step 2: Feed data into the MD5 engine.
// Data accumulates in the internal buffer; each full 64-byte block
// triggers one md5Transform.
// ----------------------------------------------------------------
void md5Update(MD5_CTX *ctx, const uint8_t *data, size_t dataLen) {
    // 1. Compute how many bytes are already buffered
    size_t index = (size_t)((ctx->count[0] >> 3) & 0x3F);

    // 2. Update total bit length (count[0] = low 32 bits, count[1] = high 32 bits)
    ctx->count[0] += (uint32_t)(dataLen << 3);
    if (ctx->count[0] < (uint32_t)(dataLen << 3)) {
        ctx->count[1]++;    // carry from low 32 bits
    }
    ctx->count[1] += (uint32_t)(dataLen >> 29);

    // 3. Remaining space in the buffer + bytes already in it
    size_t partLen = MD5_BLOCK_SIZE - index;
    size_t i;   // tracks position in data after processing full blocks

    // 4. Fill partial buffer + process full blocks
    if (dataLen >= partLen) {
        memcpy(&ctx->buffer[index], data, partLen);
        md5Transform(ctx, ctx->buffer);

        for (i = partLen; i + MD5_BLOCK_SIZE <= dataLen; i += MD5_BLOCK_SIZE) {
            md5Transform(ctx, &data[i]);
        }

        index = 0;
    } else {
        i = 0;
    }

    // 5. Copy remaining bytes (< 64) into the buffer at the correct offset
    memcpy(&ctx->buffer[index], &data[i], dataLen - i);
}

// ----------------------------------------------------------------
// md5Final
// Step 3: Apply padding + append length + process final block(s).
//   1. Compute padding length (append 0x80 + zeros until len ≡ 448 mod 512)
//   2. Append the 64-bit original message length (little-endian)
//   3. Process the final block(s) via md5Transform
//   4. Encode A,B,C,D into ctx->digest
// ----------------------------------------------------------------
void md5Final(MD5_CTX *ctx) {
    // 1. Save original message bit-length as 8 bytes (little-endian)
    //    count[0] = low 32 bits, count[1] = high 32 bits
    uint8_t bits[8];
    bits[0] = (uint8_t)( ctx->count[0]        & 0xFF);
    bits[1] = (uint8_t)((ctx->count[0] >>  8) & 0xFF);
    bits[2] = (uint8_t)((ctx->count[0] >> 16) & 0xFF);
    bits[3] = (uint8_t)((ctx->count[0] >> 24) & 0xFF);
    bits[4] = (uint8_t)( ctx->count[1]        & 0xFF);
    bits[5] = (uint8_t)((ctx->count[1] >>  8) & 0xFF);
    bits[6] = (uint8_t)((ctx->count[1] >> 16) & 0xFF);
    bits[7] = (uint8_t)((ctx->count[1] >> 24) & 0xFF);

    // 2. Compute padding length
    //    Bytes currently in the buffer
    size_t index = (size_t)((ctx->count[0] >> 3) & 0x3F);
    //    Pad so that total length ≡ 56 mod 64 (i.e. 448 mod 512 bits)
    size_t padLen = (index < 56) ? (56 - index) : (120 - index);

    // 3. Padding data: 0x80 followed by zeros
    static const uint8_t PADDING[64] = {
        0x80, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
           0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
           0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
           0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
    };

    // 4. Feed padding data via Update
    md5Update(ctx, PADDING, padLen);

    // 5. Feed the 64-bit original length via Update
    md5Update(ctx, bits, 8);

    // 6. Encode A,B,C,D into 16-byte digest
    uint32_t state[4] = { ctx->A, ctx->B, ctx->C, ctx->D };
    encodeFromUint32(state, ctx->digest);
}

/* ================================================================
 * Layer 4: High-Level Interface — String MD5 / File MD5
 * ================================================================ */

// ----------------------------------------------------------------
// md5String
// Compute MD5 digest for an arbitrary-length string.
// Returns 32-character lowercase hex string.
// ----------------------------------------------------------------
string md5String(const string &input) {
    MD5_CTX ctx;

    // 1. Init
    md5Init(&ctx);

    // 2. Feed data
    md5Update(&ctx, (const uint8_t *)input.c_str(), input.length());

    // 3. Finalize → output digest
    md5Final(&ctx);

    // 4. Convert to hex string
    return digestToHexString(ctx.digest);
}

// ----------------------------------------------------------------
// md5File
// Compute MD5 digest for a file of any size.
// Reads the file in 4 KB chunks to avoid loading large files into memory.
// Returns 32-character lowercase hex string (empty string on error).
// ----------------------------------------------------------------
string md5File(const string &filePath) {
    // 1. Open file in binary mode
    ifstream file(filePath, ios::binary);
    if (!file.is_open()) {
        cerr << "Error: Cannot open file \"" << filePath << "\"" << endl;
        return "";
    }

    MD5_CTX ctx;
    md5Init(&ctx);

    // 2. Read in 4 KB chunks, feed each into md5Update
    const size_t BUFFER_SIZE = 4096;
    uint8_t buffer[BUFFER_SIZE];

    while (file.read((char *)buffer, BUFFER_SIZE)) {
        md5Update(&ctx, buffer, BUFFER_SIZE);
    }
    // Process any remaining bytes (< BUFFER_SIZE) from the last partial read
    if (file.gcount() > 0) {
        md5Update(&ctx, buffer, (size_t)file.gcount());
    }
    file.close();

    // 3. Finalize → output digest
    md5Final(&ctx);

    return digestToHexString(ctx.digest);
}

/* ================================================================
 * Layer 5: CLI & Verification Functions
 * ================================================================ */

// ----------------------------------------------------------------
// md5PrintHelp — Print help information (-h option)
// ----------------------------------------------------------------
void md5PrintHelp() {
    cout << "MD5: usage：[-h]    --help information" << endl;
    cout << "            [-t]    --test MD5 application" << endl;
    cout << "            [-c]    [file path of the file computed]" << endl;
    cout << "                    --compute MD5 of the given file" << endl;
    cout << "            [-v]    [file path of the file validated]" << endl;
    cout << "                    --validate the integrality of a given file" << endl;
    cout << "                           by manual input MD5 value" << endl;
    cout << "            [-f]    [file path of the file validated]" << endl;
    cout << "                    [file path of the .md5 file]" << endl;
    cout << "                    --validate the integrality of a given file" << endl;
    cout << "                           by read MD5 value from .md5 file" << endl;
}

// ----------------------------------------------------------------
// md5PrintTestCases — Print RFC 1321 test vectors (-t option)
// ----------------------------------------------------------------
void md5PrintTestCases() {
    cout << "MD5(\"\") = "
         << md5String("") << endl;
    cout << "MD5(\"a\") = "
         << md5String("a") << endl;
    cout << "MD5(\"abc\") = "
         << md5String("abc") << endl;
    cout << "MD5(\"message digest\") = "
         << md5String("message digest") << endl;
    cout << "MD5(\"abcdefghijklmnopqrstuvwxyz\") = "
         << md5String("abcdefghijklmnopqrstuvwxyz") << endl;
    cout << "MD5(\"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789\") = "
         << md5String("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789") << endl;
    cout << "MD5(\"12345678901234567890123456789012345678901234567890123456789012345678901234567890\") = "
         << md5String("12345678901234567890123456789012345678901234567890123456789012345678901234567890") << endl;
}

// ----------------------------------------------------------------
// md5ComputeFile — Compute and print MD5 for a file (-c option)
// ----------------------------------------------------------------
void md5ComputeFile(const string &filePath) {
    string md5 = md5File(filePath);
    if (!md5.empty()) {
        cout << "The MD5 value of file(\"" << filePath << "\") is " << md5 << endl;
    }
}

// ----------------------------------------------------------------
// md5ValidateByManualInput — Verify file integrity via manual MD5 input (-v option)
// ----------------------------------------------------------------
void md5ValidateByManualInput(const string &filePath) {
    // 1. Prompt user for the original MD5 value
    cout << "Please input the MD5 value of file(\"" << filePath << "\")...";

    string oldMD5;
    getline(cin, oldMD5);

    // 2. Recompute the file's MD5
    string newMD5 = md5File(filePath);
    if (newMD5.empty()) return;

    // 3. Print both values
    cout << "The old MD5 value of file(\"" << filePath
         << "\") you have input is" << endl << oldMD5 << endl;
    cout << "The new MD5 value of file(\"" << filePath
         << "\") that has computed is" << endl << newMD5 << endl;

    // 4. Compare (case-insensitive)
    string oldLower = oldMD5, newLower = newMD5;
    for (auto &c : oldLower) c = (char)tolower((unsigned char)c);
    for (auto &c : newLower) c = (char)tolower((unsigned char)c);

    if (oldLower == newLower) {
        cout << "OK! The file is integrated" << endl;
    } else {
        cout << "Match Error! The file has been modified!" << endl;
    }
}

// ----------------------------------------------------------------
// md5ValidateByFile — Verify file integrity from .md5 file (-f option)
// ----------------------------------------------------------------
void md5ValidateByFile(const string &filePath, const string &md5FilePath) {
    // 1. Read original MD5 from the .md5 file
    ifstream md5FileStream(md5FilePath);
    if (!md5FileStream.is_open()) {
        cerr << "Error: Cannot open .md5 file \"" << md5FilePath << "\"" << endl;
        return;
    }

    string oldMD5;
    getline(md5FileStream, oldMD5);
    md5FileStream.close();

    // .md5 file format: "MD5_value  filename" → extract the first token
    istringstream iss(oldMD5);
    iss >> oldMD5;

    // 2. Recompute the file's MD5
    string newMD5 = md5File(filePath);
    if (newMD5.empty()) return;

    // 3. Print both values
    cout << "The old MD5 value of file(\"" << filePath
         << "\") in " << md5FilePath << " is" << endl << oldMD5 << endl;
    cout << "The new MD5 value of file(\"" << filePath
         << "\") that has computed is" << endl << newMD5 << endl;

    // 4. Compare (case-insensitive)
    string oldLower = oldMD5, newLower = newMD5;
    for (auto &c : oldLower) c = (char)tolower((unsigned char)c);
    for (auto &c : newLower) c = (char)tolower((unsigned char)c);

    if (oldLower == newLower) {
        cout << "OK! The file is integrated" << endl;
    } else {
        cout << "Match Error! The file has been modified!" << endl;
    }
}

