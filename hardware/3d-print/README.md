# 3D print queue — rotor / tube / container POC

Print-ready STLs for the magazine/container dispensing mechanism, staged so the
cheap gauges validate the critical fit **before** you commit filament to tubes
and containers you would have to reprint.

Source package: `~/Downloads/medicine_vendo_rotor_tube_container_POC_package/`.
All numbers below were measured from the meshes themselves, not copied from the
supplied README. Mesh QA: all 14 STLs watertight, single-body, zero degenerate
faces, euler numbers matching expected hole counts.

## Target architecture — SUPERSEDED, see `MECHANISM.md`

> **This section was written against a design that is no longer being built.**
> The mechanism is now **one 9-pocket rotor per medicine, ten rotors, one motor
> each**, with a single stationary tube and a single drop hole in a deck plate.
> Read [`MECHANISM.md`](MECHANISM.md) — it is the authority.
>
> What changed and why it matters:
>
> | Old text | Now |
> | --- | --- |
> | "the 9-pocket rotor does not belong to this build" | it *is* the build — one per medicine |
> | rotor = shared 9-medicine carousel | rotor = **9 doses of one** medicine |
> | 10 rotors need 860 × 344 mm of deck | accepted; cabinet sized for it |
> | SG90-class servo | **MG90S minimum** — see the servo table below |
>
> The rotor is not indexed by a servo sweep directly. It is advanced by a
> **9-tooth ratchet**, one tooth per pocket, driven by the existing
> A → B → A `DISPENSE_ONE` motion. That keeps `motion_profiles` valid 1:1 and
> sidesteps the 84/9 = 9.333 problem below.

Retained because the tolerance, fit and print-settings analysis below is
architecture-independent and still correct.

`hardware/README.md` locks `PCA channels 0–9 → hardware slots 1–10`, and
`pos/db.py` seeds `motion_profiles` with `position_a_us` / `position_b_us` /
`travel_time_ms` / `b_dwell_ms` / `return_settle_ms` — one sweep-and-return per
slot. That mapping is unchanged: ten slots, ten medicines, ten rotors.

The container / tube / pocket **fit interface is identical either way**, so the
fit gauges below are valid and worth printing now.

---

## Nominal interface

| Feature | Size |
| --- | --- |
| Container (closed) | 35.0 × 20.0 × 15.0 mm |
| Container cavity | 32.6 × 17.6 × 11.2 mm |
| Rotor pocket | 35.8 × 20.8 mm, 9 off @ 40.000° |
| Rotor | OD 172, 16 mm thick, 84T module-2 gear, 8.2 bore, 4× M4 @ 28 PCD |
| Magazine bore | 36.2 × 21.2 mm |
| Pocket centre radius | 57.0 mm |

Measured clearances (from section polygons, corners included):

| Fit | Flats | True min (incl. corners) | Lateral float | Yaw float |
| --- | --- | --- | --- | --- |
| container → magazine bore | 0.600 mm | 0.600 mm | ±0.600 mm | ±2.25° |
| container → rotor pocket | 0.400 mm | 0.400 mm | ±0.400 mm | ±1.49° |

---

## Stage 1 — fit gauges (print first, ~1 h)

| File | Qty | Notes |
| --- | --- | --- |
| `rotor_1pocket_35x20_recommended_clearance.stl` | 1 | identical pocket, 1/9 the print time |
| `container_dummy_solid_35x20x15.stl` | **3** | need ≥3 to test stacking |
| `tube_clearance_gauge_35x20.stl` | 1 | |
| `fit_gauge_35x20_clearance_test.stl` | 1 | |

### Pass/fail gate

1. Dummy falls through the tube gauge **under its own weight**, no shaking.
2. Dummy enters the rotor pocket with **no force**.
3. **The one that matters:** push the dummy hard against one side and yaw it
   ~2°, then try to drop it in. Centred and square it will *always* work — that
   is what will mislead you. The tube allows ±0.600 mm / ±2.25°; the pocket only
   accepts ±0.400 mm / ±1.49°, so the tube can present positions the pocket
   rejects. If it hangs on the lip here, chamfer the pocket before going on.

Do not proceed to stage 2 until all three pass.

---

## Stage 2 — functional parts (only after stage 1 passes)

