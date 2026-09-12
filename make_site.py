#!/usr/bin/env python3
"""Wrap the artifact body into a standalone, self-hostable HTML document.

The Artifact host supplies <!doctype>, <head>, charset and a small reset. A file
served by your own web server gets none of that, so we add it here.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(HERE, 'suppression.html')
OUT  = os.path.join(HERE, 'site', 'index.html')

body = open(SRC, encoding='utf-8').read()
title = re.search(r'<title>(.*?)</title>', body).group(1)
body = body.replace(f'<title>{title}</title>', '', 1).lstrip()

DESC = ("How suppression works in Squad v10.5.3 — every weapon, profile and curve "
        "read straight out of the game's .uasset files.")
FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E"
           "%3Ctext y='.9em' font-size='90'%3E%F0%9F%92%A2%3C/text%3E%3C/svg%3E")

doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{DESC}">
<meta name="color-scheme" content="light dark">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{DESC}">
<meta property="og:type" content="website">
<link rel="icon" href="{FAVICON}">
<style>
  html{{color-scheme:light dark}}
  body{{margin:0}}
  img{{max-width:100%}}
  [hidden]{{display:none!important}}
</style>
{body}
</body>
</html>
"""
os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, 'w', encoding='utf-8').write(doc)
n = os.path.getsize(OUT)
print(f"wrote {OUT}  ({n/1024:.0f} KB)")
