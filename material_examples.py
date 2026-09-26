#!/usr/bin/env python3
"""Two examples of each physical material as the engine renders it.

For every SQPhysicalMaterial, find the visual materials that reference it and keep up to
two, each with the pair of images the SDK already stores:

  compiled   the material instance's own thumbnail, which is UE's render of the compiled
             material on a sphere. This is literally what the engine makes of it.
  texture    that material's base colour texture, the flat art the surface is built from.

Development, VFX and decal materials are skipped, and a name match against the physical
material is preferred, so the examples are surfaces actually used on the maps.

Writes material_examples/ (not committed: extracted game art) and material_examples.json.
"""
import os, re, io, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uasset import Package
import squad, textures
from material_images import (CONTENT, material_files, build_map, image_from,
                             ALBEDO, NOT_ALBEDO, BAD_SOURCE)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'material_examples')
N_EXAMPLES = 2

def thumb(rel):
    try:
        blob, _ = textures.extract_image(CONTENT + rel)
        if blob: return Image.open(io.BytesIO(blob)).convert('RGB')
    except Exception: pass
    return None

# shared overlays that every other material also references, and so say nothing about it
GENERIC = re.compile(r'dirt_0\d|grunge|noise|detail|blank|generic|global|default|wetness|puddle|snow_cover', re.I)

def _tokens(name):
    return {w for w in re.split(r'[^a-z0-9]+', name.lower()) if len(w) > 2 and w not in
            ('the', 'mat', 'mi', 'sm', 'tex', 'new', 'old', 'var', 'inst')}

def albedo_of(rel):
    """the base colour texture, preferring one that shares a word with the material itself"""
    try: pkg = Package(CONTENT + rel)
    except Exception: return None, None
    own = _tokens(os.path.basename(rel)[:-7])
    cands = []
    for n in pkg.names:
        if not n.startswith('/Game/'): continue
        base = n.split('/')[-1]
        if not ALBEDO.search(base) or NOT_ALBEDO.search(base) or BAD_SOURCE.search(n): continue
        score = 0
        if own & _tokens(base): score += 20
        if GENERIC.search(base): score -= 25
        cands.append((-score, n, base))
    for _, n, base in sorted(cands):
        blob = image_from(n)
        if blob:
            try: return Image.open(io.BytesIO(blob)).convert('RGB'), base
            except Exception: continue
    return None, None

def rank(files, pm):
    key = [w for w in pm.replace('PhysMat_', '').lower().split('_') if len(w) > 2]
    clean = [f for f in files if not BAD_SOURCE.search(f)] or files
    def score(f):
        b = os.path.basename(f)[:-7].lower()
        return (0 if any(w in b for w in key) else 1, 0 if b.startswith('mi_') else 1, len(f))
    return sorted(clean, key=score)

def main():
    from PIL import Image as _I
    globals()['Image'] = _I
    os.makedirs(OUT, exist_ok=True)
    mats = {r['name']: r for r in json.load(open(os.path.join(HERE, 'all_materials.json')))['materials']}
    m = build_map(material_files())
    out = {}
    for pm in sorted(mats):
        picks = []
        for rel in rank(m.get(pm, []), pm):
            if len(picks) >= N_EXAMPLES: break
            comp = thumb(rel)
            if comp is None: continue
            tex, texname = albedo_of(rel)
            base = '%s__%d' % (pm, len(picks) + 1)
            comp.save(os.path.join(OUT, base + '_compiled.png'))
            if tex is not None: tex.save(os.path.join(OUT, base + '_texture.png'))
            picks.append({'material': rel, 'name': os.path.basename(rel)[:-7],
                          'compiled': base + '_compiled.png',
                          'texture': (base + '_texture.png') if tex is not None else None,
                          'textureName': texname})
        if picks: out[pm] = picks
    json.dump(out, open(os.path.join(HERE, 'material_examples.json'), 'w'), indent=1)
    two = sum(1 for v in out.values() if len(v) >= 2)
    tex = sum(1 for v in out.values() for e in v if e['texture'])
    print('materials with an example: %d of %d (%d have two)' % (len(out), len(mats), two))
    print('example images: %d compiled renders, %d base colour textures'
          % (sum(len(v) for v in out.values()), tex))

if __name__ == '__main__':
    main()
