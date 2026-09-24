#!/usr/bin/env python3
"""Everything the Vehicle Weapons tab needs, in one JSON: per-class figures, every
weapon system with its vehicles, the blast profiles, and the icons.

The soldier-side curves, effect thresholds and infantry kits are already in
guide_payload.json; this tab reuses them for its reference lines rather than
shipping a second copy."""
import os, re, json, base64, collections
import vehicle_classes as VC
from textures import extract_image, to_web

HERE = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = '/home/osaka/Downloads/SquadEditor/Squad/Content/UI/HUD/Inventory/Weapons/VehicleWeapons'
PROFILES = json.load(open(os.path.join(HERE, 'all_profiles.json')))

VT_LABEL = {
    'Tank': 'Main battle tank', 'IFVTracked': 'IFV (tracked)', 'IFV': 'IFV (wheeled)',
    'APCTracked': 'APC (tracked)', 'APC': 'APC (wheeled)', 'Helicopter': 'Helicopter',
    'Jeep': 'Light vehicle', 'JeepAntiTank': 'Light vehicle (AT)', 'JeepTransport': 'Transport',
    'JeepLogistics': 'Logistics', 'TruckTransport': 'Transport truck', 'TruckLogistics': 'Logistics truck',
    'Boat': 'Boat', 'Motorcycle': 'Motorcycle', 'Emplacement': 'Emplacement',
}

# a weapon's icon: the game's own vehicle-weapon inventory art, matched on what the round is
ICON_RULES = [
    (r'minigun|m134|gau-?17',                          'T_M134'),
    (r'mk-?19',                                        'T_MK19'),
    (r'ags|agl|qlz|grenadelauncher|40mm',              '40mmhedp'),
    (r'mortar|hell.?cannon|propane',                    '81mm_mortar_he'),
    (r'kornet|9m133',                                  'kornet'),
    (r'tow|bgm',                                       'bgm71_tow'),
    (r'konkurs|malyutka|hj-?\d|skif|stugna|fagot|metis|spike|9m1|at3|milan|lahat|aps\d', 'kornet'),
    (r'hydra|m151|m156|ffar',                          'T_Hydra70_HE'),
    (r's-?5|s-?8|type-?57|ub32|rocket',                's5rocket'),
    (r'og-?[79]|frag.*(spg|rpg)',                      'og7v_frag'),
    (r'pg-?[79]|heat.*(spg|rpg)',                      'pg7v_heat'),
    (r'(1[0125][05]mm|100mm).*(sabot|armor|armour|ap\b)', 'tank_sabot'),
    (r'(1[0125][05]mm|100mm).*(heat|anti-?tank)',      'tank_heat'),
    (r'(1[0125][05]mm|100mm|76mm).*(frag|high.?explosive|he\b)', 'tank_frag'),
    (r'(1[0125][05]mm|100mm).*smoke',                  'tank_smoke'),
    (r'smoke.?generator|smokescreen',                  'smoke_generator'),
    (r'smoke',                                         'vehiclesmokelaunchers'),
    (r'30mm.*(frag|he\b|high)|gdp30|type-?23',         '30mm_he'),
    (r'(2[035]|30|40|45|50|57|73)mm|autocannon|2a4|2a7|2a2|ctas|bushmaster|ztm', '30mm_ap'),
    (r'14[_.]?5|kpv',                                  '14_5mm_ap'),
    (r'dshk',                                          'dshk'),
    (r'nsvt?|kord',                                    'nsvt'),
    (r'm2|browning|gau-?21|qjz|m3p|\.50|50cal',        'm2browning'),
    (r'coax|pkt|mag58|qtj',                            'coaxialmachinegun'),
    (r'm240|mg3|pkp|pkm|c6|l37|7[_.]?62',              'coaxialmachinegun_m240c'),
]

def icon_for(s):
    hay = ' '.join(filter(None, [s.get('name'), s.get('projectile'), s['asset'].split('/')[-1]])).lower()
    for pat, key in ICON_RULES:
        if re.search(pat, hay): return key
    return None

def prof(name):
    r = PROFILES.get(name)
    return (r or {}).get('values', {})

