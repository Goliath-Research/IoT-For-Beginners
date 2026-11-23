#include "itoa.h"

#include <stdio.h>

static char *format_signed(long value, char *string, int radix) {
    if (radix == 16) {
        sprintf(string, "%lx", (unsigned long)value);
    } else {
        sprintf(string, "%ld", value);
    }
    return string;
}

static char *format_unsigned(unsigned long value, char *string, int radix) {
    if (radix == 16) {
        sprintf(string, "%lx", value);
    } else {
        sprintf(string, "%lu", value);
    }
    return string;
}

char *itoa(int value, char *string, int radix) {
    return format_signed(value, string, radix);
}

char *ltoa(long value, char *string, int radix) {
    return format_signed(value, string, radix);
}

char *utoa(unsigned int value, char *string, int radix) {
    return format_unsigned(value, string, radix);
}

char *ultoa(unsigned long value, char *string, int radix) {
    return format_unsigned(value, string, radix);
}
