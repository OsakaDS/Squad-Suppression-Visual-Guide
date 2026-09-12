# Squad suppression toolkit

Extracts the suppression system out of **Squad v10.5.3** and turns it into a browsable
web page. Nothing here is scraped from a wiki or measured in-game — every number is read
directly out of the shipped `.uasset` binaries in the Squad Mod SDK.

The output is a single self-contained HTML file covering **477 weapons**, their suppression
profiles, the distance curves behind them, and the soldier-side effects. Page by
**Osaka [29th ID]**.

The extraction resolves all 521 firearms in the game; the 44 that carry
`Projectile_SuppressionNone` — smoke and signalling rounds, which suppress nothing — are
kept in the CSV but excluded from the dashboard.

```
Squad Mod SDK (.uasset)  ──▶  parser  ──▶  JSON  ──▶  one HTML file  ──▶  any web server
   246 GB of assets            ~1 s              1.3 MB, no backend
```

---

## Why this exists

Squad's suppression is undocumented and widely misunderstood. Ask around and you will be
told that heavier calibres suppress harder, or that suppression falls off with range to
the shooter. Both are wrong, and the assets say so plainly:

- Every assault rifle in the game — M4A1, AK-74M, L85A2, QBZ95-1, AKM — shares **one
  identical profile**. Calibre, faction and muzzle velocity change nothing. Only rate of
  fire separates them.
- The distance that matters is **how close the round passed you**, not how far away the
  shooter was. A sniper at 600 m and a rifleman at 40 m apply identical pressure if their
  rounds pass the same distance from your head.
- Shotguns are the hardest suppressors in the game per trigger pull, sitting on a flat
  curve-free profile that applies full power at any distance.

You cannot get to any of that by playing. You get to it by reading the data.

## Quick start

Requires Python 3.8+ and a copy of the Squad Mod SDK. `pip install pillow` is needed only
for icon extraction.

```bash
./build.sh          # rebuild everything from the assets (~1 second)
python3 serve.py    # then open the printed LAN URL
```

If you only want the data, `squad_all_weapons_suppression.csv` is already in this
directory — 521 rows, one per weapon, with power sampled at 1/2/3/4 m. That file is the
complete set, smoke rounds included.

Point the toolkit at a different SDK install by editing `CONTENT` at the top of
`squad.py`; `extract_all.py`, `dump_all.py` and `build_gui_data.py` each hold one
absolute path to a subdirectory of it.

---

## The model, as the data describes it

Suppression is a property of **the round in flight**, not of the gun. Resolution runs:

```
weapon BP ── WeaponConfig.ProjectileClass ──▶ projectile BP
                                                  │
                              SuppressionInfoClass │
                                                  ▼
                                          profile asset  ──▶  PowerToDistanceCurve
                                       (SQSuppressionInfo)
```

…unless the weapon sets **`SuppressionInfoClassOverride`**, which discards the
projectile's choice outright. **183 of 521 weapons do this.** It is the normal mechanism,
not an exception: the AKM fires a 7.62 mm round whose default profile is machine-gun
grade, and overrides itself back down to the ordinary rifle profile. The G3 and M14 use
it in the opposite direction.

### Passby — a round goes past you

`PowerToDistanceCurve` maps **perpendicular miss distance** (Unreal units, 100 uu = 1 m)
to suppression added per round. Every small-arms envelope dies at 5–7 m; outside it a
passing round does nothing at all. Totals accumulate and clamp at
`MaxSuppressionThreshold`, so a weapon's real advantage is how fast it pins you.

| Profile | Power @1 m | Envelope | Ceiling | Rounds to cap @1 m |
|---|---|---|---|---|
| Rifle | 0.125 | 5.0 m | 1.15 | 10 |
| Battle rifle | 0.300 | 5.0 m | 1.15 | 4 |
| MMG | 0.350 | 7.0 m | 1.75 | 5 |
| LMG | 0.200 | 6.0 m | 1.25 | 7 |
| LSW | 0.300 | 5.0 m | 1.25 | 5 |
| SMG / pistol | 0.100 | 5.0 m | 1.15 | 12 |
| DMR | 2.000 | 5.0 m | 2.00 | 1 |
| Sniper rifle | 3.000 | 5.0 m | 3.00 | 1 |
| Shotgun / HMG | 0.500 | flat — no curve | 2.00 | 4 |

