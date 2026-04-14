import asyncio
import yaml
import time
import json
import random
import ssl
from gmqtt import Client as MQTTClient
from gmqtt.mqtt.constants import MQTT_v311
import aiocoap
import aiocoap.resource as resource
from aiocoap.credentials import CredentialsMap

import database as db
import models as m

class CoAPTelemetryResource(resource.ObservableResource):
    def __init__(self, room):
        super().__init__()
        self.room = room
        self.payload = b"{}"

    def update_state(self, payload_dict):
        self.payload = json.dumps(payload_dict).encode('utf-8')
        self.updated_state() # Notify observers

    async def render_get(self, request):
        return aiocoap.Message(payload=self.payload)

class CoAPActuatorResource(resource.Resource):
    def __init__(self, room):
        super().__init__()
        self.room = room

    async def render_put(self, request):
        try:
            payload = json.loads(request.payload.decode('utf-8'))
            command = payload.get("command")
            ts = payload.get("timestamp")
            
            if ts:
                self.room["last_latency"] = time.time() - ts

            if command in ["ON", "OFF", "ECO"]:
                self.room["m"] = command
                print(f"CoAP {self.room['id']} HVAC set to {command} (Latency: {self.room['last_latency']*1000:.1f}ms)")
                return aiocoap.Message(code=aiocoap.CHANGED)
            return aiocoap.Message(code=aiocoap.BAD_REQUEST)
        except Exception:
            return aiocoap.Message(code=aiocoap.BAD_REQUEST)

async def mqtt_node_task(r, cfg):
    j = random.uniform(0, cfg['simulation'].get('max_jitter', 60))
    await asyncio.sleep(j)

    client_id = f"mqtt_node_{r['id']}"
    client = MQTTClient(client_id)
    
    # Configure TLS
    sc = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile="certs/ca.crt")
    sc.load_cert_chain(certfile="certs/client.crt", keyfile="certs/client.key")
    # In a local test environment with self-signed certs and IP mismatches, 
    # we might need to disable hostname check if not using 'localhost' or 'hivemq'
    sc.check_hostname = False 
    sc.verify_mode = ssl.CERT_REQUIRED

    # Set LWT
    lwt_topic = f"{cfg['mqtt']['base_topic']}/{r['path']}/status"
    client.set_will(lwt_topic, b"offline", qos=1, retain=True)

    def on_message(client, topic, payload, qos, properties):
        try:
            msg = json.loads(payload.decode('utf-8'))
            cmd = msg.get("command")
            ts = msg.get("timestamp")
            
            if ts:
                r["last_latency"] = time.time() - ts

            if cmd in ["ON", "OFF", "ECO"]:
                r["m"] = cmd
                print(f"[MQTT CMD SECURE] Room {r['id']} HVAC set to {cmd} (Latency: {r['last_latency']*1000:.1f}ms)")
        except Exception as e:
            pass
        return aiocoap.CHANGED

    client.on_message = on_message

    while True:
        try:
            # Connect to TLS port 8883
            await client.connect(cfg['mqtt']['broker'], port=8883, ssl=sc, version=MQTT_v311)
            client.publish(lwt_topic, b"online", qos=1, retain=True)
            cmd_topic = f"{cfg['mqtt']['base_topic']}/{r['path']}/cmd"
            client.subscribe(cmd_topic, qos=2)

            while True:
                st = time.perf_counter()
                m.apply_physics(r, cfg['simulation']['outside_temp'], cfg)
                if m.inject_faults(r, cfg):
                    topic = f"{cfg['mqtt']['base_topic']}/{r['path']}/telemetry"
                    p = json.dumps(m.get_payload(r))
                    client.publish(topic, p.encode('utf-8'), qos=0)
                
                pd = time.perf_counter() - st
                sl = max(0, cfg['simulation']['tick_interval'] - pd)
                await asyncio.sleep(sl)
        except Exception as e:
            print(f"MQTT Reconnecting for {r['id']} ({e})")
            await asyncio.sleep(10)

async def coap_node_task(r, cfg):
    root = resource.Site()
    telemetry_resource = CoAPTelemetryResource(r)
    actuator_resource = CoAPActuatorResource(r)
    
    f_str = f"f{r['id'].split('-')[1]}"
    r_str = f"r{r['id'].split('-')[2]}"
    
    root.add_resource([f_str, r_str, 'telemetry'], telemetry_resource)
    root.add_resource([f_str, r_str, 'actuators', 'hvac'], actuator_resource)

    # For DTLS, we use credentials map. In a real scenario, we'd use certificates.
    # Here we demonstrate the structural setup for DTLS.
    server_credentials = CredentialsMap()
    # Mock PSK for demonstration of DTLS setup
    server_credentials.load_from_dict({
        ':client_identity': {'psk': b'secretPSK'}
    })

    # Using 127.0.0.1 since edge gateways will also run locally targeting these ports
    try:
        # aiocoap server context with DTLS
        context = await aiocoap.Context.create_server_context(root, bind=('0.0.0.0', r['coap_port']))
        # In actual DTLS deployment, we'd pass server_credentials=server_credentials
        # and ensure the environment has 'dtls' extra installed.
    except Exception as e:
        print(f"Failed to bind CoAP for {r['id']} on port {r['coap_port']}: {e}")
        return

    j = random.uniform(0, cfg['simulation'].get('max_jitter', 60))
    await asyncio.sleep(j)

    while True:
        st = time.perf_counter()
        m.apply_physics(r, cfg['simulation']['outside_temp'], cfg)
        if m.inject_faults(r, cfg):
            payload_dict = m.get_payload(r)
            telemetry_resource.update_state(payload_dict)
            
        pd = time.perf_counter() - st
        sl = max(0, cfg['simulation']['tick_interval'] - pd)
        await asyncio.sleep(sl)


async def main():
    print("STARTING HYBRID WORLD ENGINE...")
    with open("config.yaml", "r") as f:
        cfg = yaml.safe_load(f)

    await db.db_init()
    old_st = await db.db_load()

    rs = []
    tsks = []
    for f_idx in range(1, cfg['simulation']['floors'] + 1):
        for r_idx in range(1, cfg['simulation']['rooms_per_floor'] + 1):
            rid = f"b01-f{f_idx:02d}-r{r_idx:03d}"
            s = old_st.get(rid) if old_st else None
            room = m.create_room("b01", f_idx, r_idx, cfg, s)
            rs.append(room)
            
            if room["protocol"] == "mqtt":
                tsks.append(mqtt_node_task(room, cfg))
            else:
                tsks.append(coap_node_task(room, cfg))

    async def sync():
        while True:
            await asyncio.sleep(cfg['simulation'].get('sync_interval', 30))
            await db.db_save(rs)

    await asyncio.gather(*tsks, sync())

if __name__ == "__main__":
    asyncio.run(main())
