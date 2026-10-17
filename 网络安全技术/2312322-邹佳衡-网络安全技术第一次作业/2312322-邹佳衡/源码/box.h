#pragma once
// box.h
// DES加密算法所需的置换盒和S盒常量声明

#ifndef BOX_H
#define BOX_H

// 初始置换 IP (Initial Permutation)
extern const int IP[64];

// 逆初始置换 IP^-1 (Inverse Initial Permutation)
extern const int IP_INV[64];

// 扩展置换 E (Expansion Permutation)
extern const int E[48];

// 置换运算 P (Permutation)
extern const int P[32];

// 密钥置换 PC-1 (Permuted Choice 1) - 64位密钥转56位
extern const int PC1[56];

// 密钥置换 PC-2 (Permuted Choice 2) - 56位密钥转48位子密钥
extern const int PC2[48];

// 每轮左移位数
extern const int SHIFT_BITS[16];

// S盒 (S-boxes) - 8个S盒，每个是4x16的矩阵
extern const int S_BOX[8][4][16];

#endif // BOX_H