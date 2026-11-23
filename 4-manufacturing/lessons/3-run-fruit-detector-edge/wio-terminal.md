# Classify an image using an IoT Edge based image classifier - Wio Terminal

In this part of the lesson, you will use the Image Classifier running on the IoT Edge device.

## Use the IoT Edge classifier

The IoT device can be re-directed to use the IoT Edge image classifier. The URL for the Image Classifier is `https://<IP address or name>/image`, replacing `<IP address or name>` with the IP address or host name of the computer running IoT Edge. This needs to be the same IP address or host name that you used when you created the certificate for the classifier.

### Task - use the IoT Edge classifier

1. Open the `fruit-quality-detector` app project if it's not already open.

1. The image classifier is running as a REST API using HTTPS with the certificate you created on the IoT Edge device, so the WiFi client needs to trust this certificate instead of the Microsoft Azure certificate. Replace the `CERTIFICATE` in the `config.h` file with the certificate you copied from the IoT Edge device. Each line of the certificate needs to be wrapped in quotes and end with `\r\n`, the same as the existing certificate:

    ```cpp
    // Certificate of the IoT Edge image classifier
    const char *CERTIFICATE =
        "-----BEGIN CERTIFICATE-----\r\n"
        "<first line of the certificate>\r\n"
        ...
        "<last line of the certificate>\r\n"
        "-----END CERTIFICATE-----\r\n";
    ```

    > 💁 You can create these lines by running `awk '{ printf "    \"%s\\r\\n\"\n", $0 }' /etc/fruit-classifier/tls/classifier.crt` on the IoT Edge device.

1. The prediction URL in the `config.h` file needs to be updated to the new URL. You can also delete the `PREDICTION_KEY` as this is not needed.

    ```cpp
    const char *PREDICTION_URL = "<URL>";
    ```

    Replace `<URL>` with the URL for your classifier. This must start with `https://`.

1. In `main.cpp`, keep the include directive for the WiFi Client Secure, and the declaration of `WiFiClientSecure`, so that the image is encrypted when it is sent:

    ```cpp
    #include <WiFiClientSecure.h>
    ```

    ```cpp
    WiFiClientSecure client;
    ```

1. Keep the line `client.setCACert(CERTIFICATE);` in the `connectWiFi` function. This means the Wio Terminal will only send the image to a server that has your classifier's certificate.

1. In the `classifyImage` function, remove the `httpClient.addHeader("Prediction-Key", PREDICTION_KEY);` line that sets the prediction key in the header.

1. At the start of the `classifyImage` function, add the following code to stop the image being sent if the URL is not HTTPS:

    ```cpp
    if (strncmp(PREDICTION_URL, "https://", 8) != 0)
    {
        Serial.println("PREDICTION_URL must start with https://, not sending the image");
        return;
    }
    ```

1. Upload and run your code. Point the camera at some fruit and press the C button. You will see the output in the serial monitor:

    ```output
    Connecting to WiFi..
    Connected!
    Image captured
    Image read to buffer with length 8200
    ripe:   56.84%
    unripe: 43.16%
    ```

> 💁 You can find this code in the [code-classify/wio-terminal](code-classify/wio-terminal) folder.

😀 Your fruit quality classifier program was a success!
