#!/usr/bin/env python3
"""Freeze the current build as a named game version.

The pages carry the icon art once and the numbers once per version. Roughly 960 KB of
a 1.25 MB page is art, so a frozen version costs only its values: about 85 KB for the
infantry tab, 96 KB for the vehicle tab and 317 KB for the data page.

Run it after ./build.sh whenever a Squad update has been extracted:

    python3 snapshot_version.py                 # uses the version in guide_payload.json
    python3 snapshot_version.py --version v10.6.0 --notes "autocannon HE reworked"

Weapons keep their icon key, so an older version still draws art from the current set.
A weapon whose icon was removed by a later update simply shows no picture.
"""
import os, sys, json, argparse, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.join(HERE, 'versions')
ART = ('icons', 'logo', 'logoSmall')          # shared across versions, never duplicated

SOURCES = {                                    # frozen file <- built payload
    'guide':   'guide_payload.json',
    'vehicle': 'vehicle_payload.json',
    'page':    'page_payload.json',
}

def strip_art(d):
    return {k: v for k, v in d.items() if k not in ART}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--version', help='defaults to the version inside guide_payload.json')
    ap.add_argument('--notes', default='', help='one line shown beside the version in the toggle')
    ap.add_argument('--force', action='store_true', help='overwrite an existing snapshot')
    a = ap.parse_args()

    guide = json.load(open(os.path.join(HERE, SOURCES['guide'])))
    ver = a.version or guide.get('version')
    if not ver: sys.exit('no version given and none in guide_payload.json')

    out = os.path.join(STORE, ver)
    if os.path.exists(out) and not a.force:
        sys.exit(f'{ver} is already frozen. Pass --force to overwrite it.')
    os.makedirs(out, exist_ok=True)

    sizes = {}
    for name, src in SOURCES.items():
        p = os.path.join(HERE, src)
        if not os.path.exists(p):
            print(f'  skipped {name}: {src} not built'); continue
        data = strip_art(json.load(open(p)))
        fp = os.path.join(out, name + '.json')
        json.dump(data, open(fp, 'w'), separators=(',', ':'))
        sizes[name] = os.path.getsize(fp)

    meta = {'version': ver, 'notes': a.notes,
            'frozen': datetime.date.today().isoformat(),
            'parts': {k: round(v / 1024) for k, v in sizes.items()}}
    json.dump(meta, open(os.path.join(out, 'meta.json'), 'w'), indent=1)
    print(f"froze {ver}  ({', '.join('%s %d KB' % (k, v/1024) for k, v in sizes.items())})")
    print(f"  -> {os.path.relpath(out, HERE)}")

if __name__ == '__main__':
    main()
