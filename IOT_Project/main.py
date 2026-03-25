import asyncio
import yaml
import time
import json
import random
import aiomqtt
import database as db
import models as m

async def rt(r, cfg):
    j = random.uniform(0, cfg['simulation'].get('max_jitter', 60))
    await asyncio.sleep(j)
    while True:
        try:
            async with aiomqtt.Client(cfg['mqtt']['broker'], port=cfg['mqtt']['port']) as c:
                while True:
                    st = time.perf_counter()
                    m.apply_physics(r, cfg['simulation']['outside_temp'], cfg)
                    if m.inject_faults(r, cfg):
                        topic = f"{cfg['mqtt']['base_topic']}/{r['path']}/telemetry"
                        p = json.dumps(m.get_payload(r))
                        await c.publish(topic, p)
                        hb = f"fleet/heartbeat/{r['id']}"
                        await c.publish(hb, json.dumps({"status": "ok", "ts": time.time()}))
                    pd = time.perf_counter() - st
                    sl = max(0, cfg['simulation']['tick_interval'] - pd)
                    await asyncio.sleep(sl)
        except Exception:
            await asyncio.sleep(10)

async def main():
    print("STARTING")
    with open("config.yaml", "r") as f:
        cfg = yaml.safe_load(f)

    await db.db_init()
    old_st = await db.db_load()

    rs = []
    tsks = []
    for f_idx in range(1, cfg['simulation']['floors'] + 1):
        for r_idx in range(1, cfg['simulation']['rooms_per_floor'] + 1):
            rid = f"b01-f{f_idx:02d}-r{r_idx:03d}"
            s = old_st.get(rid)
            room = m.create_room("b01", f_idx, r_idx, cfg, s)
            rs.append(room)
            tsks.append(rt(room, cfg))

    async def sync():
        while True:
            await asyncio.sleep(cfg['simulation'].get('sync_interval', 30))
            await db.db_save(rs)

    await asyncio.gather(*tsks, sync())

if __name__ == "__main__":
    asyncio.run(main())
