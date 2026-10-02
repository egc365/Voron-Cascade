"""Drop fasteners/small hardware from the assembly GLB, merge faces per part
and decimate heavy parts so it is small enough for a browser viewer.

Usage: python slim_glb.py <in.glb> <out.glb>
"""
import re, sys
from collections import defaultdict
import numpy as np, trimesh

HARDWARE = re.compile(r"^(M\d+(x[\d.]+)*\b|M\d+ .*(Nut|Washer|Insert)|MGN12 Rail Plug|.*T-Nut|GOM-04|.*Screw|.*Grease|.*Wiper|.*Endcap|LED_|.*(Washer|Nut)\b)", re.I)

MAX_TRIS = 2000
sc = trimesh.load(sys.argv[1])
g = sc.graph
parts = defaultdict(list)  # part name -> meshes (world space)
for node in g.nodes_geometry:
    part = node.rsplit("_", 1)[0] if re.search(r"_[0-9a-f]{6}$", node) else node
    if HARDWARE.match(part):
        continue
    T, gname = g[node]
    m = sc.geometry[gname].copy()
    m.apply_transform(T)
    parts[part].append(m)

out = trimesh.Scene()
for part, ms in parts.items():
    # group by colour so each part keeps its look
    by_col = defaultdict(list)
    for m in ms:
        c = tuple(np.round(m.visual.material.baseColorFactor if hasattr(m.visual, "material")
                           and getattr(m.visual.material, "baseColorFactor", None) is not None
                           else [200, 200, 200, 255]).astype(int))
        by_col[c].append(m)
    for i, (c, group) in enumerate(by_col.items()):
        mm = trimesh.util.concatenate(group)
        mm.merge_vertices()
        if len(mm.faces) > MAX_TRIS:  # quadric decimation, keeps silhouettes
            mm = mm.simplify_quadric_decimation(face_count=MAX_TRIS)
        mm.visual = trimesh.visual.ColorVisuals(mm, face_colors=np.tile(c, (len(mm.faces), 1)))
        out.add_geometry(mm, node_name=f"{part}#{i}" if i else part, geom_name=f"{part}#{i}")
out.export(sys.argv[2])
print(len(parts), "parts kept;", sum(len(g.faces) for g in out.geometry.values()), "triangles")
