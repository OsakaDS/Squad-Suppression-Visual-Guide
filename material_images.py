#!/usr/bin/env python3
"""Pull a surface image for each physical material out of the editor thumbnails.

Physical materials carry no art of their own, so the image has to come one hop away,
from a visual material that references them. Two sources exist, both already stored in
the assets as content-browser thumbnails:

  texture   the material's base colour texture, a flat surface swatch. Much the better
            of the two, and what this script tries first.
  material  the material instance's own thumbnail, a rendered sphere. Used as a fallback.

KNOWN LIMITATION: automatic selection gets the solid building materials right (brick,
plaster, mud wall, concrete, rock, sheet metal, floorboards, gravel, sand, asphalt,
dirt) and fails on terrain and foliage, which are landscape layer blends or foliage
shaders with no single base colour texture. Those fall through to whatever else the
material references, often a particle sheet. Three rounds of selection rules each fixed
some and broke others, so the remaining ones want a hand-picked source recorded in
CURATED below rather than a cleverer heuristic.

Images are written to material_images/, which is not committed: it is extracted game art
and it rebuilds from the assets in about a minute.
"""
import os, re, io, sys, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uasset import Package
import squad, textures

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = '/home/osaka/Downloads/SquadEditor/Squad/Content/'
OUT = os.path.join(HERE, 'material_images')

# hand-picked sources for the materials the heuristic cannot resolve:
#   'PhysMat_Grass': '/Game/Environments/.../T_Grass_A'
CURATED = {}

ALBEDO = re.compile(r'(_a|_d|_bc|_basecolor|_albedo|_diffuse|_col)$', re.I)
NOT_ALBEDO = re.compile(r'_n$|_m$|_or$|_orm$|_rough|_norm|mixmap|_mask|default|_h$|_ao$', re.I)
BAD_SOURCE = re.compile(r'particle|/vfx|_vfx|decal|dust|smoke|debris|niagara|_fx|_development', re.I)

def material_files():
    """every visual material asset worth searching"""
    out = []
    for args in (['-iname', 'M_*.uasset', '-o', '-iname', 'MI_*.uasset'],
                 ['-ipath', '*materials*', '-name', '*.uasset']):
        out += subprocess.run(['find', CONTENT + 'Environments'] + args,
                              capture_output=True, text=True).stdout.split('\n')
    out += subprocess.run(['find', CONTENT + 'Vehicles', '-ipath', '*material*', '-name', '*.uasset'],
                          capture_output=True, text=True).stdout.split('\n')
    return sorted({p for p in out if p.endswith('.uasset')})

def build_map(files):
    """which visual materials name which physical material"""
    listing = '\n'.join(files)
    proc = subprocess.run(['xargs', '-d', '\n', 'grep', '-aoH', '-E', 'PhysMat_[A-Za-z0-9_]+'],
                          input=listing, capture_output=True, text=True)
    m = {}
    for line in proc.stdout.split('\n'):
        if ':PhysMat_' not in line: continue
        f, pm = line.rsplit(':', 1)
        m.setdefault(pm, set()).add(os.path.relpath(f, CONTENT))
    return {k: sorted(v) for k, v in m.items()}

_is_tex = {}
def is_texture(fp):
    if fp not in _is_tex:
        try: _is_tex[fp] = any('Texture' in str(p.resolve(e['class'])) for p in [Package(fp)] for e in p.exports)
        except Exception: _is_tex[fp] = False
    return _is_tex[fp]

def image_from(gpath):
    fp = squad.asset_path(gpath)
    if not fp or not os.path.exists(fp) or not is_texture(fp): return None
    try:
        blob, _ = textures.extract_image(fp)
        if blob: return blob
    except Exception: pass
    return None

def pick(pm, files):
    if pm in CURATED:
        blob = image_from(CURATED[pm])
        if blob: return blob, CURATED[pm].split('/')[-1], 'curated'
    key = [w for w in pm.replace('PhysMat_', '').lower().split('_') if len(w) > 2]
    ranked = sorted([f for f in files if not BAD_SOURCE.search(f)] or files,
                    key=lambda f: (0 if any(w in os.path.basename(f).lower() for w in key) else 1, len(f)))[:12]
    for f in ranked:                                    # the base colour texture first
        try: pkg = Package(CONTENT + f)
        except Exception: continue
        for n in pkg.names:
            if not n.startswith('/Game/'): continue
            base = n.split('/')[-1]
            if not ALBEDO.search(base) or NOT_ALBEDO.search(base) or BAD_SOURCE.search(n): continue
            blob = image_from(n)
            if blob: return blob, base, 'texture'
    for f in ranked:                                    # then the sphere render
        try:
            blob, _ = textures.extract_image(CONTENT + f)
            if blob: return blob, os.path.basename(f)[:-7], 'material'
        except Exception: continue
    return None, None, None

def main():
    os.makedirs(OUT, exist_ok=True)
    mats = {r['name'] for r in json.load(open(os.path.join(HERE, 'all_materials.json')))['materials']}
    print('searching material assets...')
    m = build_map(material_files())
    print('physical materials referenced by a visual material: %d of %d' % (len(mats & set(m)), len(mats)))
    got, kinds = {}, {}
    from PIL import Image
    for pm in sorted(mats):
        blob, src, kind = pick(pm, m.get(pm, []))
        if not blob: continue
        try: im = Image.open(io.BytesIO(blob)).convert('RGB')
        except Exception: continue
        im.save(os.path.join(OUT, pm + '.png'))
        got[pm] = {'source': src, 'kind': kind}
        kinds[kind] = kinds.get(kind, 0) + 1
    json.dump(got, open(os.path.join(HERE, 'material_images.json'), 'w'), indent=1)
    print('images written: %d  %s' % (len(got), kinds))
    missing = sorted(mats - set(got))
    if missing: print('no image (%d): %s' % (len(missing), ', '.join(x.replace('PhysMat_', '') for x in missing)))

if __name__ == '__main__':
    main()
