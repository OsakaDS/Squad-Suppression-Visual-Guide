"""Pull an icon out of a .uasset.

Editor assets embed a content-browser thumbnail: the texture composited over the
editor's grey checkerboard (values 128 / 64), stored as PNG or JPEG. Squad's
inventory icons are white silhouettes, so the alpha that the checkerboard destroyed
can be recovered as (luma - 128) / 127 and the colour reset to white.
"""
import os, io, sys, struct

def extract_image(path):
    d = open(path, 'rb').read()
    i = d.find(b'\x89PNG\r\n\x1a\n')
    if i != -1:
        j = i + 8
        while j + 8 <= len(d):
            ln = struct.unpack_from('>I', d, j)[0]
            typ = d[j+4:j+8]
            j += 8 + ln + 4
            if typ == b'IEND': return d[i:j], 'png'
            if ln > len(d): break
    i = d.find(b'\xff\xd8\xff')
    if i != -1:
        j = d.rfind(b'\xff\xd9')
        if j > i: return d[i:j+2], 'jpeg'
    return None, None

def to_web(blob, max_w=104, keep_colour=False):
    from PIL import Image
    im = Image.open(io.BytesIO(blob))
    im.load()
    if keep_colour:
        rgba = im.convert('RGBA')
    else:
        luma = im.convert('L')
        alpha = luma.point(lambda v: 0 if v <= 128 else min(255, round((v - 128) * 255 / 127)))
        white = Image.new('L', im.size, 255)
        rgba = Image.merge('RGBA', (white, white, white, alpha))
    bbox = rgba.getchannel('A').getbbox()
    if bbox: rgba = rgba.crop(bbox)
    if rgba.width > max_w:
        h = max(1, round(rgba.height * max_w / rgba.width))
        rgba = rgba.resize((max_w, h), Image.LANCZOS)
    # a white silhouette + alpha compresses hard as a palette-free greyscale+alpha PNG
    out = io.BytesIO()
    rgba.convert('LA').save(out, 'PNG', optimize=True)
    return out.getvalue(), rgba.size

def extract_png(path):        # kept for the older scripts
    return extract_image(path)[0]

if __name__ == '__main__':
    for p in sys.argv[1:]:
        b, kind = extract_image(p)
        if not b: print(p, 'NO IMAGE'); continue
        w, size = to_web(b)
        print(f"{os.path.basename(p):34s} {kind:4s} raw={len(b):>7} web={len(w):>6} {size}")
