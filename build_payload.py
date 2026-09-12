#!/usr/bin/env python3
"""Fold the profile / curve / rifle-sample data into the page's base payload.

Reads gui_data.json (from build_gui_data.py) and writes payload.json: the eight
curve-driven passby profiles, the flat curve-free ones, the explosive radial
profiles, the ten-rifle sample and the soldier-side punch curves.
"""
import os, json

HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, 'gui_data.json')))
P = d['profiles']

def pack(name, label, cls):
    p = P[name]; v = p['values']
    return {
        'id': name.replace('Projectile_Suppression', '').replace('Info_', '').replace('_', '') or name,
        'label': label, 'cls': cls, 'asset': name,
        'power': round(v['SuppressionPower'], 4) if v.get('SuppressionPower') is not None else None,
        'thr': round(v['MaxSuppressionThreshold'], 3) if v.get('MaxSuppressionThreshold') is not None else None,
        'sway': v.get('AddSuppressSway'), 'maxSway': v.get('MaxSuppressSwayFactor'),
        'swayRelease': v.get('SuppressSwayFactorRelease'), 'obstructed': v.get('ObstructedClosenessMult'),
        'keys': [{'x': round(k['d'], 2), 'y': round(k['v'], 5), 'i': k['interp'],
                  'a': round(k['arrive'], 6), 'l': round(k['leave'], 6)} for k in p['keys']],
    }

# the eight profiles the passby chart plots, in categorical-colour order
ORDER = [
    ('Projectile_SuppressionInfo_Rifle',      'Rifle',           'Assault rifles, carbines'),
    ('Projectile_Suppression_BattleRifle',    'Battle rifle',    'G3, FAL, M14, SKS'),
    ('Projectile_Suppression_MMG',            'MMG',             'PKM, M240, 7.62 GPMG'),
    ('Projectile_Suppression_LMG',            'LMG',             'RPK, M249, 5.56 belt-fed'),
    ('Projectile_Suppression_LSW',            'LSW',             'L86A2, M27, auto rifles'),
    ('Projectile_Suppression_SMG',            'SMG / pistol',    'MP5, Uzi, sidearms, AS VAL'),
    ('Projectile_Suppression_PrecisionRifle', 'Precision rifle', 'DMRs with optics'),
    ('Projectile_Suppression_SniperRifle',    'Sniper rifle',    'M110, SV-98, Mosin'),
]
profiles = [pack(n, l, c) for n, l, c in ORDER]
# Pistol is identical to SMG and shares its slot rather than burning a ninth colour
for p in profiles:
    if p['asset'] == 'Projectile_Suppression_SMG':
        p['alias'] = ['Projectile_Suppression_Pistol']

FLAT = [('Projectile_SuppressionHMG', 'HMG (.50 cal)'), ('Projectile_Suppression_20mm_AP', '20 mm AP'),
        ('Projectile_Suppression_50mm_AP', '50 mm AP'), ('Projectile_Suppression_120mm_AP', '120 mm AP'),
        ('Projectile_SuppressionNone', 'None')]
flat = [{'label': l, 'power': P[n]['values'].get('SuppressionPower'),
         'thr': P[n]['values'].get('MaxSuppressionThreshold')} for n, l in FLAT]

BLAST = [('Explosion_Suppression_HandGrenade', 'Hand grenade'),
         ('Explosion_Suppression_GrenadeLauncher', 'Grenade launcher'),
         ('Explosion_Suppression_C4', 'C4 / IED'),
         ('Explosion_Suppression_Mortar_82mm', 'Mortar 82 mm'),
         ('Projectile_Suppression_Tank', 'Tank HE (120 mm)'),
         ('Explosion_Suppression_155mm_Frag', 'Artillery 155 mm'),
         ('Explosion_Suppression_CAS_Minigun', 'CAS minigun')]
blast = [{'label': l, 'power': P[n]['values'].get('ImpactSuppressionPower'),
          'inner': P[n]['values'].get('InnerRadius'), 'outer': P[n]['values'].get('OuterRadius'),
          'thr': P[n]['values'].get('MaxRadialSuppressionThreshold')} for n, l in BLAST]

rifles = [{'w': r['weapon'], 'faction': r['faction'], 'cal': r['caliber'], 'rpm': r['rpm'],
           'profile': r['suppression_profile'], 'src': r['profile_source'],
           'p1': r['power_at_1m'], 'p2': r['power_at_2m'], 'p3': r['power_at_3m'],
           'thr': r['max_suppression_threshold'], 'sway': r['add_suppress_sway'],
           'proj': r['projectile'], 'mv': r['muzzle_velocity_ms']} for r in d['rifles']]

soldier = {k: [{'x': p['x'], 'y': p['y'], 'i': p['interp'], 'a': p['arrive'], 'l': p['leave']}
               for p in v] for k, v in d['soldier_curves'].items()}

out = {'profiles': profiles, 'flat': flat, 'blast': blast, 'rifles': rifles, 'soldier': soldier}
json.dump(out, open(os.path.join(HERE, 'payload.json'), 'w'), separators=(',', ':'))
print(f"payload.json  profiles {len(profiles)} · flat {len(flat)} · blast {len(blast)} · "
      f"rifles {len(rifles)} · soldier curves {len(soldier)}")
