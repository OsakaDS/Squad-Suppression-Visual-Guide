#!/usr/bin/env python3
"""Bundle every frozen version into the payloads the pages inject as __VERSIONS__.

Writes versions_guide.json (infantry and vehicle tabs) and versions_page.json (data page),
both values only: the art is carried once by the page itself.
"""
import os, re, json

HERE = os.path.dirname(os.path.abspath(__file__))
STORE = os.path.join(HERE, 'versions')

def sort_key(v):
    """v10.5.3 sorts before v10.6.0; anything unparseable sorts last by name"""
    nums = [int(x) for x in re.findall(r'\d+', v)]
    return (0, nums) if nums else (1, [], v)

def main():
    order, data, meta = [], {}, {}
    if os.path.isdir(STORE):
        for ver in sorted(os.listdir(STORE), key=sort_key):
            d = os.path.join(STORE, ver)
            if not os.path.isdir(d): continue
            parts = {}
            for name in ('guide', 'vehicle', 'page'):
                fp = os.path.join(d, name + '.json')
                if os.path.exists(fp): parts[name] = json.load(open(fp))
            if not parts: continue
            order.append(ver); data[ver] = parts
            mf = os.path.join(d, 'meta.json')
            meta[ver] = json.load(open(mf)) if os.path.exists(mf) else {'version': ver}
    # each page carries only the parts it draws, so the guide does not ship the data
    # page's weapon list and the other way round
    base = {'order': order, 'current': order[-1] if order else None, 'meta': meta}
    for fname, parts in (('versions_guide.json', ('guide', 'vehicle')),
                         ('versions_page.json', ('page',))):
        out = dict(base, data={v: {k: d[k] for k in parts if k in d} for v, d in data.items()})
        p = os.path.join(HERE, fname)
        json.dump(out, open(p, 'w'), separators=(',', ':'))
        print('%-22s %d version(s): %-24s %5.0f KB'
              % (fname, len(order), ', '.join(order) or 'none', os.path.getsize(p) / 1024))

if __name__ == '__main__':
    main()