A single sniper round passing at 1 m fills its entire ceiling. Shotguns and the KS-23
have no curve at all, so their flat value applies at any miss distance.

### Blast — a separate, larger model

Explosives zero their passby power and suppress radially instead, using
`ImpactSuppressionPower` and `ImpactSuppressionDistanceCurve` between `InnerRadius` and
`OuterRadius`, against their own `MaxRadialSuppressionThreshold`. A hand grenade is
**5.5 power out to 22.5 m** against a rifle round's 0.125 at 1 m — roughly forty rifle
rounds arriving at once, against a ceiling of 6.5 rather than 1.15.

### Two independent selections on the page

The page carries two pickers that deliberately do **not** talk to each other. The pair at
the top — weapon type and weapon — drives the passby and build-up sections: the type
supplies the curve, the weapon supplies only its rate of fire. The armoury further down is
a lookup; picking a weapon there traces its asset wiring in the section beneath it and
changes nothing above.

### The receiving end

Soldier-side curves work from a 0–1 **closeness ratio**. Flinch is a step function, not a
ramp: nothing below 0.33, then 0.6, then full past 0.67. Near misses also bank
**immunity** — 1 point past 0.33 closeness, 2 past 0.67 — and immunity reduces camera
punch to 0.35× and weapon-alignment punch to 0.30× at 7.5 points. Stay under fire long
enough and you shoot back nearly steady.

---

## How the extraction works

### Why parse the binaries directly

The Mod SDK ships **Win64 binaries only** — there is no Linux `UnrealEditor` to run a
commandlet with, and `Engine/Source` contains just `Developer/` and `Programs/`, so the
CoreUObject source isn't available to consult either. The assets are uncooked editor
packages, which is good news: they still carry a name table and tagged properties in the
clear.

### UE 5.7 package layout

`uasset.py` implements just enough of the format. Four details cost the most time to work
out, and they are what a naive parser gets wrong:

**1. The property tag.** UE 5.4 replaced the old type FName with `FPropertyTypeName`:

```
Name      FName        8 bytes  (name-table index + number)
TypeName  FName        8 bytes  + int32 param count + that many nested type names
Size      int32        4 bytes
Flags     uint8        1 byte   bit0 = ArrayIndex follows, bit1 = 16-byte guid, bit2 = extensions
Value     Size bytes
```

`ArrayIndex` is **only written when non-zero**. Assuming a fixed 4-byte field there
shifts every value by four bytes and yields plausible-looking garbage.

**2. The summary.** After the package-name FString: `PackageFlags`, `NameCount`/`Offset`,
soft-object-path count/offset, then a `LocalizationId` FString that leaves the following
fields **unaligned**, then gatherable-text, export and import counts and offsets. Import
entries are 40 bytes, export entries 112.

**3. `FRichCurveKey` is 27 bytes** — three enum bytes (interp, tangent, tangent weight)
followed by six floats: time, value, arrive tangent, arrive weight, leave tangent, leave
weight. `curve.py` reads these, and the page evaluates them the way UE does, including
cubic segments as a Bézier built from the stored tangents.

**4. ObjectRedirectors are everywhere.** `Projectile_Suppression_GPMG` is not a profile —
it is a redirector to `Projectile_Suppression_MMG`. The destination is the package index
in the last four bytes of the 17-byte export blob. `squad.py` follows them transparently;
without that, five weapon classes resolve to nothing.

Blueprint defaults only store properties that **differ from the parent**, so reading a
weapon means walking its `_C` class chain upward and merging — most-derived wins. That is
what `squad.merged()` does, and why `BP_AK74M` looks nearly empty on its own while
`BP_GenericRifle` three levels up holds the projectile class.

### Icons

