/*
 * Calls classifyImage in src/main.cpp. The response body is parsed by
 * Seeed Arduino rpcWiFi 1.0.5 HTTPClient and ArduinoJson 6.17.3.
 *
 * Same unbounded sprintf of tagName, not covered here:
 *   4-manufacturing/lessons/2-check-fruit-from-device/code-classify/wio-terminal/fruit-quality-detector/src/main.cpp
 *   5-retail/lessons/2-check-stock-device/code-detect/wio-terminal/stock-counter/src/main.cpp
 *   5-retail/lessons/2-check-stock-device/code-count/wio-terminal/stock-counter/src/main.cpp
 * Those sketches use WiFiClientSecure and a prediction key. This file tests the
 * edge sketch, which the lesson configures as plain HTTP.
 */
#include "Arduino.h"
#include "exchange.h"

#include <ArduinoJson.h>

#include <iostream>
#include <string>

void classifyImage(byte *buffer, uint32_t length);

static const char kCanonicalSuffix[] = ":\t50.00%";

static std::string predictions_json(const std::string &first_tag, const std::string &second_tag) {
    std::string json = std::string("{\"predictions\":[{\"tagName\":\"") + first_tag +
                       "\",\"probability\":0.5}";
    if (!second_tag.empty()) {
        json += std::string(",{\"tagName\":\"") + second_tag + "\",\"probability\":0.5}";
    }
    json += "]}";
    return json;
}

static std::string http_response(int code, const std::string &body) {
    std::string reason = (code == 200) ? "OK" : "ERR";
    return std::string("HTTP/1.1 ") + std::to_string(code) + " " + reason +
           "\r\nContent-Type: application/json\r\nContent-Length: " + std::to_string(body.size()) +
           "\r\nConnection: close\r\n\r\n" + body;
}

static std::string first_line(const std::string &serial) {
    std::string line = serial;
    size_t end = line.find_first_of("\r\n");
    if (end != std::string::npos) {
        line.resize(end);
    }
    return line;
}

/* Same document the sketch allocates. Returns false when ArduinoJson drops the tag. */
static bool tag_survives_document(const std::string &json, const std::string &tag) {
    DynamicJsonDocument doc(1024);
    DeserializationError err = deserializeJson(doc, json.c_str());
    if (err) {
        return false;
    }
    JsonArray predictions = doc.as<JsonObject>()["predictions"].as<JsonArray>();
    if (predictions.size() == 0) {
        return false;
    }
    const char *parsed = predictions[predictions.size() - 1]["tagName"];
    return parsed != nullptr && tag == parsed;
}

static void require(bool cond, const char *message) {
    if (!cond) {
        std::cerr << message << "\nserial=[" << g_serial << "]\nhost=" << g_exchange.host
                  << " port=" << g_exchange.port << "\nrequest=[" << g_exchange.request << "]\n";
        std::exit(1);
    }
}

static void classify(const std::string &body, int code) {
    test_queue_response(http_response(code, body));
    byte image[] = {0xff, 0xd8, 0xff, 0xd9};
    classifyImage(image, sizeof(image));
}

static void expect_http_post_to_lesson_url() {
    require(g_exchange.connects == 1, "classifier did not open a TCP connection");
    require(g_exchange.host == "192.0.2.10", "classifier did not use the lesson host");
    require(g_exchange.port == 80, "classifier did not use the HTTP port from the lesson URL");
    require(g_exchange.request.find("POST /image HTTP/1.1\r\n") == 0, "classifier did not POST /image");
    require(g_exchange.request.find("Content-Type: application/octet-stream\r\n") != std::string::npos,
            "classifier did not send the image content type");
    require(g_exchange.request.find(std::string("\r\n\r\n\xff\xd8\xff\xd9", 8)) != std::string::npos,
            "classifier did not send the captured image as the POST body");
}

/*
 * A bounded print is either the whole formatted label or a prefix of it.
 * Printing the Arduino String directly includes the whole tag.
 */
static void expect_bounded_label(const std::string &tag) {
    std::string full = tag + kCanonicalSuffix;
    std::string line = first_line(g_serial);
    bool prefix = !line.empty() && full.compare(0, line.size(), line) == 0;
    bool direct = line.find(tag) != std::string::npos;
    require(prefix || direct, "label was not printed as a bounded formatter result or as the full tag");
}

static void test_short_label() {
    const std::string tag = "ripe";
    std::string json = predictions_json(tag, "");
    require(tag_survives_document(json, tag), "short label did not round-trip through ArduinoJson");
    classify(json, 200);
    expect_http_post_to_lesson_url();
    std::string line = first_line(g_serial);
    require(line == tag + kCanonicalSuffix, "short label was not formatted into the serial line");
}

static void test_long_label(const std::string &tag, const std::string &leading) {
    std::string json = predictions_json(leading.empty() ? tag : leading, leading.empty() ? "" : tag);
    require(tag_survives_document(json, tag), "long label does not fit in the 1024-byte JSON document");
    classify(json, 200);
    expect_http_post_to_lesson_url();
    if (!leading.empty()) {
        std::string first = first_line(g_serial);
        require(first == leading + kCanonicalSuffix, "first short label was not printed");
        size_t nl = g_serial.find('\n');
        require(nl != std::string::npos, "second prediction was not printed");
        g_serial = g_serial.substr(nl + 1);
    }
    expect_bounded_label(tag);
}

static void test_http_error_is_ignored() {
    std::string tag(48, 'B');
    classify(predictions_json(tag, ""), 500);
    expect_http_post_to_lesson_url();
    require(g_serial.empty(), "a non-200 response was still printed");
}

int main(int argc, char **argv) {
    if (argc != 2) {
        std::cerr << "usage: classify_tests <short_label|long_label|second_prediction|http_error>\n";
        return 2;
    }
    std::string name = argv[1];
    if (name == "short_label") {
        test_short_label();
    } else if (name == "long_label") {
        test_long_label(std::string(48, 'A'), "");
    } else if (name == "second_prediction") {
        test_long_label(std::string(48, 'C'), "unripe");
    } else if (name == "http_error") {
        test_http_error_is_ignored();
    } else if (name == "long_label_fits_document") {
        /* Longer than a small stack bump, still inside DynamicJsonDocument(1024). */
        std::string tag(200, 'D');
        test_long_label(tag, "");
    } else {
        std::cerr << "unknown test " << name << "\n";
        return 2;
    }
    return 0;
}
