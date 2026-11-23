import json
import os
import time

import paho.mqtt.client as mqtt

id = '<ID>'

client_telemetry_topic = id + '/telemetry'
server_command_topic = id + '/commands'
client_name = id + 'nightlight_server'

mqtt_client = mqtt.Client(client_name)
mqtt_client.username_pw_set(os.environ['MQTT_USERNAME'], os.environ['MQTT_PASSWORD'])
mqtt_client.tls_set(ca_certs=os.environ.get('MQTT_CA_CERTS'))
mqtt_client.connect(os.environ['MQTT_BROKER'], 8883)

mqtt_client.loop_start()

def handle_telemetry(client, userdata, message):
    payload = json.loads(message.payload.decode())
    print("Message received:", payload)

    command = { 'led_on' : payload['light'] < 300 }
    print("Sending message:", command)

    client.publish(server_command_topic, json.dumps(command))

mqtt_client.subscribe(client_telemetry_topic)
mqtt_client.on_message = handle_telemetry

while True:
    time.sleep(2)