"""
3D 도면 자동 생성 프로그램
- FreeCAD Scripting Basics (wiki.freecad.org) 기반
- Part 모듈로 실제 형상 생성 후 FCStd / STEP / STL 저장
- 다중 생성 / 간격 / 내부 도형 지원
"""

import os
import sys
import shutil
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# ── 단위 변환 ──────────────────────────────────────────────────────────────────
UNIT_TO_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0}


def to_mm(value, unit):
    return value * UNIT_TO_MM[unit]


# ── FreeCAD 실행 파일 탐색 ────────────────────────────────────────────────────
def find_freecad_executables(custom_dir=None):
    if custom_dir and os.path.isdir(custom_dir):
        if sys.platform.startswith("win"):
            g = os.path.join(custom_dir, "FreeCAD.exe")
            c = os.path.join(custom_dir, "FreeCADCmd.exe")
        else:
            g = os.path.join(custom_dir, "FreeCAD")
            c = os.path.join(custom_dir, "FreeCADCmd")
        gui = g if os.path.exists(g) else None
        cmd = c if os.path.exists(c) else None
        if gui or cmd:
            return gui, cmd

    if sys.platform.startswith("win"):
        gui_cands = [
            shutil.which("FreeCAD.exe"),
            r"C:\Program Files\FreeCAD 1.0\bin\FreeCAD.exe",
            r"C:\Program Files\FreeCAD 0.21\bin\FreeCAD.exe",
            r"C:\Program Files\FreeCAD\bin\FreeCAD.exe",
        ]
        cmd_cands = [
            shutil.which("FreeCADCmd.exe"),
            r"C:\Program Files\FreeCAD 1.0\bin\FreeCADCmd.exe",
            r"C:\Program Files\FreeCAD 0.21\bin\FreeCADCmd.exe",
            r"C:\Program Files\FreeCAD\bin\FreeCADCmd.exe",
        ]
    elif sys.platform == "darwin":
        gui_cands = [shutil.which("FreeCAD"), "/Applications/FreeCAD.app/Contents/MacOS/FreeCAD"]
        cmd_cands = [shutil.which("FreeCADCmd"), "/Applications/FreeCAD.app/Contents/MacOS/FreeCADCmd"]
    else:
        gui_cands = [shutil.which("freecad"), shutil.which("FreeCAD"),
                     "/usr/bin/freecad", "/usr/bin/FreeCAD", "/snap/bin/freecad"]
        cmd_cands = [shutil.which("freecadcmd"), shutil.which("FreeCADCmd"),
                     "/usr/bin/freecadcmd", "/usr/bin/FreeCADCmd"]

    gui = next((p for p in gui_cands if p and os.path.exists(p)), None)
    cmd = next((p for p in cmd_cands if p and os.path.exists(p)), None)
    return gui, cmd


# ── FreeCAD 스크립트 생성 ─────────────────────────────────────────────────────

def _make_shape_call(shape_type, params, px, py, pz):
    """Part.make* 호출 문자열 생성 (위치 포함)."""
    pos = f"App.Vector({px:.6g}, {py:.6g}, {pz:.6g})"
    if shape_type == "Box":
        return (f"Part.makeBox({params['length']:.6g}, {params['width']:.6g}, "
                f"{params['height']:.6g}, {pos})")
    if shape_type == "Cylinder":
        return f"Part.makeCylinder({params['radius']:.6g}, {params['height']:.6g}, {pos})"
    if shape_type == "Cone":
        return (f"Part.makeCone({params['radius1']:.6g}, {params['radius2']:.6g}, "
                f"{params['height']:.6g}, {pos})")
    if shape_type == "Sphere":
        return f"Part.makeSphere({params['radius']:.6g}, {pos})"
    raise ValueError(f"Unknown shape type: {shape_type}")


def _shape_x_extent(shape_type, params):
    """X 방향 전체 크기 (간격 계산용)."""
    if shape_type == "Box":      return params["length"]
    if shape_type == "Cylinder": return 2.0 * params["radius"]
    if shape_type == "Cone":     return 2.0 * max(params["radius1"], params["radius2"])
    if shape_type == "Sphere":   return 2.0 * params["radius"]


def _shape_center_offset(shape_type, params):
    """도형 위치 벡터 기준 기하학적 중심 오프셋 (cx, cy, cz)."""
    if shape_type == "Box":
        return params["length"] / 2, params["width"] / 2, params["height"] / 2
    if shape_type in ("Cylinder", "Cone"):
        return 0.0, 0.0, params["height"] / 2
    if shape_type == "Sphere":
        return 0.0, 0.0, 0.0


