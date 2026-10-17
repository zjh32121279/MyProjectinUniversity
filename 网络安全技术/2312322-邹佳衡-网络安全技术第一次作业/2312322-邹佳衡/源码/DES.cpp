// DES.cpp
// DES加密算法实现

#include "DES.h"
#include "box.h"
#include <iostream>
#include <cstring>
#include <vector>

using namespace std;

// ========== 全局加密密钥（统一在这里设置）==========
// 所有客户端和服务器都使用这个密钥
static const string GLOBAL_ENCRYPTION_KEY = "12345678";  // 修改这里可以改变密钥

// 获取全局加密密钥
string getEncryptionKey() {
    return GLOBAL_ENCRYPTION_KEY;
}

// 辅助函数：将8字节字符串转换为64位bitset
bitset<64> stringToBitset(const string& data) {
    bitset<64> bits;
    for (int i = 0; i < 8 && i < data.length(); i++) {
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

// 辅助函数：将64位bitset转换为8字节字符串
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

// IP置换函数
bitset<64> ipPermutation(const bitset<64>& input) {
    bitset<64> output;

    for (int i = 0; i < 64; i++) {
        int sourceBitIndex = 64 - IP[i];
        output[63 - i] = input[sourceBitIndex];
    }

    return output;
}

// 扩展置换函数（内部使用）
bitset<48> expansionPermutation(const bitset<32>& input) {
    bitset<48> output;

    for (int i = 0; i < 48; i++) {
        int sourceBitIndex = 32 - E[i];
        output[47 - i] = input[sourceBitIndex];
    }

    return output;
}

// S盒替换函数（内部使用）
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

// P盒置换函数（内部使用）
bitset<32> pPermutation(const bitset<32>& input) {
    bitset<32> output;

    for (int i = 0; i < 32; i++) {
        int sourceBitIndex = 32 - P[i];
        output[31 - i] = input[sourceBitIndex];
    }

    return output;
}

// F函数
bitset<32> feistelFunction(const bitset<32>& right, const bitset<48>& subKey) {
    bitset<48> expandedRight = expansionPermutation(right);
    bitset<48> xorResult = expandedRight ^ subKey;
    bitset<32> sboxResult = sBoxSubstitution(xorResult);
    bitset<32> output = pPermutation(sboxResult);

    return output;
}

// PC-1置换：将64位密钥转换为56位
bitset<56> pc1Permutation(const bitset<64>& key) {
    bitset<56> output;

    for (int i = 0; i < 56; i++) {
        int sourceBitIndex = 64 - PC1[i];
        output[55 - i] = key[sourceBitIndex];
    }

    return output;
}

// PC-2置换：将56位密钥转换为48位子密钥
bitset<48> pc2Permutation(const bitset<56>& input) {
    bitset<48> output;

    for (int i = 0; i < 48; i++) {
        int sourceBitIndex = 56 - PC2[i];
        output[47 - i] = input[sourceBitIndex];
    }

    return output;
}

// 循环左移函数
bitset<28> leftShift(const bitset<28>& input, int shift) {
    bitset<28> output;

    for (int i = 0; i < 28; i++) {
        int newPos = (i + shift) % 28;
        output[27 - newPos] = input[27 - i];
    }

    return output;
}

// 生成16轮子密钥
vector<bitset<48>> generateSubKeys(const bitset<64>& key) {
    vector<bitset<48>> subKeys(16);

    // 1. PC-1置换：64位 -> 56位
    bitset<56> permutedKey = pc1Permutation(key);

    // 2. 分成左右两半，各28位
    bitset<28> leftHalf;
    bitset<28> rightHalf;

    for (int i = 0; i < 28; i++) {
        leftHalf[27 - i] = permutedKey[55 - i];
        rightHalf[27 - i] = permutedKey[27 - i];
    }

    // 3. 生成16轮子密钥
    for (int round = 0; round < 16; round++) {
        // 循环左移
        leftHalf = leftShift(leftHalf, SHIFT_BITS[round]);
        rightHalf = leftShift(rightHalf, SHIFT_BITS[round]);

        // 合并左右两半
        bitset<56> combined;
        for (int i = 0; i < 28; i++) {
            combined[55 - i] = leftHalf[27 - i];
            combined[27 - i] = rightHalf[27 - i];
        }

        // PC-2置换：56位 -> 48位
        subKeys[round] = pc2Permutation(combined);
    }

    return subKeys;
}

// 逆IP置换函数
// 输入：经过16轮Feistel网络处理后的64位数据
// 输出：经过逆IP置换后的64位数据（最终密文）
bitset<64> ipInvPermutation(const bitset<64>& input) {
    bitset<64> output;

    // 执行逆IP置换
    for (int i = 0; i < 64; i++) {
        // IP_INV[i]的值是从1开始的，对应输入的第IP_INV[i]位
        // 在bitset中，第1位对应索引63
        int sourceBitIndex = 64 - IP_INV[i];
        output[63 - i] = input[sourceBitIndex];
    }

    return output;
}

// 单轮Feistel变换
// 输入：64位数据（左右各32位）
// 输出：经过一轮Feistel变换后的64位数据
bitset<64> feistelRound(const bitset<64>& input, const bitset<48>& subKey) {
    // 分割成左右两半，各32位
    bitset<32> left;
    bitset<32> right;

    // 左半部分：高32位（位63-32）
    for (int i = 0; i < 32; i++) {
        left[31 - i] = input[63 - i];
        right[31 - i] = input[31 - i];
    }

    // 保存旧的右半部分
    bitset<32> oldRight = right;

    // 计算新的右半部分：left XOR F(right, subKey)
    bitset<32> newRight = left ^ feistelFunction(oldRight, subKey);

    // 新的左半部分就是旧的右半部分
    bitset<32> newLeft = oldRight;

    // 合并左右两半
    bitset<64> output;
    for (int i = 0; i < 32; i++) {
        output[63 - i] = newLeft[31 - i];
        output[31 - i] = newRight[31 - i];
    }

    return output;
}

// 完整DES加密函数
// 输入：64位明文块，64位密钥
// 输出：64位密文块
bitset<64> desEncryptBlock(const bitset<64>& plaintext, const bitset<64>& key) {
    // 1. 生成16轮子密钥
    vector<bitset<48>> subKeys = generateSubKeys(key);

    // 2. 初始IP置换
    bitset<64> current = ipPermutation(plaintext);

    // 3. 执行16轮Feistel变换
    for (int round = 0; round < 16; round++) {
        current = feistelRound(current, subKeys[round]);
    }

    // 4. 最后一轮后交换左右两半（因为标准DES最后一轮后不交换）
    bitset<32> left, right;
    for (int i = 0; i < 32; i++) {
        left[31 - i] = current[63 - i];
        right[31 - i] = current[31 - i];
    }

    // 交换左右
    bitset<64> swapped;
    for (int i = 0; i < 32; i++) {
        swapped[63 - i] = right[31 - i];
        swapped[31 - i] = left[31 - i];
    }

    // 5. 逆IP置换
    bitset<64> ciphertext = ipInvPermutation(swapped);

    return ciphertext;
}

// 完整DES解密函数
// 输入：64位密文块，64位密钥
// 输出：64位明文块
bitset<64> desDecryptBlock(const bitset<64>& ciphertext, const bitset<64>& key) {
    // 1. 生成16轮子密钥
    vector<bitset<48>> subKeys = generateSubKeys(key);

    // 2. 初始IP置换
    bitset<64> current = ipPermutation(ciphertext);

    // 3. 执行16轮Feistel变换（使用逆序子密钥）
    for (int round = 0; round < 16; round++) {
        // 解密时使用逆序的子密钥
        current = feistelRound(current, subKeys[15 - round]);
    }

    // 4. 最后一轮后交换左右两半
    bitset<32> left, right;
    for (int i = 0; i < 32; i++) {
        left[31 - i] = current[63 - i];
        right[31 - i] = current[31 - i];
    }

    // 交换左右
    bitset<64> swapped;
    for (int i = 0; i < 32; i++) {
        swapped[63 - i] = right[31 - i];
        swapped[31 - i] = left[31 - i];
    }

    // 5. 逆IP置换
    bitset<64> plaintext = ipInvPermutation(swapped);

    return plaintext;
}

// PKCS#7填充函数
string pkcs7Pad(const string& data) {
    size_t paddingLen = 8 - (data.length() % 8);
    if (paddingLen == 0) paddingLen = 8;

    string padded = data;
    for (size_t i = 0; i < paddingLen; i++) {
        padded += (char)paddingLen;
    }
    return padded;
}

// PKCS#7去除填充
string pkcs7Unpad(const string& data) {
    if (data.empty()) return data;

    size_t paddingLen = (unsigned char)data.back();
    if (paddingLen > 8 || paddingLen > data.length()) {
        return data; // 无效填充，返回原数据
    }

    // 验证填充是否有效
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

// 字符串加密函数
// 输入：任意长度的明文字符串，8字节密钥字符串
// 输出：加密后的字符串（长度是8的倍数）
string desEncryptString(const string& plaintext, const string& key) {
    // 1. 确保密钥是8字节
    string paddedKey = key;
    if (paddedKey.length() < 8) {
        // 如果密钥不足8字节，用0填充
        paddedKey.append(8 - paddedKey.length(), '\0');
    }
    else if (paddedKey.length() > 8) {
        // 如果密钥超过8字节，只取前8字节
        paddedKey = paddedKey.substr(0, 8);
    }

    bitset<64> keyBits = stringToBitset(paddedKey);

    // 2. PKCS#7填充
    string paddedPlaintext = pkcs7Pad(plaintext);

    // 3. 分块加密
    string ciphertext;
    for (size_t i = 0; i < paddedPlaintext.length(); i += 8) {
        string block = paddedPlaintext.substr(i, 8);
        bitset<64> plaintextBits = stringToBitset(block);
        bitset<64> ciphertextBits = desEncryptBlock(plaintextBits, keyBits);
        ciphertext += bitsetToString(ciphertextBits);
    }

    return ciphertext;
}

// 字符串解密函数
// 输入：加密后的字符串（长度是8的倍数），8字节密钥字符串
// 输出：解密后的原始字符串
string desDecryptString(const string& ciphertext, const string& key) {
    // 1. 确保密钥是8字节
    string paddedKey = key;
    if (paddedKey.length() < 8) {
        paddedKey.append(8 - paddedKey.length(), '\0');
    }
    else if (paddedKey.length() > 8) {
        paddedKey = paddedKey.substr(0, 8);
    }

    bitset<64> keyBits = stringToBitset(paddedKey);

    // 2. 检查密文长度是否是8的倍数
    if (ciphertext.length() % 8 != 0) {
        cerr << "错误：密文长度不是8的倍数" << endl;
        return "";
    }

    // 3. 分块解密
    string decrypted;
    for (size_t i = 0; i < ciphertext.length(); i += 8) {
        string block = ciphertext.substr(i, 8);
        bitset<64> ciphertextBits = stringToBitset(block);
        bitset<64> plaintextBits = desDecryptBlock(ciphertextBits, keyBits);
        decrypted += bitsetToString(plaintextBits);
    }

    // 4. 去除PKCS#7填充
    return pkcs7Unpad(decrypted);
}