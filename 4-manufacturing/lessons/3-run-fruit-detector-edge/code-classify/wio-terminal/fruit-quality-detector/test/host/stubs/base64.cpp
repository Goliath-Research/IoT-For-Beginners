#include "base64.h"

#include <stdio.h>
#include <stdlib.h>

String base64::encode(const uint8_t *, size_t) {
    fprintf(stderr, "base64::encode was called; the edge classifier URL has no userinfo\n");
    abort();
}

String base64::encode(const String &) {
    fprintf(stderr, "base64::encode was called; the edge classifier URL has no userinfo\n");
    abort();
}
