#!/usr/bin/env python3
"""One source of truth for how vehicle weapon assets are grouped.

Two steps:
  systems()  collapses the 546 weapon assets into distinct weapon systems, folding
             away faction skins (BP_..._Desert and BP_..._Woodland are one gun).
  CLASSES    buckets those systems the way a player would name them, and each bucket
             carries the suppression model its rounds use: a passby profile, a radial
             blast profile, or neither.
"""
import os, re, json, collections

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'vehicle_weapons_raw.json')

SKIN = re.compile(r'_(Desert|Woodland|Winter|Arid|Snow|Tropic|Naval|GFI|AFU|IMF|INS|MIL|RUS|USA|CAF|AUS|UK|PLA|WPMC|TLF|ADF)(?=$|_)', re.I)


def ident(r):
    """what makes two assets the same weapon system"""
    a = SKIN.sub('', r['asset'].split('/')[-1])
    return (r['vehicleType'], r['name'] or a, r['projectile'], r['profile'],
            r['rpm'], r['dmgMax'], r['penMM'])


def role(r):
    """the player-facing name for what kind of weapon this is"""
    low = ((r['projectile'] or '') + ' ' + r['asset'].split('/')[-1] + ' ' + (r['name'] or '')).lower()
    if r['profile'] == 'Projectile_SuppressionNone' or 'smoke' in low:      return 'Smoke'
    if re.search(r'coax|pkt|m240c|mag58|qtj', low):                         return 'Coax / MG (7.62)'
    if re.search(r'spg-?9|og-?9|pg-?9|zis3|76mm|recoilless', low):          return 'Recoilless / field gun'
    if re.search(r'konkurs|kornet|tow|milan|fagot|shturm|atgm|9m1|hj-?\d|'
                 r'malyutka|metis|spike|baz|stugna|at3|skif', low):         return 'ATGM'
    if re.search(r'mortar|hell_?cannon|propane', low):                      return 'Mortar / barrage'
    if re.search(r'ags|agl|40mm_gl|grenadelauncher|gp-?25|qlz|mk-?19', low):return 'Grenade launcher'
    if re.search(r'm134|minigun|gau-?17', low):                            return 'Minigun'
    if re.search(r'rocket|s-?5|s-?8|hydra|ffar|ub32|type-?57|m151|m156', low): return 'Rocket'
    if re.search(r'1(05|15|20|25)mm|100mm|tankgun|2a46|2a70|m256|l30|rh120', low): return 'Tank main gun'
    if re.search(r'2(0|3|5|30)mm|30mm|40mm|45mm|50mm|57mm|73mm|autocannon|'
                 r'2a42|2a72|2a28|ctas|bushmaster|ztm', low):              return 'Autocannon'
    if re.search(r'50cal|\.50|kpvt|kpv|dshk|nsvt|nsv|kord|qjz|m2hb|m2a1|m2 |'
                 r'browning|gau-?21|m3p|14_5|145mm', low):                 return 'HMG (.50 / 14.5)'
    if re.search(r'7_62|762|m240|mg3|l37|c6|pkp|pkm|mg42', low):            return 'Coax / MG (7.62)'
    return 'Other'


def model(s):
    """which of the two suppression models this system's rounds use"""
    if s['profile'] == 'Projectile_SuppressionNone': return 'none'
    if s['impactPower'] is not None: return 'blast'
    return 'passby'


def family(s):
    """HEAT / HE-frag / AP, read off the profile name"""
    p = (s['profile'] or '')
    if 'HEAT' in p: return 'HEAT'
    if 'Frag' in p or 'Barrage' in p: return 'HE'
    if '_AP' in p: return 'AP'
    return None


def practical_rpm(s):
    """a one-shot gun cycles on its reload, not on TimeBetweenShots, the same
    correction the bolt-action rifles needed"""
    if s['mag'] == 1 and s['reload']: return round(60 / s['reload'])
    return s['rpm']


def systems(path=RAW):
    d = json.load(open(path))
    uniq = collections.OrderedDict()
    for r in d['weapons']:
        uniq.setdefault(ident(r), []).append(r)
    out = []
    for group in uniq.values():
        s = dict(group[0])
        s['variants'] = len(group)
        s['vehicles'] = sorted({x['vehicle'] for x in group})
        s['vehicleTypes'] = sorted({x['vehicleType'] for x in group if x['vehicleType']})
        s['role'] = role(group[0])
        s['model'] = model(s)
        s['family'] = family(s)
        s['rpmPractical'] = practical_rpm(s)
        out.append(s)
    return out, d['vehicles']


# id, label, predicate. A class is a role, split by suppression model where a role
# fires both kinds of round (an autocannon's AP belt and its HE belt are not the same
# threat), and tank rounds are split again because HEAT and HE have different radii.
def _is(rl, md=None, fam=None):
    return lambda s: s['role'] == rl and (md is None or s['model'] == md) and (fam is None or s['family'] == fam)

CLASSES = [
    ('coax',     'Coax MG (7.62)',            _is('Coax / MG (7.62)'),                  'coaxialmachinegun'),
    ('hmg',      'Heavy MG (.50 / 14.5)',     _is('HMG (.50 / 14.5)'),                  'm2browning'),
    ('minigun',  'Minigun',                   _is('Minigun'),                           'T_M134'),
    ('acap',     'Autocannon, AP',            _is('Autocannon', 'passby'),              '30mm_ap'),
    ('tankap',   'Tank gun, sabot',           _is('Tank main gun', 'passby'),           'tank_sabot'),
    ('achE',     'Autocannon, HE',            _is('Autocannon', 'blast'),               '30mm_he'),
    ('tankheat', 'Tank gun, HEAT',            _is('Tank main gun', 'blast', 'HEAT'),    'tank_heat'),
    ('tankhe',   'Tank gun, HE',              _is('Tank main gun', 'blast', 'HE'),      'tank_frag'),
    ('atgm',     'ATGM',                      _is('ATGM'),                              'kornet'),
    ('rocket',   'Rockets',                   _is('Rocket'),                            's5rocket'),
    ('gl',       'Grenade launcher',          _is('Grenade launcher'),                  'T_MK19'),
    ('mortar',   'Mortar / barrage',          _is('Mortar / barrage'),                  '81mm_mortar_he'),
    ('rr',       'Recoilless / field gun',    _is('Recoilless / field gun'),            'pg7v_heat'),
    ('smoke',    'Smoke',                     _is('Smoke'),                             'vehiclesmokelaunchers'),
]


def classify(s):
    for cid, label, test, icon in CLASSES:
        if test(s): return cid
    return None


if __name__ == '__main__':
    sys_, veh = systems()
    print(f"{len(sys_)} systems, {len(veh)} vehicles")
    unplaced = [s for s in sys_ if classify(s) is None]
    for cid, label, test, icon in CLASSES:
        ss = [s for s in sys_ if classify(s) == cid]
        pf = collections.Counter(s['profile'] for s in ss)
        print(f"  {label:26s} {len(ss):3d}  {', '.join(f'{k.replace('Explosion_Suppression_','E_').replace('Projectile_Suppression','P')}×{v}' for k, v in pf.most_common(3))}")
    print(f"  {'UNPLACED':26s} {len(unplaced):3d}  {[s['name'] for s in unplaced][:6]}")
