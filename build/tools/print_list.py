"""Measure every STL and produce a config-aware print list.

Reads the 'Printed & Machined Parts' tab of CAD/Voron_Cascade_BOM.xlsx for
quantity / colour / material / notes, measures each STL with trimesh, and
estimates filament use from the slicer settings in the manual (4 walls,
5 top/bottom, 40% infill).

Usage: python build/tools/print_list.py [--config build/config.json]
Writes build/print_list.csv and prints a summary.
"""
import argparse, csv, json, re, sys
from pathlib import Path
from itertools import permutations
import openpyxl, trimesh

ROOT = Path(__file__).resolve().parents[2]
DENSITY = {"ABS": 1.04, "PLA": 1.24, "PETG": 1.27}  # g/cm3
LINE_W, WALLS, TB_LAYERS, LAYER_H, INFILL = 0.4, 4, 5, 0.2, 0.40


# BOM name -> STL name where the two disagree
ALIASES = {"[pp_p]_wago_221_415_3x5_2020mount": "[pp_p]_wago_221_415_2020mount_3x5"}


def norm(name):
    name = re.sub(r"\.stl$", "", name.strip(), flags=re.I)
    name = re.sub(r"_x\d+$", "", name)
    name = re.sub(r"_v\d+$", "", name)
    name = re.sub(r"[\s-]+", "_", name.lower())
    return ALIASES.get(name, name)


def bom_rows():
    ws = openpyxl.load_workbook(ROOT / "CAD/Voron_Cascade_BOM.xlsx", data_only=True)["Printed  & Machined Parts"]
    rows, cat = [], None
    for r in ws.iter_rows(values_only=True):
        c0, name, count, color, mat, notes = (list(r) + [None] * 6)[:6]
        if name == "Name" or not name:
            continue
        if str(name).startswith("[mp-a]"):
            break  # machined parts follow; not printed
        cat = c0 or cat
        rows.append(dict(category=cat, name=str(name).strip(), qty=int(count or 1),
                         color=color, material=mat, notes=notes or ""))
    return rows


def estimate_grams(mesh, material):
    """Shell + infill estimate: perimeters/top/bottom solid, interior at INFILL."""
    vol = abs(mesh.volume) / 1000.0  # cm3
    area = mesh.area / 100.0  # cm2
    shell_t = min(WALLS * LINE_W, TB_LAYERS * LAYER_H) / 10.0  # cm (conservative)
    shell = min(vol, area * shell_t)
    plastic = shell + (vol - shell) * INFILL
    return plastic * DENSITY.get(material, 1.04), vol


def wanted(row, cfg):
    """Apply the 'Choose 1 of N' / 'Only if' notes using config choices."""
    n, notes = norm(row["name"]), row["notes"].lower()
    sel = cfg["selections"]
    if "only needed if self drilling frame" in notes:
        return cfg["self_drill_frame"]
    if "only needed if self cutting panels" in notes:
        return cfg["self_cut_panels"]
    for key, opts in sel.items():
        if any(norm(o) == n for o in cfg["options"][key]):
            return norm(opts) == n
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "build/config.json"))
    ap.add_argument("--bed", default=None, help="bed size XxYxZ mm, overrides config")
    a = ap.parse_args()
    cfg = json.loads(Path(a.config).read_text())
    bed = [float(v) for v in (a.bed or cfg["printer_bed_mm"]).split("x")]

    stls = {norm(p.name): p for p in (ROOT / "STLs").rglob("*.stl")}
    out, missing, used = [], [], set()
    for row in bom_rows():
        key = norm(row["name"])
        p = stls.get(key)
        rec = dict(row, include=wanted(row, cfg), file="", grams=0, volume_cm3=0,
                   bbox_mm="", fits_bed="")
        if p is None:
            missing.append(row["name"])
        else:
            used.add(key)
            m = trimesh.load(p, force="mesh")
            g, v = estimate_grams(m, row["material"])
            # fits if any axis-aligned orientation fits the build volume
            fits = any(all(e <= b for e, b in zip(perm, bed)) for perm in permutations(m.extents))
            rec.update(file=str(p.relative_to(ROOT)), grams=round(g, 1), volume_cm3=round(v, 1),
                       bbox_mm="x".join(f"{e:.0f}" for e in m.extents), fits_bed=fits)
        out.append(rec)

    orphans = sorted(str(p.relative_to(ROOT)) for k, p in stls.items() if k not in used)
    cols = ["include", "category", "name", "qty", "color", "material", "grams", "volume_cm3",
            "bbox_mm", "fits_bed", "notes", "file"]
    with open(ROOT / "build/print_list.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)

    inc = [r for r in out if r["include"]]
    tot = {}
    for r in inc:
        k = f'{r["material"]} {r["color"]}'
        tot[k] = tot.get(k, 0) + r["grams"] * r["qty"]
    print(f"parts to print: {len(inc)} files, {sum(r['qty'] for r in inc)} pieces")
    for k, g in sorted(tot.items()):
        print(f"  {k:<16} {g/1000:5.2f} kg")
    print(f"  total            {sum(tot.values())/1000:5.2f} kg (est., before supports/purge)")
    big = [r["name"] for r in inc if r["fits_bed"] is False]
    print("does not fit bed:", big or "none")
    print("BOM entries with no STL in repo:", missing or "none")
    print("STLs not referenced by BOM:", orphans or "none")


if __name__ == "__main__":
    sys.exit(main())
