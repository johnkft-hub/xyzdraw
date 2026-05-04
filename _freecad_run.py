import FreeCAD as App
import Part

doc = App.newDocument("GeneratedModel")

shape = Part.makeBox(3.0, 5.0, 1.0)

part = doc.addObject("Part::Feature", "Box")
part.Shape = shape
doc.recompute()

doc.saveAs(r"D:/17_my_project/xyzdraw\generated_box.FCStd")
print("FCStd:", r"D:/17_my_project/xyzdraw\generated_box.FCStd")
shape.exportStep(r"D:/17_my_project/xyzdraw\generated_box.step")
print("STEP:", r"D:/17_my_project/xyzdraw\generated_box.step")
shape.exportStl(r"D:/17_my_project/xyzdraw\generated_box.stl")
print("STL:", r"D:/17_my_project/xyzdraw\generated_box.stl")

# GUI 모드일 때만 실행: ViewProvider 초기화 + 3D 뷰 맞춤
try:
    import FreeCADGui as Gui
    Gui.ActiveDocument.ActiveView.viewIsometric()
    Gui.SendMsgToActiveView("ViewFit")
except Exception:
    pass  # 헤드리스 모드에서는 Gui 모듈이 없으므로 무시

print("Done.")