def prof_keys(name):
    r = PROFILES.get(name) or {}
    return [{'x': round(k['d'], 2), 'y': round(k['v'], 5), 'i': k['interp'], 'a': k['arrive'], 'l': k['leave']}
            for k in r.get('keys', [])]

systems, vehicles = VC.systems()
for s in systems: s['cls'] = VC.classify(s)

# ---------- icons ----------
icons, want = {}, {}
for s in systems:
    k = icon_for(s)
    s['icon'] = k
    if k: want[k] = True
for cid, label, test, emblem in VC.CLASSES: want[emblem] = True
for k in sorted(want):
    p = os.path.join(ICON_DIR, k + '.uasset')
    if not os.path.exists(p): print('  icon missing:', k); continue
    blob, _ = extract_image(p)
    if not blob: print('  no thumbnail in:', k); continue
    web, _sz = to_web(blob, 96)
    icons[k] = 'data:image/png;base64,' + base64.b64encode(web).decode()

# ---------- classes ----------
classes = []
for cid, label, test, emblem in VC.CLASSES:
    ss = [s for s in systems if s['cls'] == cid]
    if not ss: continue
    pc = collections.Counter(s['profile'] for s in ss)
    dom = pc.most_common(1)[0][0]
    v = prof(dom)
    rpms = sorted(x for x in (s['rpmPractical'] for s in ss) if x)
    models = collections.Counter(s['model'] for s in ss)
    mdl = models.most_common(1)[0][0]
    # the spread across the profiles this class actually fires
    pows, ceils, outers = [], [], []
    for pn in pc:
        pv = prof(pn)
        pows.append(pv.get('ImpactSuppressionPower') if mdl == 'blast' else pv.get('SuppressionPower'))
        ceils.append(pv.get('MaxRadialSuppressionThreshold') if mdl == 'blast' else pv.get('MaxSuppressionThreshold'))
        outers.append(pv.get('OuterRadius'))
    pows = [x for x in pows if x is not None]; ceils = [x for x in ceils if x is not None]
    outers = [x for x in outers if x is not None]
    flagship = sorted(ss, key=lambda s: (-s['variants'], len(str(s['name']))))[0]
    classes.append({
        'id': cid, 'label': label, 'emblem': emblem if emblem in icons else None, 'model': mdl,
        'count': len(ss), 'variants': sum(s['variants'] for s in ss),
        'vehicles': len({x for s in ss for x in s['vehicles']}),
        'profile': dom, 'profiles': [{'name': k, 'n': n} for k, n in pc.most_common()],
        'power': v.get('SuppressionPower'), 'ceiling': v.get('MaxSuppressionThreshold'),
        'keys': prof_keys(dom),
        'blastPower': v.get('ImpactSuppressionPower'), 'inner': v.get('InnerRadius'),
        'outer': v.get('OuterRadius'), 'radialCeiling': v.get('MaxRadialSuppressionThreshold'),
        'obstructed': v.get('ObstructedClosenessMult'),
        'powMin': min(pows) if pows else None, 'powMax': max(pows) if pows else None,
        'ceilMin': min(ceils) if ceils else None, 'ceilMax': max(ceils) if ceils else None,
        'outerMax': max(outers) if outers else None,
        'rpm': rpms[len(rpms) // 2] if rpms else None,
        'rpmMin': rpms[0] if rpms else None, 'rpmMax': rpms[-1] if rpms else None,
        'example': flagship['name'] or flagship['asset'].split('/')[-1],
    })

# ---------- the armoury ----------
weapons = []
for s in systems:
    v = prof(s['profile'])
    weapons.append({
        'name': s['name'] or s['asset'].split('/')[-1], 'cls': s['cls'], 'icon': s['icon'],
        'veh': s['vehicles'][:6], 'nveh': len(s['vehicles']),
        'vt': s['vehicleTypes'][0] if s['vehicleTypes'] else None,
        'rpm': s['rpmPractical'], 'cyclic': s['rpm'], 'mag': s['mag'], 'reload': s['reload'],
        'pen': s['penMM'], 'profile': s['profile'], 'model': s['model'],
        'power': v.get('SuppressionPower'), 'ceiling': v.get('MaxSuppressionThreshold'),
        'blastPower': v.get('ImpactSuppressionPower'), 'inner': v.get('InnerRadius'),
        'outer': v.get('OuterRadius'), 'radialCeiling': v.get('MaxRadialSuppressionThreshold'),
        'variants': s['variants'],
    })
weapons.sort(key=lambda w: (w['cls'], -(w['nveh'] or 0), str(w['name']).lower()))

# ---------- blast profiles used by vehicles, for the radius chart ----------
blast_used = collections.OrderedDict()
for s in systems:
    if s['model'] != 'blast': continue
    blast_used.setdefault(s['profile'], set()).add(s['cls'])
BLAST_LABEL = {
    'Explosion_Suppression_120mm_Barrage_NoPassby': '120 mm barrage',
    'Explosion_Suppression_155mm_Frag_NoPassby': '155 mm improvised',
    'Explosion_Suppression_120mm_Frag': 'Tank HE (120 mm)',
    'Explosion_Suppression_120mm_HEAT': 'Tank HEAT (120 mm)',
    'Explosion_Suppression_120mm_HEAT_NoPassby': 'Rocket HEAT (120 mm)',
    'Explosion_Suppression_90mm_Frag_NoPassby': 'ATGM / 90 mm frag',
    'Explosion_Suppression_90mm_Frag': '76 mm field gun frag',
    'Explosion_Suppression_90mm_HEAT_NoPassby': 'Rocket / SPG HEAT',
    'Explosion_Suppression_90mm_HEAT': '76 mm field gun HEAT',
    'Explosion_Suppression_90mm_Mortar_NoPassby': 'Mortar 81 mm',
    'Explosion_Suppression_GrenadeLauncher_NoPassby': 'Grenade launcher (AGS)',
    'Explosion_Suppression_50mm_Frag': 'Autocannon HE (50 mm)',
    'Explosion_Suppression_20mm_Frag': 'Autocannon HE (frag)',
    'Explosion_Suppression_Autocannon_HE': 'Autocannon HE (alt)',
    'Explosion_Suppression_CAS_Minigun': 'CAS minigun burst',
}
blast = []
for name, clss in blast_used.items():
    v = prof(name)
    blast.append({'label': BLAST_LABEL.get(name, name), 'profile': name,
                  'power': v.get('ImpactSuppressionPower'), 'inner': v.get('InnerRadius'),
                  'outer': v.get('OuterRadius'), 'thr': v.get('MaxRadialSuppressionThreshold'),
                  'classes': sorted(clss)})
blast.sort(key=lambda b: -(b['outer'] or 0))

vt = collections.Counter(s['vt'] for s in weapons if s['vt'])
out = {
    'classes': classes, 'weapons': weapons, 'icons': icons, 'blast': blast,
    'vtypes': [{'id': k, 'label': VT_LABEL.get(k, k), 'count': n} for k, n in vt.most_common()],
    'counts': {'assets': sum(s['variants'] for s in systems), 'systems': len(systems),
               'vehicles': len(vehicles), 'types': len(vt)},
}
p = os.path.join(HERE, 'vehicle_payload.json')
json.dump(out, open(p, 'w'), separators=(',', ':'))
print(f"vehicle_payload.json {os.path.getsize(p)/1024:.0f} KB")
print(f"  {out['counts']['assets']} assets -> {len(weapons)} systems on {out['counts']['vehicles']} vehicles | icons: {len(icons)}")
for c in classes:
    fig = (f"blast {c['blastPower']} @ {(c['inner'] or 0)/100:.1f}-{(c['outer'] or 0)/100:.1f} m ceiling {c['radialCeiling']}"
           if c['model'] == 'blast' else f"passby {c['power']} ceiling {c['ceiling']}" + (' curve' if c['keys'] else ' flat'))
    print(f"  {c['label']:24s} n={c['count']:3d} veh={c['vehicles']:3d} rpm={str(c['rpm']):>5s}  {fig}")
missing = [w['name'] for w in weapons if not w['icon']]
print(f"  systems without an icon: {len(missing)} {missing[:5]}")
