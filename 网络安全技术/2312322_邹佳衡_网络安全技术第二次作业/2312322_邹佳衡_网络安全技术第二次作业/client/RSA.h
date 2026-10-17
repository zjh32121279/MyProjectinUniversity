#ifndef RSA_H
#define RSA_H

#include <string>
using namespace std;

// Generate RSA key pair and save to files
void generateRSAKeys(unsigned int keyLength, const string& pubFile, const string& privFile);

// Load public key from file and encrypt plaintext (returns Base64-encoded ciphertext)
string rsaEncrypt(const string& plaintext, const string& pubFile);

// Load private key from file and decrypt Base64-encoded ciphertext
string rsaDecrypt(const string& ciphertext, const string& privFile);

// Read any key file (public or private) and encode as Base64 string for transmission
string getKeyAsString(const string& keyFile);

// Decode Base64 string and save as key file (public or private)
void saveKeyFromString(const string& keyStr, const string& keyFile);


#endif // RSA_H