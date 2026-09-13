# What to print

Every STL in this folder is **verified watertight** and dimensionally checked
against the mechanism in [`../MECHANISM.md`](../MECHANISM.md). Re-check any time:

```bash
./.venv/bin/python hardware/3d-print/source/stl_qa.py
```

**Architecture:** ten rotors, ten OTC medicines, one motor each. Every pocket in
a rotor holds the same medicine. One stationary tube, one drop hole.

Naming: **`MAIN - `** is a real part of the machine. **`PROTOTYPE - `** is a
throwaway coupon that proves a fit and then gets binned.

Material PETG (PLA/PLA+ fine for dry fit tests), 0.4 mm nozzle, **no supports on
anything**, elephant-foot compensation 0.15–0.25 mm.

---

## Verified file list

| File | Size mm | ~g | Time | Role |
| --- | --- | ---: | ---: | --- |
| `PROTOTYPE - dummy container` | 35.0 × 20.0 × 15.0 | 6 | 12 m | tolerance check |
| `PROTOTYPE - dummy blister` | 30.0 × 15.0 × 8.0 | 2 | 6 m | fake contents |
| `PROTOTYPE - pocket coupon` | 48 × 64 × 17.5 | 16 | 1 h | chamfer A/B test |
| `PROTOTYPE - transfer tube 40mm` | 48 × 32 × 43 | 8 | 45 m | short stand-in tube |
| `PROTOTYPE - tube clearance gauge` | 131 × 26 × 15 | 7 | 40 m | go/no-go |
| `PROTOTYPE - flange nesting coupon` | 74 × 134 × 3 | 7 | — | **obsolete, do not print** |
| `MAIN - rotor deck plate` | ⌀180 × 5.0 | 69 | ~4 h | the floor + drop hole |
| `MAIN - rotor 9 pocket` | ⌀172 × 17.5 | 152 | ~9 h | the dispenser |
| `MAIN - magazine tube 90mm` | 51.6 × 52.1 × 94 | 17 | 2.5 h | the reload stack |
| `MAIN - magazine tube 180mm` | 51.6 × 52.1 × 184 | 32 | 5 h | taller option |
| `MAIN - container body and lid` | 78.8 × 20.0 × 13.8 | 2 | 5 m | body + lid, one plate |
| `MAIN - container lid loose` | 34.6 × 19.6 × 2.6 | 1 | 3 m | 0.40 mm/side spare |
| `MAIN - tube dust cap` | 42 × 27 × 5 | 3 | 6 m | 0.20 mm/side plug |

Three things worth knowing about these files:

- The rotor is the **corrected** revision — 17.5 mm thick with the 1.5 × 45°
  chamfer, not the defective 16.0 mm original still kept in `../superseded/`.
- Both magazine tubes shipped with 8–10 zero-area triangles from the original
  export, which made them read as non-manifold. Repaired; volume unchanged.
- `PROTOTYPE - flange nesting coupon` only proved that nine wedge flanges tile
  342° without colliding. There is one stationary tube now, so nothing tiles.
  Kept for provenance.

---

# Print in this order

Each batch is the cheapest print that proves the next expensive one is worth
starting. **Do not skip ahead** — every fault repeats in every part downstream.

## Batch 1 — is the printer dimensionally honest? (~25 min, ~12 g)

`PROTOTYPE - dummy container` × 2 · 0.20 layer, 3 walls, 15 % infill

**Gate — calipers, do not eyeball.** 35.00 / 20.00 / 15.00 mm, each ±0.10.
Measure the **bed face** separately from the middle. If the bottom is wider that
is elephant's foot, and it is the single most likely thing to break this build —
the pocket only has 0.40 mm per side.

**Fail →** raise elephant-foot compensation or apply −0.05 to −0.15 mm
horizontal expansion, reprint. Nothing downstream works at 35.4 mm.

## Batch 2 — the critical fit (~1 h 45, ~24 g)

`PROTOTYPE - pocket coupon` × 1 · `PROTOTYPE - transfer tube 40mm` × 1
0.20 layer, 3 walls, 20 % infill

**Gate**

1. **Free drop.** Dummy into the chamfered pocket, square → falls under its own
   weight, no push.
2. **A/B.** Push a dummy hard to one side and yaw it ~2°, then try each pocket.
   Chamfered funnels it in; sharp hangs on the lip. If *both* accept, the
   printer runs undersize; if both reject, oversize — back to batch 1.
3. **Headroom.** Seated dummy must not stand above the 17.5 mm face, even rocked
   to its limit (a cocked container stands 16.98 mm).
