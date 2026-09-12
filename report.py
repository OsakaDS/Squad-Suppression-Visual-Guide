#!/usr/bin/env python3
"""Dump suppression stats for a set of Squad weapons straight out of the .uasset files."""
import sys, os, csv, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import squad

# display name -> asset path under /Game/Blueprints/Items
WEAPONS = [
    ("M4A1",        "USA",  "5.56x45",  "Rifles/BP_M4A1"),
    ("M16A4",       "USA",  "5.56x45",  "Rifles/BP_M16A4"),
    ("AK-74M",      "RUS",  "5.45x39",  "Rifles/BP_AK74M"),
    ("AK-12",       "RUS",  "5.45x39",  "Rifles/BP_AK12"),
    ("AKM",         "INS/MEA", "7.62x39", "Rifles/BP_AKM"),
    ("L85A2",       "GB",   "5.56x45",  "Rifles/BP_L85A2"),
    ("QBZ-95-1",    "PLA",  "5.8x42",   "Rifles/BP_QBZ95-1"),
    ("G3A3",        "MEA/INS", "7.62x51", "Rifles/BP_G3A3"),
    ("M14 (DMR)",   "USA",  "7.62x51",  "Rifles/BP_M14"),
    ("AS VAL",      "RUS",  "9x39 subsonic", "Rifles/BP_ASVAL"),
]

def curve_at(keys, d):
    """Evaluate an FRichCurve the way UE does (linear / constant / cubic-bezier segments)."""
    if not keys: return None
    ks = sorted(keys, key=lambda k: k['time'])
    if d <= ks[0]['time']: return ks[0]['value']
    if d >= ks[-1]['time']: return ks[-1]['value']
    for a, b in zip(ks, ks[1:]):
        if not (a['time'] <= d <= b['time']): continue
        diff = b['time'] - a['time']
        t = (d - a['time']) / diff
        if a['interp'] == 'Constant': return a['value']
        if a['interp'] == 'Linear':   return a['value'] + t * (b['value'] - a['value'])
        # Cubic: UE builds a bezier from the leave/arrive tangents
        p0, p3 = a['value'], b['value']
        p1 = p0 + a['leave'] * diff / 3.0
        p2 = p3 - b['arrive'] * diff / 3.0
        u = 1.0 - t
        return u*u*u*p0 + 3*u*u*t*p1 + 3*u*t*t*p2 + t*t*t*p3
    return None

def main():
    rows = []
    for name, faction, cal, rel in WEAPONS:
        rep = squad.weapon_report('/Game/Blueprints/Items/' + rel)
        v, keys = rep['values'], rep['curve_keys']
        short = lambda s: (s or '').split('/')[-1].split('.')[0]
        rate = rep['weapon_config'].get('TimeBetweenShots')
        rpm = round(60.0 / rate) if rate else None
        rows.append({
            'weapon': name, 'faction': faction, 'caliber': cal,
            'asset': rel,
            'projectile': short(rep['projectile']),
            'suppression_profile': short(rep['suppression_class']),
            'profile_source': 'weapon override' if 'override' in (rep['suppression_source'] or '') else 'projectile',
            'suppression_power': round(v.get('SuppressionPower'), 4) if v.get('SuppressionPower') is not None else None,
            'max_suppression_threshold': round(v.get('MaxSuppressionThreshold'), 3) if v.get('MaxSuppressionThreshold') is not None else None,
            'suppression_range_m': round(max(k['time'] for k in keys) / 100, 2) if keys else None,
            'power_at_1m': round(curve_at(keys, 100), 4) if keys else None,
            'power_at_2m': round(curve_at(keys, 200), 4) if keys else None,
            'power_at_3m': round(curve_at(keys, 300), 4) if keys else None,
            'power_at_4m': round(curve_at(keys, 400), 4) if keys else None,
            'add_suppress_sway': v.get('AddSuppressSway'),
            'max_suppress_sway_factor': v.get('MaxSuppressSwayFactor'),
            'suppress_sway_release': v.get('SuppressSwayFactorRelease'),
            'obstructed_closeness_mult': v.get('ObstructedClosenessMult'),
            'lof_suppress_range': v.get('LofSuppressRange'),
            'rpm': rpm,
            'supp_per_sec_at_1m': round(curve_at(keys, 100) * rpm / 60, 3) if (keys and rpm) else None,
            'muzzle_velocity_ms': round(rep['weapon_config'].get('MuzzleVelocity', 0) / 100) or None,
            'curve_asset': short(rep['curve']),
            'curve_keys': [(k['time'], round(k['value'], 4)) for k in keys],
        })
    return rows

if __name__ == '__main__':
    rows = main()
    out = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out, 'squad_rifle_suppression.json'), 'w') as f:
        json.dump(rows, f, indent=1)
    cols = [c for c in rows[0] if c != 'curve_keys']
    with open(os.path.join(out, 'squad_rifle_suppression.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols + ['curve_keys'])
        w.writeheader()
        for r in rows:
            r = dict(r); r['curve_keys'] = '; '.join(f"{t/100:g}m:{v}" for t, v in r['curve_keys'])
            w.writerow(r)
    hdr = ['weapon','suppression_profile','suppression_power','suppression_range_m',
           'power_at_1m','power_at_2m','power_at_3m','power_at_4m','max_suppression_threshold',
           'add_suppress_sway','rpm','supp_per_sec_at_1m']
    widths = [max(len(h), max(len(str(r[h])) for r in rows)) for h in hdr]
    print(' | '.join(h.ljust(w) for h, w in zip(hdr, widths)))
    print('-+-'.join('-' * w for w in widths))
    for r in rows:
        print(' | '.join(str(r[h]).ljust(w) for h, w in zip(hdr, widths)))
