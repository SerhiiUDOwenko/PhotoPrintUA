import streamlit as st
from PIL import Image, ImageOps, ImageDraw, ImageFont
import io
import requests
from datetime import datetime

# Налаштування сторінки
st.set_page_config(page_title="PhotoPrint UA", page_icon="📸", layout="centered")

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

def get_font(size):
    try:
        return ImageFont.truetype("font.ttf", size)
    except:
        return ImageFont.load_default()

def apply_watermark(image):
    """Накладає напівпрозорий водяний знак по діагоналі на зображення для попереднього перегляду."""
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
    """Відправляє тихе сповіщення в Telegram при успішній генерації"""
    try:
        token = st.secrets["TELEGRAM_TOKEN"]
        chat_id = st.secrets["TELEGRAM_CHAT_ID"]
        
        text = f"🎉 <b>Нова генерація макету!</b>\n\n" \
               f"📄 Папір: {paper}\n" \
               f"🖼 Фото: {photo}\n" \
               f"🔢 Копій: {copies}\n" \
               f"🚀 Заповнення аркуша: {'Так' if is_fill else 'Ні'}\n" \
               f"⏰ Час: {datetime.now().strftime('%H:%M:%S')}"
               
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_notification": True}
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        pass

st.title("📸 PhotoPrint UA")
st.markdown("Автоматична генерація макетів для друку фото на документи.")

# --- БЛОК НАЛАШТУВАНЬ ---
col1, col2 = st.columns(2)
with col1:
    paper_choice = st.selectbox("Формат паперу:", list(PAPER_SIZES.keys()))
with col2:
    photo_choice = st.selectbox("Розмір фото:", list(PHOTO_FORMATS.keys()))

copies = st.number_input("Кількість копій кожного фото:", min_value=1, max_value=50, value=1)
fill_all = st.checkbox("Заповнити весь лист (якщо фото лише одне)")

# --- БЛОК ЗАВАНТАЖЕННЯ ФАЙЛІВ ---
uploaded_files = st.file_uploader("Завантажте фотографії (JPG, PNG)", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True)

if st.button("Згенерувати PDF", type="primary"):
    if not uploaded_files:
        st.warning("Будь ласка, завантажте хоча б одне фото.")
    else:
        st.info("🔄 Починаємо обробку...")
        
        paper_w_mm, paper_h_mm = PAPER_SIZES[paper_choice]
        photo_w_mm, photo_h_mm, sp_y_mm, sp_x_mm = PHOTO_FORMATS[photo_choice]
        
        canvas_w, canvas_h = int((paper_w_mm/25.4)*DPI), int((paper_h_mm/25.4)*DPI)
        target_w, target_h = int((photo_w_mm/25.4)*DPI), int((photo_h_mm/25.4)*DPI)
        gap_x, gap_y = int((sp_x_mm/25.4)*DPI), int((sp_y_mm/25.4)*DPI)
        margin = int((5 / 25.4) * DPI)

        is_fill_mode = fill_all and len(uploaded_files) == 1
        
        full_queue = []
        if is_fill_mode:
            full_queue = [uploaded_files[0]]
        else:
            for f in uploaded_files:
                full_queue.extend([f] * copies)

        pages, q_idx = [], 0
        
        while q_idx < len(full_queue) or (is_fill_mode and not pages):
            canvas = Image.new('RGB', (canvas_w, canvas_h), 'white')
            draw = ImageDraw.Draw(canvas)
            x, y, h_lines = margin, margin, []

            while True:
                if x == margin: h_lines.extend([y, y + target_h, y + target_h + gap_y])
                
                file_obj = full_queue[q_idx if q_idx < len(full_queue) else 0]
                label = file_obj.name.rsplit('.', 1)[0].upper()
                
                try:
                    img = Image.open(file_obj)
                    resized_img = ImageOps.fit(img, (target_w, target_h), centering=(0.5, 0.5))
                    canvas.paste(resized_img, (x, y))
                    
                    fs = 35 if photo_w_mm < 50 else 60
                    f = get_font(fs)
                    while True:
                        bbox = draw.textbbox((0, 0), label, font=f)
                        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
                        if tw <= target_w - 6 or fs <= 10: break
                        fs -= 2
                        f = get_font(fs)
                    draw.text((x + (target_w - tw)//2, y + target_h + (gap_y - th)//2), label, fill="black", font=f)
                    
                    q_idx += 1
                    x += target_w + gap_x
                    if x + target_w > canvas_w - margin:
                        x, y = margin, y + target_h + gap_y
                    if y + target_h + gap_y > canvas_h: break
                    if not is_fill_mode and q_idx >= len(full_queue): break
                except Exception as e:
                    st.error(f"Помилка з файлом {label}: {e}")
                    q_idx += 1
                    if q_idx >= len(full_queue): break

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
            with st.spinner('Створення попереднього перегляду...'):
                watermarked_preview = apply_watermark(pages[0])
            
            st.success("✅ Макет згенеровано!")
            
            # --- ВІДПРАВКА СТАТИСТИКИ В TELEGRAM ---
            send_telegram_stats(paper_choice, photo_choice, copies, is_fill_mode)
            
            # --- БЛОК ПРЕВ'Ю ---
            st.subheader("🖼 Попередній перегляд")
            st.markdown("Перевірте макет. Водяний знак зникне на PDF-файлі після оплати.")
            st.image(watermarked_preview, caption="Водяний знак PREVIEW", use_container_width=True)

            # --- ПАКУЄМО ОРИГІНАЛЬНИЙ PDF ---
            st.info("🔄 Пакування чистого PDF... Це може зайняти хвилину...")
            pdf_buffer = io.BytesIO()
            pages[0].save(pdf_buffer, format="PDF", save_all=True, append_images=pages[1:], resolution=DPI)
            pdf_bytes = pdf_buffer.getvalue()

            # --- ІНТЕГРАЦІЯ ОПЛАТИ (DONATELLO) ---
            st.markdown("---")
            st.subheader("🔓 Завантажити чистий макет")
            st.write("Щоб отримати готовий PDF-файл високої якості без водяного знаку, підтримайте розробника.")
            
            st.markdown(
                f'<a href="https://donatello.to/s.udowenko" target="_blank" style="display: inline-block; padding: 10px 20px; background-color: #FF8A65; color: white; text-align: center; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 16px;">☕ Підтримати на Donatello (від 20 грн)</a>',
                unsafe_allow_html=True
            )
            st.caption("*Після успішної оплати платформа Donatello покаже вам код доступу.*")
            
            # Інформація для ЗСУ
            st.info("🇺🇦 **Для військовослужбовців ЗСУ користування сервісом є безкоштовним.** Зверніться до розробника (sudo.wqa@gmail.com) для отримання постійного коду доступу.")

            # --- НАЛАШТУВАННЯ КОДІВ ---
            ZSU_CODE = "ZSU-HEROES-2026"
            REGULAR_CODE = "PHOTO-MARCH"

            # Поле для введення коду
            unlock_code = st.text_input("Введіть код доступу:", type="password").strip()

            if unlock_code in [ZSU_CODE, REGULAR_CODE]: 
                st.download_button(
                    label="📥 Завантажити чистий PDF для друку",
                    data=pdf_bytes,
                    file_name=f"PhotoPrint_Final_{paper_choice.split()[0]}_{photo_choice.split()[0]}.pdf",
                    mime="application/pdf",
                    type="primary"
                )
            elif unlock_code:
                st.error("❌ Невірний код. Спробуйте ще раз або зверніться до підтримки.")
