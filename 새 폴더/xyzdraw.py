import tkinter as tk
from tkinter import ttk, messagebox


def submit():
    try:
        x_value = float(entry_x.get())
        y_value = float(entry_y.get())
        z_value = float(entry_z.get())

        x_unit = combo_x_unit.get()
        y_unit = combo_y_unit.get()
        z_unit = combo_z_unit.get()

        result_text = (
            f"x = {x_value} {x_unit}\n"
            f"y = {y_value} {y_unit}\n"
            f"z = {z_value} {z_unit}"
        )

        result_label.config(text=result_text)

    except ValueError:
        messagebox.showerror("입력 오류", "x, y, z 값에는 숫자를 입력해주세요.")


# 메인 창 생성
root = tk.Tk()
root.title("x, y, z 입력 GUI")
root.geometry("420x260")
root.resizable(False, False)

# 단위 목록
units = ["mm", "cm", "m"]

# 제목
title_label = tk.Label(root, text="x, y, z 값과 단위 입력", font=("Arial", 14, "bold"))
title_label.grid(row=0, column=0, columnspan=3, pady=10)

# x 입력
label_x = tk.Label(root, text="x 값")
label_x.grid(row=1, column=0, padx=10, pady=5, sticky="e")
entry_x = tk.Entry(root, width=15)
entry_x.grid(row=1, column=1, padx=5, pady=5)

combo_x_unit = ttk.Combobox(root, values=units, width=8, state="readonly")
combo_x_unit.grid(row=1, column=2, padx=5, pady=5)
combo_x_unit.set("mm")

# y 입력
label_y = tk.Label(root, text="y 값")
label_y.grid(row=2, column=0, padx=10, pady=5, sticky="e")
entry_y = tk.Entry(root, width=15)
entry_y.grid(row=2, column=1, padx=5, pady=5)

combo_y_unit = ttk.Combobox(root, values=units, width=8, state="readonly")
combo_y_unit.grid(row=2, column=2, padx=5, pady=5)
combo_y_unit.set("mm")

# z 입력
label_z = tk.Label(root, text="z 값")
label_z.grid(row=3, column=0, padx=10, pady=5, sticky="e")
entry_z = tk.Entry(root, width=15)
entry_z.grid(row=3, column=1, padx=5, pady=5)

combo_z_unit = ttk.Combobox(root, values=units, width=8, state="readonly")
combo_z_unit.grid(row=3, column=2, padx=5, pady=5)
combo_z_unit.set("mm")

# 제출 버튼
submit_button = tk.Button(root, text="입력 확인", command=submit, width=15)
submit_button.grid(row=4, column=0, columnspan=3, pady=15)

# 결과 표시
result_label = tk.Label(root, text="", font=("Arial", 11), justify="left", fg="blue")
result_label.grid(row=5, column=0, columnspan=3, pady=10)

root.mainloop()
