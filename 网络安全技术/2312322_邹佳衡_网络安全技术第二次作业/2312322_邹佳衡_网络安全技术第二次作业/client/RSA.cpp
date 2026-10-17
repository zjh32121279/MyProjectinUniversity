#include "RSA.h"
#include <cryptopp/rsa.h>
#include <cryptopp/osrng.h>
#include <cryptopp/filters.h>
#include <cryptopp/files.h>
// Base64 encoder/decoder
#include <cryptopp/base64.h>

using namespace std;
using namespace CryptoPP;

// Generate RSA key pair and save to files
void generateRSAKeys(unsigned int keyLength, const string& pubFile, const string& privFile) {
    AutoSeededRandomPool rng;
    InvertibleRSAFunction params;
    params.GenerateRandomWithKeySize(rng, keyLength);

    RSA::PrivateKey privateKey(params);
    RSA::PublicKey publicKey(params);

    // Create named FileSink variables before passing to Save
    FileSink privSink(privFile.c_str());
    privateKey.Save(privSink);

    FileSink pubSink(pubFile.c_str());
    publicKey.Save(pubSink);
}

// RSA encryption: returns Base64-encoded ciphertext string
string rsaEncrypt(const string& plaintext, const string& pubFile) {
    AutoSeededRandomPool rng;
    RSA::PublicKey publicKey;

    // Create named FileSource variable before calling Load
    FileSource fs(pubFile.c_str(), true);
    publicKey.Load(fs);

    string ciphertext;
    RSAES_OAEP_SHA_Encryptor encryptor(publicKey);

    StringSource ss(plaintext, true,
        new PK_EncryptorFilter(rng, encryptor,
            new StringSink(ciphertext)
        )
    );
    // Base64-encode the ciphertext for safe network transmission
    string encoded;
    StringSource ss_encode(ciphertext, true,
        new Base64Encoder(new StringSink(encoded))
    );
    return encoded;
}

// RSA decryption: accepts Base64-encoded ciphertext string, returns plaintext
string rsaDecrypt(const string& encoded_ciphertext, const string& privFile) {
    AutoSeededRandomPool rng;
    RSA::PrivateKey privateKey;

    // Create named FileSource variable before calling Load
    FileSource fs(privFile.c_str(), true);
    privateKey.Load(fs);

    string ciphertext;
    StringSource ss_decode(encoded_ciphertext, true,
        new Base64Decoder(new StringSink(ciphertext))
    );

    string decryptedtext;
    RSAES_OAEP_SHA_Decryptor decryptor(privateKey);

    StringSource ss(ciphertext, true,
        new PK_DecryptorFilter(rng, decryptor,
            new StringSink(decryptedtext)
        )
    );
    return decryptedtext;
}

// Generic: convert any key file (public or private) to Base64 string for transmission
string getKeyAsString(const string& keyFile) {
    string binaryKey, base64Key;

    // 1. Read raw binary data from file
    FileSource fs(keyFile.c_str(), true, new StringSink(binaryKey));

    // 2. Base64 encode
    StringSource ss(binaryKey, true, new Base64Encoder(new StringSink(base64Key)));

    return base64Key;
}

// Generic: decode Base64 string and save as key file (public or private)
void saveKeyFromString(const string& keyStr, const string& keyFile) {
    string decodedKey;

    // 1. Base64 decode
    StringSource ss(keyStr, true, new Base64Decoder(new StringSink(decodedKey)));

    // 2. Write decoded binary data to file
    FileSink fs(keyFile.c_str());
    fs.Put((const byte*)decodedKey.data(), decodedKey.size());
    fs.MessageEnd(); // Ensure data is flushed to disk
}
