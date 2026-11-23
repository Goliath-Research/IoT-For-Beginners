#pragma once

#ifdef __cplusplus
extern "C" {
#endif

char *itoa(int value, char *string, int radix);
char *ltoa(long value, char *string, int radix);
char *utoa(unsigned int value, char *string, int radix);
char *ultoa(unsigned long value, char *string, int radix);

#ifdef __cplusplus
}
#endif
