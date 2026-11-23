#pragma once

#include <string>

using namespace std;

// WiFi credentials
const char *SSID = "<SSID>";
const char *PASSWORD = "<PASSWORD>";

// Must be the https:// address of the classifier, for example https://<IP address or name>/image
const char *PREDICTION_URL = "<PREDICTION_URL>";

// Certificate of the IoT Edge image classifier, from /etc/fruit-classifier/tls/classifier.crt on the IoT Edge device
const char *CERTIFICATE =
    "-----BEGIN CERTIFICATE-----\r\n"
    "<CERTIFICATE>\r\n"
    "-----END CERTIFICATE-----\r\n";
