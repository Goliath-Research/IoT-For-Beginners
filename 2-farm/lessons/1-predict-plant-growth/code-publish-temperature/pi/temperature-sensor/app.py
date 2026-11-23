import time
from seeed_dht import DHT
import os
import paho.mqtt.client as mqtt
import json

sensor = DHT("11", 5)

id = '<ID>'

client_telemetry_topic = id + '/telemetry'
client_name = id + 'temperature_sensor_client'

mqtt_client = mqtt.Client(client_name)
mqtt_client.username_pw_set(os.environ['MQTT_USERNAME'], os.environ['MQTT_PASSWORD'])
mqtt_client.tls_set(ca_certs=os.environ.get('MQTT_CA_CERTS'))
mqtt_client.connect(os.environ['MQTT_BROKER'], 8883)

mqtt_client.loop_start()

print("MQTT connected!")

while True:
    _, temp = sensor.read()
    telemetry = json.dumps({'temperature' : temp})

    print("Sending telemetry ", telemetry)

    mqtt_client.publish(client_telemetry_topic, telemetry)

    time.sleep(10 * 60)