4. **Transfer.** Stand the 40 mm tube over the chamfered pocket, drop 3 dummies.
   All three reach the pocket unaided.

**Fail → do not print the rotor.** Say which check failed and by how much.

## Batch 3 — container and lid (~25 min, ~9 g)

`MAIN - container body and lid` × 2 · `MAIN - container lid loose` × 1 ·
`PROTOTYPE - dummy blister` × 2

**Gate.** Lid seats by hand without cracking the 1.2 mm wall · blister fits and
the lid still closes · closed container dropped 200 mm keeps its lid.

If the plate's NORMAL lid (0.30 mm/side) won't go, use LOOSE. If it pops on the
drop that is the known retention weakness — tape the seam and note it; a snap
bead is a design change.

## Batch 4 — the deck plate (~4 h, ~69 g)

`MAIN - rotor deck plate` × 1 · 0.20–0.24 layer, 4 walls, 25 % infill, **brim**

180 mm disc flat on the bed. Same rim-warp risk as the rotor — the brim is not
optional.

**Gate**

1. **Flat.** Rock it on glass. A bowed deck binds the rotor.
2. **Aperture clears.** Drop a dummy through by hand — obvious room (2.0 mm
   radial, 2.6 mm tangential per side). If it catches, the exit has become the
   tight feature, which is the one thing it must never be.
3. **It holds.** Deck under rotor, dummy in a pocket → sits on the deck, does
   not fall. Index by hand to the aperture → drops cleanly under its own weight.
4. **Shutter.** With one dummy resting through a pocket, slide the rotor one
   pocket over. The 19.0 mm land must hold a second dummy up.
   **This is the entire metering principle.** If it fails, nothing downstream
   matters.

**Fail → do not print the rotor.**

---

# ▲ GATE — batches 1–4 must all pass ▲

Above: **~6.5 h, ~115 g.** Below: **~12 h, ~190 g** per machine, ×10.

---

## Batch 5 — the rotor (~9 h, ~152 g)

`MAIN - rotor 9 pocket` × 1 · 0.20–0.24 layer, 4 walls, 25–30 % infill, **brim**

172 mm disc flat on the bed. The brim is not optional — the rim warps.

**Gate.** Check 3 pockets at different clock positions with a dummy, as batch 2.
A warped disc shows up as one pocket accepting and another binding.

## Batch 6 — the tube (~2.5 h, ~17 g)

`MAIN - magazine tube 90mm` × **1** — one stationary tube serves all nine
pockets. Upright on the flange, 8–12 mm brim, 0.24–0.28 layer, 4 walls.

The wedge flange is now redundant; bolt the tube to a stationary frame, not to
the rotor. Print `MAIN - magazine tube 180mm` (~32 g, 5 h) only after a 90 mm
tube runs clean.

**Gate.** Drop 6 dummies down the mounted tube into the pocket below. All six
arrive, none jams, and **only one enters per index**.

## Batch 7 — fill it out (~40 min, ~30 g)

`MAIN - container body and lid` × 9 (one per pocket) · `MAIN - tube dust cap` × 1
· `PROTOTYPE - tube clearance gauge` × 1 (optional bench reference)

Scale the dust cap 100.5 % if tight.

---

## Budget

| Stage | Time | Filament |
| --- | ---: | ---: |
| Batches 1–4 (test + deck) | ~6.5 h | ~115 g |
| Rotor | ~9 h | ~152 g |
| Tube | ~2.5 h | ~17 g |
| 9 containers | ~45 m | ~20 g |
| **One complete medicine slot** | **~19 h** | **~305 g** |
| **All ten** | **~155 h** | **~2.9 kg** |

Capacity: 9 in the rotor + 6 in a 90 mm tube = **15 doses per medicine**
(21 with the 180 mm tube). Ten medicines → 150–210 doses per refill.

---

## Not printable yet

The **ratchet ring, pawl and servo bracket** do not exist. The rotor must
advance 40° per dispense through a full 360°, which a 180° servo cannot do
directly, and 84 gear teeth / 9 pockets = 9.333 rules out tooth counting.
`../MECHANISM.md` specifies a 9-tooth ratchet — one tooth per pocket, integer by
construction — driven by the existing A → B → A servo motion. The pawl geometry
depends on how the servo mounts, which is not decided.

You can print and validate batches 1–7 without it. You cannot run the machine.

## Safety

Dummy blisters or sealed samples only. These parts are not validated
pharmaceutical-contact packaging.
