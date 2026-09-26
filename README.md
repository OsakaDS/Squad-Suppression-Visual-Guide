# Squad suppression toolkit

Extracts the suppression system out of **Squad v10.5.3** and turns it into a browsable
web page. Nothing here is scraped from a wiki or measured in-game. Every number is read
directly out of the shipped `.uasset` binaries in the Squad Mod SDK.

The output is two self-contained HTML pages by **Osaka [29th ID]**:

- **`guide.html`** is the field guide for players, in two tabs. **Infantry Weapons** covers the
  eight kits (shotguns are left out for now), each with the game's role emblem, a
  fireteam-against-a-target tool and an armoury of what is in each kit. **Vehicle Weapons** covers
  every vehicle-mounted and emplaced weapon in the game, grouped into fourteen classes, with an
  under-fire-from-a-vehicle tool of its own. Every figure is labelled READ / INFERRED / UNKNOWN.
- **`suppression.html`** is the data page for modders: all **521 weapons** with icons, the
  asset wiring behind each one, and every profile curve.

Both are branded with the 29th Infantry Division logo (`branding/`).

```
Squad Mod SDK (.uasset)  ──▶  parser  ──▶  JSON  ──▶  one HTML file  ──▶  any web server
   246 GB of assets            ~1 s              1.3 MB, no backend
```

---

## Why this exists

Squad's suppression is undocumented and widely misunderstood. Ask around and you will be
told that heavier calibres suppress harder, or that suppression falls off with range to
the shooter. Both are wrong, and the assets say so plainly:

- Every assault rifle in the game (M4A1, AK-74M, L85A2, QBZ95-1, AKM) shares **one
  identical profile**. Calibre, faction and muzzle velocity change nothing. Only rate of
  fire separates them.
- The distance that matters is **how close the round passed you**, not how far away the
  shooter was. A sniper at 600 m and a rifleman at 40 m apply identical pressure if their
  rounds pass the same distance from your head.
- Rifle fire alone can never blur, desaturate or dirty your screen. Every screen effect
  except the vignette switches on above the highest suppression level a rifle can reach
  (1.15); the heavy effects belong to marksmen, snipers and explosives.

You cannot get to any of that by playing. You get to it by reading the data.

## Quick start

Requires Python 3.8+ and a copy of the Squad Mod SDK. `pip install pillow` is needed only
for icon extraction.

```bash
./build.sh          # rebuild everything from the assets (~1 second)
python3 serve.py    # then open the printed LAN URL
```

If you only want the data, `squad_all_weapons_suppression.csv` is already in this
directory, 521 rows, one per weapon, with power sampled at 1/2/3/4 m.

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

### Passby: a round goes past you

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
| Precision Rifle (DMR) | 2.000 | 5.0 m | 2.00 | 1 |
| Sniper rifle | 3.000 | 5.0 m | 3.00 | 1 |
| Shotgun / HMG | 0.500 | flat, no curve | 2.00 | 4 |

A single sniper round passing at 1 m fills its entire ceiling. Shotguns and the KS-23 have
no curve at all, one flat value instead of a distance curve. How far out that value still
applies, and whether it counts per pellet, is decided in the game's C++ and isn't known,
which is why shotguns are left out of the field guide for now.

### Blast: a separate, larger model

Explosives zero their passby power and suppress radially instead, using
`ImpactSuppressionPower` and `ImpactSuppressionDistanceCurve` between `InnerRadius` and
`OuterRadius`, against their own `MaxRadialSuppressionThreshold`. A hand grenade is
**5.5 power out to 22.5 m** against a rifle round's 0.125 at 1 m, roughly forty rifle
rounds arriving at once, against a ceiling of 6.5 rather than 1.15.

### The receiving end

The soldier blueprint's node graph was decoded in full. See `SUPPRESSION_LOGIC.md`.
Squad's C++ hands the blueprint each round's result, including the new suppression level
and a 0–1 **closeness ratio**, and the blueprint reacts:

