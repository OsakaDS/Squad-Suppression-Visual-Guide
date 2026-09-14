# Squad suppression — the decoded logic

Squad v10.5.3 · read from `BP_MutableSoldier`, its curve assets, `SuppressionConfig/`, and the
weapon/projectile assets. Decoded 2026-09-13 by parsing the blueprint node graph directly
(542 nodes, 1,140 pin links, zero unresolved) — see `graph.py` / `decompile.py`.

Every statement below carries one of three labels:

- **READ** — a value or a piece of logic taken directly from the assets.
- **INFERRED** — follows from names, tooltips and structure, but the operative code is in
  compiled C++ that the Mod SDK does not ship.
- **UNKNOWN** — cannot be settled without the C++ source or in-game testing.

---

## 1. Where the pieces live

| Layer | Where | What it decides |
|---|---|---|
| Weapon → profile | `Blueprints/Items/**` (READ) | which `SQSuppressionInfo` a round carries, rate of fire |
| Profile | `Projectiles/SuppressionInfo/*` (READ) | power-vs-miss-distance curve, ceiling, sway numbers |
| Round → soldier | `/Script/Squad` C++ (UNKNOWN) | whether a passing round counts, how much it adds, the closeness ratio, the decay of the total |
| Soldier reaction | `Soldiers/BP_MutableSoldier` (READ) | camera and weapon **punch**, the **immunity** system, which VFX preset is active |
| Screen effects | `SuppressionConfig/*`, `CameraManager/CameraEffects/*` (READ) | vignette, desaturation, grain, dirt, blur, fisheye — and the level each switches on at |
| Sway | `VC_SuppressionSwayBySuppressionPercent` (READ value, INFERRED use) | extra weapon sway while suppressed |

The C++ soldier hands the blueprint one event per suppressing round:

```
OnSuppressionEventDelegate(IsRadial, AddedSuppressionAmount, NewSupressionLevel,
                           SuppressionResistance, ClosenessRatio, SuppressionSourcePoint,
                           ProjStartOverlapPoint, ProjEndOverlapPoint, SuppressionInfoClass)
```

Everything the blueprint does is downstream of those parameters. In particular the blueprint
**never computes the suppression total itself** — it receives `NewSupressionLevel` already
accumulated and already capped. The accumulation, the cap, the miss-distance test and the decay
are C++.

The variable holding the total is named `UnderSuppressionPercentage`, but it is **not a
percentage** (INFERRED, high confidence): the VFX curves that read it are keyed from 0 to 7.5
and 10, the profile ceilings run 1.15–3.0 for small arms and up to 6.5 for blasts, and the debug
function `AdjustSuppressionLevel` adds a raw delta with no upper clamp. Treat it as *the level*.

---

## 2. The event handler, decoded

Cleaned-up pseudo-code of `EventGraph :: OnSuppressionEventDelegate` (READ):

```
if not CanExecuteCosmeticEvents():        # local player only — servers and other clients skip this
    return
LastSuppressionClosenessRatio = ClosenessRatio

if NewSupressionLevel > 0 and AddedSuppressionAmount > 0:
    bActivelySuppressed = true
    if the 1-second "still under fire" timer is paused:  unpause it
    else:                                                 restart it from 0

    # 1. punches — magnitude uses the CURRENT immunity, before the first-shot bump below
    weapon-alignment punch, camera-rotation punch, camera-location punch   (see §4)

    # 2. experimental first-shot flinch — gated by UseExperimentalSuppressionFirstShotFlinch,
    #    which is not set in the asset (so it takes the class default: false).  Dead in v10.5.3.

    # 3. first-shot immunity
    if SuppressionImmunityFactor == 0:
        SuppressionImmunityFactor = FirstShotIncrementByClosenessRatio(ClosenessRatio)
```

Two consequences a player would care about:

