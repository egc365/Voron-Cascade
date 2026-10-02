"""Tessellate the Cascade STEP assembly into a GLB (colors + part names kept).

Usage: python step_to_glb.py <assembly.step> <out.glb> [linear_deflection_mm]
"""
import sys, time
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString, TCollection_AsciiString
from OCP.XCAFApp import XCAFApp_Application
from OCP.IFSelect import IFSelect_RetDone
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.RWGltf import RWGltf_CafWriter
from OCP.TColStd import TColStd_IndexedDataMapOfStringString
from OCP.Message import Message_ProgressRange
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.TDF import TDF_LabelSequence

src, out = sys.argv[1], sys.argv[2]
defl = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
t = time.time()
app = XCAFApp_Application.GetApplication_s()
doc = TDocStd_Document(TCollection_ExtendedString("XmlXCAF"))
app.InitDocument(doc)
r = STEPCAFControl_Reader()
r.SetColorMode(True); r.SetNameMode(True)
assert r.ReadFile(src) == IFSelect_RetDone, "read failed"
r.Transfer(doc)
print(f"read {time.time()-t:.0f}s", flush=True)
st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
labels = TDF_LabelSequence(); st.GetFreeShapes(labels)
for i in range(1, labels.Length() + 1):
    BRepMesh_IncrementalMesh(st.GetShape_s(labels.Value(i)), defl, False, 0.5, True)
print(f"meshed {time.time()-t:.0f}s", flush=True)
w = RWGltf_CafWriter(TCollection_AsciiString(out), True)
# STEP is mm, Z-up; glTF is metres, Y-up
w.ChangeCoordinateSystemConverter().SetInputLengthUnit(0.001)
w.Perform(doc, TColStd_IndexedDataMapOfStringString(), Message_ProgressRange())
print(f"wrote {out} {time.time()-t:.0f}s", flush=True)
