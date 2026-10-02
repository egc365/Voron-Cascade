"""Camera placement study for an in-enclosure vision rig / digital twin.

Places candidate cameras in the real Cascade assembly (slim GLB from
slim_glb.py) and ray-casts against the machine to measure what each camera
can actually see: the cutting zone in front of the tool, and the table top.

Machine frame used here (mm): X right, D toward the back, U up.
The GLB stores (x=X, y=D, z=U) in metres.

Usage: python vision_study.py <cascade_slim.glb>  -> build/vision/rig.json
"""
import json, math, re, sys
from pathlib import Path
import numpy as np, trimesh

ROOT = Path(__file__).resolve().parents[2]

# Parts in the CAD that are alternatives, setup tools or optional accessories,
# not on a running machine with the default config: other Z plates/spindles,
# the grid table (T-slot is the default), jigs, the dial indicator, and the
# optional above-table tool setter that sits under the spindle in the CAD.
NOT_INSTALLED = re.compile(
    r"OPTIONAL|123block|alignment_|setup_tool|tramming|drill_(jig|template)|x_spacer_washer_guide|"
    r"WS55|se_600|scylla|_grid\b|Grid Worktable|portrait|_long_body|_probe_mount|z_carriage_cover_blank|"
    r"z_carriage_plate_(M6|M8_99|blank)|Spindle Clamp 50|Spindle Mount 80|M6x100_threaded_rod|"
    r"(Housing|Top Housing|Main Housing|Rubber Seal|Plunger|Base|Magnet|Air manifold|Cable Connector|"
    r"Dial|Case|Glass|Shaft|Tip|Stem|Stand 7010SN|M6x°\d+ Star Knob|Spring 0.8x°8x1\d|Sleeve °10.*|"
    r"Clamp Block °1\d|Core °10.*|°10 Arm|Long pointer|Cover knob|Back cover and lug) \(sub\)", re.I)
# the clear panels are see-through; cameras sit inside them
CLEAR = re.compile(r"\[sp-c\]|Accordion", re.I)

# Geometry measured from the assembly (see README in build/vision)
TABLE = dict(x=(-129, 171), d=(-53, 167), u=-1)        # grid / T-slot table top
SPINDLE_AXIS = dict(x=160.5, d=153.5, nose_u=43)        # 65 mm spindle as modelled

CAMERAS = [
    dict(id="A", name="Cut-zone overview", kind="global-shutter 2D",
         example="Raspberry Pi Global Shutter Camera (IMX296, 1456x1088) + 4 mm CS lens",
         mount="fixed, front 2020 rail of the working enclosure, looking back-down at the tool line",
         pos=(21, 0, 262), look=(21, 150, 20), hfov=64.2, vfov=50.2, px=(1456, 1088), moves_with=None),
    dict(id="B", name="Tool cam", kind="global-shutter 2D, close range",
         example="small USB global-shutter module (OV9281 class) with ~70 deg M12 lens, behind an air-purged window",
         mount="on the Z carriage, front-left of the spindle; moves with X and Z",
         pos=(112, 95, 115), look=(160.5, 150, 20), hfov=70, vfov=50, px=(1280, 800), moves_with="Z carriage"),
    dict(id="C", name="Stock + fixture depth", kind="short-range stereo depth",
         example="RealSense D405 (87x58 deg, 7-50 cm ideal range)",
         mount="fixed, enclosure top rail, straight down over the table's front (load) position",
         pos=(21, 40, 262), look=(21, 40, 0), hfov=87, vfov=58, px=(1280, 720), moves_with=None),
]


def load_scene(path):
    sc = trimesh.load(path)
    keep = []
    for node in sc.graph.nodes_geometry:
        if NOT_INSTALLED.search(node) or CLEAR.search(node):
            continue
        T, g = sc.graph[node]
        m = sc.geometry[g].copy()
        m.apply_transform(T)
        keep.append(m)
    m = trimesh.util.concatenate(keep)
    m.apply_scale(1000.0)  # -> mm, frame (X, D, U)
    return m