- **A round only counts if it actually added something.** `AddedSuppressionAmount > 0` means a
  round that arrives while you are already at the profile's ceiling does nothing to your
  camera or weapon — it can't push the level, so it adds 0, so the guard fails. Being at cap is,
  perversely, the moment further rounds stop kicking you. (READ for the guard; the "adds 0 at
  cap" half is INFERRED from `MaxSuppressionThreshold`.)
- **The first round of an engagement always hits at full strength.** The punch is applied
  before immunity is granted, so shot one is unmitigated; shots two onward are damped.

---

## 3. Immunity — the numbers and the timeline

Blueprint variables, all READ from the class defaults:

| Variable | Value | Developer tooltip |
|---|---|---|
| `SuppressionImmunityTickRate` | 0.1 s | — |
| `SuppressionImmunityIncrement` | 1.0 | "Amount to increment Suppression Immunity Factor per second." |
| `MaxSuppressionImmunityFactor` | 7.5 | — |
| `SuppressionImmunityDecayThreshold` | 1.0 s | — |

Two looping 0.1 s timers are created on BeginPlay (READ):

**`UpdateSuppressionImmunity`** — runs always:
```
Immunity = clamp(Immunity + (bActivelySuppressed ? +0.1 : −0.1), 0, 7.5)
```
So immunity **rises 1.0 per second while you are "actively suppressed" and falls 1.0 per second
when you are not.** Full immunity takes 7.5 s of sustained fire; it is fully gone 7.5 s after the
fire stops.

**`SuppressionImmunityDecayTimer`** — starts paused, unpaused by each suppressing round:
```
if DecayStartTimer >= 1.0 s:  bActivelySuppressed = false; pause self; DecayStartTimer = 0
else:                         DecayStartTimer += 0.1
```
So "actively suppressed" persists for **exactly 1.0 s after the last qualifying round**, and
every new round restarts that second. Any gap in fire longer than one second flips you out of the
state and immunity begins draining.

**First-shot bump** (READ, `FC_SuppressionImmunityIncrementByClosenessRatio`): applied only when
immunity is at 0 — i.e. the first round of a fresh engagement:

| closeness ratio | immunity granted immediately |
|---|---|
| below 0.33 | 0 |
| 0.33 – 0.66 | 1.0 |
| 0.67 and above | 2.0 |

Developer comment on the block: *"Increment Suppression Immunity after first shot, to moderate
punches from bursts and tap fire."* A very close first round therefore makes the *following*
rounds of that burst softer, faster.

**Worked timeline** — rifle fire, rounds passing at closeness 0.8, continuous:

| time | immunity | note |
|---|---|---|
| 0.0 s | 0 → 2.0 | first round: full punch, then jumps to 2.0 |
| 1.0 s | 3.0 | +1 per second while under fire |
| 3.0 s | 5.0 | |
| 5.5 s | 7.5 | ceiling — every punch now at its minimum multiplier |
| fire stops at 6.0 s | 7.5 | |
| 7.0 s | 7.5 | still "actively suppressed" for 1 s after the last round |
| 8.0 s | 6.5 | draining at 1 per second |
| 14.5 s | 0 | back to fresh — the next round hits at full strength again |

---

## 4. Punch — what a passing round does to your view

Every qualifying round fires three punches through `SQGenericPunchSubsystem` (READ):

```
multiplier = RandomizedVectorOffset(variability 0.25)          # each axis × random 0.75 … 1.25
           × PunchByClosenessRatio(ClosenessRatio)               # how close it passed
           × PunchByImmunity(SuppressionImmunityFactor)          # how numb you are
           × (aiming down sights ? weapon's ADS multiplier : 1)  # per-weapon, from its StaticInfo
offset     = random 0 … 360°                                     # random direction every time
```

**By closeness** (READ):

| closeness | camera location | camera rotation | weapon alignment |
|---|---|---|---|
| 0 | 0 | 0 | 0 |
| 0.1 | 0.50 | 0.50 | 0.375 |
| 0.8 | ~0.89 | ~0.89 | 0.625 |
| 1.0 | 1.00 | 1.00 | 1.00 |

Half of the punch arrives by closeness 0.1 — anything inside the envelope kicks you noticeably;
only the last stretch to 1.0 adds the rest.

**By immunity** (READ; cubic curves, values approximate between keys):

| immunity | camera location | camera rotation | weapon alignment |
|---|---|---|---|
| 0 | 1.00 | 1.00 | **0.70** |
| 0.4 | 0.79 | 0.79 | 0.50 |
| 2 | ~0.72 | ~0.75 | ~0.46 |
| 5 | ~0.50 | ~0.66 | ~0.36 |
| 7.5 | 0.35 | 0.60 | 0.30 |

Note weapon alignment starts at 0.70, not 1.0 — even a fresh first round only ever throws your
weapon 70 % of the closeness value.

**Per-weapon ADS multipliers** (READ from weapon `StaticInfo` assets; the C++ default for
weapons that don't set them is UNKNOWN):

| weapons | camera location | camera rotation | weapon alignment | X-axis camera punch |
|---|---|---|---|---|
| MAG / Maximi / Minimi / MG3 families (12 assets) | 0.5 | 0.2 | 0.5 | on |
| 65 optic-equipped rifles, LSWs, LMGs | 0.4 | default | default | **disabled** |
| 14 others (C9A2, L110A1, M240 M145/MGO…) | default | default | default | **disabled** |
| Binoculars, M27 parent | 0.4 | default | default | on |
| M4 optic (legacy) | 0.4 | 0.24 | default | disabled |

So **aiming down an optic roughly halves the camera kick** on most weapons, and the belt-fed
machine guns are deliberately the steadiest platforms under fire (rotation ×0.2 in ADS).

**Punch shape over time** (READ, `VC_Suppression_*` curves; units are whatever the punch
subsystem applies them as — treat as relative):

| | peak | at | back to zero |
|---|---|---|---|
| camera rotation | X −2.68 · Y +2.58 · Z −1.18 | 0.11–0.13 s | 0.7–1.0 s |
| camera location | X −0.90 · Y +0.64 · Z −0.40 | 0.18–0.21 s | 0.7 s |
| weapon alignment | 0.52 / −0.32 / 0.31, with a −0.11 overshoot at 1.1 s | 0.17–0.24 s | 2.8 s |

The camera settles in under a second; **the weapon keeps wandering for almost three**, with a
counter-swing. That is the sight picture "floating" after a near miss.

---

## 5. Screen effects — what each weapon class can even trigger

The active preset is `Suppression_VignetteOnly` (READ: `SuppresionPresets[0]`, and
`SuppressionEffectPresetIndex` defaults to 0). Despite the name it carries five effect layers.
Each switches on over a **level range** of the suppression total:

| effect | fades in over level | reachable from |
|---|---|---|
| Vignette | from 0 (intensity 0.34 at level 0.1, 0.56 at 0.5, 0.73 at 1.0, 0.82 at 3, 0.85 at 10) | everything |
| Film grain (intensity 0.17) | 1.0 → 2.0 | partial from rifles (cap 1.15); full from DMR and up |
| Desaturation | 1.4 → 1.9 | **not rifles**, **not SMGs** — MMG (1.75) partial; DMR / sniper / blasts full |
| Colour grading (contrast) | 1.4 → 1.9 | same |
| Chromatic aberration | 1.9 → 5.0 | DMR (2.0) barely; sniper (3.0); blasts |
| Depth-of-field blur (aperture 4.67, focal 46) | 3.0 → 4.0 | sniper at cap; blasts |
| Screen dirt (×180) | 2.95 → 4.0 | sniper at cap; blasts |
| Fisheye (to 0.5) | 5.0 → 7.0 | blasts only (grenade cap 6.5) |

Cross-referenced with the profile ceilings from the weapon side:

- **Rifle / SMG / battle rifle (cap 1.15):** vignette plus a hint of film grain. Nothing else,
  ever — they physically cannot push the level past 1.15.
- **LSW / LMG (1.25):** as above.
- **MMG (1.75):** adds partial desaturation and colour shift.
- **DMR (2.0):** full desaturation, the first trace of chromatic aberration.
- **Sniper (3.0):** the first DOF blur and screen dirt, at cap.
- **Explosions (up to 6.5):** everything including fisheye.

This is the single most useful thing the decode turned up for players: *the heavy "I can't see"
effects are an explosives-and-marksmen phenomenon. Rifle fire only ever vignettes you.*

Vignette also **pulses** — amplitude 0.15 per hit, decaying at 2 per second, capped at 2.0 (READ).
The DOF and fisheye layers additionally read `VC_DOFbyFOVScale`, which just compensates for FOV.

---

## 6. Sway

`AdditiveSwayBySuppressionCurve` on the soldier points at `VC_SuppressionSwayBySuppressionPercent`
(READ). The blueprint comment says *"Sway is controlled elsewhere. See param
AdditiveSwayBySuppressionCurve"* — the application is C++.

| input | X | Y |
|---|---|---|
| 0 | 0 | 0 |
| 0.1 | 19.4 | ~2.5 (at 0.024) |
| 0.26 | 32.0 | — |
| 1.0 | 39.9 | 5.0 |

INFERRED: X is sway amplitude and Y sway speed; both saturate at input 1.0. Whether the input
is the raw level or a normalised fraction is UNKNOWN — the name says "percent", the curve is
keyed 0–1, and a rifle's cap of 1.15 would sit just past the top of it either way. Half of the
extra sway is already present at 0.1, so **even light suppression costs most of the sway
penalty**.

---

## 7. Decay — what the assets say and don't

- `SuppressionEffectsDecayRate` = **0.5**, `bDecaySuppression` = true (READ). The blueprint's
  debug block ("Toggling decay of suppression effects on/off — should not be ported to C++")
  zeroes this rate and restores it from `SavedDecayRate`, which confirms it is the live decay
  parameter the C++ reads.
- **How it decays is UNKNOWN**: 0.5 could be level-per-second (a rifle's 1.15 gone in ~2.3 s) or
  a fraction per second. Nothing in the assets resolves it.
- Immunity decay is fully READ (§3) and is a separate system from the level decay.

---

## 8. Things that look like features but aren't

- `Experimental - Suppression First Shot Flinch` (75 nodes, its own curves): the developers'
  comment reads *"Experimental and not currently used. Mainly here for modders and experiments.
  Needs more cleanup and review before being used for production."* Gated by a flag that is
  not set. **Not live.**
- The `Suppression Immunity` function (older +0.02 / max 1.0 version with a debug print): **no
  callers**. Dead code.
- `VC_SuppressionPunchIntensityBySuppressionPercentage`: **referenced by nothing**. An orphan.
  (An earlier draft of this project offered to chart it — it should not be on the page.)
- The `Suppression_*` presets other than `VignetteOnly` (`Proto`, `Peripheral`, `PinholeBlur`,
  `NoDesat`…): switchable with debug keys, not used in play.

---

## 9. What is still in C++ — named so it can be tested

These `SQSoldier` defaults are READ from the class defaults; how they are used is UNKNOWN:

| parameter | value | probable meaning (INFERRED) |
|---|---|---|
| `SuppressionRadius` | 800 uu (8 m) | outer edge of the closeness test — closeness 0 here |
| `FullSuppressionRadius` | 100 uu (1 m) | closeness 1 inside this |
| `MaxSuppressionAngleOff` | 17.5° | a round must be travelling within this angle of you to count |
| `SuppressionWallIgnoranceRange` | 250 uu (2.5 m) | a wall closer than this to the path doesn't block suppression |
| `SuppressionEffectsDecayRate` | 0.5 | see §7 |

Also UNKNOWN: what supplies `SuppressionResistance` (it is a delegate parameter; no asset sets
it — likely a per-role or per-seat value in C++), and whether the closeness ratio driving the
punch uses the 8 m soldier radius or the 5–7 m profile envelope. These are the questions an
in-game test with `W_SuppressionDebug` would settle.

---

## 10. Corrections to earlier statements in this project

| earlier claim | correct |
|---|---|
| "Decay isn't in the assets" | A decay rate (0.5) and the full immunity-decay logic are in the assets; only the level-decay *formula* is C++. |
| "Immunity is banked per near miss: +1 or +2" | Immunity climbs at a steady 1.0/s while actively suppressed and drains at 1.0/s otherwise. The +1/+2 is a one-time first-shot bump. |
| "Punch intensity decreases as your suppression meter fills" (the `…BySuppressionPercentage` curve) | That curve is unreferenced. Punch damping comes from immunity, not from the level. |
| Flinch presented as a live step function | The flinch curve belongs to the experimental, disabled first-shot flinch. What is live is the closeness→punch mapping in §4. |
