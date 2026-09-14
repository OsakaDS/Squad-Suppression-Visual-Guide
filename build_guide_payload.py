#!/usr/bin/env python3
"""Everything the player guide needs, in one JSON: per-kit figures, soldier-side curves,
screen-effect thresholds, sway, blasts, ADS multipliers, immunity constants, and the logo."""
import os, json, io, base64, glob, collections
from PIL import Image
from curve import read_curves

HERE = os.path.dirname(os.path.abspath(__file__))
SOLD = '/home/osaka/Downloads/SquadEditor/Squad/Content/Blueprints/Soldiers'
base = json.load(open(os.path.join(HERE, 'payload.json')))          # profiles / flat / blast / soldier
ALL = json.load(open(os.path.join(HERE, 'all_weapons.json')))
allw = ALL['weapons']

# ---------- kits (= suppression profiles), named the way players say them ----------
KITS = [  # id, label, profile asset, weapon category id
    ('rifle',   'Rifle',        'Projectile_SuppressionInfo_Rifle',      'rifle'),
    ('br',      'Battle rifle', 'Projectile_Suppression_BattleRifle',    'battlerifle'),
    ('dmr',     'Precision Rifle (DMR)', 'Projectile_Suppression_PrecisionRifle', 'dmr'),
    ('sniper',  'Sniper',       'Projectile_Suppression_SniperRifle',    'sniper'),
    ('lsw',     'LSW',          'Projectile_Suppression_LSW',            'lsw'),
    ('lmg',     'LMG',          'Projectile_Suppression_LMG',            'lmg'),
    ('mmg',     'MMG',          'Projectile_Suppression_MMG',            'mmg'),
    ('smg',     'SMG / pistol', 'Projectile_Suppression_SMG',            'smg'),
]
prof = {p['asset']: p for p in base['profiles']}

def pick_examples(ws, n=3):
    """three distinct real guns: skip generic bases, one entry per base name (before any ' + optic')"""
    out, seen = [], set()
    for w in sorted(ws, key=lambda w: (-w['variants'], len(w['name']))):
        nm = w['name']
        if nm.startswith('BP_') or 'Generic' in nm: continue
        base_name = nm.split(' + ')[0].strip()
        if base_name in seen: continue
        seen.add(base_name); out.append({'name': base_name, 'icon': w.get('iconKey')})
        if len(out) == n: break
    return out
flat = {'Projectile_SuppressionHMG': {'power': 0.5, 'thr': 2.0}}
kits = []
for kid, label, asset, cat in KITS:
    ws = [w for w in allw if w['cat'] == cat and w['rpm']]
    rpms = sorted(w['rpm'] for w in ws)
    flagship = sorted(ws, key=lambda w: (-w['variants'], len(w['name'])))[0] if ws else None
    p = prof.get(asset)
    kits.append({
        'id': kid, 'label': label, 'cat': cat,
        'keys': p['keys'] if p else [],
        'flatPower': None if p else flat[asset]['power'],
        'ceiling': p['thr'] if p else flat[asset]['thr'],
        'swayAdd': p['sway'] if p else None,
        'count': len([w for w in allw if w['cat'] == cat]),
        'rpm': flagship['rpm'] if flagship else None,
        'rpmMin': rpms[0] if rpms else None, 'rpmMax': rpms[-1] if rpms else None,
        'example': flagship['name'] if flagship else None,
        # a rate a player can actually sustain — cyclic for automatics; an assumption (labelled) for the rest
        'rpmPractical': {'dmr': 150, 'sniper': 30, 'br': 200, 'shotgun': 60}.get(kid, flagship['rpm'] if flagship else 0),
        'rpmAssumed': kid in ('dmr', 'sniper', 'br', 'shotgun'),
        'emblem': ALL['catIcons'].get(cat),
    })

# ---------- soldier-side curves ----------
def keys_of(path):
    cs = read_curves(path)
    return {ax: [{'x': round(k['time'], 4), 'y': round(k['value'], 5), 'i': k['interp'],
                  'a': k['arrive'], 'l': k['leave']} for k in ks] for ax, ks in cs.items()}