def _inner_position(inner_type, inner_params, cx, cy, cz):
    """내부 도형의 중심이 (cx, cy, cz)가 되도록 하는 위치 벡터."""
    if inner_type == "Box":
        l, w, h = inner_params["length"], inner_params["width"], inner_params["height"]
        return cx - l / 2, cy - w / 2, cz - h / 2
    if inner_type in ("Cylinder", "Cone"):
        return cx, cy, cz - inner_params["height"] / 2
    if inner_type == "Sphere":
        return cx, cy, cz


def make_freecad_script(outer_type, outer_params, count, spacing,
                         inner_type, inner_params,
                         out_fcstd, out_step, out_stl):
    step_x = _shape_x_extent(outer_type, outer_params) + spacing
    has_inner = inner_type is not None

    lines = [
        "import FreeCAD as App",
        "import Part",
        "",
        'doc = App.newDocument("GeneratedModel")',
        "all_shapes = []",
        "",
    ]

    for i in range(count):
        px = i * step_x
        lines.append(f"# outer shape {i + 1}")
        lines.append(f"s{i} = {_make_shape_call(outer_type, outer_params, px, 0, 0)}")
        lines.append(f"all_shapes.append(s{i})")
        if has_inner:
            ocx, ocy, ocz = _shape_center_offset(outer_type, outer_params)
            ipx, ipy, ipz = _inner_position(inner_type, inner_params, px + ocx, ocy, ocz)
            lines.append(f"inner{i} = {_make_shape_call(inner_type, inner_params, ipx, ipy, ipz)}")
            lines.append(f"all_shapes.append(inner{i})")
        lines.append("")

    lines += [
        "result = Part.makeCompound(all_shapes) if len(all_shapes) > 1 else all_shapes[0]",
        'part = doc.addObject("Part::Feature", "GeneratedModel")',
        "part.Shape = result",
        "doc.recompute()",
        "",
    ]

    if out_fcstd:
        lines += [f'doc.saveAs(r"{out_fcstd}")', f'print("FCStd:", r"{out_fcstd}")']
    if out_step:
        lines += [f'result.exportStep(r"{out_step}")', f'print("STEP:", r"{out_step}")']
    if out_stl:
        lines += [f'result.exportStl(r"{out_stl}")', f'print("STL:", r"{out_stl}")']

    lines += [
        "",
        "try:",
        "    import FreeCADGui as Gui",
        "    Gui.ActiveDocument.ActiveView.viewIsometric()",
        '    Gui.SendMsgToActiveView("ViewFit")',
        "except Exception:",
        "    pass",
        "",
        'print("Done.")',
    ]
    return "\n".join(lines)


# ── GUI 콜백 ─────────────────────────────────────────────────────────────────
def browse_freecad_folder():
    folder = filedialog.askdirectory(title="FreeCAD 실행 파일이 있는 폴더 선택")
    if folder:
        entry_freecad_dir.delete(0, tk.END)
        entry_freecad_dir.insert(0, folder)


def browse_output_folder():
    folder = filedialog.askdirectory(title="출력 폴더 선택")
    if folder:
        entry_output_dir.delete(0, tk.END)
        entry_output_dir.insert(0, folder)


def on_shape_changed(event=None):
    s = combo_shape.get()
    for widget in param_frame.winfo_children():
        widget.grid_remove()
    if s == "Box":
        lbl_p1.config(text="x (길이)")
        lbl_p2.config(text="y (너비)")
        lbl_p3.config(text="z (높이)")
        for w in [lbl_p1, entry_p1, combo_u1,
                  lbl_p2, entry_p2, combo_u2,
                  lbl_p3, entry_p3, combo_u3]:
            w.grid()
    elif s == "Cylinder":
        lbl_p1.config(text="반지름 (r)")
        lbl_p2.config(text="높이 (h)")
        for w in [lbl_p1, entry_p1, combo_u1,
                  lbl_p2, entry_p2, combo_u2]:
            w.grid()
    elif s == "Cone":
        lbl_p1.config(text="밑면 반지름")
        lbl_p2.config(text="윗면 반지름")
        lbl_p3.config(text="높이 (h)")
        for w in [lbl_p1, entry_p1, combo_u1,
                  lbl_p2, entry_p2, combo_u2,
                  lbl_p3, entry_p3, combo_u3]:
            w.grid()
    elif s == "Sphere":
        lbl_p1.config(text="반지름 (r)")
        for w in [lbl_p1, entry_p1, combo_u1]:
            w.grid()


