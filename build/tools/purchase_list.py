"""Turn the BOM tab into a purchase list for the choices in build/config.json.

Handles the BOM's 'Option N:' groups (spindle, controller, work table),
'SELECT:' Z carriage plates, '- OPTIONAL' items and the drilling-tool
sections that only apply when you drill/tap raw extrusions yourself.

Usage: python build/tools/purchase_list.py [--config build/config.json]
Writes build/purchase_list.csv.
"""
import argparse, csv, json
from pathlib import Path
import openpyxl

ROOT = Path(__file__).resolve().parents[2]
OPTION_GROUPS = {"Work Table Options": "work_table", "Spindle Options": "spindle",
                 "Controller Configuration": "controller"}
SELF_DRILL = ("Tools for drilling extrusion bed", "Tools for drilling and preparing extrusions and panels")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "build/config.json"))
    cfg = json.loads(Path(ap.parse_args().config).read_text())
    ws = openpyxl.load_workbook(ROOT / "CAD/Voron_Cascade_BOM.xlsx", data_only=True)["BOM"]

    out, section, group, option, sub = [], None, None, None, None
    for item, pn, qty, *_ in ws.iter_rows(min_row=2, values_only=True):
        item = (item or "").strip()
        pn = (str(pn).strip() if pn is not None else "")
        if not item and not pn:
            continue
        heading = qty is None and item and (not pn or item.startswith(("Option", "Tools for"))
                                            or item in OPTION_GROUPS or section == "Panels (see other tab)")
        if heading:
            if item.startswith("Option"):
                option = item
            elif item in OPTION_GROUPS:
                section, group, option, sub = item, OPTION_GROUPS[item], None, None
            elif section == "Panels (see other tab)" and pn:
                sub = f"{item} ({pn})"
            else:
                section, group, option, sub = item, None, None, None
            continue

        include, why = True, ""
        if group:
            include = option == cfg[group]
            why = option
        if item.startswith("SELECT:"):
            include = pn == cfg["z_carriage_plate"]
            why = "Z plate choice"
        if "OPTIONAL" in item.upper() or pn.lower().startswith("optional"):
            include = include and cfg["include_optional"]
            why = "optional"
        if section in SELF_DRILL:
            include = cfg["self_drill_frame"] or cfg["self_cut_panels"]
            why = "only if drilling/tapping raw stock"
        if section == "Panels (see other tab)" and not item:
            item = pn
            pn = sub or ""
        out.append(dict(include=include, section=section, item=item, part_number=pn,
                        qty=qty, note=why))

    with open(ROOT / "build/purchase_list.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["include", "section", "item", "part_number", "qty", "note"])
        w.writeheader()
        w.writerows(out)
    inc = [r for r in out if r["include"]]
    by = {}
    for r in inc:
        by[r["section"]] = by.get(r["section"], 0) + 1
    print(f"{len(inc)} line items to buy/source ({len(out) - len(inc)} excluded by config)")
    for s, n in by.items():
        print(f"  {n:3d}  {s}")


if __name__ == "__main__":
    main()
