#!/usr/bin/env python3
"""Sweep every physical material in the game and the penetration model around it.

Squad puts penetration on the material, not on the surface type. An SQPhysicalMaterial
carries an armour value in millimetres and a damage cost for passing through it; a weapon
carries ArmorPenetrationDepthMillimeters, and the heavy calibres additionally carry an
ArmorPenetrationDepthCurve keyed on distance. A round gets through when its penetration
meets the material's thickness.

How DamageAbsorbed combines with the round's damage is compiled C++ and stays UNKNOWN.

Writes all_materials.json and squad_materials.csv.
"""
import os, sys, csv, json, glob, subprocess, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uasset import Package
from curve import read_curves
import squad

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = '/home/osaka/Downloads/SquadEditor/Squad/Content'
ENGINE_INI = '/home/osaka/Downloads/SquadEditor/Squad/Config/DefaultEngine.ini'
PEN_CURVES = os.path.join(CONTENT, 'Gameplay', 'PenetrationCurves')

# the 29 named surface types are for effects and sound; penetration does not use them
def surface_names():
    out = {}
    for line in open(ENGINE_INI, encoding='utf-8', errors='ignore'):
        if line.startswith('+PhysicalSurfaces='):
            out[line.split('Type=')[1].split(',')[0]] = line.split('Name="')[1].split('"')[0]
    return out

def find_materials():
    """physical materials are named by convention; there is no cheap way to find them by class"""
    cmd = ['find', CONTENT, '-iname', '*physmat*.uasset', '-o', '-iname', '*phys_mat*.uasset']
    out = subprocess.run(cmd, capture_output=True, text=True).stdout.split('\n')
    return sorted(p for p in out if p.endswith('.uasset'))

KEYS = ['ArmorThicknessMillimeters', 'DamageAbsorbed', 'bConsiderForPenetration',
        'bAllowPenetration', 'bDamageParentActor', 'Friction', 'StaticFriction', 'Restitution']

def main():
    surf = surface_names()
    rows, seen = [], set()
    for fp in find_materials():
        try: pkg = Package(fp)
        except Exception: continue
        for e in pkg.exports:
            if 'PhysicalMaterial' not in str(pkg.resolve(e['class'])): continue
            p = {pr['name']: pr['value'] for pr in pkg.export_props(e)}
            rel = os.path.relpath(fp, CONTENT)[:-7].replace(os.sep, '/')
            if rel in seen: continue
            seen.add(rel)
            st = p.get('SurfaceType')
            rows.append({'name': e['name'], 'path': rel,
                         'surface': surf.get(str(st), str(st) if st is not None else None),
                         **{k: p.get(k) for k in KEYS}})
    rows.sort(key=lambda r: (-(r['ArmorThicknessMillimeters'] or 0), r['name']))

    curves = {}
    for f in sorted(glob.glob(os.path.join(PEN_CURVES, '*.uasset'))):
        try: cs = read_curves(f)
        except Exception: continue
        for _, ks in cs.items():
            if not ks: continue
            # X reads as metres: a .50 losing most of its penetration over 2000 only makes
            # sense as 2 km, and the same curves start at the weapon's flat millimetre value
            curves[os.path.basename(f)[:-7].replace('_ArmorPenetrationCurve', '')] = \
                [{'m': round(k['time'], 1), 'mm': round(k['value'], 1)} for k in ks]

    json.dump({'materials': rows, 'penetrationCurves': curves},
              open(os.path.join(HERE, 'all_materials.json'), 'w'), indent=1, default=str)
    cols = ['name', 'surface', 'ArmorThicknessMillimeters', 'DamageAbsorbed',
            'bConsiderForPenetration', 'bAllowPenetration', 'bDamageParentActor', 'path']
    with open(os.path.join(HERE, 'squad_materials.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        for r in rows: w.writerow(r)

    armoured = [r for r in rows if r['ArmorThicknessMillimeters'] is not None]
    print('physical materials: %d (%d with an armour value)' % (len(rows), len(armoured)))
    print('penetration curves: %d' % len(curves))
    cover = [r for r in armoured if 'Vehicles/' not in r['path']]
    g = collections.defaultdict(list)
    for r in cover: g[r['ArmorThicknessMillimeters']].append(r['name'].replace('PhysMat_', ''))
    print('\ncover by armour value:')
    for mm in sorted(g):
        print('  %5d mm  %s' % (mm, ', '.join(sorted(g[mm]))[:86]))

if __name__ == '__main__':
    main()
