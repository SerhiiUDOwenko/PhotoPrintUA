import os
import sys
import subprocess
import platform
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from PIL import Image, ImageOps, ImageDraw, ImageFont
from datetime import datetime

DPI = 300
GRID_COLOR = (200, 200, 200)

PAPER_SIZES = {
    "A4 (210x297 мм)": (210, 297),
    "10x15 см (4x6\")": (101.6, 152.4)
}

PHOTO_FORMATS = {
    "3 x 4 см (Посвідчення)": (30, 40, 10, 4),
    "3.5 x 4.5 см (Паспорт)": (35, 45, 10, 4),
    "4 x 6 см (Військовий)": (40, 60, 12, 5),
    "9 x 12 см (Особова справа)": (90, 120, 15, 5),
    "10 x 15 см (Альбомне)": (100, 150, 15, 5)
}

def get_system_font(size):
    # Пріоритет на системні шрифти Windows
    paths = []
    if platform.system() == "Windows":
        paths = ["C:\\Windows\\Fonts\\arialbd.ttf", "C:\\Windows\\Fonts\\arial.ttf", "C:\\Windows\\Fonts\\tahomabd.ttf"]
    else:
        paths = ["/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]
    
    for p in paths:
        if os.path.exists(p): return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def open_file(filepath):
    if platform.system() == "Windows":
        os.startfile(filepath)
    else:
        subprocess.run(["xdg-open", filepath])

class AppSelector:
    def __init__(self, file_count=0):
        self.root = tk.Tk()
        self.root.title("PhotoPrint UA - Налаштування")
        self.root.geometry("400x350")
        self.root.eval('tk::PlaceWindow . center')
        self.result = None
        
        # Вибір паперу
        tk.Label(self.root, text="1. Формат паперу:", font=('Arial', 10, 'bold')).pack(pady=(10, 0))
        self.paper_combo = ttk.Combobox(self.root, values=list(PAPER_SIZES.keys()), state="readonly", width=30)
        self.paper_combo.current(0)
        self.paper_combo.pack(pady=5)
        
        # Вибір фото
        tk.Label(self.root, text="2. Розмір фотографій:", font=('Arial', 10, 'bold')).pack(pady=(10, 0))
        self.photo_combo = ttk.Combobox(self.root, values=list(PHOTO_FORMATS.keys()), state="readonly", width=30)
        self.photo_combo.current(0)
        self.photo_combo.pack(pady=5)
        
        # Кількість копій
        tk.Label(self.root, text="3. Кількість копій на кожного:", font=('Arial', 10, 'bold')).pack(pady=(10, 0))
        self.copy_count = tk.IntVar(value=1)
        tk.Spinbox(self.root, from_=1, to=100, textvariable=self.copy_count, width=10, justify='center').pack(pady=5)

        self.fill_all = tk.BooleanVar(value=False)
        self.fill_check = tk.Checkbutton(self.root, text="Заповнити весь лист однією людиною", variable=self.fill_all)
        self.fill_check.pack(pady=5)
        
        tk.Button(self.root, text="ОБРАТИ ПАПКУ ТА ЗАПУСТИТИ", bg="#4CAF50", fg="white", 
                  font=('Arial', 10, 'bold'), command=self.confirm, height=2).pack(pady=20)
        self.root.mainloop()

    def confirm(self):
        self.result = {
            "paper": self.paper_combo.get(),
            "photo": self.photo_combo.get(),
            "copies": self.copy_count.get(),
            "fill": self.fill_all.get()
        }
        self.root.destroy()

def process():
    # Виклик UI спочатку
    ui = AppSelector()
    if not ui.result: return

    # ТЕПЕР ВИБІР ПАПОК ЧЕРЕЗ ДІАЛОГ
    root = tk.Tk()
    root.withdraw()
    
    in_dir = filedialog.askdirectory(title="Виберіть папку з фотографіями")
    if not in_dir: return

    out_dir = filedialog.askdirectory(title="Виберіть папку, куди зберегти результат")
    if not out_dir: return

    files = [f for f in os.listdir(in_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
    files.sort()
    
    if not files:
        messagebox.showwarning("Пусто", "В обраній папці не знайдено зображень!")
        return

    # Якщо фото одне, а вказано "Заповнити весь лист"
    is_fill_mode = ui.result["fill"] and len(files) == 1
    
    paper_w_mm, paper_h_mm = PAPER_SIZES[ui.result["paper"]]
    photo_w_mm, photo_h_mm, sp_y_mm, sp_x_mm = PHOTO_FORMATS[ui.result["photo"]]
    
    canvas_w, canvas_h = int((paper_w_mm/25.4)*DPI), int((paper_h_mm/25.4)*DPI)
    target_w, target_h = int((photo_w_mm/25.4)*DPI), int((photo_h_mm/25.4)*DPI)
    gap_x, gap_y = int((sp_x_mm/25.4)*DPI), int((sp_y_mm/25.4)*DPI)
    margin = int((5 / 25.4) * DPI)

    full_queue = []
    if is_fill_mode:
        full_queue = [files[0]] # В режимі заповнення беремо лише перше фото
    else:
        for f in files:
            full_queue.extend([f] * ui.result["copies"])

    pages, q_idx = [], 0
    while q_idx < len(full_queue) or (is_fill_mode and not pages):
        canvas = Image.new('RGB', (canvas_w, canvas_h), 'white')
        draw = ImageDraw.Draw(canvas)
        x, y, h_lines = margin, margin, []

        while True:
            if x == margin: h_lines.extend([y, y + target_h, y + target_h + gap_y])
            fname = full_queue[q_idx if q_idx < len(full_queue) else 0]
            label = os.path.splitext(fname)[0].upper()
            
            try:
                with Image.open(os.path.join(in_dir, fname)) as img:
                    resized_img = ImageOps.fit(img, (target_w, target_h), centering=(0.5, 0.5))
                    canvas.paste(resized_img, (x, y))
                    fs = 35 if photo_w_mm < 50 else 60
                    f = get_system_font(fs)
                    while True:
                        bbox = draw.textbbox((0, 0), label, font=f)
                        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
                        if tw <= target_w - 6 or fs <= 10: break
                        fs -= 2
                        f = get_system_font(fs)
                    draw.text((x + (target_w - tw)//2, y + target_h + (gap_y - th)//2), label, fill="black", font=f)
                
                q_idx += 1
                x += target_w + gap_x
                if x + target_w > canvas_w - margin:
                    x, y = margin, y + target_h + gap_y
                if y + target_h + gap_y > canvas_h: break
                if not is_fill_mode and q_idx >= len(full_queue): break
            except:
                q_idx += 1
                if q_idx >= len(full_queue): break

        # Сітка
        curr_lx = margin
        while curr_lx < canvas_w:
            draw.line([(curr_lx, 0), (curr_lx, canvas_h)], fill=GRID_COLOR, width=2)
            if curr_lx + target_w < canvas_w:
                draw.line([(curr_lx + target_w, 0), (curr_lx + target_w, canvas_h)], fill=GRID_COLOR, width=2)
            curr_lx += (target_w + gap_x)
        for ly in h_lines: draw.line([(0, ly), (canvas_w, ly)], fill=GRID_COLOR, width=2)
            
        pages.append(canvas)
        if is_fill_mode: break

    if pages:
        timestamp = datetime.now().strftime('%H%M%S')
        out_name = os.path.join(out_dir, f"Print_Result_{timestamp}.pdf")
        pages[0].save(out_name, save_all=True, append_images=pages[1:], resolution=DPI)
        open_file(out_name)

if __name__ == "__main__":
    process()