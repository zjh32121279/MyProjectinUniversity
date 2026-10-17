// DES.cpp
// DES encryption algorithm implementation

#include "DES.h"
#include "box.h"
#include <iostream>
#include <cstring>
#include <vector>
#include <iomanip>
#include <chrono>
#include <random>

using namespace std;

// ========== Base64 Encode/Decode Helpers ==========
static const char BASE64_CHARS[] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

string base64Encode(const string& data) {
    string encoded;
    int val = 0;
    int valb = -6;
    for (unsigned char c : data) {
        val = (val << 8) + c;
        valb += 8;
        while (valb >= 0) {
            encoded.push_back(BASE64_CHARS[(val >> valb) & 0x3F]);
            valb -= 6;
        }
    }
    if (valb > -6) {
        encoded.push_back(BASE64_CHARS[((val << 8) >> (valb + 8)) & 0x3F]);
    }
    while (encoded.length() % 4 != 0) {
        encoded.push_back('=');
    }
    return encoded;
}

string base64Decode(const string& encoded) {
    string decoded;
    vector<int> T(256, -1);
    for (int i = 0; i < 64; i++) T[(unsigned char)BASE64_CHARS[i]] = i;

    int val = 0;
    int valb = -8;
    for (unsigned char c : encoded) {
        if (T[c] == -1) break; // '=' or invalid char ends decoding
        val = (val << 6) + T[c];
        valb += 6;
        if (valb >= 0) {
            decoded.push_back((char)((val >> valb) & 0xFF));
            valb -= 8;
        }
    }
    return decoded;
}

// ========== Global Encryption Key (unified key setting) ==========
// Both client and server can use this shared key mechanism
static string GLOBAL_ENCRYPTION_KEY = "";

// Generate random 8-byte DES key
string generateRandomKey() {
    // Use Mersenne Twister random number engine seeded with system clock
    unsigned seed = chrono::system_clock::now().time_since_epoch().count();
    mt19937 gen(seed);
    uniform_int_distribution<> dis(33, 126);  // Printable ASCII range: 33-126

    string key;
    for (int i = 0; i < 8; i++) {
        key += static_cast<char>(dis(gen));
    }
    return key;
}

// Get/set global encryption key
string getEncryptionKey() {
    GLOBAL_ENCRYPTION_KEY = generateRandomKey();
    return GLOBAL_ENCRYPTION_KEY;
}

// Convert 8-byte string to 64-bit bitset
bitset<64> stringToBitset(const string& data) {
    bitset<64> bits;
    for (int i = 0; i < 8 && i < (int)data.length(); i++) {
        unsigned char c = data[i];
        for (int j = 0; j < 8; j++) {
            int bitPos = i * 8 + j;
            if (c & (1 << (7 - j))) {
                bits.set(63 - bitPos);
            }
        }
    }
    return bits;
}

// Convert 64-bit bitset to 8-byte string
string bitsetToString(const bitset<64>& bits) {
    string result(8, '\0');
    for (int i = 0; i < 8; i++) {
        unsigned char c = 0;
        for (int j = 0; j < 8; j++) {
            int bitPos = i * 8 + j;
            if (bits[63 - bitPos]) {
                c |= (1 << (7 - j));
            }
        }
        result[i] = c;
    }
    return result;
}

// IP permutation function
bitset<64> ipPermutation(const bitset<64>& input) {
    bitset<64> output;

    for (int i = 0; i < 64; i++) {
        int sourceBitIndex = 64 - IP[i];
        output[63 - i] = input[sourceBitIndex];
    }

    return output;
}

// Expansion permutation E (32 bits -> 48 bits, internal use)
bitset<48> expansionPermutation(const bitset<32>& input) {
    bitset<48> output;

    for (int i = 0; i < 48; i++) {
        int sourceBitIndex = 32 - E[i];
        output[47 - i] = input[sourceBitIndex];
    }

    return output;
}

// S-box substitution (48 bits -> 32 bits, internal use)
bitset<32> sBoxSubstitution(const bitset<48>& input) {
    bitset<32> output;

    for (int i = 0; i < 8; i++) {
        int groupStart = 48 - (i + 1) * 6;
        bitset<6> sixBits;
        for (int j = 0; j < 6; j++) {
            sixBits[5 - j] = input[groupStart + j];
        }

        int row = (sixBits[5] << 1) | sixBits[0];
        int col = (sixBits[4] << 3) | (sixBits[3] << 2) | (sixBits[2] << 1) | sixBits[1];

        int sboxValue = S_BOX[i][row][col];

        int outputStart = 32 - (i + 1) * 4;
        for (int j = 0; j < 4; j++) {
            output[outputStart + (3 - j)] = (sboxValue >> j) & 1;
        }
    }

    return output;
}

// P permutation (32 bits -> 32 bits, internal use)
bitset<32> pPermutation(const bitset<32>& input) {
    bitset<32> output;

    for (int i = 0; i < 32; i++) {
        int sourceBitIndex = 32 - P[i];
        output[31 - i] = input[sourceBitIndex];
    }

    return output;
}

