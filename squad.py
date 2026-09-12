import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uasset import Package
from curve import read_curve

CONTENT = '/home/osaka/Downloads/SquadEditor/Squad/Content'
_cache = {}

_dircache = {}
def asset_path(game_path):
    """/Game/Foo/Bar.Bar_C -> Content/Foo/Bar.uasset (case-insensitive fallback)"""
    if not game_path: return None
    gp = game_path.split('.')[0]
    if not gp.startswith('/Game/'): return None
    p = os.path.join(CONTENT, gp[len('/Game/'):] + '.uasset')
    if os.path.exists(p): return p
    d, base = os.path.split(p)
    if not os.path.isdir(d): return p
    if d not in _dircache:
        _dircache[d] = {f.lower(): f for f in os.listdir(d)}
    hit = _dircache[d].get(base.lower())
    return os.path.join(d, hit) if hit else p

def load(game_path, _depth=0):
    fp = asset_path(game_path)
    if not fp or not os.path.exists(fp): return None
    if fp not in _cache:
        try: _cache[fp] = Package(fp)
        except Exception: _cache[fp] = None
    pkg = _cache[fp]
    if pkg is not None and _depth < 4:
        tgt = redirect_target(pkg)
        if tgt: return load(tgt, _depth + 1)
    return pkg


def redirect_target(pkg):
    """if package is an ObjectRedirector, return the destination /Game path"""
    import struct
    for e in pkg.exports:
        if pkg.resolve(e['class']) == '/Script/CoreUObject.ObjectRedirector' or 'ObjectRedirector' in str(pkg.resolve(e['class'])):
            o, s = e['offset'], e['size']
            if s >= 4:
                idx = struct.unpack_from('<i', pkg.d, o + s - 4)[0]
                if idx < 0:
                    k = -idx - 1
                    if k < len(pkg.imports):
                        imp = pkg.imports[k]
                        outer = imp['outer']
                        if outer < 0 and -outer - 1 < len(pkg.imports):
                            pkgname = pkg.imports[-outer - 1]['name']
                            if pkgname.startswith('/Game'):
                                return f"{pkgname}.{imp['name']}"
    return None

def cdo_props(pkg):
    c = pkg.cdo()
    if not c: return {}
    out = {}
    for pr in pkg.export_props(c):
        out[pr['name']] = pr['value']
    return out

def parent_of(pkg):
    for e in pkg.exports:
        if e['name'].endswith('_C') and not e['name'].startswith('Default__'):
            return pkg.resolve(e['super'])
    return None

def chain(game_path, maxdepth=12):
    """returns list of (path, pkg) from most-derived up"""
    out = []
    seen = set()
    cur = game_path
    for _ in range(maxdepth):
        if not cur or cur in seen: break
        seen.add(cur)
        pkg = load(cur)
        if pkg is None: break
        out.append((cur, pkg))
        cur = parent_of(pkg)
        if cur and not cur.startswith('/Game'): break
    return out

def flat(prop):
    """flatten nested struct props into dict"""
    if isinstance(prop, dict) and 'props' in prop:
        return {p['name']: p['value'] for p in prop['props']}
    return {}

def merged(game_path, key=None):
    """walk chain, most-derived wins"""
    result = {}
    wc = {}
    for path, pkg in chain(game_path):
        props = cdo_props(pkg)
        for k, v in props.items():
            result.setdefault(k, (v, path))
        for k, v in flat(props.get('WeaponConfig')).items():
            wc.setdefault(k, (v, path))
    return result, wc

def suppression_for_projectile(proj_class):
    res, _ = merged(proj_class)
    si = res.get('SuppressionInfoClass')
    return si[0] if si else None

def suppression_values(si_class):
    res, _ = merged(si_class)
    return {k: v[0] for k, v in res.items()}

def weapon_report(weapon_game_path):
    res, wc = merged(weapon_game_path)
    proj = wc.get('ProjectileClass')
    proj_class = proj[0] if proj else None
    ovr = res.get('SuppressionInfoClassOverride')
    si_proj = suppression_for_projectile(proj_class) if proj_class else None
    si = ovr[0] if (ovr and ovr[0]) else si_proj
    src_of_si = ('weapon override: ' + ovr[1]) if (ovr and ovr[0]) else ('projectile: ' + str(proj_class))
    vals = suppression_values(si) if si else {}
    curve_path = vals.get('PowerToDistanceCurve')
    keys = []
    if curve_path:
        fp = asset_path(curve_path)
        if fp and os.path.exists(fp):
            _, keys = read_curve(fp)
    return {
        'weapon': weapon_game_path,
        'projectile': proj_class,
        'projectile_src': proj[1] if proj else None,
        'suppression_class': si,
        'suppression_source': src_of_si,
        'suppression_class_from_projectile': si_proj,
        'values': vals,
        'curve': curve_path,
        'curve_keys': keys,
        'weapon_config': {k: v[0] for k, v in wc.items()},
        'chain': [c[0] for c in chain(weapon_game_path)],
    }
