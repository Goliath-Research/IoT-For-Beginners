#pragma once

#include "WiFiClient.h"

/* The edge sketch does not construct this type. HTTPClient.cpp still references it from the unused TLS helper. */
class WiFiClientSecure : public WiFiClient {
  public:
    void setCACert(const char *) {}
    void setCertificate(const char *) {}
    void setPrivateKey(const char *) {}
};
