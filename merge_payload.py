#!/usr/bin/env python3
"""One payload for the page: profiles, curves, every weapon, every icon."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
base = json.load(open(os.path.join(HERE, 'payload.json')))       # profiles / flat / blast / soldier
allw = json.load(open(os.path.join(HERE, 'all_weapons.json')))   # weapons / icons / catIcons

# 'none' (smoke and signalling rounds) is deliberately excluded from the dashboard
CAT_ORDER = ['rifle','battlerifle','dmr','sniper','lsw','lmg','mmg','smg','hmg','explosive']
CAT_LABEL = {'rifle':'Rifle','battlerifle':'Battle rifle','dmr':'DMR','sniper':'Sniper rifle',
             'lsw':'LSW','lmg':'LMG','mmg':'MMG','smg':'SMG / pistol','hmg':'Shotgun / HMG',
             'explosive':'Explosive','none':'No suppression'}
CAT_NOTE = {
  'rifle':'Assault rifles and carbines — one shared profile across every faction.',
  'battlerifle':'Full-power semi-autos. Triple the punch on a close pass, gone by 2 m.',
  'dmr':'Scoped marksman rifles. Enormous close-pass power, a 2.0 ceiling.',
  'sniper':'Bolt actions and heavy semi-autos. The hardest single round in the game.',
  'lsw':'Squad automatic weapons on the light support profile.',
  'lmg':'Belt-fed 5.56. The flattest curve — still working at 6 m.',
  'mmg':'7.62 general-purpose guns. Widest envelope at 7 m and a 1.75 ceiling.',
  'smg':'Submachine guns, sidearms and subsonics. The weakest passby in the game.',
  'hmg':'Shotguns and the KS-23 sit on flat, curve-free profiles — full power at any distance.',
  'explosive':'Launched ordnance. Zero passby power; suppresses radially on detonation instead.',
  'none':'Smoke and signalling rounds. No suppression at all.',
}
# profile a category maps to, for the passby chart
CAT_PROFILE = {'rifle':'Rifle','battlerifle':'BattleRifle','dmr':'PrecisionRifle','sniper':'SniperRifle',
               'lsw':'LSW','lmg':'LMG','mmg':'MMG','smg':'SMG'}

cats = []
for c in CAT_ORDER:
    ws = [w for w in allw['weapons'] if w['cat'] == c]
    if not ws: continue
    cats.append({'id': c, 'label': CAT_LABEL[c], 'note': CAT_NOTE[c], 'count': len(ws),
                 'icon': allw['catIcons'].get(c), 'iconSrc': allw['catSource'].get(c),
                 'profileId': CAT_PROFILE.get(c)})

keep = {c['id'] for c in cats}
weapons = [w for w in allw['weapons'] if w['cat'] in keep]
used = {w['iconKey'] for w in weapons if w.get('iconKey')}
base['weapons'] = weapons
base['icons'] = {k: v for k, v in allw['icons'].items() if k in used}
base['cats'] = cats
base['counts'] = {'weapons': len(weapons),
                  'assets': sum(w['variants'] for w in weapons),
                  'profiles': len({w['profile'] for w in weapons})}
json.dump(base, open(os.path.join(HERE, 'page_payload.json'), 'w'), separators=(',', ':'))
n = os.path.getsize(os.path.join(HERE, 'page_payload.json'))
print(f"payload {n/1024:.0f} KB | weapons {len(base['weapons'])} | assets {base['counts']['assets']} "
      f"| icons {len(base['icons'])} | cats {len(cats)}")
for c in cats: print(f"   {c['label']:16s} {c['count']:>3}  icon={c['iconSrc']}")