def on_inner_shape_changed(event=None):
    s = combo_inner_shape.get()
    for widget in inner_param_frame.winfo_children():
        widget.grid_remove()
    if s == "Box":
        lbl_ip1.config(text="x (길이)")
        lbl_ip2.config(text="y (너비)")
        lbl_ip3.config(text="z (높이)")
        for w in [lbl_ip1, entry_ip1, combo_iu1,
                  lbl_ip2, entry_ip2, combo_iu2,
                  lbl_ip3, entry_ip3, combo_iu3]:
            w.grid()
    elif s == "Cylinder":
        lbl_ip1.config(text="반지름 (r)")
        lbl_ip2.config(text="높이 (h)")
        for w in [lbl_ip1, entry_ip1, combo_iu1,
                  lbl_ip2, entry_ip2, combo_iu2]:
            w.grid()
    elif s == "Cone":
        lbl_ip1.config(text="밑면 반지름")
        lbl_ip2.config(text="윗면 반지름")
        lbl_ip3.config(text="높이 (h)")
        for w in [lbl_ip1, entry_ip1, combo_iu1,
                  lbl_ip2, entry_ip2, combo_iu2,
                  lbl_ip3, entry_ip3, combo_iu3]:
            w.grid()
    elif s == "Sphere":
        lbl_ip1.config(text="반지름 (r)")
        for w in [lbl_ip1, entry_ip1, combo_iu1]:
            w.grid()


def on_inner_toggle():
    if var_inner.get():
        inner_frame.grid(row=9, column=0, columnspan=3,
                         padx=10, pady=4, sticky="ew")
        on_inner_shape_changed()
    else:
        inner_frame.grid_remove()


def get_param(entry, combo):
    v = float(entry.get())
    if v <= 0:
        raise ValueError("0보다 커야 합니다")
    return to_mm(v, combo.get())


def get_inner_params():
    """내부 도형 비활성화 시 (None, None), 활성화 시 (type, params) 반환."""
    if not var_inner.get():
        return None, None
    inner_type = combo_inner_shape.get()
    try:
        if inner_type == "Box":
            params = {
                "length": get_param(entry_ip1, combo_iu1),
                "width":  get_param(entry_ip2, combo_iu2),
                "height": get_param(entry_ip3, combo_iu3),
            }
        elif inner_type == "Cylinder":
            params = {
                "radius": get_param(entry_ip1, combo_iu1),
                "height": get_param(entry_ip2, combo_iu2),
            }
        elif inner_type == "Cone":
            params = {
                "radius1": get_param(entry_ip1, combo_iu1),
                "radius2": get_param(entry_ip2, combo_iu2),
                "height":  get_param(entry_ip3, combo_iu3),
            }
        elif inner_type == "Sphere":
            params = {"radius": get_param(entry_ip1, combo_iu1)}
        else:
            raise ValueError("내부 도형을 선택해주세요.")
        return inner_type, params
    except ValueError as e:
        raise ValueError(f"내부 도형 파라미터 오류: {e}")


