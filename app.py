import streamlit as st
from PIL import Image, ImageOps, ImageDraw, ImageFont
import io
import requests
from datetime import datetime
import base64

# --- НАЛАШТУВАННЯ СТОРІНКИ ---
st.set_page_config(
    page_title="PhotoPrint UA", 
    page_icon="logo.ico", 
    layout="centered"
)

DPI = 300
GRID_COLOR = (200, 200, 200)

PAPER_SIZES = {
    "A4 (210x297 мм)": (210, 297),
    "10x15 см (4x6\")": (101.6, 152.4)
}

PHOTO_FORMATS = {
    "3 x 4 см (Студентський, перепустки, медкнижка)": (30, 40, 10, 4),
    "3.5 x 4.5 см (Паспорт, візи, довідка водія 083/о)": (35, 45, 10, 4),
    "4 x 6 см (Військовий квиток, посвідчення УБД)": (40, 60, 12, 5),
    "5 x 5 см (Віза США, Green Card)": (50, 50, 10, 5),
    "9 x 12 см (Особова справа ЗСУ / МВС / держслужба)": (90, 120, 15, 5),
    "10 x 15 см (Стандартне фото в альбом)": (100, 150, 15, 5)
}

def get_font(size):
    try:
        return ImageFont.truetype("font.ttf", size)
    except:
        return ImageFont.load_default()