// F function: Expansion -> XOR with subkey -> S-box substitution -> P permutation
bitset<32> feistelFunction(const bitset<32>& right, const bitset<48>& subKey) {
    bitset<48> expandedRight = expansionPermutation(right);
    bitset<48> xorResult = expandedRight ^ subKey;
    bitset<32> sboxResult = sBoxSubstitution(xorResult);
    bitset<32> output = pPermutation(sboxResult);

    return output;
}

// PC-1 permutation: 64-bit key -> 56 bits (removes parity bits)
bitset<56> pc1Permutation(const bitset<64>& key) {
    bitset<56> output;

    for (int i = 0; i < 56; i++) {
        int sourceBitIndex = 64 - PC1[i];
        output[55 - i] = key[sourceBitIndex];
    }

    return output;
}

// PC-2 permutation: 56-bit key -> 48-bit subkey
bitset<48> pc2Permutation(const bitset<56>& input) {
    bitset<48> output;

    for (int i = 0; i < 48; i++) {
        int sourceBitIndex = 56 - PC2[i];
        output[47 - i] = input[sourceBitIndex];
    }

    return output;
}

// Left circular shift function
bitset<28> leftShift(const bitset<28>& input, int shift) {
    bitset<28> output;

    for (int i = 0; i < 28; i++) {
        int newPos = (i + shift) % 28;
        output[27 - newPos] = input[27 - i];
    }

    return output;
}

// Generate 16 subkeys from the 64-bit master key
vector<bitset<48>> generateSubKeys(const bitset<64>& key) {
    vector<bitset<48>> subKeys(16);

    // 1. PC-1 permutation: 64 bits -> 56 bits
    bitset<56> permutedKey = pc1Permutation(key);

    // 2. Split into left and right halves, 28 bits each
    bitset<28> leftHalf;
    bitset<28> rightHalf;

    for (int i = 0; i < 28; i++) {
        leftHalf[27 - i] = permutedKey[55 - i];
        rightHalf[27 - i] = permutedKey[27 - i];
    }

    // 3. Generate 16 subkeys
    for (int round = 0; round < 16; round++) {
        // Left circular shift
        leftHalf = leftShift(leftHalf, SHIFT_BITS[round]);
        rightHalf = leftShift(rightHalf, SHIFT_BITS[round]);

        // Combine left and right halves
        bitset<56> combined;
        for (int i = 0; i < 28; i++) {
            combined[55 - i] = leftHalf[27 - i];
            combined[27 - i] = rightHalf[27 - i];
        }

        // PC-2 permutation: 56 bits -> 48 bits
        subKeys[round] = pc2Permutation(combined);
    }

    return subKeys;
}

// Inverse IP permutation
// Input:  64-bit block after 16 Feistel rounds (with swapped halves)
// Output: 64-bit ciphertext block
bitset<64> ipInvPermutation(const bitset<64>& input) {
    bitset<64> output;

    // Apply inverse IP permutation
    for (int i = 0; i < 64; i++) {
        // IP_INV[i] values are 1-indexed, bit 1 maps to bitset index 63
        int sourceBitIndex = 64 - IP_INV[i];
        output[63 - i] = input[sourceBitIndex];
    }

    return output;
}

// Single Feistel round
// Input:  64-bit block (left 32 bits + right 32 bits)
// Output: 64-bit block after one Feistel transformation
bitset<64> feistelRound(const bitset<64>& input, const bitset<48>& subKey) {
    // Split into left and right halves, 32 bits each
    bitset<32> left;
    bitset<32> right;

    // Left half (high 32 bits: bits 63-32)
    for (int i = 0; i < 32; i++) {
        left[31 - i] = input[63 - i];
        right[31 - i] = input[31 - i];
    }

    // Save old right half
    bitset<32> oldRight = right;

    // Compute new right half: left XOR F(right, subKey)
    bitset<32> newRight = left ^ feistelFunction(oldRight, subKey);

    // New left half is the old right half
    bitset<32> newLeft = oldRight;

    // Combine left and right halves
    bitset<64> output;
    for (int i = 0; i < 32; i++) {
        output[63 - i] = newLeft[31 - i];
        output[31 - i] = newRight[31 - i];
    }

    return output;
}

// DES block encryption function
// Input:  64-bit plaintext block, 64-bit key
// Output: 64-bit ciphertext block
bitset<64> desEncryptBlock(const bitset<64>& plaintext, const bitset<64>& key) {
    // 1. Generate 16 subkeys
    vector<bitset<48>> subKeys = generateSubKeys(key);

    // 2. Initial IP permutation
    bitset<64> current = ipPermutation(plaintext);

    // 3. Apply 16 Feistel rounds (subkeys in forward order)
    for (int round = 0; round < 16; round++) {
        current = feistelRound(current, subKeys[round]);
    }

    // 4. Swap left and right halves after the last round
    // (Standard DES swaps after the final round)
    bitset<32> left, right;
    for (int i = 0; i < 32; i++) {
        left[31 - i] = current[63 - i];
        right[31 - i] = current[31 - i];
    }

    // Swap
    bitset<64> swapped;
    for (int i = 0; i < 32; i++) {
        swapped[63 - i] = right[31 - i];
        swapped[31 - i] = left[31 - i];
    }

    // 5. Inverse IP permutation
    bitset<64> ciphertext = ipInvPermutation(swapped);

    return ciphertext;
}