def generate_model():
    shape = combo_shape.get()

    # ── 외부 도형 파라미터 ──
    try:
        if shape == "Box":
            outer_params = {
                "length": get_param(entry_p1, combo_u1),
                "width":  get_param(entry_p2, combo_u2),
                "height": get_param(entry_p3, combo_u3),
            }
            desc = (f"x={entry_p1.get()} {combo_u1.get()}  "
                    f"y={entry_p2.get()} {combo_u2.get()}  "
                    f"z={entry_p3.get()} {combo_u3.get()}")
        elif shape == "Cylinder":
            outer_params = {
                "radius": get_param(entry_p1, combo_u1),
                "height": get_param(entry_p2, combo_u2),
            }
            desc = (f"r={entry_p1.get()} {combo_u1.get()}  "
                    f"h={entry_p2.get()} {combo_u2.get()}")
        elif shape == "Cone":
            outer_params = {
                "radius1": get_param(entry_p1, combo_u1),
                "radius2": get_param(entry_p2, combo_u2),
                "height":  get_param(entry_p3, combo_u3),
            }
            desc = (f"r1={entry_p1.get()} {combo_u1.get()}  "
                    f"r2={entry_p2.get()} {combo_u2.get()}  "
                    f"h={entry_p3.get()} {combo_u3.get()}")
        elif shape == "Sphere":
            outer_params = {"radius": get_param(entry_p1, combo_u1)}
            desc = f"r={entry_p1.get()} {combo_u1.get()}"
        else:
            messagebox.showerror("오류", "도형을 선택해주세요.")
            return
    except ValueError as e:
        messagebox.showerror("입력 오류", f"파라미터 값을 확인해주세요.\n{e}")
        return

    # ── 개수 / 간격 ──
    try:
        count = int(spin_count.get())
        if count < 1 or count > 20:
            raise ValueError("개수는 1~20 사이여야 합니다.")
        spacing_raw = entry_spacing.get().strip() or "0"
        spacing = to_mm(float(spacing_raw), combo_spacing_unit.get())
        if spacing < 0:
            raise ValueError("간격은 0 이상이어야 합니다.")
    except ValueError as e:
        messagebox.showerror("입력 오류", f"개수/간격 값을 확인해주세요.\n{e}")
        return

    # ── 내부 도형 파라미터 ──
    try:
        inner_type, inner_params = get_inner_params()
    except ValueError as e:
        messagebox.showerror("입력 오류", str(e))
        return

    # ── 출력 폴더 ──
    out_dir = entry_output_dir.get().strip()
    if not out_dir:
        out_dir = os.path.join(os.path.expanduser("~"), "Documents")
    os.makedirs(out_dir, exist_ok=True)

    base = os.path.join(out_dir, f"generated_{shape.lower()}")
    out_fcstd = base + ".FCStd" if var_fcstd.get() else ""
    out_step  = base + ".step"  if var_step.get()  else ""
    out_stl   = base + ".stl"   if var_stl.get()   else ""

    if not any([out_fcstd, out_step, out_stl]):
        messagebox.showerror("저장 형식 오류", "저장 형식을 하나 이상 선택해주세요.")
        return

    # ── FreeCAD 실행 파일 탐색 ──
    custom_dir = entry_freecad_dir.get().strip() or None
    gui_path, cmd_path = find_freecad_executables(custom_dir)

    if not gui_path and not cmd_path:
        messagebox.showerror(
            "FreeCAD 없음",
            "FreeCAD 실행 파일을 찾을 수 없습니다.\n"
            "FreeCAD 설치 폴더를 직접 입력하거나 FreeCAD를 설치해주세요."
        )
        return

    # ── 스크립트 생성 ──
    script_path = os.path.join(out_dir, "_freecad_run.py")
    script_content = make_freecad_script(
        shape, outer_params, count, spacing,
        inner_type, inner_params,
        out_fcstd, out_step, out_stl,
    )
    try:
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)
    except OSError as e:
        messagebox.showerror("파일 오류", f"스크립트 파일을 생성할 수 없습니다.\n{e}")
        return

    count_desc  = f" ×{count}" if count > 1 else ""
    inner_desc  = f"  / 내부: {inner_type}" if inner_type else ""
    full_desc   = f"{desc}{count_desc}{inner_desc}"

    if gui_path:
        try:
            subprocess.Popen([gui_path, script_path])
        except Exception as e:
            messagebox.showerror("실행 오류", f"FreeCAD 실행 실패\n{e}")
            return
        result_label.config(
            text=f"[{shape}]{count_desc} FreeCAD 실행 중...\n{full_desc}\n\n"
                 "※ 파일 생성 완료 후 아래에 경로가 표시됩니다."
        )
        root.after(6000, lambda: _check_saved(shape, full_desc, out_fcstd, out_step, out_stl))
    else:
        try:
            subprocess.run(
                [cmd_path, script_path],
                check=True, capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=120,
            )
        except subprocess.CalledProcessError as e:
            err = (e.stderr or e.stdout or str(e))[:800]
            messagebox.showerror("실행 오류", f"FreeCADCmd 실행 오류\n\n{err}")
            return
        except Exception as e:
            messagebox.showerror("오류", str(e))
            return
        _check_saved(shape, full_desc, out_fcstd, out_step, out_stl, show_popup=True)