| File | Qty | Notes |
| --- | --- | --- |
| `magazine_tube_90mm_ID36p2x21p2.stl` | 1 | short tube first, never the 180 mm |
| `medicine_container_body_35x20x15.stl` | 2–3 | |
| `medicine_container_lid_loose.stl` | 2–3 | **start with LOOSE** — see tolerances |
| `medicine_container_lid_normal.stl` | 1 | only if LOOSE is too easy to remove |
| `magazine_tube_dust_cap.stl` | 1 | 0.20 mm/side plug — may need scaling |
| `dummy_blister_30x15x8.stl` | 2–3 | 1.3 mm/side, 3.2 mm headroom in cavity |

The supplied README says start with NORMAL. **That is wrong for most printers** —
see the tolerance table below.

---

## Per-slot mechanism — decide before designing anything new

Two viable ways to build one slot with one 9 g servo:

| | Metering disc | **Pusher paddle (recommended)** |
| --- | --- | --- |
| Principle | pocket rotates from under tube to over drop hole | paddle shoves bottom container out from under the stack |
| Size per slot | 87–96 mm disc | ~60 × 60 mm |
| 10 slots | ~500 × 200 mm | **~300 × 120 mm** |
| Servo sweep | >73–91° (SG90's 180° is enough) | 90° on a 30 mm horn = 42 mm stroke |
| Printing | 10 discs | 10 small paddles |
| Fits `motion_profiles`? | yes | yes, 1:1 |

Minimum disc sizes, pocket long-side turned tangential:

| Pocket radius | Disc OD | Sweep needed |
| --- | --- | --- |
| R = 25 mm | 87 mm | >91° |
| R = 30 mm | 96 mm | >73° |
| R = 57 mm (as drawn) | 148 mm | >37° |

Ejection stroke for a 35 mm container is ~38–40 mm, so a pusher horn must be
≥30 mm (a 25 mm horn at 90° gives only 35.4 mm — too short).

### Servo choice

Torque is **not** the constraint: shearing one container out from under a
12-high stack needs ~10 mN·m, and even an SG90 delivers ~177 mN·m.

| Servo | Torque | Gears |
| --- | --- | --- |
| SG90 (9 g) | 1.8 kg·cm = 177 mN·m | **plastic — strips on stall** |
| MG90S (13.4 g) | 2.2 kg·cm = 216 mN·m | metal, same 23 × 12 body |
| MG996R (55 g) | 10 kg·cm = 981 mN·m | metal — what `hardware/README.md` specifies |

**Use MG90S at minimum.** An SG90 stalls destructively and the first jam strips
it; with 10 units that is a recurring failure. Keep the firmware's "only one
servo active at a time" rule — 10 stalled servos would draw ~7 A.

---

## Print settings

Material PETG preferred (PLA/PLA+ fine for dry indoor fit tests), 0.4 mm nozzle.

| Part | Layer | Walls | Infill | Orientation |
| --- | --- | --- | --- | --- |
| container body | 0.20 | 3–4 | 20–30 % | open side **up** |
| lid | 0.20 | 3–4 | 20–30 % | large flat top on bed, plug **up** |
| tube | 0.24–0.28 | 4 | 15–25 % | upright on flange, 8–12 mm brim |
| tube cap | 0.20 | 3–4 | 20–30 % | flat top on bed, plug **up** |
| rotor | 0.20–0.24 | 4 | 25–30 % | flat, brim (rim warping risk) |

**No supports on any part** — verified, zero downward-facing area below 45°.

**Enable elephant-foot compensation (0.15–0.25 mm).** This is not optional here:
the container prints open-side-up, so its 35 × 20 bottom face — the exact face
that must clear the pocket — sits on the bed.

```
elephant's foot  →  resulting pocket gap per side
    +0.10 mm            0.300 mm   ok
    +0.20 mm            0.200 mm   marginal
    +0.30 mm            0.100 mm   BINDS
```

Alternative if your printer can't compensate: chamfer the container's bottom
edge 0.5 mm.

### Lid clearance vs real FDM tolerance

Holes print 0.10–0.20 mm undersize per side, walls 0.05–0.15 mm oversize:

| Lid | Nominal | Good printer | Typical printer |
| --- | --- | --- | --- |
| TIGHT (0.20) | 0.200 | −0.05 press-fit | **−0.25 won't assemble** |
| NORMAL (0.30) | 0.300 | +0.05 press-fit | **−0.15 won't assemble** |
| LOOSE (0.40) | 0.400 | +0.15 free | −0.05 press-fit |

Same issue on the tube dust cap (0.20 mm/side).

---

## Open design issues

### 1. Nine tube flanges do not fit around the rotor — VOID for this build (see 5)

At R = 57 mm, adjacent pocket centres are **38.99 mm** apart. The tube flange is
**42 mm** across that direction.

```
9 flanges × 42 mm  = 378 mm needed
circumference @R57 = 358 mm available
→ each flange overlaps its neighbour by 3.01 mm
```

Tube *bodies* (26 mm) clear fine — it is purely the 58 × 42 mm bolt flange.
Options: replace per-tube flanges with one 9-hole carousel deck (cleanest); trim
the flange to ≤ 37 mm tangential; or move pockets to R ≥ 64.3 mm (grows the
rotor, forces gear regeneration).

### 2. Magazine bore is larger than the rotor pocket — inverted

The exit aperture must be larger than the guide aperture; here it is backwards
by 0.2 mm per side. A container resting against one tube wall overhangs the
pocket lip; one yawed 1.5–2.25° cannot enter at all. The pocket top edge is a
sharp extruded 90° with no lead-in.

**Fix: chamfer the pocket top edge ~1.5 mm × 45°.** That opens the capture mouth
to 38.8 × 23.8 mm — swallows anything the tube can present — while the pocket
stays 35.8 × 20.8 lower down to limit cocking.

### 3. A cocked container stands proud of a 16 mm pocket — STILL APPLIES

```
pocket ALLOWS a 3.28° cock → container stands 16.98 mm tall
rotor thickness             16.00 mm
```

A guide plate at 16.2–16.5 mm still shears anything cocked past 1.98–2.48°, so
there is a live window (~2°–3.3°) where a container is legally in the pocket,
standing proud, and gets sheared by the fixed top plate.

**Fix: rotor thickness ≥ 17.3 mm**, plus the chamfer from issue 2.

### 4. Lid retention

Friction plug only, no latch — the supplied README tells you to tape the seam.
Across a 90–180 mm stack drop plus tumbling out the chute, lids will pop and
spill blisters into the mechanism. Needs a snap bead before this is more than a
bench demo.

### 5. Issue 1 is void — but for a different reason than written here

Issue 1 (nine tube flanges colliding at R=57) is dead because there is now
**one stationary tube per rotor**, not nine rotating ones. Nothing tiles, so
nothing collides. The flange shape is irrelevant; bolt the tube to a frame.

The indexing problem is **not** void. 84/9 = 9.333 still means this rotor cannot
be indexed by tooth counting — which is why `MECHANISM.md` specifies a 9-tooth
ratchet instead, one tooth per pocket, integer by construction.

**Issue 3 still applies in modified form:** whatever pocket or paddle the
container passes through must give it ≥1 mm of vertical headroom, because a
container cocked 3.28° stands 16.98 mm tall against a 15.0 mm nominal.

Retained for reference only, in case the shared carousel is ever revisited:
`84 / 9 = 9.333` teeth per index is not an integer, so that design could never
be indexed by tooth-counting or a Geneva — it would need an absolute homing
datum every cycle, plus a bearing (67–118 mN·m of sliding drag if a 172 mm disc
runs flat on a plate, vs ~16 mN·m of inertia).

---

## Safety

Use the dummy blister or an empty sealed sample for all mechanism tests. Do not
put loose tablets or capsules in the printed carrier — these parts are not
validated pharmaceutical-contact packaging. Sealed blisters stay intact.

---

## Directory layout

```
3d-print/
├── MECHANISM.md             ** the authority on how the machine works **
├── PRINT-READY/             MAIN - (real parts) and PROTOTYPE - (test coupons)
├── stage1-fit-gauges/       validates the critical fit
├── stage2-functional/       earlier functional revision
├── fixed-v2/                corrected rotor + wedge-flange tubes
├── superseded/              defective originals, kept for provenance
├── source/                  editable OpenSCAD, + deck_plate_generator.py
└── previews/                assembly reference renders
```

`source/medicine_rotor_parametric.scad` — edit `rotor_thickness`,
`pocket_radius`, `pocket_count` there; the gear outline is a baked point list,
so changing the OD requires regenerating it, not just editing a variable.
