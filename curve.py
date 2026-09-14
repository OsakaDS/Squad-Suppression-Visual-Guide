import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uasset import Package

INTERP = {0:'Linear',1:'Constant',2:'Cubic',3:'None'}

def read_curves(path):
    """CurveFloat -> {'': keys}; CurveVector -> {'X': keys, 'Y': keys, 'Z': keys}"""
    p = Package(path)
    out = {}
    for e in p.exports:
        for pr in p.export_props(e):
            if pr['name'] in ('FloatCurve', 'FloatCurves') and isinstance(pr['value'], dict):
                keys = []
                for sp in pr['value'].get('props', []):
                    if sp['name'] == 'Keys':
                        v = sp['value']; n = v['count']; off = v['raw_range'][0]
                        for k in range(n):
                            o = off + k*27
                            t, val, at, atw, lt, ltw = struct.unpack_from('<6f', p.d, o+3)
                            keys.append({'time': t, 'value': val, 'interp': INTERP.get(p.d[o], p.d[o]), 'arrive': at, 'leave': lt})
                axis = 'XYZ'[pr['index']] if pr['name'] == 'FloatCurves' else ''
                out[axis] = keys
    return out

def read_curve(path):
    p = Package(path)
    out = []
    for e in p.exports:
        for pr in p.export_props(e):
            if pr['name'] == 'FloatCurve' and isinstance(pr['value'], dict):
                for sp in pr['value'].get('props', []):
                    if sp['name'] == 'Keys':
                        v = sp['value']; n = v['count']; off = v['raw_range'][0]
                        for k in range(n):
                            o = off + k*27
                            interp, tanmode, tanwm = p.d[o], p.d[o+1], p.d[o+2]
                            t, val, at, atw, lt, ltw = struct.unpack_from('<6f', p.d, o+3)
                            out.append({'time': t, 'value': val, 'interp': INTERP.get(interp, interp),
                                        'arrive': at, 'leave': lt})
    return p, out

if __name__ == '__main__':
    for f in sys.argv[1:]:
        p, keys = read_curve(f)
        print(f"== {f}")
        for k in keys:
            print(f"   dist={k['time']:>10.2f}  power_mult={k['value']:<8.4f} interp={k['interp']}")
