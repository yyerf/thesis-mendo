# Hardware reference provenance

These files are tracked copies of the user-supplied reference assets. The
original files remain at the repository root so their provenance is not lost.

| Tracked asset | Source asset | SHA-256 |
| --- | --- | --- |
| `allan-coinslot-calibration.pdf` | `allan coinslot calibration.pdf` | `f61b90333173e95069c2289ed1c668c82da0534886f46532962bb72f7905f08b` |
| `tb-series-installation-guide.pdf` | `tb_series.pdf` | `e76750a452e1b8256df684c881cd9940aa46bf6f3ee66b8e4ce60f6dc296d407` |
| `rotor_9pocket_35x20_recommended_clearance.stl` | `rotor_9pocket_35x20_recommended_clearance.stl` | `00e499be5a23a621b7a459fb6b675dc161f6a2a7e32c4f136401d9f087d7f9a8` |

The TB PDF is a generic TB-Series installation guide. It is not the missing
Philippine currency/DIP sheet and must not be used to infer PHP bill settings.

## Vendor DIP sheets

`vendor-dip-sheets/` holds manufacturer DIP-switch sheets retrieved for sibling
currency builds, including a genuine TOPVME **TB74** sheet on the same 10-way +
4-way bank layout as our unit, and two **PHP6** currency sheets. See
[`vendor-dip-sheets/README.md`](vendor-dip-sheets/README.md) for provenance and
the analysis in
[`docs/architecture/tb74-pulse-protocol-analysis.md`](../../docs/architecture/tb74-pulse-protocol-analysis.md).
These are still not the Philippine sheet for our exact unit; they narrow the
Phase-0 bench trial, they do not replace it.

## Legacy evidence

`legacy/Bill_Acceptor.ino` is the supplied V1 bill sketch. It is retained for
audit/provenance only and is not an approved controller source. Its 1-pulse =
₱10 mapping is an unverified starting hypothesis; do not flash it or use its
timing constants as calibration evidence.