def _check_saved(shape, desc, out_fcstd, out_step, out_stl, show_popup=False):
    saved = []
    if out_fcstd and os.path.exists(out_fcstd):
        saved.append(f"FCStd : {out_fcstd}")
    if out_step and os.path.exists(out_step):
        saved.append(f"STEP  : {out_step}")
    if out_stl and os.path.exists(out_stl):
        saved.append(f"STL   : {out_stl}")

    if saved:
        result_label.config(
            text=f"[{shape}] 생성 완료\n{desc}\n\n" + "\n".join(saved)
        )
        if show_popup:
            messagebox.showinfo("완료", f"{shape} 3D 도면 생성이 완료되었습니다.")
    else:
        current = result_label.cget("text")
        if "재확인" not in current:
            result_label.config(
                text=result_label.cget("text") + "\n(파일 저장 대기 중... 재확인)"
            )
        root.after(3000, lambda: _check_saved(shape, desc, out_fcstd, out_step, out_stl))


# ── GUI 구성 ──────────────────────────────────────────────────────────────────
root = tk.Tk()
root.title("3D 도면 자동 생성 프로그램")
root.geometry("580x840")
root.resizable(False, True)

units = ["mm", "cm", "m"]
PAD = {"padx": 8, "pady": 4}

# 제목
tk.Label(root, text="3D 도면 자동 생성 프로그램",
         font=("Arial", 14, "bold")).grid(row=0, column=0, columnspan=3, pady=10)

# ── 도형 선택 ──
tk.Label(root, text="도형 선택").grid(row=1, column=0, sticky="e", **PAD)
combo_shape = ttk.Combobox(root, values=["Box", "Cylinder", "Cone", "Sphere"],
                            width=16, state="readonly")
combo_shape.grid(row=1, column=1, columnspan=2, sticky="w", **PAD)
combo_shape.set("Box")
combo_shape.bind("<<ComboboxSelected>>", on_shape_changed)

ttk.Separator(root, orient="horizontal").grid(
    row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=3)

# ── 파라미터 프레임 ──
param_frame = tk.Frame(root)
param_frame.grid(row=3, column=0, columnspan=3)


def make_param_row(frame, row, default_label):
    lbl = tk.Label(frame, text=default_label, width=14, anchor="e")
    lbl.grid(row=row, column=0, **PAD)
    ent = tk.Entry(frame, width=16)
    ent.grid(row=row, column=1, **PAD)
    cmb = ttk.Combobox(frame, values=units, width=8, state="readonly")
    cmb.grid(row=row, column=2, **PAD)
    cmb.set("mm")
    return lbl, ent, cmb


lbl_p1, entry_p1, combo_u1 = make_param_row(param_frame, 0, "x (길이)")
lbl_p2, entry_p2, combo_u2 = make_param_row(param_frame, 1, "y (너비)")
lbl_p3, entry_p3, combo_u3 = make_param_row(param_frame, 2, "z (높이)")

ttk.Separator(root, orient="horizontal").grid(
    row=4, column=0, columnspan=3, sticky="ew", padx=10, pady=3)

# ── 생성 개수 ──
tk.Label(root, text="생성 개수").grid(row=5, column=0, sticky="e", **PAD)
count_frame = tk.Frame(root)
count_frame.grid(row=5, column=1, columnspan=2, sticky="w")
spin_count = ttk.Spinbox(count_frame, from_=1, to=20, width=5)
spin_count.set("1")
spin_count.pack(side="left")
tk.Label(count_frame, text="개  (최대 20개)",
         fg="gray", font=("Arial", 9)).pack(side="left", padx=6)

# ── 도형 간격 ──
tk.Label(root, text="도형 간격").grid(row=6, column=0, sticky="e", **PAD)
spacing_frame = tk.Frame(root)
spacing_frame.grid(row=6, column=1, columnspan=2, sticky="w")
entry_spacing = tk.Entry(spacing_frame, width=10)
entry_spacing.insert(0, "0")
entry_spacing.pack(side="left")
combo_spacing_unit = ttk.Combobox(spacing_frame, values=units, width=6, state="readonly")
combo_spacing_unit.set("mm")
combo_spacing_unit.pack(side="left", padx=4)
tk.Label(spacing_frame, text="(인접 도형 사이 빈 공간)",
         fg="gray", font=("Arial", 9)).pack(side="left")

ttk.Separator(root, orient="horizontal").grid(
    row=7, column=0, columnspan=3, sticky="ew", padx=10, pady=3)

