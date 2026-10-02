"""Write the configured machine (default build, no jigs/alternatives) as a
web-ready GLB with normals, for the 3D viewer.

Usage: python web_glb.py <cascade_slim.glb> <out.glb>
"""
import sys
import trimesh
from vision_study import NOT_INSTALLED

sc = trimesh.load(sys.argv[1])
out = trimesh.Scene()
for node in sc.graph.nodes_geometry:
    if NOT_INSTALLED.search(node):
        continue
    T, g = sc.graph[node]
    m = sc.geometry[g].copy()
    m.apply_transform(T)
    out.add_geometry(m, node_name=node, geom_name=node)
out.export(sys.argv[2], include_normals=True)
print(len(out.geometry), "parts")
