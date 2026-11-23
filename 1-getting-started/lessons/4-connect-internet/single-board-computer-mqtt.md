# Control your nightlight over the Internet - Virtual IoT Hardware and Raspberry Pi

The IoT device needs to be coded to communicate with your MQTT broker using MQTT to send telemetry values with the light sensor reading, and receive commands to control the LED.

In this part of the lesson, you will connect your Raspberry Pi or virtual IoT device to an MQTT broker.

## Install the MQTT client package

To communicate with the MQTT broker, you need to install an MQTT library pip package either on your Pi, or in your virtual environment if you are using a virtual device.

### Task

Install the pip package

1. Open the nightlight project in VS Code.

1. If you are using a virtual IoT device, ensure the terminal is running the virtual environment. If you are using a Raspberry Pi you won't be using a virtual environment.

1. Run the following command to install the MQTT pip package:

    ```sh
    pip3 install paho-mqtt
    ```

## Code the device

The device is ready to code.

### Task

Write the device code.

1. Add the following imports to the top of the `app.py` file:

    ```python
    import os
    import paho.mqtt.client as mqtt
    ```

    The `paho.mqtt.client` library allows your app to communicate over MQTT. The `os` module is used to read the broker details from environment variables.

1. Add the following code after the definitions of the light sensor and LED:

    ```python
    id = '<ID>'

    client_name = id + 'nightlight_client'
    ```

    Replace `<ID>` with the unique ID you used when [setting up your MQTT broker](README.md#task---set-up-your-mqtt-broker). It will be used as the name of this device client, and later for the topics that this device publishes and subscribes to. You will also need this ID when you are creating the server code later in this assignment.

    The `client_name` is a unique name for this MQTT client on the broker.

1. Add the following code below this new code to create an MQTT client object and connect to the MQTT broker:

    ```python
    mqtt_client = mqtt.Client(client_name)
    mqtt_client.username_pw_set(os.environ['MQTT_USERNAME'], os.environ['MQTT_PASSWORD'])
    mqtt_client.tls_set(ca_certs=os.environ.get('MQTT_CA_CERTS'))
    mqtt_client.connect(os.environ['MQTT_BROKER'], 8883)
    
    mqtt_client.loop_start()

    print("MQTT connected!")
    ```

    This code creates the client object, sets the username and password the device logs in with, and turns on TLS so the connection is encrypted and the broker's certificate is checked against your CA. It then connects to your MQTT broker on port 8883, and starts a processing loop that runs in a background thread listening for messages on any subscribed topics.

1. Set the `MQTT_BROKER`, `MQTT_USERNAME`, `MQTT_PASSWORD` and `MQTT_CA_CERTS` environment variables for the `<ID>-device` user in your terminal. For example, on macOS, Linux or a Raspberry Pi:

    ```sh
    export MQTT_BROKER=<BROKER>
    export MQTT_USERNAME=<ID>-device
    export MQTT_CA_CERTS=/path/to/ca.crt
    read -s -p "MQTT password: " MQTT_PASSWORD && export MQTT_PASSWORD
    ```

1. Run the code in the same way as you ran the code from the previous part of the assignment. If you are using a virtual IoT device, then make sure the CounterFit app is running and the light sensor and LED have been created on the correct pins.

    ```output
    (.venv) ➜  nightlight python app.py 
    MQTT connected!
    Light level: 0
    Light level: 0
    ```

> 💁 You can find this code in the [code-mqtt/virtual-device](code-mqtt/virtual-device) folder or the [code-mqtt/pi](code-mqtt/pi) folder.

😀 You have successfully connected your device to an MQTT broker.