# ── 내부 도형 ──
var_inner = tk.BooleanVar(value=False)
tk.Checkbutton(
    root,
    text="내부 도형 추가  (각 외부 도형의 중심에 배치)",
    variable=var_inner,
    command=on_inner_toggle,
    font=("Arial", 10),
).grid(row=8, column=0, columnspan=3, sticky="w", padx=12, pady=2)

# inner_frame — on_inner_toggle 에 의해 row=9 에 표시/숨김
inner_frame = tk.LabelFrame(root, text="내부 도형 설정", padx=6, pady=4)

tk.Label(inner_frame, text="도형 종류", width=12, anchor="e").grid(
    row=0, column=0, **PAD)
combo_inner_shape = ttk.Combobox(
    inner_frame, values=["Box", "Cylinder", "Cone", "Sphere"],
    width=14, state="readonly")
combo_inner_shape.grid(row=0, column=1, columnspan=2, sticky="w", **PAD)
combo_inner_shape.set("Sphere")
combo_inner_shape.bind("<<ComboboxSelected>>", on_inner_shape_changed)

inner_param_frame = tk.Frame(inner_frame)
inner_param_frame.grid(row=1, column=0, columnspan=3)

lbl_ip1, entry_ip1, combo_iu1 = make_param_row(inner_param_frame, 0, "반지름 (r)")
lbl_ip2, entry_ip2, combo_iu2 = make_param_row(inner_param_frame, 1, "높이 (h)")
lbl_ip3, entry_ip3, combo_iu3 = make_param_row(inner_param_frame, 2, "z (높이)")

# row 10 은 inner_frame 이 없을 때 separator 역할 (inner 가 없으면 row 9 가 비어있음)
ttk.Separator(root, orient="horizontal").grid(
    row=10, column=0, columnspan=3, sticky="ew", padx=10, pady=3)

# ── 저장 형식 ──
tk.Label(root, text="저장 형식").grid(row=11, column=0, sticky="e", **PAD)
fmt_frame = tk.Frame(root)
fmt_frame.grid(row=11, column=1, columnspan=2, sticky="w")
var_fcstd = tk.BooleanVar(value=True)
var_step  = tk.BooleanVar(value=True)
var_stl   = tk.BooleanVar(value=True)
tk.Checkbutton(fmt_frame, text="FCStd", variable=var_fcstd).pack(side="left", padx=4)
tk.Checkbutton(fmt_frame, text="STEP",  variable=var_step).pack(side="left", padx=4)
tk.Checkbutton(fmt_frame, text="STL",   variable=var_stl).pack(side="left", padx=4)

# ── 출력 폴더 ──
tk.Label(root, text="출력 폴더").grid(row=12, column=0, sticky="e", **PAD)
entry_output_dir = tk.Entry(root, width=30)
entry_output_dir.grid(row=12, column=1, sticky="ew", **PAD)
entry_output_dir.insert(0, os.path.join(os.path.expanduser("~"), "Documents"))
tk.Button(root, text="찾아보기", command=browse_output_folder, width=10).grid(
    row=12, column=2, **PAD)

ttk.Separator(root, orient="horizontal").grid(
    row=13, column=0, columnspan=3, sticky="ew", padx=10, pady=3)

# ── FreeCAD 설치 폴더 ──
tk.Label(root, text="FreeCAD\n실행 폴더").grid(row=14, column=0, sticky="e", **PAD)
entry_freecad_dir = tk.Entry(root, width=30)
entry_freecad_dir.grid(row=14, column=1, sticky="ew", **PAD)
tk.Button(root, text="찾아보기", command=browse_freecad_folder, width=10).grid(
    row=14, column=2, **PAD)
tk.Label(root, text="※ 비워두면 자동 탐색 (Program Files 등)",
         font=("Arial", 8), fg="gray").grid(row=15, column=0, columnspan=3)

# ── 생성 버튼 ──
tk.Button(
    root,
    text="▶  3D 도면 생성 및 저장",
    command=generate_model,
    width=28,
    bg="#2E7D32",
    fg="white",
    font=("Arial", 11, "bold"),
    relief="raised",
    cursor="hand2",
).grid(row=16, column=0, columnspan=3, pady=14)

# ── 결과 표시 ──
result_label = tk.Label(root, text="", justify="left", fg="#1565C0",
                         font=("Arial", 9), wraplength=540)
result_label.grid(row=17, column=0, columnspan=3, padx=10, pady=4)

# 초기 파라미터 표시
on_shape_changed()

root.mainloop()
