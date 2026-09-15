#!/usr/bin/env python3
"""all_weapons.json -> squad_all_weapons_suppression.csv, one row per weapon."""
import os, json, csv
HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, 'page_payload.json')))
P = {p['asset']: p for p in d['profiles']}
def prof(a):
    for p in d['profiles']:
        if p['asset'] == a or a in p.get('alias', []): return p
def ev(k, x):
    if not k: return None
    if x <= k[0]['x']: return k[0]['y']
    if x >= k[-1]['x']: return k[-1]['y']
    for a, b in zip(k, k[1:]):
        if a['x'] <= x <= b['x']:
            t = (x - a['x']) / (b['x'] - a['x'])
            if a['i'] == 'Constant': return a['y']
            if a['i'] == 'Linear': return a['y'] + t * (b['y'] - a['y'])
            p0, p3 = a['y'], b['y']; diff = b['x'] - a['x']; p1 = p0 + a['l'] * diff / 3; p2 = p3 - b['a'] * diff / 3; u = 1 - t
            return u**3*p0 + 3*u*u*t*p1 + 3*u*t*t*p2 + t**3*p3
cols = ['weapon','category','fire_mode','rate_rpm','cyclic_rpm','bolt_cycle_s','profile','profile_from_override','projectile','asset',
        'envelope_m','power_1m','power_2m','power_3m','power_4m','ceiling','sway_add','rounds_to_cap_1m','per_second_1m','muzzle_ms','moa','mag','pen_mm','variants','icon_asset']
rows = []
for w in json.load(open(os.path.join(HERE, 'all_weapons.json')))['weapons']:
    p = prof(w['profile'])
    pw = lambda x: (ev(p['keys'], x) if p else (w['power'] or None))
    p1 = pw(100); cap = p['thr'] if p else w['thr']
    rows.append({'weapon': w['name'], 'category': w['catLabel'], 'fire_mode': w.get('fire') or '', 'rate_rpm': w['rpm'] or '',
        'cyclic_rpm': w.get('rpmCyclic') or '', 'bolt_cycle_s': w.get('boltTime') or '', 'profile': w['profile'],
        'profile_from_override': 'yes' if w['override'] else 'no', 'projectile': w['projectile'], 'asset': w['asset'],
        'envelope_m': round(p['keys'][-1]['x'] / 100, 2) if (p and p['keys']) else ('flat' if p1 else ''),
        'power_1m': round(p1, 4) if p1 else '', 'power_2m': round(pw(200), 4) if pw(200) else '',
        'power_3m': round(pw(300), 4) if pw(300) else '', 'power_4m': round(pw(400), 4) if pw(400) else '',
        'ceiling': round(cap, 3) if cap else '', 'sway_add': (p['sway'] if p else w['sway']) or '',
        'rounds_to_cap_1m': -(-cap // p1) if (p1 and cap) else '', 'per_second_1m': round(p1 * w['rpm'] / 60, 3) if (p1 and w['rpm']) else '',
        'muzzle_ms': w['mv'] or '', 'moa': w['moa'] or '', 'mag': w['mag'] or '', 'pen_mm': w['pen'] or '',
        'variants': w['variants'], 'icon_asset': (w['icon'] or '').split('/')[-1].split('.')[0]})
rows.sort(key=lambda r: (r['category'], r['weapon'].lower()))
out = os.path.join(HERE, 'squad_all_weapons_suppression.csv')
with open(out, 'w', newline='') as f:
    wr = csv.DictWriter(f, fieldnames=cols); wr.writeheader(); wr.writerows(rows)
print(f"wrote {out}  ({len(rows)} rows)")
