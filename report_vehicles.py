#!/usr/bin/env python3
"""Group the vehicle weapon sweep into distinct systems and print an inspection report."""
import os, re, json, csv, collections
HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, 'vehicle_weapons_raw.json')))
rows = d['weapons']

SKIN = re.compile(r'_(Desert|Woodland|Winter|Arid|Snow|Tropic|Naval|GFI|AFU|IMF|INS|MIL|RUS|USA|CAF|AUS|UK|PLA|WPMC|TLF|ADF)(?=$|_)', re.I)
def ident(r):
    a = SKIN.sub('', r['asset'].split('/')[-1])
    return (r['vehicleType'], r['name'] or a, r['projectile'], r['profile'], r['rpm'], r['dmgMax'], r['penMM'])

def role(r):
    p = (r['projectile'] or '') + ' ' + r['asset'].split('/')[-1]
    low = p.lower()
    if r['profile'] == 'Projectile_SuppressionNone' or 'smoke' in low: return 'Smoke'
    if re.search(r'konkurs|kornet|tow|milan|fagot|shturm|atgm|9m11|9m13|hj-?\d|malyutka|metis|spike|baz', low): return 'ATGM'
    if re.search(r'mortar', low): return 'Mortar'
    if re.search(r'ags|agl|40mm_gl|grenadelauncher|gp-?25|qlz', low): return 'Grenade launcher'
    if re.search(r'm134|minigun', low): return 'Minigun'
    if re.search(r'rocket|s-?8|hydra|ffar|ub32', low): return 'Rocket'
    if re.search(r'1(05|15|20|25)mm|tankgun|2a46|2a70|m256|l30|rh120', low): return 'Tank main gun'
    if re.search(r'2(0|3|5|30)mm|30mm|40mm|45mm|50mm|57mm|73mm|autocannon|2a42|2a72|2a28|ctas|bushmaster|ztm', low): return 'Autocannon'
    if re.search(r'50cal|\.50|kpvt|dshk|nsvt|kord|qjz|m2hb|14_5|145mm', low): return 'HMG (.50/14.5)'
    if re.search(r'7_62|762|pkt|m240|coax|mg3|l37|c6', low): return 'Coax / MG (7.62)'
    return 'Other'

uniq = collections.OrderedDict()
for r in rows: uniq.setdefault(ident(r), []).append(r)
systems = []
for k, v in uniq.items():
    rep = dict(v[0]); rep['variants'] = len(v); rep['role'] = role(v[0])
    rep['vehicles'] = sorted({x['vehicle'] for x in v})
    systems.append(rep)

def fmt(x, n=2):
    return '-' if x is None else (f'{x:.{n}f}' if isinstance(x, float) else str(x))

print(f"{len(rows)} weapon assets  ->  {len(systems)} distinct systems  across {len({s['vehicleFolder'] for s in systems})} vehicle folders\n")

print('=' * 118)
print('BY ROLE'.ljust(22), 'systems  profiles used (passby power / ceiling, or blast power @ inner-outer m)')
print('=' * 118)
for rl, items in sorted(collections.Counter(s['role'] for s in systems).most_common(), key=lambda x: -x[1]):
    ss = [s for s in systems if s['role'] == rl]
    profs = collections.Counter(s['profile'] for s in ss)
    print(f"\n{rl:22s} {len(ss):3d}")
    for pf, n in profs.most_common():
        e = next(s for s in ss if s['profile'] == pf)
        if e['impactPower'] is not None:
            desc = f"blast {fmt(e['impactPower'])} · {fmt((e['innerR'] or 0)/100,1)}–{fmt((e['outerR'] or 0)/100,1)} m · ceiling {fmt(e['radialCeiling'])}"
        else:
            desc = f"passby {fmt(e['power'],3)} · ceiling {fmt(e['ceiling'])}" + (f" · curve {e['curve']}" if e['curve'] else ' · flat')
        print(f"     {n:3d}×  {pf:46s} {desc}")

print('\n' + '=' * 118)
print('HEADLINE SYSTEMS')
print('=' * 118)
hdr = f"{'weapon':34s} {'vehicle':20s} {'role':17s} {'rpm':>5s} {'dmg':>6s} {'pen':>5s} {'suppression':>34s}"
print(hdr); print('-' * 118)
want = ['M256A1', '2A46', '2A42', '2A72', '2A70', 'CTAS', 'Bushmaster', 'KPVT', 'M2', 'DShK', 'NSVT', 'Kord',
        'PKT', 'M240', 'Konkurs', 'TOW', 'M134', 'UB32', 'AGS', 'Mortar']
seen = set()
for w in want:
    for s in systems:
        tag = (s['name'] or s['asset'].split('/')[-1])
        if w.lower() not in (tag + s['asset']).lower() or s['role'] in ('Smoke',): continue
        if s['role'] in seen and w in ('M2',): continue
        supp = (f"{s['profile'][:30]}" if s['profile'] else '-')
        val = (f"blast {fmt(s['impactPower'])}" if s['impactPower'] is not None else f"passby {fmt(s['power'],3)}")
        print(f"{tag[:34]:34s} {str(s['vehicle'])[:20]:20s} {s['role'][:17]:17s} {str(s['rpm'] or '-'):>5s} "
              f"{fmt(s['dmgMax'],0):>6s} {fmt(s['penMM'],0):>5s} {supp[:22]:>22s} {val:>11s}")
        seen.add(s['role']); break

print('\n' + '=' * 118)
print('BLAST PROFILES USED BY VEHICLE WEAPONS  (radial model)')
print('=' * 118)
print(f"{'profile':48s} {'power':>7s} {'full to':>9s} {'zero at':>9s} {'ceiling':>8s}  used by")
blast = {}
for s in systems:
    if s['impactPower'] is None: continue
    blast.setdefault(s['profile'], [s, set()])[1].add(s['role'])
for pf, (s, roles) in sorted(blast.items(), key=lambda kv: -(kv[1][0]['impactPower'] or 0)):
    print(f"{pf:48s} {fmt(s['impactPower']):>7s} {fmt((s['innerR'] or 0)/100,1)+' m':>9s} "
          f"{fmt((s['outerR'] or 0)/100,1)+' m':>9s} {fmt(s['radialCeiling']):>8s}  {', '.join(sorted(roles))}")

cols = ['vehicle','vehicleType','weapon','role','asset','projectile','profile','override','rpm','mv','dmgMax','penMM',
        'mag','mags','reload','moa','power','ceiling','sway','curve','impactPower','innerR','outerR','radialCeiling',
        'expBase','expInner','expOuter','expKill','impactDmg','variants']
out = os.path.join(HERE, 'squad_vehicle_weapons.csv')
with open(out, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
    for s in sorted(systems, key=lambda s: (s['role'], str(s['vehicleType']), str(s['name']))):
        w.writerow({'vehicle': s['vehicle'], 'vehicleType': s['vehicleType'],
                    'weapon': s['name'] or s['asset'].split('/')[-1], 'role': s['role'],
                    **{k: s.get(k) for k in cols if k not in ('vehicle','vehicleType','weapon','role')}})
print(f"\nwrote {out}  ({len(systems)} rows)")
