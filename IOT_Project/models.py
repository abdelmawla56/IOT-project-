import random
import time

def create_room(b_id, f_num, r_num, cfg, state=None):
    protocol = "mqtt" if r_num <= cfg['simulation']['mqtt_rooms_per_floor'] else "coap"
    coap_port = None
    if protocol == "coap":
        coap_port = 50000 + (f_num * 100) + r_num

    r = {
        "id": f"{b_id}-{f_num:02d}-{r_num:03d}",
        "path": f"bldg_{b_id}/floor_{f_num:02d}/room_{r_num:03d}",
        "t": 22.0,
        "h": 45.0,
        "m": "OFF",
        "tt": 22.0,
        "occ": False,
        "l": 0,
        "ts": int(time.time()),
        "f": False,
        "protocol": protocol,
        "coap_port": coap_port,
        "last_latency": 0.0
    }
    if state:
        r["t"] = state.get('last_temp', 22.0)
        r["h"] = state.get('last_humidity', 45.0)
        r["m"] = state.get('hvac_mode', "OFF")
        r["tt"] = state.get('target_temp', 22.0)
        r["last_latency"] = state.get('last_latency', 0.0)
    return r

def get_pwr(m):
    if m == "ON": return 1.0
    if m == "ECO": return 0.5
    return 0.0

def apply_physics(r, out_t, cfg):
    if r['f']: return
    diff = out_t - r['t']
    l = cfg['physics']['alpha'] * diff
    d = -1 if r['t'] > r['tt'] else 1
    h_i = d * cfg['physics']['beta'] * get_pwr(r['m'])
    o_i = cfg['physics']['occ_temp_boost'] if r['occ'] else 0
    r['t'] += l + h_i + o_i
    r['ts'] = int(time.time())

def inject_faults(r, cfg):
    p = cfg['faults']['probability']
    if random.random() < p:
        c = random.choice(["DRIFT", "FROZEN", "DROPOUT"])
        if c == "DRIFT": r['t'] += 2.0
        if c == "FROZEN": r['f'] = True
        if c == "DROPOUT": return False 
    return True

def get_payload(r):
    return {
        "metadata": {"sensor_id": r['id'], "timestamp": r['ts']},
        "sensors": {"temperature": round(r['t'], 2), "humidity": round(r['h'], 2), "occupancy": r['occ'], "light_level": 500 if r['occ'] else 50},
        "actuators": {"hvac_mode": r['m']},
        "metrics": {"latency_ms": round(r['last_latency'] * 1000, 2)}
    }
