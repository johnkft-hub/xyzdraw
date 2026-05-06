"""
3D 도면 자동 생성 프로그램
- FreeCAD Scripting Basics (wiki.freecad.org) 기반
- Part 모듈로 실제 형상 생성 후 FCStd / STEP / STL 저장
"""

import os
import sys
import shutil
import tempfile
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


# ── FreeCAD 스크립트 생성 ────────────────────────────────────────────────────
# wiki.freecad.org/FreeCAD_Scripting_Basics 기반:
#   GUI 모드  : FreeCAD.exe 로 실행 → ViewProvider 포함 생성 → 3D 뷰 표시
#   헤드리스  : FreeCADCmd.exe 로 실행 → 파일 저장만 (GUI 없음)

def _shape_code_and_label(shape_type, params):
    if shape_type == "Box":
        code = (f"shape = Part.makeBox("
                f"{params['length']}, {params['width']}, {params['height']})")
        return code, "Box"
    if shape_type == "Cylinder":
        code = f"shape = Part.makeCylinder({params['radius']}, {params['height']})"
        return code, "Cylinder"
    if shape_type == "Cone":
        code = (f"shape = Part.makeCone("
                f"{params['radius1']}, {params['radius2']}, {params['height']})")
        return code, "Cone"
    if shape_type == "Sphere":
        code = f"shape = Part.makeSphere({params['radius']})"
        return code, "Sphere"
    raise ValueError(f"Unknown shape type: {shape_type}")


def make_freecad_script(shape_type, params, out_fcstd, out_step, out_stl):
    """
    GUI 모드(FreeCAD.exe)와 헤드리스(FreeCADCmd.exe) 모두에서 동작.
    GUI 모드에서는 FreeCADGui를 통해 ViewProvider를 생성하고 3D 뷰를 맞춤.
    """
    shape_code, label = _shape_code_and_label(shape_type, params)

    save_lines = []
    if out_fcstd:
        save_lines.append(f'doc.saveAs(r"{out_fcstd}")')
        save_lines.append(f'print("FCStd:", r"{out_fcstd}")')
    if out_step:
        save_lines.append(f'shape.exportStep(r"{out_step}")')
        save_lines.append(f'print("STEP:", r"{out_step}")')
    if out_stl:
        save_lines.append(f'shape.exportStl(r"{out_stl}")')
        save_lines.append(f'print("STL:", r"{out_stl}")')
    save_block = "\n".join(save_lines)

    return f"""\
import FreeCAD as App
import Part

doc = App.newDocument("GeneratedModel")

{shape_code}

part = doc.addObject("Part::Feature", "{label}")
part.Shape = shape
doc.recompute()

{save_block}

# GUI 모드일 때만 실행: ViewProvider 초기화 + 3D 뷰 맞춤
try:
    import FreeCADGui as Gui
    Gui.ActiveDocument.ActiveView.viewIsometric()
    Gui.SendMsgToActiveView("ViewFit")
except Exception:
    pass  # 헤드리스 모드에서는 Gui 모듈이 없으므로 무시

print("Done.")
"""


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
    """도형 종류에 따라 파라미터 행을 표시/숨김"""
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


def get_param(entry, combo):
    v = float(entry.get())
    if v <= 0:
        raise ValueError("0보다 커야 합니다")
    return to_mm(v, combo.get())


