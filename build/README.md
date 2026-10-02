# Cascade build — egc365

Working folder for building this Cascade. Everything here is generated from
the official files in this repo (BOM, STLs, assembly STEP), so a change to
`config.json` regenerates the lists.

| File | What it is |
|---|---|
| `config.json` | Build choices (spindle, controller, table, Z plate, printed-part variants, printer bed) |
| `purchase_list.csv` | Everything to buy or source, `include` column applies the config (149 lines for the default) |
| `print_list.csv` | Every printed part with qty, material, colour, filament estimate, size and bed fit |
| `vision/` | Camera / digital-twin study: sensor placement ray-traced against the CAD, renders, 3D page |
| `tools/` | The scripts that produce all of the above |

## Default configuration

These are the defaults in `config.json`. Each is a real choice, so change it before ordering.

| Choice | Default | Why |
|---|---|---|
| Spindle | AC: G-Penny 1.5 kW 24k ER16 + H100 VFD | BOM marks it "strongly preferred". The H100 also talks Modbus, which the vision rig uses for spindle load |
| Controller | Expatria FlexiHAL + 3× DM542T | grblHAL with Ethernet (uFlexiNET), so the twin can stream machine position. BTT Scylla is the other option |
| Work table | T-slot (2× HFSQN4-15100-300) | Cheaper; the SMW grid plate is the upgrade |
| Z carriage plate | `M8_80x30` | Pick the plate by **clamp bolt pattern**, not spindle diameter. The BOM's AC option uses a 65 mm clamp with an 80×30 pattern |
| Printed variants | short-body endstops, air-mount Z cover, extrusion tool setter/sexbolt mounts, landscape display | Edit `selections` in `config.json` |
| Frame/panels | bought pre-cut and tapped | Set `self_drill_frame` / `self_cut_panels` to add the jigs and drill/tap tools |

## Numbers for the default build

- **Printing:** 75 files, 105 pieces, about **1.6 kg** of filament. That's 0.80 kg primary ABS, 0.51 kg accent ABS, 0.28 kg PLA for jigs/tools and a few grams of clear PETG. Everything fits a 250 mm bed. Estimates use the manual's settings (0.2 mm layers, 4 walls, 5 top/bottom, 40% infill) and exclude supports and purge.
- **Buying:** 149 line items. The long-lead ones are the HFS extrusions cut and tapped to length, the machined aluminium parts (`[mp-a]`, drawings in `Drawings/`, STEPs in `STEPs/`), the laser-cut panels (DXFs in `Panel_DXFs/`), ballscrews, and the spindle/VFD.

## Fixes and flags found while building the lists

- **Missing STL, added.** The BOM calls for `[pp-s]_panel_latch_corner_mount_B` and the manual says to fit one on each side, but only `_A` was in `STLs/`. I checked against the assembly CAD: B is an exact mirror of A (max deviation 0.04 mm, which is tessellation noise), and *not* the same part (A unmirrored deviates by 4 mm). It's now in `STLs/Electronics/Frame Enclosure/Frame Enclosure Latch Corner/`. The sibling A/B pairs (frame hook, latch arm) are mirrors across the same axis.
- **Name mismatch.** The BOM's `WAGO_221-415_3x5_2020mount` is the file `WAGO_221-415_2020mount-3x5.stl`.
- **Manual text says MGN12, buy MGN15.** Manual pp. 21, 27 and 88 say "MGN12 linear rails". The BOM and the CAD both use MGN15 (400 mm with H carriages on Y and X, 200 mm with C carriages on Z).
- **Manual says M6x12 BHCS (p. 13 bottom panel ×24, p. 82), BOM has none.** The BOM lists 85× M6x10 BHCS, and the CAD has exactly 85 M6x10 BHCS modelled. Treat the manual's M6x12 as a typo, or buy a few M6x12 as cheap insurance.

## Build order

1. **Order long-lead parts:** extrusions, machined parts, panels, ballscrews, spindle/VFD, motors, rails.
2. **Print** while you wait. Start with the PLA jigs and alignment tools, since you need them first: `include=True`, `material=PLA` in `print_list.csv`. Then the primary and accent ABS.
3. **Base frame and Y axis** (manual p. 6–74), then **gantry** (p. 75–169), **bracing** (p. 170–212), **panels** (p. 213), **electrical** (p. 236–267), **working enclosure** (p. 268+).
4. **Vision rig**, see `vision/README.md`. Fit the camera mounts and run the cable before the working enclosure panels go on.

## Regenerating

```sh
pip install openpyxl trimesh numpy rtree
python build/tools/print_list.py       # -> build/print_list.csv
python build/tools/purchase_list.py    # -> build/purchase_list.csv
```

The vision study and 3D page are covered in `vision/README.md`.
