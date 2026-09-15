#!/usr/bin/env python3
"""Sweep every infantry firearm in the game and resolve its suppression profile."""
import sys, os, json, glob, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import squad
from curve import read_curve

ITEMS = '/home/osaka/Downloads/SquadEditor/Squad/Content/Blueprints/Items'
CATS = ['Rifles', 'MachineGuns', 'Pistols', 'SubmachineGuns', 'Shotguns',
        'GrenadeLaunchers', 'RocketLaunchers']

def txt(v):
    return v.get('text') if isinstance(v, dict) else None

def walk(cat):
    out = []
    for f in sorted(glob.glob(os.path.join(ITEMS, cat, '**', '*.uasset'), recursive=True)):
        rel = os.path.relpath(f, ITEMS)[:-7].replace(os.sep, '/')
        base = os.path.basename(rel)
        if not base.startswith('BP_'): continue
        if '/StaticInfo/' in '/'+rel or 'StaticInfo' in base: continue
        out.append((cat, '/Game/Blueprints/Items/' + rel))
    return out

rows, errors = [], []
for cat in CATS:
    for c, gp in walk(cat):
        try:
            pkg = squad.load(gp)
            if pkg is None: continue
            res, wc = squad.merged(gp)
            proj = wc.get('ProjectileClass')
            if not proj or not proj[0]: continue
            ovr = res.get('SuppressionInfoClassOverride')
            si = ovr[0] if (ovr and ovr[0]) else squad.suppression_for_projectile(proj[0])
            vals = squad.suppression_values(si) if si else {}
            dn = res.get('DisplayName'); tex = res.get('HUDSelectedTexture')
            rate = wc.get('TimeBetweenShots')
            # bolt-actions keep their real cycle time on the StaticInfo, not in WeaponConfig
            bolt, bolt_t = None, None
            sinfo = res.get('ItemStaticInfoClass')
            if sinfo and sinfo[0]:
                sres, _ = squad.merged(sinfo[0])
                bolt = sres.get('bRequiresManualBolt', (None,))[0]
                bolt_t = sres.get('ManualBoltingCompletionTime', (None,))[0]
            fm = wc.get('Firemodes', (None,))[0]     # burst lengths: 1 = semi, -1 = full auto
            rows.append({
                'cat': c,
                'asset': gp.replace('/Game/Blueprints/Items/', ''),
                'name': txt(dn[0]) if dn else None,
                'icon': tex[0] if tex else None,
                'projectile': (proj[0] or '').split('/')[-1].split('.')[0],
                'profile': (si or '').split('/')[-1].split('.')[0] or None,
                'override': bool(ovr and ovr[0]),
                'override_src': (ovr[1].split('/')[-1] if (ovr and ovr[0]) else None),
                'tbs': round(rate[0], 5) if rate else None,
                'bolt': bool(bolt), 'bolt_time': round(bolt_t, 3) if bolt_t else None,
                'firemodes': fm if isinstance(fm, list) else None,
                'mv': wc.get('MuzzleVelocity', (None,))[0],
                'moa': wc.get('MOA', (None,))[0],
                'mag': wc.get('RoundsPerMag', (None,))[0],
                'pen': wc.get('ArmorPenetrationDepthMillimeters', (None,))[0],
                'power': vals.get('SuppressionPower'),
                'thr': vals.get('MaxSuppressionThreshold'),
                'sway': vals.get('AddSuppressSway'),
                'curve': (vals.get('PowerToDistanceCurve') or '').split('/')[-1].split('.')[0] or None,
            })
        except Exception as e:
            errors.append((gp, repr(e)))

json.dump({'rows': rows, 'errors': errors}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'all_weapons_raw.json'), 'w'), indent=1)
print('weapons resolved:', len(rows), '| errors:', len(errors))
from collections import Counter
print('\nby category asset folder:'); [print('   %-18s %d' % (k, v)) for k, v in Counter(r['cat'] for r in rows).items()]
print('\nby suppression profile:'); [print('   %-42s %d' % (k, v)) for k, v in Counter(r['profile'] for r in rows).most_common()]
print('\nunnamed:', sum(1 for r in rows if not r['name']), '| no icon:', sum(1 for r in rows if not r['icon']))
for e in errors[:5]: print('ERR', e)
