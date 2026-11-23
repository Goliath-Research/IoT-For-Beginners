#pragma once

#include <string>

using namespace std;

// WiFi credentials
const char *SSID = "<SSID>";
const char *PASSWORD = "<PASSWORD>";

// MQTT settings
const string ID = "<ID>";

const string BROKER = "<BROKER>";
const int BROKER_PORT = 8883;

// MQTT credentials for this device, issued by your broker
const char *MQTT_USERNAME = "<MQTT_USERNAME>";
const char *MQTT_PASSWORD = "<MQTT_PASSWORD>";

// Certificate of the CA that signed your broker's TLS certificate
const char *BROKER_CA_CERTIFICATE =
    "-----BEGIN CERTIFICATE-----\r\n"
    "<CA_CERTIFICATE>\r\n"
    "-----END CERTIFICATE-----\r\n";

const string CLIENT_NAME = ID + "nightlight_client";

const string CLIENT_TELEMETRY_TOPIC = ID + "/telemetry";