- **Punch.** Every round that adds suppression kicks the target's camera and weapon,
  scaled by how close it passed, by the target's current immunity, and by the target's own
  weapon if he is aiming down sights, and finally by a random 0.75–1.25, in a random direction.
  Nothing about the shooter's weapon enters the blueprint's kick calculation.
- **Immunity** is a 0–7.5 number on the soldier under fire. It rises 1.0 per second while
  he is "actively suppressed", a state that lasts 1 second after each qualifying round,
  and drains 1.0 per second otherwise. The first round of a fresh engagement kicks at full
  strength, then grants 1.0 or 2.0 immunity at once depending on closeness. At 7.5, camera
  location punch is 0.35×, camera rotation 0.60× and weapon alignment 0.30×; most of that
  reduction arrives in the first two points. Immunity only reduces the kick, not the
  suppression level, the screen effects or the sway.
- **Flinch** has curves in the assets, but they belong to an experimental first-shot flinch
  the developers left disabled (*"Experimental and not currently used"*). It is not live.
- **Screen effects** key on the suppression level: vignette from 0, film grain from 1.0,
  desaturation and colour shift from 1.4, chromatic aberration from 1.9, blur and screen
  dirt from about 3.0, fisheye from 5.0.

---

## How the extraction works

### Why parse the binaries directly

The Mod SDK ships **Win64 binaries only**. There is no Linux `UnrealEditor` to run a
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

**3. `FRichCurveKey` is 27 bytes**, three enum bytes (interp, tangent, tangent weight)
followed by six floats: time, value, arrive tangent, arrive weight, leave tangent, leave
weight. `curve.py` reads these, and the page evaluates them the way UE does, including
cubic segments as a Bézier built from the stored tangents.

**4. ObjectRedirectors are everywhere.** `Projectile_Suppression_GPMG` is not a profile,
it is a redirector to `Projectile_Suppression_MMG`. The destination is the package index
in the last four bytes of the 17-byte export blob. `squad.py` follows them transparently;
without that, five weapon classes resolve to nothing.

Blueprint defaults only store properties that **differ from the parent**, so reading a
weapon means walking its `_C` class chain upward and merging; most-derived wins. That is
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
from the game's own role art. Category emblems are matched to profiles by hand. Squad
ships no per-profile artwork.

---

## What the vehicle side says

546 vehicle weapon assets across 99 vehicle folders fold into **254 distinct weapon systems**
on 141 vehicles, in fourteen classes. Faction skins collapse into one row, so a Desert and a
Woodland BMP-2 autocannon count once.

- **Most vehicle passby profiles carry no distance curve.** A .50 is worth 0.500 a round, an
  autocannon sabot 0.700 and a tank sabot 1.500, wherever the round passes. Only the coax
  tapers, on the same MMG curve infantry machine guns use. Where a flat profile stops applying
  is a C++ decision and stays UNKNOWN.
- **The ceilings are what make vehicles different.** Coax 1.75, everything else on passby 2.00,
  and the explosive profiles 4.00 to 6.00. Blur needs 3.0 and fisheye 5.0, so those two effects
  are unreachable by any gun and belong to shells.
- **Eight of the fourteen classes suppress radially**, several of them with the passby power
  zeroed outright, which is why a missile is worth nothing until it lands. A tank HE shell is
  at full power to 16.9 m and still reaches 50 m; a 120 mm barrage reaches 75 m, against 22.5 m
  for a hand grenade.
- **A main gun's reload outlasts the immunity drain.** Six to nine seconds between shells
  against a clock that holds for one second then drains at 1.0 a second means every shell lands
  on a target with no immunity at all, kicking at full strength. A coax pins that same clock at
  its maximum.
- **One-shot guns cycle on their reload**, not on `TimeBetweenShots`, the same correction the
  bolt-action rifles needed. A tank gun's honest rate is 8 rpm, not 60.

