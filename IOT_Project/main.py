import asyncio
import yaml
import time
import json
import random
from gmqtt import Client as MQTTClient, Message as MQTTMessage
from gmqtt.mqtt.constants import MQTTv311
import aiocoap
import aiocoap.resource as resource

import database as db
import models as m


class CoAPTelemetryResource(resource.ObservableResource):
    def __init__(self, room):
        super().__init__()
        self.room = room
        self.payload = b"{}"

    def update_state(self, payload_dict):
        self.payload = json.dumps(payload_dict).encode('utf-8')
        self.updated_state()

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
                print(f"[CoAP CMD] Room {self.room['id']} HVAC set to {command} "
                      f"(Latency: {self.room['last_latency']*1000:.1f}ms)")
                return aiocoap.Message(code=aiocoap.CHANGED)
            return aiocoap.Message(code=aiocoap.BAD_REQUEST)
        except Exception:
            return aiocoap.Message(code=aiocoap.BAD_REQUEST)


async def mqtt_node_task(r, cfg):
    j = random.uniform(0, cfg['simulation'].get('max_jitter', 10))
    await asyncio.sleep(j)

    client_id = f"mqtt_{r['id']}_{random.randint(1000,9999)}"
    lwt_topic = f"{cfg['mqtt']['base_topic']}/{r['path']}/status"

    client = MQTTClient(
        client_id,
        will_message=MQTTMessage(lwt_topic, b"offline", qos=1, retain=True)
    )

    def on_message(client, topic, payload, qos, properties):
        try:
            msg = json.loads(payload.decode('utf-8'))
            cmd = msg.get("command")
            ts = msg.get("timestamp")
            if ts:
                r["last_latency"] = time.time() - ts
            if cmd in ["ON", "OFF", "ECO"]:
                r["m"] = cmd
                print(f"[MQTT CMD] Room {r['id']} HVAC -> {cmd} "
                      f"(Latency: {r['last_latency']*1000:.1f}ms)")
        except Exception:
            pass

    client.on_message = on_message

    while True:
        try:
            await client.connect(cfg['mqtt']['broker'], port=cfg['mqtt']['port'], version=MQTTv311)
            client.publish(lwt_topic, b"online", qos=1, retain=True)
            client.subscribe(f"{cfg['mqtt']['base_topic']}/{r['path']}/cmd", qos=1)
            print(f"[MQTT] {r['id']} connected to {cfg['mqtt']['broker']}")

            while True:
                st = time.perf_counter()
                m.apply_physics(r, cfg['simulation']['outside_temp'], cfg)
                if m.inject_faults(r, cfg):
                    topic = f"{cfg['mqtt']['base_topic']}/{r['path']}/telemetry"
                    p = json.dumps(m.get_payload(r))
                    client.publish(topic, p.encode('utf-8'), qos=0)
                elapsed = time.perf_counter() - st
                await asyncio.sleep(max(0, cfg['simulation']['tick_interval'] - elapsed))
        except Exception as e:
            print(f"[MQTT] Reconnecting {r['id']}: {e}")
            await asyncio.sleep(10)


async def coap_sim_task(r, cfg, telemetry_res):
    """Physics simulation loop for a single CoAP room — updates the shared resource."""
    j = random.uniform(0, cfg['simulation'].get('max_jitter', 10))
    await asyncio.sleep(j)

    while True:
        st = time.perf_counter()
        m.apply_physics(r, cfg['simulation']['outside_temp'], cfg)
        if m.inject_faults(r, cfg):
            telemetry_res.update_state(m.get_payload(r))
        elapsed = time.perf_counter() - st
        await asyncio.sleep(max(0, cfg['simulation']['tick_interval'] - elapsed))


async def main():
    print("STARTING HYBRID WORLD ENGINE...")
    with open("config.yaml", "r") as f:
        cfg = yaml.safe_load(f)

    await db.db_init()
    old_st = await db.db_load()

    # Build a single shared CoAP server root for all CoAP rooms
    coap_root = resource.Site()
    coap_rooms = []
    mqtt_rooms = []

    for f_idx in range(1, cfg['simulation']['floors'] + 1):
        for r_idx in range(1, cfg['simulation']['rooms_per_floor'] + 1):
            rid = f"b01-f{f_idx:02d}-r{r_idx:03d}"
            s = old_st.get(rid) if old_st else None
            room = m.create_room("b01", f_idx, r_idx, cfg, s)

            if room["protocol"] == "mqtt":
                mqtt_rooms.append(room)
            else:
                # Register resources under /f<floor>/r<room>/...
                f_str = f"f{f_idx:02d}"
                r_str = f"r{r_idx:03d}"
                tel_res = CoAPTelemetryResource(room)
                act_res = CoAPActuatorResource(room)
                coap_root.add_resource([f_str, r_str, 'telemetry'], tel_res)
                coap_root.add_resource([f_str, r_str, 'actuators', 'hvac'], act_res)
                coap_rooms.append((room, tel_res))

    # Start the single shared CoAP server
    coap_port = cfg.get('coap', {}).get('base_port', 5683)
    try:
        await aiocoap.Context.create_server_context(coap_root, bind=('127.0.0.1', coap_port))
        print(f"[CoAP] Server listening on port {coap_port} "
              f"({len(coap_rooms)} rooms registered)")
    except Exception as e:
        print(f"[CoAP] Failed to start server on port {coap_port}: {e}")

    # Gather all tasks
    tasks = []
    for room in mqtt_rooms:
        tasks.append(mqtt_node_task(room, cfg))
    for room, tel_res in coap_rooms:
        tasks.append(coap_sim_task(room, cfg, tel_res))

    all_rooms = mqtt_rooms + [r for r, _ in coap_rooms]

    async def sync():
        while True:
            await asyncio.sleep(cfg['simulation'].get('sync_interval', 30))
            await db.db_save(all_rooms)
            print(f"[DB] State saved for {len(all_rooms)} rooms.")

    print(f"[Engine] {len(mqtt_rooms)} MQTT rooms | {len(coap_rooms)} CoAP rooms | "
          f"Tick: {cfg['simulation']['tick_interval']}s")
    await asyncio.gather(*tasks, sync())


if __name__ == "__main__":
    import sys
    # gmqtt is incompatible with Windows ProactorEventLoop — use SelectorEventLoop
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