S = base['soldier']
soldier = {
    'closeness': {  # punch multiplier by closeness ratio
        'camLoc': S['FC_SuppressionCloseness_CameraLocationPunchByClosenessRatio'],
        'camRot': S['FC_SuppressionCloseness_CameraRotationPunchByClosenessRatio'],
        'weapon': S['FC_SuppressionCloseness_WeaponAlignmentPunchByClosenessRatio'],
    },
    'immunity': {   # punch multiplier by immunity factor
        'camLoc': S['FC_SuppressionImmunity_CameraLocPunchByImmunity'],
        'camRot': S['FC_SuppressionImmunity_CameraRotPunchByImmunity'],
        'weapon': S['FC_SuppressionImmunity_WeaponAlignmentPunchByImmunity'],
    },
    'firstShot': S['FC_SuppressionImmunityIncrementByClosenessRatio'],
    'punchShape': {k: keys_of(f'{SOLD}/PunchCurves/Suppression/{f}.uasset') for k, f in
                   [('camRot', 'VC_Suppression_CameraRotation'), ('camLoc', 'VC_Suppression_CameraLocation'),
                    ('weapon', 'VC_Suppression_WeaponAlignment')]},
    'sway': keys_of(f'{SOLD}/SuppressionConfig/VC_SuppressionSwayBySuppressionPercent.uasset'),
    'vignette': keys_of('/home/osaka/Downloads/SquadEditor/Squad/Content/Blueprints/CameraManager/CameraEffects/FC_SuppressionVignetteIntensity.uasset')[''],
    'const': {'tick': 0.1, 'increment': 1.0, 'max': 7.5, 'window': 1.0, 'variability': 0.25,
              'decayRate': 0.5, 'radius': 800, 'fullRadius': 100, 'angleOff': 17.5, 'wallIgnore': 250},
}
# screen-effect layers on the active preset (Suppression_VignetteOnly)
effects = [
    {'id': 'vignette', 'label': 'Vignette',             'from': 0.0,  'to': 0.0,  'note': 'always on; intensity follows the level'},
    {'id': 'grain',    'label': 'Film grain',           'from': 1.0,  'to': 2.0,  'note': 'intensity 0.17'},
    {'id': 'desat',    'label': 'Desaturation',         'from': 1.4,  'to': 1.9,  'note': ''},
    {'id': 'grade',    'label': 'Colour shift',         'from': 1.4,  'to': 1.9,  'note': 'contrast grading'},
    {'id': 'ca',       'label': 'Chromatic aberration', 'from': 1.9,  'to': 5.0,  'note': ''},
    {'id': 'dof',      'label': 'Blur (depth of field)','from': 3.0,  'to': 4.0,  'note': 'aperture 4.67, focus 46 cm'},
    {'id': 'dirt',     'label': 'Screen dirt',          'from': 2.95, 'to': 4.0,  'note': ''},
    {'id': 'fisheye',  'label': 'Fisheye',              'from': 5.0,  'to': 7.0,  'note': 'to 0.5 intensity'},
]
ads = [
    {'who': 'MAG / Maximi / Minimi / MG3 machine guns', 'n': 12, 'camLoc': 0.5, 'camRot': 0.2, 'weapon': 0.5, 'xAxis': True},
    {'who': 'Optic-equipped rifles, LSWs, LMGs',        'n': 65, 'camLoc': 0.4, 'camRot': None, 'weapon': None, 'xAxis': False},
    {'who': 'C9A2, L110A1, M240 M145 / MGO and others',  'n': 14, 'camLoc': None, 'camRot': None, 'weapon': None, 'xAxis': False},
]
# logo → two data URIs
logo_path = [f for f in glob.glob(os.path.join(HERE, 'branding', '*.png'))][0]
def uri(size):
    im = Image.open(logo_path).convert('RGBA')
    im.thumbnail((size, size), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, 'PNG', optimize=True)
    return 'data:image/png;base64,' + base64.b64encode(b.getvalue()).decode()
# the armoury: every weapon in the eight kits, with its icon
kit_cats = {k['cat']: k for k in kits}
weapons = [{'name': w['name'], 'kit': kit_cats[w['cat']]['id'], 'rpm': w['rpm'], 'mv': w['mv'],
            'icon': w.get('iconKey'), 'variants': w['variants'], 'override': w['override']}
           for w in allw if w['cat'] in kit_cats]
weapons.sort(key=lambda w: (w['kit'], w['name'].lower()))
used = {w['icon'] for w in weapons if w['icon']}
icons = {k: v for k, v in ALL['icons'].items() if k in used}
out = {'kits': kits, 'weapons': weapons, 'icons': icons,
       'soldier': soldier, 'effects': effects, 'ads': ads, 'blast': base['blast'],
       'logo': uri(260), 'logoSmall': uri(64),
       'version': 'v10.5.3', 'author': 'Osaka [29th ID]'}
json.dump(out, open(os.path.join(HERE, 'guide_payload.json'), 'w'), separators=(',', ':'))
print(f"guide_payload.json {os.path.getsize(os.path.join(HERE,'guide_payload.json'))/1024:.0f} KB")
print(f"  weapons in the armoury: {len(weapons)} | icons: {len(icons)}")
for k in kits:
    print(f"  {k['label']:22s} n={k['count']:3d} rpm={k['rpm']} ceiling={k['ceiling']} emblem={'yes' if k['emblem'] else 'NO'}")
