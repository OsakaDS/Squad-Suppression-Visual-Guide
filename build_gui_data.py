#!/usr/bin/env python3
"""Consolidate everything the suppression GUI needs into one JSON payload."""
import sys, os, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import squad
from curve import read_curve
import report as rifle_report

HERE = os.path.dirname(os.path.abspath(__file__))
SOLDIER = '/home/osaka/Downloads/SquadEditor/Squad/Content/Blueprints/Soldiers/PunchCurves/Suppression'

def keys_of(path):
    _, k = read_curve(path)
    return [{'x': round(x['time'], 4), 'y': round(x['value'], 5), 'interp': x['interp'],
             'arrive': x['arrive'], 'leave': x['leave']} for x in k]

data = {}
data['rifles'] = rifle_report.main()
data['profiles'] = json.load(open(os.path.join(HERE, 'all_profiles.json')))

# receiving-end curves
soldier = {}
for f in sorted(glob.glob(os.path.join(SOLDIER, '*.uasset'))):
    base = os.path.basename(f)[:-7]
    try:
        k = keys_of(f)
    except Exception:
        k = []
    if k:
        soldier[base] = k
data['soldier_curves'] = soldier

json.dump(data, open(os.path.join(HERE, 'gui_data.json'), 'w'), indent=1)
print('rifles:', len(data['rifles']))
print('profiles:', len(data['profiles']))
print('soldier curves:', len(soldier))
for k, v in soldier.items():
    print(f"   {k:60s} {[(x['x'], x['y']) for x in v]}")
