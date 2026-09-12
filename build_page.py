#!/usr/bin/env python3
"""Inject page_payload.json into the page template -> suppression.html."""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TMPL = os.path.join(HERE, 'suppression.template.html')
DATA = os.path.join(HERE, 'page_payload.json')
OUT  = os.path.join(HERE, 'suppression.html')

tmpl = open(TMPL, encoding='utf-8').read()
if '__PAYLOAD__' not in tmpl:
    sys.exit(f'{TMPL} has no __PAYLOAD__ placeholder')
payload = open(DATA, encoding='utf-8').read()
open(OUT, 'w', encoding='utf-8').write(tmpl.replace('__PAYLOAD__', payload))
print(f"wrote {OUT}  ({os.path.getsize(OUT)/1024:.0f} KB, payload {len(payload)/1024:.0f} KB)")