def generate_model():
    shape = combo_shape.get()

    try:
        if shape == "Box":
            params = {
                "length": get_param(entry_p1, combo_u1),
                "width":  get_param(entry_p2, combo_u2),
                "height": get_param(entry_p3, combo_u3),
            }
            desc = (f"x={entry_p1.get()} {combo_u1.get()}  "
                    f"y={entry_p2.get()} {combo_u2.get()}  "
                    f"z={entry_p3.get()} {combo_u3.get()}")
        elif shape == "Cylinder":
            params = {
                "radius": get_param(entry_p1, combo_u1),
                "height": get_param(entry_p2, combo_u2),
            }
            desc = (f"r={entry_p1.get()} {combo_u1.get()}  "
                    f"h={entry_p2.get()} {combo_u2.get()}")
        elif shape == "Cone":
            params = {
                "radius1": get_param(entry_p1, combo_u1),
                "radius2": get_param(entry_p2, combo_u2),
                "height":  get_param(entry_p3, combo_u3),
            }
            desc = (f"r1={entry_p1.get()} {combo_u1.get()}  "
                    f"r2={entry_p2.get()} {combo_u2.get()}  "
                    f"h={entry_p3.get()} {combo_u3.get()}")
        elif shape == "Sphere":
            params = {"radius": get_param(entry_p1, combo_u1)}
            desc = f"r={entry_p1.get()} {combo_u1.get()}"
        else:
            messagebox.showerror("오류", "도형을 선택해주세요.")
            return
    except ValueError as e:
        messagebox.showerror("입력 오류", f"파라미터 값을 확인해주세요.\n{e}")
        return

    # 출력 폴더
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

    # FreeCAD 실행 파일 탐색
    custom_dir = entry_freecad_dir.get().strip() or None
    gui_path, cmd_path = find_freecad_executables(custom_dir)

    if not gui_path and not cmd_path:
        messagebox.showerror(
            "FreeCAD 없음",
            "FreeCAD 실행 파일을 찾을 수 없습니다.\n"
            "FreeCAD 설치 폴더를 직접 입력하거나 FreeCAD를 설치해주세요."
        )
        return

    # 스크립트를 출력 폴더에 저장 (Popen 비동기 실행 시 삭제 타이밍 문제 방지)
    script_path = os.path.join(out_dir, "_freecad_run.py")
    script_content = make_freecad_script(shape, params, out_fcstd, out_step, out_stl)
    try:
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)
    except OSError as e:
        messagebox.showerror("파일 오류", f"스크립트 파일을 생성할 수 없습니다.\n{e}")
        return

    if gui_path:
        # ── GUI 모드: FreeCAD.exe 로 스크립트 실행 ──────────────────────────
        # FreeCAD.exe 가 스크립트를 읽어 실행하면서 ViewProvider 포함 생성,
        # Gui.SendMsgToActiveView("ViewFit") 으로 3D 뷰에 도형이 바로 표시됨.
        try:
            subprocess.Popen([gui_path, script_path])
        except Exception as e:
            messagebox.showerror("실행 오류", f"FreeCAD 실행 실패\n{e}")
            return

        result_label.config(
            text=f"[{shape}] FreeCAD 실행 중...\n{desc}\n\n"
                 f"※ 파일 생성 완료 후 아래에 경로가 표시됩니다."
        )
        # 비동기로 파일 생성 여부 확인 (FreeCAD 기동에 ~5초 소요)
        root.after(6000, lambda: _check_saved(shape, desc, out_fcstd, out_step, out_stl))

    else:
        # ── 헤드리스 모드: FreeCADCmd.exe 로 실행 (GUI 없음) ────────────────
        try:
            result = subprocess.run(
                [cmd_path, script_path],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
        except subprocess.CalledProcessError as e:
            err = (e.stderr or e.stdout or str(e))[:800]
            messagebox.showerror("실행 오류", f"FreeCADCmd 실행 오류\n\n{err}")
            return
        except Exception as e:
            messagebox.showerror("오류", str(e))
            return

        _check_saved(shape, desc, out_fcstd, out_step, out_stl, show_popup=True)


def _check_saved(shape, desc, out_fcstd, out_step, out_stl, show_popup=False):
    """생성된 파일 목록을 확인하고 result_label 갱신. 미생성 시 재시도."""
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
        # 아직 FreeCAD가 파일을 저장 중일 수 있으므로 3초 후 재확인
        current = result_label.cget("text")
        if "재확인" not in current:
            result_label.config(
                text=result_label.cget("text") + "\n(파일 저장 대기 중... 재확인)"
            )
        root.after(3000, lambda: _check_saved(shape, desc, out_fcstd, out_step, out_stl))


# ── GUI 구성 ──────────────────────────────────────────────────────────────────
root = tk.Tk()
root.title("3D 도면 자동 생성 프로그램")
root.geometry("520x560")
root.resizable(False, False)

units = ["mm", "cm", "m"]
PAD = {"padx": 8, "pady": 5}

# 제목
tk.Label(root, text="3D 도면 자동 생성 프로그램",
         font=("Arial", 14, "bold")).grid(row=0, column=0, columnspan=3, pady=12)

# ── 도형 선택 ──
tk.Label(root, text="도형 선택").grid(row=1, column=0, sticky="e", **PAD)
combo_shape = ttk.Combobox(root, values=["Box", "Cylinder", "Cone", "Sphere"],
                            width=16, state="readonly")
combo_shape.grid(row=1, column=1, columnspan=2, sticky="w", **PAD)
combo_shape.set("Box")
combo_shape.bind("<<ComboboxSelected>>", on_shape_changed)

ttk.Separator(root, orient="horizontal").grid(
    row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=4)

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
    row=4, column=0, columnspan=3, sticky="ew", padx=10, pady=4)

# ── 저장 형식 ──
tk.Label(root, text="저장 형식").grid(row=5, column=0, sticky="e", **PAD)
fmt_frame = tk.Frame(root)
fmt_frame.grid(row=5, column=1, columnspan=2, sticky="w")
var_fcstd = tk.BooleanVar(value=True)
var_step  = tk.BooleanVar(value=True)
var_stl   = tk.BooleanVar(value=True)
tk.Checkbutton(fmt_frame, text="FCStd", variable=var_fcstd).pack(side="left", padx=4)
tk.Checkbutton(fmt_frame, text="STEP",  variable=var_step).pack(side="left", padx=4)
tk.Checkbutton(fmt_frame, text="STL",   variable=var_stl).pack(side="left", padx=4)

# ── 출력 폴더 ──
tk.Label(root, text="출력 폴더").grid(row=6, column=0, sticky="e", **PAD)
entry_output_dir = tk.Entry(root, width=30)
entry_output_dir.grid(row=6, column=1, sticky="ew", **PAD)
entry_output_dir.insert(0, os.path.join(os.path.expanduser("~"), "Documents"))
tk.Button(root, text="찾아보기", command=browse_output_folder, width=10).grid(
    row=6, column=2, **PAD)

ttk.Separator(root, orient="horizontal").grid(
    row=7, column=0, columnspan=3, sticky="ew", padx=10, pady=4)

# ── FreeCAD 설치 폴더 ──
tk.Label(root, text="FreeCAD\n실행 폴더").grid(row=8, column=0, sticky="e", **PAD)
entry_freecad_dir = tk.Entry(root, width=30)
entry_freecad_dir.grid(row=8, column=1, sticky="ew", **PAD)
tk.Button(root, text="찾아보기", command=browse_freecad_folder, width=10).grid(
    row=8, column=2, **PAD)
tk.Label(root, text="※ 비워두면 자동 탐색 (Program Files 등)",
         font=("Arial", 8), fg="gray").grid(row=9, column=0, columnspan=3)

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
).grid(row=10, column=0, columnspan=3, pady=16)

# ── 결과 표시 ──
result_label = tk.Label(root, text="", justify="left", fg="#1565C0",
                         font=("Arial", 9), wraplength=480)
result_label.grid(row=11, column=0, columnspan=3, padx=10, pady=4)

# 초기 파라미터 표시
on_shape_changed()

root.mainloop()