def apply_watermark(image):
    base = image.copy().convert('RGBA')
    txt_layer = Image.new('RGBA', base.size, (255,255,255,0))
    d = ImageDraw.Draw(txt_layer)
    fs = int(image.width * 0.06)
    try:
        f = ImageFont.truetype("font.ttf", fs)
    except:
        f = ImageFont.load_default()
    text_str = "ПОПЕРЕДНІЙ ПЕРЕГЛЯД • PREVIEW • ОПЛАТІТЬ ДЛЯ ЗАВАНТАЖЕННЯ"
    w_color = (150, 150, 150, 70)
    for y_off in range(fs * 2, base.height, fs * 5):
        bbox = d.textbbox((0, 0), text_str, font=f)
        t_w, t_h = bbox[2]-bbox[0], bbox[3]-bbox[1]
        d.text(((base.width - t_w)//2, y_off), text_str, font=f, fill=w_color)
    out = Image.alpha_composite(base, txt_layer)
    return out.convert('RGB')

def send_telegram_stats(paper, photo, copies, is_fill):
    try:
        token = st.secrets["TELEGRAM_TOKEN"]
        chat_id = st.secrets["TELEGRAM_CHAT_ID"]
        text = f"🎉 <b>Нова генерація макету!</b>\n\n📄 Папір: {paper}\n🖼 Фото: {photo}\n🔢 Копій: {copies}\n🚀 Заповнення: {'Так' if is_fill else 'Ні'}"
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=5)
    except:
        pass

def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except:
        return None

# --- ШАПКА САЙТУ (ЦЕНТРУВАННЯ ЛОГО ТА ТЕКСТУ) ---
logo_base64 = get_base64_image("logo.png")
if logo_base64:
    st.markdown(f'<div style="text-align: center; margin-bottom: 10px;"><img src="data:image/png;base64,{logo_base64}" width="180"></div>', unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center; margin-top: 0;'>PhotoPrint UA</h1>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align: center; color: #666;'>Автоматичний генератор макетів для фото на документи</h3>", unsafe_allow_html=True)

st.markdown("<p style='text-align: center;'>Забудьте про ручне масштабування в Photoshop. Отримайте готовий до друку PDF із професійною сіткою за кілька секунд.</p>", unsafe_allow_html=True)

with st.expander("ℹ️ Як це працює?"):
    st.markdown("""
    1. **Підготуйте фото:** Перейменуйте файли (напр. ПРІЗВИЩЕ.jpg) для автоматичного підпису.
    2. **Оберіть параметри:** Формат паперу та необхідний розмір фото.
    3. **Завантажте та згенеруйте:** Отримайте макет із водяним знаком для перевірки.
    4. **Завантажте PDF:** Введіть код доступу для отримання чистого файлу без водяних знаків.
    """)

st.markdown("---")

# --- НАЛАШТУВАННЯ ---
col1, col2 = st.columns(2)
paper_choice = col1.selectbox("Формат паперу:", list(PAPER_SIZES.keys()))
photo_choice = col2.selectbox("Розмір фото:", list(PHOTO_FORMATS.keys()))
copies = st.number_input("Кількість копій кожного фото:", min_value=1, max_value=50, value=1)
fill_all = st.checkbox("Заповнити весь лист (якщо фото лише одне)")

uploaded_files = st.file_uploader("Завантажте фотографії (JPG, PNG)", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True)

# --- ЛОГІКА ГЕНЕРАЦІЇ ---
if st.button("Згенерувати PDF", type="primary"):
    if not uploaded_files:
        st.warning("Будь ласка, завантажте хоча б одне фото.")
    else:
        with st.spinner("Створення макету..."):
            paper_w_mm, paper_h_mm = PAPER_SIZES[paper_choice]
            photo_w_mm, photo_h_mm, sp_y_mm, sp_x_mm = PHOTO_FORMATS[photo_choice]
            canvas_w, canvas_h = int((paper_w_mm/25.4)*DPI), int((paper_h_mm/25.4)*DPI)
            target_w, target_h = int((photo_w_mm/25.4)*DPI), int((photo_h_mm/25.4)*DPI)
            gap_x, gap_y = int((sp_x_mm/25.4)*DPI), int((sp_y_mm/25.4)*DPI)
            margin = int((5 / 25.4) * DPI)

            full_queue = [uploaded_files[0]] if (fill_all and len(uploaded_files) == 1) else []
            if not full_queue:
                for f in uploaded_files: full_queue.extend([f] * copies)

            pages, q_idx = [], 0
            while q_idx < len(full_queue) or (fill_all and len(uploaded_files)==1 and not pages):
                canvas = Image.new('RGB', (canvas_w, canvas_h), 'white')
                draw = ImageDraw.Draw(canvas)
                x, y, h_lines = margin, margin, []
                while True:
                    if x == margin: h_lines.extend([y, y + target_h, y + target_h + gap_y])
                    file_obj = full_queue[q_idx if q_idx < len(full_queue) else 0]
                    label = file_obj.name.rsplit('.', 1)[0].upper()
                    img = Image.open(file_obj)
                    canvas.paste(ImageOps.fit(img, (target_w, target_h)), (x, y))
                    
                    f = get_font(30)
                    draw.text((x + 5, y + target_h + 2), label, fill="black", font=f)
                    
                    q_idx += 1
                    x += target_w + gap_x
                    if x + target_w > canvas_w - margin: x, y = margin, y + target_h + gap_y
                    if y + target_h + gap_y > canvas_h or (not (fill_all and len(uploaded_files)==1) and q_idx >= len(full_queue)): break

                for lx in range(margin, canvas_w, target_w + gap_x):
                    draw.line([(lx, 0), (lx, canvas_h)], fill=GRID_COLOR, width=2)
                    draw.line([(lx + target_w, 0), (lx + target_w, canvas_h)], fill=GRID_COLOR, width=2)
                for ly in h_lines: draw.line([(0, ly), (canvas_w, ly)], fill=GRID_COLOR, width=2)
                pages.append(canvas)
                if fill_all and len(uploaded_files)==1: break

            pdf_buf = io.BytesIO()
            pages[0].save(pdf_buf, format="PDF", save_all=True, append_images=pages[1:], resolution=DPI)
            st.session_state['pdf_bytes'] = pdf_buf.getvalue()
            st.session_state['preview'] = apply_watermark(pages[0])
            st.session_state['unlocked'] = False
            send_telegram_stats(paper_choice, photo_choice, copies, fill_all)

# --- ВИВІД РЕЗУЛЬТАТУ ---
if 'preview' in st.session_state:
    st.image(st.session_state['preview'], caption="Попередній перегляд", use_container_width=True)
    
    st.markdown("---")
    st.subheader("🔓 Отримати чистий макет")
    
    col_pay, col_info = st.columns(2)
    with col_pay:
        st.markdown(f'<a href="https://donatello.to/s.udowenko" target="_blank" style="display: inline-block; padding: 10px 20px; background-color: #FF8A65; color: white; text-align: center; text-decoration: none; border-radius: 5px; font-weight: bold; width: 100%;">☕ Підтримати (отримати код)</a>', unsafe_allow_html=True)
    with col_info:
        st.info("🇺🇦 ЗСУ/ТЦК: sudo.wqa@gmail.com")
    
    col_in, col_chk = st.columns([3, 1])
    with col_in:
        u_code = st.text_input("Введіть код доступу:", type="password", key="pwd").strip()
    with col_chk:
        st.write(" ")
        st.write(" ")
        if st.button("Перевірити"):
            if u_code in ["ZSU-2026", "PHOTO-MARCH"]:
                st.session_state['unlocked'] = True
                st.success("Доступ надано!")
            else:
                st.session_state['unlocked'] = False
                st.error("Невірний код")

    if st.session_state.get('unlocked', False):
        st.download_button(
            label="📥 ЗАВАНТАЖИТИ PDF ДЛЯ ДРУКУ",
            data=st.session_state['pdf_bytes'],
            file_name="PhotoPrint_UA.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )

# --- FOOTER (З ПОСИЛАННЯМИ НА ПРОЄКТИ) ---
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; padding-top: 10px; color: #666;">
        <p style="margin-bottom: 5px;">👨‍💻 <b>Розробник: <a href="https://github.com/serhiiudowenko" target="_blank" style="text-decoration: none; color: #FF8A65;">Serhii Udowenko</a></b></p>
        <p style="font-size: 14px; margin-bottom: 15px;">✉️ <a href="mailto:sudo.wqa@gmail.com" style="text-decoration: none; color: #666;">sudo.wqa@gmail.com</a></p>
        <div style="font-size: 14px; background-color: #f0f2f6; padding: 10px; border-radius: 8px; display: inline-block;">
            <b>🔗 Інші мої сервіси:</b><br>
            <a href="https://serhiiudowenko.github.io/dovidniktck/" target="_blank" style="text-decoration: none; color: #1f77b4;">📚 Довідник ТЦК</a> &nbsp;|&nbsp; 
            <a href="https://github.com/serhiiudowenko" target="_blank" style="text-decoration: none; color: #1f77b4;">🔤 Сервіс транслітерації та інші</a>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)
