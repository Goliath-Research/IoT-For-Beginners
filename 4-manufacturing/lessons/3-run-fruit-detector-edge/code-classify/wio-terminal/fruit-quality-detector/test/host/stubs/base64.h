#pragma once

#include "WString.h"

/* Present because HTTPClient.cpp links base64::encode. The edge URL has no userinfo, so encode is not on the request path. */
class base64 {
  public:
    static String encode(const uint8_t *data, size_t length);
    static String encode(const String &text);
};
