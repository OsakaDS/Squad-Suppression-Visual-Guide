#!/usr/bin/env python3
"""Sweep every vehicle-mounted and emplaced weapon in the game.

Vehicle weapons use the same SQWeaponData WeaponConfig as infantry weapons, so the
resolution chain is identical: weapon -> ProjectileClass -> SuppressionInfoClass, with
SuppressionInfoClassOverride taking precedence. Explosive rounds additionally carry the
radial blast model (ImpactSuppressionPower / Inner+OuterRadius / MaxRadialSuppressionThreshold).
"""
import sys, os, re, json, glob, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import squad

VEH = '/home/osaka/Downloads/SquadEditor/Squad/Content/Vehicles/'
SKIP = re.compile(r'turret|reticle|wreck|destroy|seat|anim|camera|widget|hud|scope|sight|mesh|skin', re.I)

def txt(v):
    return v.get('text') if isinstance(v, dict) else None

# ---------- 1. what each vehicle folder is ----------
def classify(chain_names, vtype):
    if vtype: return str(vtype).split('::')[-1]
    j = ' '.join(chain_names)
    if 'Helicopter' in j: return 'Helicopter'
    if 'Deployable' in j or 'Emplaced' in j: return 'Emplacement'
    return None

vehicles = {}
for folder in sorted(os.listdir(VEH)):
    if not os.path.isdir(VEH + folder): continue
    for f in sorted(glob.glob(VEH + folder + '/BP_*.uasset')):
        base = os.path.basename(f)[:-7]
        if SKIP.search(base): continue
        gp = f'/Game/Vehicles/{folder}/{base}'
        try:
            res, _ = squad.merged(gp)
        except Exception:
            continue
        if not res: continue
        chain = [p.split('/')[-1].split('.')[0] for p, _ in squad.chain(gp)]
        vt = res.get('VehicleType', (None,))[0]
        cls = classify(chain, vt)
        if not cls: continue
        dn = res.get('DisplayName')
        vehicles.setdefault(folder, {'folder': folder, 'bp': base, 'type': cls,
                                     'name': txt(dn[0]) if dn else None, 'chain': chain})
        break

# ---------- 2. every weapon asset under a vehicle folder ----------
rows, errors = [], []
paths = []
for sub in ('Weapons', 'Attachments', 'Turrets', ''):
    paths += glob.glob(VEH + f'*/{sub}/**/*.uasset' if sub else VEH + '*/*.uasset', recursive=True)
seen = set()
for f in sorted(set(paths)):
    base = os.path.basename(f)[:-7]
    if not base.startswith('BP_'): continue
    rel = os.path.relpath(f, VEH)[:-7].replace(os.sep, '/')
    folder = rel.split('/')[0]
    if rel in seen: continue
    seen.add(rel)
    gp = '/Game/Vehicles/' + rel
    try:
        res, wc = squad.merged(gp)
        proj = wc.get('ProjectileClass')
        if not proj or not proj[0]: continue                    # not a weapon
        ovr = res.get('SuppressionInfoClassOverride')
        si = ovr[0] if (ovr and ovr[0]) else squad.suppression_for_projectile(proj[0])
        sv = squad.suppression_values(si) if si else {}
        pres, _ = squad.merged(proj[0])                          # the round itself
        dn = res.get('DisplayName')
        rate = wc.get('TimeBetweenShots', (None,))[0]
        fm = wc.get('Firemodes', (None,))[0]
        rows.append({
            'asset': rel, 'vehicleFolder': folder,
            'vehicle': (vehicles.get(folder) or {}).get('name') or folder,
            'vehicleType': (vehicles.get(folder) or {}).get('type'),
            'name': txt(dn[0]) if dn else None,
            'projectile': (proj[0] or '').split('/')[-1].split('.')[0],
            'damageType': (pres.get('DamageTypeToApply', ('',))[0] or '').split('/')[-1].split('.')[0],
            # the round's own explosive stats (HE/HEAT shells, rockets, mortar bombs)
            'expBase': pres.get('ExplosiveBaseDamage', (None,))[0],
            'expInner': pres.get('ExplosiveDamageInnerRadius', (None,))[0],
            'expOuter': pres.get('ExplosiveDamageOuterRadius', (None,))[0],
            'expKill': pres.get('ExplosiveKillZoneRadius', (None,))[0],
            'expMin': pres.get('ExplosiveMinimumDamage', (None,))[0],
            'impactDmg': pres.get('ImpactDamageToApply', (None,))[0],
            'projPen': pres.get('ArmorPenetrationDepthMillimeters', (None,))[0],
            'explosionClass': (pres.get('ExplosionClass', ('',))[0] or '').split('/')[-1].split('.')[0],
            'profile': (si or '').split('/')[-1].split('.')[0] or None,
            'override': bool(ovr and ovr[0]),
            'rpm': round(60 / rate) if rate else None,
            'tbs': rate,
            'firemodes': fm if isinstance(fm, list) else None,
            'mv': round(wc.get('MuzzleVelocity', (0,))[0] / 100) or None if wc.get('MuzzleVelocity') else None,
            'dmgMax': wc.get('MaxDamageToApply', (None,))[0],
            'dmgMin': wc.get('MinDamageToApply', (None,))[0],
            'penMM': wc.get('ArmorPenetrationDepthMillimeters', (None,))[0],
            'mag': wc.get('RoundsPerMag', (None,))[0],
            'mags': wc.get('MaxMags', (None,))[0],
            'reload': wc.get('TacticalReloadDuration', (None,))[0],
            'moa': wc.get('MOA', (None,))[0],
            # passby suppression
            'power': sv.get('SuppressionPower'), 'ceiling': sv.get('MaxSuppressionThreshold'),
            'sway': sv.get('AddSuppressSway'), 'curve': (sv.get('PowerToDistanceCurve') or '').split('/')[-1].split('.')[0] or None,
            # radial / blast suppression
            'impactPower': sv.get('ImpactSuppressionPower'), 'innerR': sv.get('InnerRadius'),
            'outerR': sv.get('OuterRadius'), 'radialCeiling': sv.get('MaxRadialSuppressionThreshold'),
        })
    except Exception as e:
        errors.append((rel, repr(e)))

out = {'vehicles': vehicles, 'weapons': rows, 'errors': errors}
HERE = os.path.dirname(os.path.abspath(__file__))
json.dump(out, open(os.path.join(HERE, 'vehicle_weapons_raw.json'), 'w'), indent=1)
print(f"vehicles classified: {len(vehicles)} | weapon assets resolved: {len(rows)} | errors: {len(errors)}")
print('\nby vehicle type:')
for t, n in collections.Counter(r['vehicleType'] for r in rows).most_common():
    print(f'   {str(t):16s} {n}')
print('\nby suppression profile:')
for p, n in collections.Counter(r['profile'] for r in rows).most_common(20):
    print(f'   {str(p):46s} {n}')
for e in errors[:5]: print('ERR', e)
