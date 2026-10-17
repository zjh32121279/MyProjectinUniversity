// DES.h
// DES encryption algorithm header file

#ifndef DES_H
#define DES_H

#include <bitset>
#include <string>
#include <vector>

using namespace std;

// Generate random 8-byte DES key
string generateRandomKey();

// Get global encryption key
string getEncryptionKey();

// Conversion between 8-byte string and 64-bit bitset
bitset<64> stringToBitset(const string& data);
string bitsetToString(const bitset<64>& bits);

// IP permutation function
bitset<64> ipPermutation(const bitset<64>& input);

// Inverse IP permutation function
bitset<64> ipInvPermutation(const bitset<64>& input);

// F function
bitset<32> feistelFunction(const bitset<32>& right, const bitset<48>& subKey);

// Subkey generation function
vector<bitset<48>> generateSubKeys(const bitset<64>& key);

// Single Feistel round
bitset<64> feistelRound(const bitset<64>& input, const bitset<48>& subKey);

// DES block encryption function
bitset<64> desEncryptBlock(const bitset<64>& plaintext, const bitset<64>& key);

// DES block decryption function
bitset<64> desDecryptBlock(const bitset<64>& ciphertext, const bitset<64>& key);

// String encryption function (supports arbitrary length)
string desEncryptString(const string& plaintext, const string& key);

// String decryption function (supports arbitrary length)
string desDecryptString(const string& ciphertext, const string& key);

// Base64 encode/decode helpers for network-safe transmission
string base64Encode(const string& data);
string base64Decode(const string& encoded);

#endif // DES_H