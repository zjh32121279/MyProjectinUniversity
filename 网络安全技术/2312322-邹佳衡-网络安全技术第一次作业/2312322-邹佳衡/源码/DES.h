// DES.h
// DES加密算法头文件

#ifndef DES_H
#define DES_H

#include <bitset>
#include <string>
#include <vector>

using namespace std;

// 获取全局加密密钥
string getEncryptionKey();

// 辅助函数：字符串与bitset之间的转换
bitset<64> stringToBitset(const string& data);
string bitsetToString(const bitset<64>& bits);

// IP置换函数
bitset<64> ipPermutation(const bitset<64>& input);

// 逆IP置换函数
bitset<64> ipInvPermutation(const bitset<64>& input);

// F函数
bitset<32> feistelFunction(const bitset<32>& right, const bitset<48>& subKey);

// 子密钥生成函数
vector<bitset<48>> generateSubKeys(const bitset<64>& key);

// 单轮Feistel变换
bitset<64> feistelRound(const bitset<64>& input, const bitset<48>& subKey);

// 完整加密函数
bitset<64> desEncryptBlock(const bitset<64>& plaintext, const bitset<64>& key);

// 完整解密函数
bitset<64> desDecryptBlock(const bitset<64>& ciphertext, const bitset<64>& key);

// 字符串加密函数（支持任意长度）
string desEncryptString(const string& plaintext, const string& key);

// 字符串解密函数（支持任意长度）
string desDecryptString(const string& ciphertext, const string& key);

#endif // DES_H