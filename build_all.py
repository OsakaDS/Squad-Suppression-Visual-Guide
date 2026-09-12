#!/usr/bin/env python3
"""Group the raw sweep into one entry per weapon and attach icons."""
import sys, os, json, base64
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import squad
from textures import extract_image, to_web

HERE = os.path.dirname(os.path.abspath(__file__))
raw = json.load(open(os.path.join(HERE, 'all_weapons_raw.json')))['rows']

# the eight categories the profiles collapse into, plus the leftovers
CATEGORY = {
    'Projectile_SuppressionInfo_Rifle':      ('rifle',       'Rifle'),
    'Projectile_Suppression_BattleRifle':    ('battlerifle', 'Battle rifle'),
    'Projectile_Suppression_MMG':            ('mmg',         'MMG'),
    'Projectile_Suppression_GPMG':           ('mmg',         'MMG'),
    'Projectile_Suppression_LMG':            ('lmg',         'LMG'),
    'Projectile_Suppression_LSW':            ('lsw',         'LSW'),
    'Projectile_Suppression_SMG':            ('smg',         'SMG / pistol'),
    'Projectile_Suppression_Pistol':         ('smg',         'SMG / pistol'),
    'Projectile_Suppression_PrecisionRifle': ('dmr',         'DMR'),
    'Projectile_Suppression_SniperRifle':    ('sniper',      'Sniper rifle'),
    'Projectile_SuppressionHMG':             ('hmg',         'Shotgun / HMG'),
    'Projectile_Suppression_20mm_AP':        ('hmg',         'Shotgun / HMG'),
    'Projectile_SuppressionNone':            ('none',        'No suppression'),
}
def cat_of(p):
    if p in CATEGORY: return CATEGORY[p]
    if p and p.startswith('Explosion_'): return ('explosive', 'Explosive')
    return ('other', 'Other')

def plainness(r):
    """prefer the bare, ironsighted variant as the representative of a weapon"""
    a = r['asset'].split('/')[-1]
    return (a.count('_'), len(a))

groups = defaultdict(list)
for r in raw:
    groups[(r['name'] or r['asset'].split('/')[-1], r['profile'])].append(r)

weapons = []
for (name, profile), rs in groups.items():
    rep = sorted(rs, key=plainness)[0]
    icon = next((x['icon'] for x in sorted(rs, key=plainness) if x['icon']), None)
    cid, clabel = cat_of(profile)
    rpms = sorted({round(60 / x['tbs']) for x in rs if x['tbs']})
    weapons.append({
        'name': name, 'cat': cid, 'catLabel': clabel, 'profile': profile,
        'folder': rep['cat'], 'asset': rep['asset'], 'icon': icon,
        'projectile': rep['projectile'], 'override': rep['override'],
        'overrideSrc': rep['override_src'],
        'rpm': rpms[0] if rpms else None, 'rpmAlt': rpms[1:] if len(rpms) > 1 else None,
        'mv': round(rep['mv'] / 100) if rep['mv'] else None,
        'moa': rep['moa'], 'mag': rep['mag'], 'pen': rep['pen'],
        'power': round(rep['power'], 4) if rep['power'] is not None else None,
        'thr': round(rep['thr'], 3) if rep['thr'] is not None else None,
        'sway': rep['sway'], 'curve': rep['curve'],
        'variants': len(rs),
    })
weapons.sort(key=lambda w: (w['cat'], (w['name'] or '').lower()))

# ---------- icons ----------
CONTENT = squad.CONTENT
def png_for(game_path, max_w):
    p = squad.asset_path(game_path)
    if not p or not os.path.exists(p): return None
    b, kind = extract_image(p)
    if not b: return None
    try:
        web, size = to_web(b, max_w)
    except Exception:
        return None
    return 'data:image/png;base64,' + base64.b64encode(web).decode()

icons, seen = {}, {}
for w in weapons:
    if not w['icon']:
        w['iconKey'] = None; continue
    k = w['icon'].split('/')[-1].split('.')[0]
    if k not in seen:
        seen[k] = png_for(w['icon'], 96)
    w['iconKey'] = k if seen[k] else None
    if seen[k]: icons[k] = seen[k]

# category icons, drawn from the game's own inventory / role art
CAT_ICON = {
    'rifle':       '/Game/UI/HUD/Roles/T_role_rifleman',
    'battlerifle': '/Game/UI/HUD/Roles/T_role_rifleman_scoped',
    'mmg':         '/Game/UI/HUD/Roles/T_role_machinegunner',
    'lmg':         '/Game/UI/HUD/Roles/T_role_automaticrifleman',
    'lsw':         '/Game/UI/HUD/Roles/T_role_automaticrifleman_optic',
    'smg':         '/Game/UI/HUD/Roles/T_role_raider',
    'dmr':         '/Game/UI/HUD/Roles/T_role_designatedmarksman',
    'sniper':      '/Game/UI/HUD/Roles/T_role_sniper',
    'hmg':         '/Game/UI/HUD/Roles/T_role_breacher',
    'explosive':   '/Game/UI/HUD/Roles/T_role_grenadier',
    'none':        '/Game/UI/HUD/Roles/T_role_unarmed',
}
caticons = {}
for k, p in CAT_ICON.items():
    v = png_for(p, 80)
    if v: caticons[k] = v
    else: print('!! missing category icon', k, p)

out = {'weapons': weapons, 'icons': icons, 'catIcons': caticons,
       'catSource': {k: v.split('/')[-1] for k, v in CAT_ICON.items()}}
json.dump(out, open(os.path.join(HERE, 'all_weapons.json'), 'w'), separators=(',', ':'))

kb = lambda n: f"{n/1024:.0f} KB"
print('weapons:', len(weapons), '| unique icons:', len(icons), '| category icons:', len(caticons))
print('icon payload:', kb(sum(len(v) for v in icons.values())),
      '| category icons:', kb(sum(len(v) for v in caticons.values())),
      '| total file:', kb(os.path.getsize(os.path.join(HERE, 'all_weapons.json'))))
from collections import Counter
for c, n in Counter(w['catLabel'] for w in weapons).most_common():
    print(f"   {c:16s} {n}")
print('no icon:', [w['name'] for w in weapons if not w['iconKey']][:12], '...' )
print('count without icon:', sum(1 for w in weapons if not w['iconKey']))
