import os
import sys
import shutil
import tempfile
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox


# ----------------------------
# 단위 변환: 모두 mm 기준으로 변환
# ----------------------------
UNIT_TO_MM = {
    "mm": 1.0,
    "cm": 10.0,
    "m": 1000.0
}


def to_mm(value, unit):
    return value * UNIT_TO_MM[unit]


# ----------------------------
# FreeCAD 실행 파일 찾기
# ----------------------------
def find_freecad_executables():
    gui_candidates = []
    cmd_candidates = []

    if sys.platform.startswith("win"):
        gui_candidates = [
            shutil.which("FreeCAD.exe"),
            r"C:\Program Files\FreeCAD 1.0\bin\FreeCAD.exe",
            r"C:\Program Files\FreeCAD 0.21\bin\FreeCAD.exe",
            r"C:\Program Files\FreeCAD\bin\FreeCAD.exe",
        ]
        cmd_candidates = [
            shutil.which("FreeCADCmd.exe"),
            r"C:\Program Files\FreeCAD 1.0\bin\FreeCADCmd.exe",
            r"C:\Program Files\FreeCAD 0.21\bin\FreeCADCmd.exe",
            r"C:\Program Files\FreeCAD\bin\FreeCADCmd.exe",
        ]

    elif sys.platform == "darwin":
        gui_candidates = [
            shutil.which("FreeCAD"),
            "/Applications/FreeCAD.app/Contents/MacOS/FreeCAD",
        ]
        cmd_candidates = [
            shutil.which("FreeCADCmd"),
            "/Applications/FreeCAD.app/Contents/MacOS/FreeCADCmd",
        ]

    else:  # Linux
        gui_candidates = [
            shutil.which("freecad"),
            shutil.which("FreeCAD"),
            "/usr/bin/freecad",
            "/usr/bin/FreeCAD",
            "/snap/bin/freecad",
        ]
        cmd_candidates = [
            shutil.which("freecadcmd"),
            shutil.which("FreeCADCmd"),
            "/usr/bin/freecadcmd",
            "/usr/bin/FreeCADCmd",
        ]

    gui_path = next((p for p in gui_candidates if p and os.path.exists(p)), None)
    cmd_path = next((p for p in cmd_candidates if p and os.path.exists(p)), None)

    return gui_path, cmd_path


# ----------------------------
# FreeCAD 스크립트 생성
# ----------------------------
def make_freecad_script(x_mm, y_mm, z_mm, output_fcstd):
    script = f'''import FreeCAD as App

doc = App.newDocument("GeneratedModel")
box = doc.addObject("Part::Box", "Box")

box.Length = {x_mm}
box.Width = {y_mm}
box.Height = {z_mm}

doc.recompute()
doc.saveAs(r"{output_fcstd}")
print("Saved:", r"{output_fcstd}")
'''
    return script