// DES block decryption function
// Input:  64-bit ciphertext block, 64-bit key
// Output: 64-bit plaintext block
bitset<64> desDecryptBlock(const bitset<64>& ciphertext, const bitset<64>& key) {
    // 1. Generate 16 subkeys
    vector<bitset<48>> subKeys = generateSubKeys(key);

    // 2. Initial IP permutation
    bitset<64> current = ipPermutation(ciphertext);

    // 3. Apply 16 Feistel rounds (subkeys in reverse order for decryption)
    for (int round = 0; round < 16; round++) {
        // Use subkeys in reverse order for decryption
        current = feistelRound(current, subKeys[15 - round]);
    }

    // 4. Swap left and right halves after the last round
    bitset<32> left, right;
    for (int i = 0; i < 32; i++) {
        left[31 - i] = current[63 - i];
        right[31 - i] = current[31 - i];
    }

    // Swap
    bitset<64> swapped;
    for (int i = 0; i < 32; i++) {
        swapped[63 - i] = right[31 - i];
        swapped[31 - i] = left[31 - i];
    }

    // 5. Inverse IP permutation
    bitset<64> plaintext = ipInvPermutation(swapped);

    return plaintext;
}

// PKCS#7 padding function
string pkcs7Pad(const string& data) {
    size_t paddingLen = 8 - (data.length() % 8);
    if (paddingLen == 0) paddingLen = 8;

    string padded = data;
    for (size_t i = 0; i < paddingLen; i++) {
        padded += (char)paddingLen;
    }
    return padded;
}

// PKCS#7 unpadding function
string pkcs7Unpad(const string& data) {
    if (data.empty()) return data;

    size_t paddingLen = (unsigned char)data.back();
    if (paddingLen > 8 || paddingLen > data.length()) {
        return data; // Invalid padding, return original data
    }

    // Verify padding is valid
    bool valid = true;
    for (size_t i = data.length() - paddingLen; i < data.length(); i++) {
        if ((unsigned char)data[i] != paddingLen) {
            valid = false;
            break;
        }
    }

    if (valid) {
        return data.substr(0, data.length() - paddingLen);
    }
    return data;
}

// String encryption function
// Input:  plaintext string of arbitrary length, 8-byte key string
// Output: ciphertext string (length is a multiple of 8)
string desEncryptString(const string& plaintext, const string& key) {
    // 1. Ensure key is exactly 8 bytes
    string paddedKey = key;
    if (paddedKey.length() < 8) {
        // Key shorter than 8 bytes: pad with zeros
        paddedKey.append(8 - paddedKey.length(), '\0');
    }
    else if (paddedKey.length() > 8) {
        // Key longer than 8 bytes: truncate to first 8 bytes
        paddedKey = paddedKey.substr(0, 8);
    }

    bitset<64> keyBits = stringToBitset(paddedKey);

    // 2. Apply PKCS#7 padding
    string paddedPlaintext = pkcs7Pad(plaintext);

    // 3. Encrypt block by block (ECB mode)
    string ciphertext;
    for (size_t i = 0; i < paddedPlaintext.length(); i += 8) {
        string block = paddedPlaintext.substr(i, 8);
        bitset<64> plaintextBits = stringToBitset(block);
        bitset<64> ciphertextBits = desEncryptBlock(plaintextBits, keyBits);
        ciphertext += bitsetToString(ciphertextBits);
    }

    return ciphertext;
}

// String decryption function
// Input:  ciphertext string (length must be a multiple of 8), 8-byte key string
// Output: decrypted original plaintext string
string desDecryptString(const string& ciphertext, const string& key) {
    // 1. Ensure key is exactly 8 bytes
    string paddedKey = key;
    if (paddedKey.length() < 8) {
        paddedKey.append(8 - paddedKey.length(), '\0');
    }
    else if (paddedKey.length() > 8) {
        paddedKey = paddedKey.substr(0, 8);
    }

    bitset<64> keyBits = stringToBitset(paddedKey);

    // 2. Verify ciphertext length is a multiple of 8
    if (ciphertext.length() % 8 != 0) {
        cerr << "Ciphertext length is not a multiple of 8" << endl;
        return "";
    }

    // 3. Decrypt block by block (ECB mode)
    string decrypted;
    for (size_t i = 0; i < ciphertext.length(); i += 8) {
        string block = ciphertext.substr(i, 8);
        bitset<64> ciphertextBits = stringToBitset(block);
        bitset<64> plaintextBits = desDecryptBlock(ciphertextBits, keyBits);
        decrypted += bitsetToString(plaintextBits);
    }

    // 4. Remove PKCS#7 padding
    return pkcs7Unpad(decrypted);
}