`squad_vehicle_weapons.csv` has all 254 rows: vehicle, class, profile, rate, penetration and
both suppression models.

---

## Penetration and materials

Squad puts penetration on the **material**, not on the surface type. Every `SQPhysicalMaterial`
carries an armour value in millimetres and a damage cost for passing through it. Every weapon
carries `ArmorPenetrationDepthMillimeters`, and the heavy calibres carry a distance curve as well.
A round gets through when its penetration meets the material's thickness. 129 materials, 102 of
them with an armour value.

| cover | armour | absorbs |
|---|---|---|
| Glass, thin metal, fabric, leaves, oil drums | 1 mm | 5 to 100 |
| Wood, floorboards | 3 mm | 30 |
| Plaster, sheet metal, metal stairs | 5 mm | 50 to 70 |
| Brick, concrete, tree logs | 10 mm | 100 to 120 |
| Sandbags, including deployables | 12 mm | 120 |
| Dry mud wall | 20 mm | 200 |
| Rock, deployable rock and concrete | 100 mm | 75 |
| All terrain: dirt, grass, sand, snow, asphalt, gravel, mud | 5000 mm | none |

Against that, infantry get 1 mm on pistols and 9x19 submachine guns, 5 mm on 5.56 and 5.45,
7 mm on 7.62, and 9 mm on the bolt-action precision rifles. The practical line therefore sits
between 9 mm and 10 mm: nothing a rifleman carries goes through brick, concrete or sandbags, and
everything they carry goes through wood, glass and plaster.

Ten heavy calibres drop their penetration with distance instead, through curves keyed in metres
(inferred from the magnitudes): a .50 falls from 28 mm to 4 mm by 2 km, a 30 mm APDS from 95 mm
to 30 mm by 3 km, and a 120 mm sabot from 800 mm to 500 mm.

Three vehicles have hand-built armour zones of eleven materials each. The M1A2 is 600 mm at the
turret front and 10 mm on the rear side skirt; the T-72B3 is 700 mm at the turret front and 50 mm
on the hull side; the T-62 is 250 mm and 80 mm. Every other vehicle uses generic plates named by
thickness, from 3 mm to 400 mm, plus an engine and an ammo rack that each absorb 1000.

**What is not settled:** how `DamageAbsorbed` combines with the round's damage is compiled C++, and
where a weapon sets both a flat penetration and a curve, which one wins is UNKNOWN. Several
disagree, for example the 30 mm APDS is 62 flat against 95 on its curve.

`material_images.py` recovers a surface image for each material from the editor thumbnails. It gets
the solid building materials right and fails on terrain and foliage, which are layer blends with no
single base colour texture; those want a hand-picked source in its `CURATED` table.

---

## Reproducing it

`./build.sh` runs the chain below. It is byte-reproducible: run it twice and the output
files hash identically.

| Step | Script | Produces |
|---|---|---|
| 1 | `extract_all.py` | `all_weapons_raw.json`, every weapon asset, resolved |
| 2 | `build_all.py` | `all_weapons.json`, grouped weapons + base64 icons |
| 3 | `dump_all.py` | `all_profiles.json`, all 58 suppression profiles |
| 4 | `report.py` | `squad_rifle_suppression.{csv,json}`, ten-rifle sample |
| 5 | `build_gui_data.py` | `gui_data.json`, profiles, curves, soldier data |
| 6 | `build_payload.py` | `payload.json`, the page's base payload |
| 7 | `merge_payload.py` | `page_payload.json`, + weapons and icons |
| 8 | `build_csv.py` | `squad_all_weapons_suppression.csv`, one row per weapon, with fire mode and bolt cycle |
| 9 | `build_page.py` | `suppression.html`, data page: template + payload |
| 10 | `build_guide_payload.py` | `guide_payload.json`, per-kit figures, soldier curves, effect thresholds, logo |
| 11 | `build_vehicle_payload.py` | `vehicle_payload.json`, per-class figures, vehicle weapon art |
| 12 | `build_guide.py` | `guide.html`, field guide: template + both payloads |
| 13 | `make_site.py` | `docs/index.html` (guide) and `docs/modders.html` (data page) |

