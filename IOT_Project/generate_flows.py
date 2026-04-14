import json
import os

def generate_nodered_flow(floor_idx):
    # This generates a basic Node-RED flow template for a floor gateway
    # It demonstrates the MQTT subscription, edge thinning, and CoAP structural needs.
    f_str = f"f{floor_idx:02d}"
    
    nodes = [
        {
            "id": f"mqtt-broker-{f_str}",
            "type": "mqtt-broker",
            "name": "HiveMQ Backbone",
            "broker": "hivemq",
            "port": "1883",
            "clientid": f"gateway-{f_str}",
            "usetls": False,
            "keepalive": "60",
            "cleansession": True,
        },
        {
            "id": f"mqtt-sub-{f_str}",
            "type": "mqtt in",
            "name": f"Floor {f_str} Telemetry",
            "topic": f"campus/b01/{f_str}/+/telemetry",
            "qos": "0",
            "datatype": "json",
            "broker": f"mqtt-broker-{f_str}",
            "x": 150, "y": 100, "wires": [[f"edge-thinning-{f_str}"]]
        },
        {
            "id": f"edge-thinning-{f_str}",
            "type": "function",
            "name": "60s Average Thinning",
            "func": "// Averages data over 60 seconds (Mock)\nvar count = context.get('count') || 0;\nvar sum = context.get('sum') || 0;\nsum += msg.payload.sensors.temperature;\ncount += 1;\nif (count >= 60) {\n  var avg = sum/count;\n  context.set('count', 0);\n  context.set('sum', 0);\n  return {payload: {floor_avg_temp: avg}};\n}\nreturn null;",
            "x": 400, "y": 100, "wires": [[f"mqtt-pub-summary-{f_str}"]]
        },
        {
            "id": f"mqtt-pub-summary-{f_str}",
            "type": "mqtt out",
            "name": "Publish Summary",
            "topic": f"campus/b01/{f_str}/summary",
            "qos": "0",
            "retain": "",
            "broker": f"mqtt-broker-{f_str}",
            "x": 650, "y": 100, "wires": []
        },
        {
            "id": f"coap-req-{f_str}",
            "type": "coap request",
            "name": "CoAP Observer (Example)",
            "method": "GET",
            "observe": True,
            "url": "coap://host.docker.internal:50111/f01/r011/telemetry",
            "content-format": "application/json",
            "x": 150, "y": 200, "wires": [[f"mqtt-pub-coap-translate-{f_str}"]]
        },
        {
            "id": f"mqtt-pub-coap-translate-{f_str}",
            "type": "mqtt out",
            "name": "CoAP -> MQTT Bridge",
            "topic": f"campus/b01/{f_str}/r011/telemetry",
            "qos": "0",
            "retain": "",
            "broker": f"mqtt-broker-{f_str}",
            "x": 400, "y": 200, "wires": []
        }
    ]
    return nodes

def main():
    os.makedirs("flows", exist_ok=True)
    for i in range(1, 11):
        floor_dir = f"flows/f{i:02d}"
        os.makedirs(floor_dir, exist_ok=True)
        flow_data = generate_nodered_flow(i)
        with open(f"{floor_dir}/flows.json", "w") as f:
            json.dump(flow_data, f, indent=2)
    print("Node-RED flows generated. Mount these via Docker Compose.")

if __name__ == "__main__":
    main()