def in_frustum(cam, pts):
    p = np.asarray(cam["pos"], float)
    fwd = np.asarray(cam["look"], float) - p
    fwd /= np.linalg.norm(fwd)
    up_hint = np.array([0, 0, 1.0]) if abs(fwd[2]) < 0.95 else np.array([0, 1.0, 0])
    right = np.cross(fwd, up_hint); right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    v = pts - p
    z = v @ fwd
    ok = z > 1
    ax = np.degrees(np.arctan2(np.abs(v @ right), z))
    ay = np.degrees(np.arctan2(np.abs(v @ up), z))
    return ok & (ax <= cam["hfov"] / 2) & (ay <= cam["vfov"] / 2), np.linalg.norm(v, axis=1)


def visible(mesh, cam, pts):
    """Unoccluded = no machine surface between camera and point (2 mm grace)."""
    p = np.asarray(cam["pos"], float)
    d = pts - p
    dist = np.linalg.norm(d, axis=1)
    hits, ray_idx, _ = mesh.ray.intersects_location(
        np.tile(p, (len(pts), 1)), d / dist[:, None], multiple_hits=True)
    first = np.full(len(pts), np.inf)
    hd = np.linalg.norm(hits - p, axis=1)
    np.minimum.at(first, ray_idx, hd)
    return first >= dist - 2.0


def mm_per_px(cam, dist):
    return 2 * dist * math.tan(math.radians(cam["hfov"] / 2)) / cam["px"][0]


def main():
    mesh = load_scene(sys.argv[1])
    # Cut zone: the line the tool sweeps (X across the table) at the spindle's
    # fixed depth, from table top to 60 mm of stock; sampled on the tool's front side.
    xs = np.linspace(*TABLE["x"], 31)
    us = np.linspace(0, 60, 7)
    cut = np.array([(x, SPINDLE_AXIS["d"] - 8, u) for x in xs for u in us])
    tx, td = np.meshgrid(np.linspace(*TABLE["x"], 25), np.linspace(*TABLE["d"], 19))
    table = np.c_[tx.ravel(), td.ravel(), np.full(tx.size, TABLE["u"] + 0.5)]

    results = []
    for cam in CAMERAS:
        r = dict(cam)
        if cam["moves_with"]:
            # tool cam: check the tool tip region relative to the spindle, at this X/Z
            tip = np.array([(SPINDLE_AXIS["x"] + dx, SPINDLE_AXIS["d"] - 8, u)
                            for dx in np.linspace(-15, 15, 7) for u in np.linspace(5, 45, 9)])
            f, dist = in_frustum(cam, tip)
            v = visible(mesh, cam, tip)
            r["tool_tip_visible_pct"] = float(round(100 * (f & v).mean(), 1))
            r["mm_per_px_at_tip"] = float(round(mm_per_px(cam, dist.mean()), 3))
        else:
            f, dist = in_frustum(cam, cut)
            v = visible(mesh, cam, cut)
            r["cut_zone_visible_pct"] = float(round(100 * (f & v).mean(), 1))
            r["cut_zone_in_frame_pct"] = float(round(100 * f.mean(), 1))
            r["mm_per_px_at_cut_zone"] = float(round(mm_per_px(cam, dist[f].mean()), 3)) if f.any() else None
            f2, dist2 = in_frustum(cam, table)
            # table measured at its front (load) position: shift by the D offset of that view
            r["table_in_frame_pct"] = float(round(100 * f2.mean(), 1))
            r["mm_per_px_at_table"] = float(round(mm_per_px(cam, dist2.mean()), 3))
        results.append(r)
        print(cam["id"], cam["name"], {k: float(v) for k, v in r.items()
                                       if k.endswith(("_pct", "_tip", "_zone", "_table")) and v is not None})
    out = dict(frame="mm; X right, D toward back, U up; GLB stores (X, D, U) in metres",
               table=TABLE, spindle=SPINDLE_AXIS, cameras=results)
    (ROOT / "build/vision").mkdir(parents=True, exist_ok=True)
    (ROOT / "build/vision/rig.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
