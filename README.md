# IoT Reference Room – Wokwi Simulation

## Overview

This project simulates a single IoT-enabled room using an ESP32 in Wokwi.
It serves as a **Proof of Concept (POC)** for the larger distributed campus system in Phase 1.

The system reads environmental data, processes it, and publishes telemetry to an MQTT broker.

---

## Components Used

* ESP32 Microcontroller
* DHT22 Temperature & Humidity Sensor
* PIR Motion Sensor
* LED (status indicator)

---

## Pin Configuration

| Component  | ESP32 Pin |
| ---------- | --------- |
| DHT22 DATA | GPIO 4    |
| PIR OUT    | GPIO 13   |
| LED        | GPIO 15   |
| DHT22 VCC  | 3.3V      |
| PIR VCC    | VIN (5V)  |
| GND        | GND       |

---

## Features

* Reads temperature and humidity from DHT22
* Detects occupancy using PIR sensor
* Simulates ambient light based on motion
* Publishes structured JSON telemetry via MQTT
* Validates sensor data before publishing
* LED indicates motion detection

---

## Telemetry Format (JSON)

```json
{
  "sensor_id": "b01-f01-r001",
  "timestamp": 1700000000,
  "temperature": 24.5,
  "humidity": 55,
  "occupancy": true,
  "light_level": 600,
  "hvac_mode": "OFF",
  "lighting_dimmer": 60
}
```

---

## MQTT Configuration

* Broker: `test.mosquitto.org`
* Topic:

```
campus/bldg_01/floor_01/room_001/telemetry
```

---

## How to Run

1. Open the project in Wokwi
2. Start the simulation
3. Monitor output in the serial console
4. Subscribe to the MQTT topic using an MQTT client

---

## Notes

* MQTT connection may occasionally timeout due to Wokwi network limitations
* The system automatically retries connection if it fails
* This implementation is a prototype for scaling to 200 simulated rooms in Phase 1

---

## Future Work

* Add MQTT command handling (actuator control)
* Integrate with Python asyncio simulation engine
* Expand to full campus-scale simulation

---
