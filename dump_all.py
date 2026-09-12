#!/usr/bin/env python3
"""Dump every suppression profile + curve in the game to JSON."""
import sys, os, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import squad
from curve import read_curve

SI_DIR = '/home/osaka/Downloads/SquadEditor/Squad/Content/Blueprints/Items/Projectiles/SuppressionInfo'
GAME = '/Game/Blueprints/Items/Projectiles/SuppressionInfo/'

profiles = {}
for f in sorted(glob.glob(os.path.join(SI_DIR, '*.uasset'))):
    base = os.path.basename(f)[:-7]
    if base.startswith('FC_'):
        continue
    gp = GAME + base
    pkg = squad.load(gp)
    if pkg is None:
        continue
    real = pkg.package_name.split('/')[-1]          # after redirector follow
    vals = squad.suppression_values(gp + '.' + real + '_C')
    if not vals:
        continue
    def load_keys(cpath):
        if not cpath: return []
        fp = squad.asset_path(cpath)
        if fp and os.path.exists(fp):
            _, k = read_curve(fp)
            return [{'d': x['time'], 'v': x['value'], 'interp': x['interp'],
                     'arrive': x['arrive'], 'leave': x['leave']} for x in k]
        return []
    cpath = vals.get('PowerToDistanceCurve')
    ipath = vals.get('ImpactSuppressionDistanceCurve')
    keys = load_keys(cpath)
    ikeys = load_keys(ipath)
    profiles[base] = {
        'name': base,
        'redirects_to': real if real != base else None,
        'values': {k: v for k, v in vals.items() if isinstance(v, (int, float))},
        'curve': (cpath or '').split('/')[-1].split('.')[0] or None,
        'keys': keys,
        'impact_curve': (ipath or '').split('/')[-1].split('.')[0] or None,
        'impact_keys': ikeys,
    }

json.dump(profiles, open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
          'all_profiles.json'), 'w'), indent=1)
print(f"{len(profiles)} profiles")
for k, v in profiles.items():
    vv = v['values']
    p = vv.get('SuppressionPower'); ip = vv.get('ImpactSuppressionPower')
    rng = max((x['d'] for x in v['keys']), default=None)
    irng = vv.get('OuterRadius')
    print(f"  {k:46s} pass={p} r={rng} | impact={ip} inner={vv.get('InnerRadius')} outer={irng} thr={vv.get('MaxRadialSuppressionThreshold')}")