# ----------------------------
# 모델 생성 + FreeCAD 열기
# ----------------------------
def generate_model():
    try:
        x_value = float(entry_x.get())
        y_value = float(entry_y.get())
        z_value = float(entry_z.get())
    except ValueError:
        messagebox.showerror("입력 오류", "x, y, z 값에는 숫자를 입력해주세요.")
        return

    if x_value <= 0 or y_value <= 0 or z_value <= 0:
        messagebox.showerror("입력 오류", "x, y, z 값은 0보다 커야 합니다.")
        return

    x_unit = combo_x_unit.get()
    y_unit = combo_y_unit.get()
    z_unit = combo_z_unit.get()

    x_mm = to_mm(x_value, x_unit)
    y_mm = to_mm(y_value, y_unit)
    z_mm = to_mm(z_value, z_unit)

    gui_path, cmd_path = find_freecad_executables()

    if not gui_path and not cmd_path:
        messagebox.showerror(
            "FreeCAD 없음",
            "FreeCAD 실행 파일을 찾을 수 없습니다.\n"
            "FreeCAD를 설치했는지 확인하거나, 코드 안의 경로를 직접 지정해주세요."
        )
        return

    output_dir = os.path.join(os.path.expanduser("~"), "Documents")
    os.makedirs(output_dir, exist_ok=True)
    output_fcstd = os.path.join(output_dir, "generated_box.FCStd")

    # 임시 FreeCAD 파이썬 스크립트 생성
    with tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode="w", encoding="utf-8") as tmp:
        script_path = tmp.name
        tmp.write(make_freecad_script(x_mm, y_mm, z_mm, output_fcstd))

    try:
        # 1) headless로 모델 생성
        if cmd_path:
            subprocess.run([cmd_path, script_path], check=True)
        elif gui_path:
            # FreeCADCmd가 없으면 GUI 실행 파일에 스크립트를 넘겨서 실행
            subprocess.run([gui_path, script_path], check=True)

        # 2) 생성된 파일을 FreeCAD GUI로 열기
        if gui_path:
            subprocess.Popen([gui_path, output_fcstd])

        result_text = (
            f"모델 생성 완료\n\n"
            f"x = {x_value} {x_unit} ({x_mm} mm)\n"
            f"y = {y_value} {y_unit} ({y_mm} mm)\n"
            f"z = {z_value} {z_unit} ({z_mm} mm)\n\n"
            f"저장 위치:\n{output_fcstd}"
        )
        result_label.config(text=result_text)
        messagebox.showinfo("완료", "FreeCAD 모델 생성이 완료되었습니다.")

    except subprocess.CalledProcessError as e:
        messagebox.showerror("실행 오류", f"FreeCAD 실행 중 오류가 발생했습니다.\n{e}")
    except Exception as e:
        messagebox.showerror("오류", str(e))
    finally:
        try:
            os.remove(script_path)
        except Exception:
            pass


# ----------------------------
# GUI 구성
# ----------------------------
root = tk.Tk()
root.title("FreeCAD 3D 모델 생성기")
root.geometry("470x320")
root.resizable(False, False)

units = ["mm", "cm", "m"]

title_label = tk.Label(root, text="x, y, z 입력 후 FreeCAD 3D 모델 생성", font=("Arial", 13, "bold"))
title_label.grid(row=0, column=0, columnspan=3, pady=12)

# x
tk.Label(root, text="x 값").grid(row=1, column=0, padx=10, pady=6, sticky="e")
entry_x = tk.Entry(root, width=18)
entry_x.grid(row=1, column=1, padx=5, pady=6)
combo_x_unit = ttk.Combobox(root, values=units, width=10, state="readonly")
combo_x_unit.grid(row=1, column=2, padx=5, pady=6)
combo_x_unit.set("mm")

# y
tk.Label(root, text="y 값").grid(row=2, column=0, padx=10, pady=6, sticky="e")
entry_y = tk.Entry(root, width=18)
entry_y.grid(row=2, column=1, padx=5, pady=6)
combo_y_unit = ttk.Combobox(root, values=units, width=10, state="readonly")
combo_y_unit.grid(row=2, column=2, padx=5, pady=6)
combo_y_unit.set("mm")

# z
tk.Label(root, text="z 값").grid(row=3, column=0, padx=10, pady=6, sticky="e")
entry_z = tk.Entry(root, width=18)
entry_z.grid(row=3, column=1, padx=5, pady=6)
combo_z_unit = ttk.Combobox(root, values=units, width=10, state="readonly")
combo_z_unit.grid(row=3, column=2, padx=5, pady=6)
combo_z_unit.set("mm")

# 버튼
generate_button = tk.Button(root, text="FreeCAD로 3D 모델 생성", command=generate_model, width=25)
generate_button.grid(row=4, column=0, columnspan=3, pady=18)

# 결과
result_label = tk.Label(root, text="", justify="left", fg="blue", font=("Arial", 10))
result_label.grid(row=5, column=0, columnspan=3, padx=10, pady=10)

root.mainloop()