The vehicle sweep itself is not in `build.sh`, because it reads 546 assets across 99 vehicle
folders and only changes when the game does. Run it by hand after an update:

```bash
python3 extract_vehicles.py && python3 report_vehicles.py
```

Edit the pages in **`guide.template.html`** and **`suppression.template.html`**, never in the
generated `.html` files, steps 9 and 12 overwrite them.

**Rate of fire** is not one number. Automatics report their cyclic rate from `TimeBetweenShots`.
Bolt-actions inherit a meaningless 0.072 s there from the generic rifle base; their real cycle is
`ManualBoltingCompletionTime` on the weapon's StaticInfo (SV-98 1.95 s, C14 and Timberwolf
2.31 s), and the pipeline uses that. `Firemodes` is a list of burst lengths (`1` semi, `-1` full
auto), which is how each weapon gets its `fire` tag.

`make_site.py` exists because the page is authored as an artifact body. Serving it
yourself needs a doctype, `<meta charset="utf-8">` and a favicon that the artifact host
would otherwise supply. Without the charset tag every en dash and middot on the page
renders as mojibake.

## Reading blueprint logic, not just values

`graph.py` parses the node graphs inside a Blueprint asset: the K2Node exports and their
binary pin lists, including links between nodes. `decompile.py` turns a graph into
pseudo-code. That is how the soldier's punch and immunity logic in `SUPPRESSION_LOGIC.md` was
recovered: 542 nodes, 1,140 links, none unresolved.

```bash
python3 decompile.py <path to BP_*.uasset> 'Suppress|Flinch'    # regex over graph + entry names
```

Two format details worth knowing: a `BoolProperty` value lives in the tag's flags byte
(`0x10` = true), and the pin body ends with a 16-byte GUID plus a 4-byte flags word and no
trailer, while classes derived from `K2Node_EditablePinBase` append their own data after the
pin list.

## Extending it to other data

The parser knows nothing about suppression specifically. To pull a different system:

1. Find an asset that mentions it: `grep -al "Penetration" **/*.uasset`. Note that
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
than range to shooter. The property is `PowerToDistanceCurve`, its companion is
`ObstructedClosenessMult`, and a 5 m envelope only makes sense as closeness. Also that
`SuppressionPower` is the fallback used when a profile has no curve, which is how the
shotgun and tank profiles are shaped.

**Not available at all:** the decay rate once fire stops, the mapping from a suppression
value to the screen effect, and how the closeness ratio is normalised. All three live in
`/Script/Squad`, which is compiled C++ that the Mod SDK ships without source. Anything claiming
to know those numbers is guessing.

## Layout

| | |
|---|---|
| `uasset.py` | UE 5.7 package reader, names, imports, exports, tagged properties |
| `curve.py` | `FRichCurve` key decoding |
| `textures.py` | icon recovery from asset thumbnails |
| `squad.py` | blueprint chains, property merging, redirector following |
| `graph.py` / `decompile.py` | Blueprint node-graph parser and pseudo-code decompiler |
| `vehicle_classes.py` | how vehicle weapon assets fold into systems and classes, shared by the report and the payload |
| `extract_materials.py` | every physical material, its armour value and the penetration curves |
| `material_images.py` | a surface image per material, recovered from editor thumbnails |
| `guide.template.html` | the field guide, both tabs, edit this one, not the output |
| `suppression.template.html` | the data page, edit this one |
| `SUPPRESSION_LOGIC.md` | the decoded soldier-side logic, with confidence labels |
| `serve.py` | gzipping static server for the LAN |
| `docs/index.html`, `docs/modders.html` | the built pages |

See **[RUNBOOK.md](RUNBOOK.md)** for hosting commands: LAN, systemd, Docker and public
static hosts.
