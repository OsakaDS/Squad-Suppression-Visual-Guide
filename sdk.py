#!/usr/bin/env python3
"""Where the Squad Mod SDK lives. One place, so a new install is a one-line change.

Resolution order:
  1. the SQUAD_SDK environment variable
  2. the SDK_PATH file beside this script
  3. the first of the known defaults that exists

The SDK is a separate download from the game and lags behind it, so the game being on
a new patch does not mean these assets are. check() compares the SDK's own version.txt
against the VERSION file the pages are stamped with, and complains when they disagree.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULTS = [
    '/mnt/ssd2/Games/epic-games-store/drive_c/Program Files/Epic Games/SquadEditor/Squad',
    '/home/osaka/Downloads/SquadEditor/Squad',
]

def sdk_root():
    env = os.environ.get('SQUAD_SDK')
    if env: return env.rstrip('/')
    f = os.path.join(HERE, 'SDK_PATH')
    if os.path.exists(f):
        p = open(f, encoding='utf-8').read().strip()
        if p: return p.rstrip('/')
    for p in DEFAULTS:
        if os.path.isdir(os.path.join(p, 'Content')): return p
    return DEFAULTS[-1]

ROOT = sdk_root()
CONTENT = os.path.join(ROOT, 'Content')
CONFIG = os.path.join(ROOT, 'Config')

def sdk_version(default=None):
    try: return open(os.path.join(ROOT, 'version.txt'), encoding='utf-8').read().strip()
    except OSError: return default

def stamped_version(default='v10.5.3'):
    try: return open(os.path.join(HERE, 'VERSION'), encoding='utf-8').read().strip() or default
    except OSError: return default

def check(verbose=True):
    """warn loudly when the pages would be stamped with a version the SDK does not hold"""
    s, v = sdk_version(), stamped_version()
    ok = (s is not None and s == v)
    if verbose:
        print(f"SDK {ROOT}")
        print(f"    sdk version.txt = {s or 'unknown'} | VERSION file = {v}"
              + ('' if ok else '   <-- MISMATCH'))
        if not ok:
            print("    the extraction will carry the SDK's values but be labelled with VERSION.")
    return ok

if __name__ == '__main__':
    sys.exit(0 if check() else 1)
