#!/usr/bin/env python3
"""Inject guide_payload.json into guide.template.html -> guide.html."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
payload = open(os.path.join(HERE, 'guide_payload.json'), encoding='utf-8').read()
for src, dst in [('guide.template.html', 'guide.html'), ('guide_v2.template.html', 'guide_v2.html')]:
    if not os.path.exists(os.path.join(HERE, src)): continue
    tmpl = open(os.path.join(HERE, src), encoding='utf-8').read()
    if '__PAYLOAD__' not in tmpl: sys.exit(f'{src}: no __PAYLOAD__ placeholder')
    out = os.path.join(HERE, dst)
    open(out, 'w', encoding='utf-8').write(tmpl.replace('__PAYLOAD__', payload))
    print(f"wrote {out}  ({os.path.getsize(out)/1024:.0f} KB)")