Uncooked textures don't expose usable source art. But every asset embeds a
**content-browser thumbnail**: the texture composited over the editor's grey
checkerboard, stored as PNG (or JPEG in some assets). Squad's inventory icons are white
silhouettes, so the alpha the checkerboard destroyed comes back as:

```python
alpha = clamp((luma - 128) / 127)      # 128/64 checker -> 0, white weapon -> opaque
```

`textures.py` does this, giving 382 clean weapon icons plus 11 category emblems taken
from the game's own role art. Category emblems are matched to profiles by hand — Squad
ships no per-profile artwork.

---

## Reproducing it

`./build.sh` runs the chain below. It is byte-reproducible: run it twice and the output
files hash identically.

| Step | Script | Produces |
|---|---|---|
| 1 | `extract_all.py` | `all_weapons_raw.json` — every weapon asset, resolved |
| 2 | `build_all.py` | `all_weapons.json` — grouped weapons + base64 icons |
| 3 | `dump_all.py` | `all_profiles.json` — all 58 suppression profiles |
| 4 | `report.py` | `squad_rifle_suppression.{csv,json}` — ten-rifle sample |
| 5 | `build_gui_data.py` | `gui_data.json` — profiles, curves, soldier data |
| 6 | `build_payload.py` | `payload.json` — the page's base payload |
| 7 | `merge_payload.py` | `page_payload.json` — + weapons and icons |
| 8 | `build_page.py` | `suppression.html` — template + payload |
| 9 | `make_site.py` | `site/index.html` — standalone document |

Edit the page itself in **`suppression.template.html`**, never in `suppression.html` —
the latter is generated and your changes will be overwritten by step 8.

`make_site.py` exists because the page is authored as an artifact body. Serving it
yourself needs a doctype, `<meta charset="utf-8">` and a favicon that the artifact host
would otherwise supply. Without the charset tag every en dash and middot on the page
renders as mojibake.

## Extending it to other data

The parser knows nothing about suppression specifically. To pull a different system:

1. Find an asset that mentions it: `grep -al "Penetration" **/*.uasset` — note that
   **`grep` needs `-a`** on these files, or it silently reports nothing.
2. Dump its properties to see the field names:
   ```python
   from uasset import Package
   p = Package('BP_Projectile.uasset')
   for pr in p.export_props(p.cdo()):
       print(pr['name'], pr['type'], pr['value'])
   ```
3. Use `squad.merged('/Game/...')` to resolve inherited values across the blueprint chain.
4. Follow object references with `squad.load()`, which handles redirectors for you.

`Content/Blueprints/Items/` holds infantry weapons; `Content/Vehicles/*/Weapons/` holds
vehicle armament; `Content/Gameplay/DamageCurves/` and `PenetrationCurves/` are the
obvious next targets and are already readable with `curve.py`.

## Limits

Read directly from the assets: every power, ceiling, radius, sway value and curve key,
the full weapon → projectile → profile wiring, display names, and icons.

**Inferred, not stated:** that the curve's X axis is perpendicular miss distance rather
than range to shooter — the property is `PowerToDistanceCurve`, its companion is
`ObstructedClosenessMult`, and a 5 m envelope only makes sense as closeness. Also that
`SuppressionPower` is the fallback used when a profile has no curve, which is how the
shotgun and tank profiles are shaped.

**Not available at all:** the decay rate once fire stops, the mapping from a suppression
value to the screen effect, and how the closeness ratio is normalised. All three live in
`/Script/Squad` — compiled C++ that the Mod SDK ships without source. Anything claiming
to know those numbers is guessing.

## Layout

| | |
|---|---|
| `uasset.py` | UE 5.7 package reader — names, imports, exports, tagged properties |
| `curve.py` | `FRichCurve` key decoding |
| `textures.py` | icon recovery from asset thumbnails |
| `squad.py` | blueprint chains, property merging, redirector following |
| `suppression.template.html` | the page — edit this one |
| `serve.py` | gzipping static server for the LAN |
| `site/index.html` | the built page |

See **[RUNBOOK.md](RUNBOOK.md)** for hosting commands — LAN, systemd, Docker and public
static hosts.
