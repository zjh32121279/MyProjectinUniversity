#pragma once
// box.h
// DES encryption algorithm permutation tables and S-box constants

#ifndef BOX_H
#define BOX_H

// Initial Permutation (IP)
extern const int IP[64];

// Inverse Initial Permutation (IP^-1)
extern const int IP_INV[64];

// Expansion Permutation (E)
extern const int E[48];

// Permutation function (P)
extern const int P[32];

// Permuted Choice 1 (PC-1) - 64-bit key to 56 bits
extern const int PC1[56];

// Permuted Choice 2 (PC-2) - 56-bit key to 48-bit subkey
extern const int PC2[48];

// Number of left shifts per round
extern const int SHIFT_BITS[16];

// S-boxes - 8 S-boxes, each is a 4x16 matrix
extern const int S_BOX[8][4][16];

#endif // BOX_H
