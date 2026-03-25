import aiosqlite
import os

async def db_init(p="data/fleet.db"):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    async with aiosqlite.connect(p) as d:
        await d.execute('''
            CREATE TABLE IF NOT EXISTS rooms (
                r_id TEXT PRIMARY KEY,
                t REAL, h REAL, m TEXT, tt REAL, ts INTEGER
            )
        ''')
        await d.commit()

async def db_load(p="data/fleet.db"):
    async with aiosqlite.connect(p) as d:
        d.row_factory = aiosqlite.Row
        async with d.execute("SELECT * FROM rooms") as c:
            res = await c.fetchall()
            st = {}
            for r in res:
                st[r['r_id']] = {
                    'last_temp': r['t'],
                    'last_humidity': r['h'],
                    'hvac_mode': r['m'],
                    'target_temp': r['tt'],
                    'last_update': r['ts']
                }
            return st

async def db_save(rs, p="data/fleet.db"):
    async with aiosqlite.connect(p) as d:
        for r in rs:
            await d.execute('''
                INSERT OR REPLACE INTO rooms 
                (r_id, t, h, m, tt, ts)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (r['id'], r['t'], r['h'], r['m'], r['tt'], r['ts']))
        await d.commit()
