import network
import time
import json
from machine import Pin
from dht import DHT22
from umqtt.simple import MQTTClient

SSID = "Wokwi-GUEST"
PASSWORD = ""

MQTT_BROKER = "test.mosquitto.org"
CLIENT_ID = "esp32_room_001"
TOPIC = "campus/bldg_01/floor_01/room_001/telemetry"

# Pin Setup
dht = DHT22(Pin(4))          
pir = Pin(13, Pin.IN)        
led = Pin(15, Pin.OUT)       

# WiFi Connection
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)

    while not wlan.isconnected():
        print("Connecting to WiFi...")
        time.sleep(1)

    print("WiFi Connected:", wlan.ifconfig())

# MQTT partt
def connect_mqtt():
    while True:
        try:
            client = MQTTClient(
                CLIENT_ID,
                MQTT_BROKER,
                port=1883,
                keepalive=60
            )
            client.connect()
            print("Connected to MQTT Broker")
            return client
        except Exception as e:
            print("MQTT connection failed:", e)
            print("Retrying in 3 seconds...")
            time.sleep(3)

# Read Sensors
def read_sensors():
    dht.measure()
    
    temperature = dht.temperature()
    humidity = dht.humidity()
    motion = pir.value()

    # LED reflects motion
    led.value(motion)

    # Light simulation
    light = 600 if motion else 50

    data = {
        "sensor_id": "b01-f01-r001",
        "timestamp": int(time.time()),
        "temperature": temperature,
        "humidity": humidity,
        "occupancy": bool(motion),
        "light_level": light,
        "hvac_mode": "OFF",
        "lighting_dimmer": int(light / 10)
    }

    return data

# Validation
def validate(data):
    if not (15 <= data["temperature"] <= 50):
        return False
    if not (0 <= data["humidity"] <= 100):
        return False
    return True

def main():
    connect_wifi()
    client = connect_mqtt()

    while True:
        try:
            data = read_sensors()

            if validate(data):
                payload = json.dumps(data)

                try:
                    client.publish(TOPIC, payload)
                    print("Published:", payload)
                except Exception as e:
                    print("Publish failed:", e)
                    print("Reconnecting MQTT...")
                    client = connect_mqtt()
            else:
                print("Invalid sensor data")

        except Exception as e:
            print("Sensor error:", e)

        time.sleep(5)


main()