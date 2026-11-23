#pragma once

#include <stdint.h>
#include <string.h>

#define PSTR(s) (s)
typedef const char *PGM_P;

#define strcpy_P(dest, src) strcpy((dest), (src))
#define strlen_P(src) strlen((src))
#define memcpy_P(dest, src, n) memcpy((dest), (src), (n))
#define pgm_read_byte(addr) (*(const uint8_t *)(addr))
#define pgm_read_dword(addr) (*(const uint32_t *)(addr))
#define pgm_read_ptr(addr) (*(const void *const *)(addr))
#define pgm_read_float(addr) (*(const float *)(addr))
