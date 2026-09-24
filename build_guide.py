#!/usr/bin/env python3
"""Inject the payloads into the guide templates.

guide.template.html carries two: __PAYLOAD__ (infantry) and __VPAYLOAD__ (vehicles).
The v2 draft only ever had the first, so the vehicle one is optional."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
payload = open(os.path.join(HERE, 'guide_payload.json'), encoding='utf-8').read()
vpath = os.path.join(HERE, 'vehicle_payload.json')
vpayload = open(vpath, encoding='utf-8').read() if os.path.exists(vpath) else None

for src, dst in [('guide.template.html', 'guide.html'), ('guide_v2.template.html', 'guide_v2.html')]:
    if not os.path.exists(os.path.join(HERE, src)): continue
    tmpl = open(os.path.join(HERE, src), encoding='utf-8').read()
    if '__PAYLOAD__' not in tmpl: sys.exit(f'{src}: no __PAYLOAD__ placeholder')
    out_html = tmpl.replace('__PAYLOAD__', payload)
    if '__VPAYLOAD__' in out_html:
        if vpayload is None: sys.exit(f'{src}: wants __VPAYLOAD__ but vehicle_payload.json is missing')
        out_html = out_html.replace('__VPAYLOAD__', vpayload)
    out = os.path.join(HERE, dst)
    open(out, 'w', encoding='utf-8').write(out_html)
    print(f"wrote {out}  ({os.path.getsize(out)/1024:.0f} KB)")
