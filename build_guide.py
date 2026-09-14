#!/usr/bin/env python3
"""Inject guide_payload.json into guide.template.html -> guide.html."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
tmpl = open(os.path.join(HERE, 'guide.template.html'), encoding='utf-8').read()
if '__PAYLOAD__' not in tmpl: sys.exit('no __PAYLOAD__ placeholder')
payload = open(os.path.join(HERE, 'guide_payload.json'), encoding='utf-8').read()
out = os.path.join(HERE, 'guide.html')
open(out, 'w', encoding='utf-8').write(tmpl.replace('__PAYLOAD__', payload))
print(f"wrote {out}  ({os.path.getsize(out)/1024:.0f} KB)")
