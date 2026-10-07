import streamlit as st
import pandas as pd
import pdfplumber
import io
import re
import os
import json
import requests
from PIL import Image

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Hệ Thống Thi Trắc Nghiệm Trực Tuyến", 
    layout="wide", 
    page_icon="🎓"
)

# 🔗 DÁN LINK GOOGLE WEB APP SCRIPT CỦA THẦY/CÔ VÀO ĐÂY (NẾU CÓ):
WEB_APP_URL = "https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec"

# --- CSS GIAO DIỆN ---
st.markdown("""
<style>
    .stApp { background-color: #f8fafc; }
    .student-info-card {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 4px 15px rgba(37, 99, 235, 0.1);
        border: 2px solid #2563eb;
        margin-bottom: 25px;
    }
    .quiz-card {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        border: 1px solid #e2e8f0;
        margin-bottom: 24px;
    }
    .part-header {
        background: linear-gradient(135deg, #1e40af, #2563eb);
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        font-weight: bold;
        font-size: 18px;
        margin-top: 20px;
        margin-bottom: 16px;
    }
    .q-title {
        font-weight: bold;
        color: #1e3a8a;
        font-size: 16px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

STORAGE_DIR = "quiz_storage"
PDF_SAVE_PATH = os.path.join(STORAGE_DIR, "current_quiz.pdf")
KEY_SAVE_PATH = os.path.join(STORAGE_DIR, "answer_key.json")

if not os.path.exists(STORAGE_DIR):
    os.makedirs(STORAGE_DIR)

query_params = st.query_params
is_student_mode = query_params.get("mode") == "student"

@st.cache_data(show_spinner="Đang tải đề thi...")
def extract_question_images(pdf_bytes):
    q_images = {}
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        q_markers = []
        for page_idx, page in enumerate(pdf.pages):
            words = page.extract_words()
            for i, w in enumerate(words):
                text = w['text'].strip()
                m = re.search(r'^Câu\s*(\d+)[\.\:]?', text, re.IGNORECASE)
                if m:
                    q_num = int(m.group(1))
                    q_markers.append({'q_num': q_num, 'page_idx': page_idx, 'top': w['top']})
                elif re.match(r'^Câu$', text, re.IGNORECASE) and i + 1 < len(words):
                    next_text = words[i+1]['text'].strip()
                    m_num = re.search(r'^\d+', next_text)
                    if m_num:
                        q_num = int(m_num.group())
                        q_markers.append({'q_num': q_num, 'page_idx': page_idx, 'top': w['top']})

        unique_markers = []
        seen = set()
        for qm in sorted(q_markers, key=lambda x: (x['page_idx'], x['top'])):
            if qm['q_num'] not in seen:
                unique_markers.append(qm)
                seen.add(qm['q_num'])
                
        unique_markers = sorted(unique_markers, key=lambda x: x['q_num'])

        for idx, curr in enumerate(unique_markers):
            q_num = curr['q_num']
            p_start = curr['page_idx']
            top_y = max(0, curr['top'] - 6)
            
            if idx + 1 < len(unique_markers):
                next_q = unique_markers[idx + 1]
                p_end = next_q['page_idx']
                bottom_y = next_q['top'] - 4
            else:
                p_end = p_start
                bottom_y = pdf.pages[p_start].height - 5

            if p_start == p_end:
                page = pdf.pages[p_start]
                if bottom_y > top_y + 10:
                    try:
                        crop_box = (0, top_y, page.width, bottom_y)
                        img = page.crop(crop_box).to_image(resolution=200).original
                        q_images[q_num] = img
                    except Exception:
                        pass
            else:
                try:
                    page1 = pdf.pages[p_start]
                    img1 = page1.crop((0, top_y, page1.width, page1.height - 5)).to_image(resolution=200).original
                    page2 = pdf.pages[p_end]
                    img2 = page2.crop((0, 0, page2.width, bottom_y)).to_image(resolution=200).original
                    
                    merged_w = max(img1.width, img2.width)
                    merged_h = img1.height + img2.height
                    merged_img = Image.new('RGB', (merged_w, merged_h), (255, 255, 255))
                    merged_img.paste(img1, (0, 0))
                    merged_img.paste(img2, (0, img1.height))
                    q_images[q_num] = merged_img
                except Exception:
                    pass
    return q_images

if 'user_answers' not in st.session_state:
    st.session_state.user_answers = {}

# ==========================================
# ⚙️ GIAO DIỆN QUẢN LÝ DÀNH CHO GIÁO VIÊN
# ==========================================
if not is_student_mode:
    with st.sidebar:
        st.title("⚙️ Tải Đề & Đáp Án")
        uploaded_pdf = st.file_uploader("1. Chọn file Đề (PDF):", type=["pdf"])
        uploaded_excel = st.file_uploader("2. Chọn file Đáp án (Excel):", type=["xlsx", "xls"])
        
        if st.button("💾 XUẤT BẢN ĐỀ THI", type="primary", use_container_width=True):
            if uploaded_pdf and uploaded_excel:
                with open(PDF_SAVE_PATH, "wb") as f:
                    f.write(uploaded_pdf.read())
                
                df = pd.read_excel(uploaded_excel)
                q_col, a_col = df.columns[0], df.columns[1]
                key_dict = {str(row[q_col]).strip().lower(): str(row[a_col]).strip() for _, row in df.iterrows()}
                
                with open(KEY_SAVE_PATH, "w", encoding="utf-8") as f:
                    json.dump(key_dict, f, ensure_ascii=False, indent=2)
                
                st.cache_data.clear()
                st.success("🎉 Đã đăng bài thi thành công!")
            else:
                st.error("Vui lòng tải đủ cả file PDF và Excel!")

    st.title("🎓 HỆ THỐNG QUẢN LÝ ĐỀ THI (GIÁO VIÊN)")
    
    # Lấy đường link hiện tại của ứng dụng
    student_url = f"https://kiemtraonline.streamlit.app/?mode=student" # Thầy/cô thay tên domain app trên Streamlit Cloud tại đây
    
    if os.path.exists(PDF_SAVE_PATH) and os.path.exists(KEY_SAVE_PATH):
        st.success("✅ Đề thi hiện tại đã sẵn sàng phục vụ học sinh.")
        st.info("📌 **ĐƯỜNG LINK GỬI CHO HỌC SINH LÀM BÀI:**")
        st.code(student_url, language="markdown")
        st.caption("💡 Học sinh mở link này sẽ thấy ngay khung điền Họ tên, Lớp và giao diện làm bài.")
    else:
        st.warning("👈 Vui lòng tải file Đề (PDF) và Đáp án (Excel) ở menu bên trái để xuất bản bài thi!")

# ==========================================
# 🎓 GIAO DIỆN LÀM BÀI DÀNH CHO HỌC SINH
# ==========================================
if is_student_mode:
    # Ẩn hoàn toàn Sidebar với học sinh
    st.markdown("<style>section[data-testid='stSidebar'] {display: none;}</style>", unsafe_allow_html=True)
    
    st.title("🎓 ĐỀ THI TRẮC NGHIỆM TRỰC TUYẾN")
    
    if os.path.exists(PDF_SAVE_PATH) and os.path.exists(KEY_SAVE_PATH):
        # --- KHUNG NHẬP HỌ TÊN VÀ LỚP (BẮT BUỘC) ---
        st.markdown("""
        <div class="student-info-card">
            <h3 style="color: #1e40af; margin-top: 0;">👤 THÔNG TIN THÍ SINH</h3>
            <p style="color: #64748b; margin-bottom: 15px;">Vui lòng điền đầy đủ Họ tên và Lớp trước khi làm và nộp bài.</p>
        </div>
        """, unsafe_allow_html=True)
        
        col_name, col_class = st.columns(2)
        with col_name:
            student_name = st.text_input("Họ và tên học sinh (*):", placeholder="Ví dụ: Nguyễn Văn A")
        with col_class:
            student_class = st.text_input("Lớp (*):", placeholder="Ví dụ: 12A1")

        st.markdown("---")

        with open(PDF_SAVE_PATH, "rb") as f:
            pdf_bytes = f.read()
        with open(KEY_SAVE_PATH, "r", encoding="utf-8") as f:
            answer_key = json.load(f)
            
        q_images = extract_question_images(pdf_bytes)
        
        # PHẦN I
        st.markdown('<div class="part-header">PHẦN I. Trắc nghiệm 4 lựa chọn (Câu 1 đến Câu 12)</div>', unsafe_allow_html=True)
        for q_num in range(1, 13):
            if q_num in q_images:
                st.markdown("<div class='quiz-card'>", unsafe_allow_html=True)
                st.markdown(f"<div class='q-title'>Câu {q_num}</div>", unsafe_allow_html=True)
                st.image(q_images[q_num], use_container_width=True)
                ans_key = f"p1_{q_num}"
                selected = st.radio(
                    f"Chọn đáp án cho Câu {q_num}:", 
                    ["A", "B", "C", "D"], 
                    horizontal=True, 
                    key=ans_key,
                    index=["A","B","C","D"].index(st.session_state.user_answers.get(ans_key)) if ans_key in st.session_state.user_answers else None
                )
                if selected:
                    st.session_state.user_answers[ans_key] = selected
                st.markdown("</div>", unsafe_allow_html=True)

        # PHẦN II
        st.markdown('<div class="part-header">PHẦN II. Trắc nghiệm Đúng / Sai (Câu 13 đến Câu 16)</div>', unsafe_allow_html=True)
        for q_num in range(13, 17):
            if q_num in q_images:
                st.markdown("<div class='quiz-card'>", unsafe_allow_html=True)
                st.markdown(f"<div class='q-title'>Câu {q_num}</div>", unsafe_allow_html=True)
                st.image(q_images[q_num], use_container_width=True)
                st.markdown("**Chọn Đúng hoặc Sai cho các mệnh đề a), b), c), d):**")
                cols = st.columns(4)
                for idx, sub in enumerate(['a', 'b', 'c', 'd']):
                    ans_key = f"p2_{q_num}_{sub}"
                    with cols[idx]:
                        sub_sel = st.radio(
                            f"Mệnh đề {sub}):", 
                            ["Đúng", "Sai"], 
                            horizontal=True, 
                            key=ans_key,
                            index=["Đúng", "Sai"].index(st.session_state.user_answers.get(ans_key)) if ans_key in st.session_state.user_answers else None
                        )
                        if sub_sel:
                            st.session_state.user_answers[ans_key] = sub_sel
                st.markdown("</div>", unsafe_allow_html=True)

        # PHẦN III
        st.markdown('<div class="part-header">PHẦN III. Trả lời ngắn (Câu 17 đến Câu 22)</div>', unsafe_allow_html=True)
        for q_num in range(17, 23):
            if q_num in q_images:
                st.markdown("<div class='quiz-card'>", unsafe_allow_html=True)
                st.markdown(f"<div class='q-title'>Câu {q_num}</div>", unsafe_allow_html=True)
                st.image(q_images[q_num], use_container_width=True)
                ans_key = f"p3_{q_num}"
                user_val = st.text_input(
                    f"Nhập kết quả dạng số cho Câu {q_num}:", 
                    value=st.session_state.user_answers.get(ans_key, ""), 
                    key=ans_key
                )
                if user_val:
                    st.session_state.user_answers[ans_key] = user_val.strip()
                st.markdown("</div>", unsafe_allow_html=True)

        # NÚT NỘP BÀI THI
        st.markdown("---")
        if st.button("📝 NỘP BÀI VÀ CHẤM ĐIỂM", type="primary", use_container_width=True):
            # KIỂM TRA BẮT BUỘC ĐIỀN HỌ TÊN VÀ LỚP
            if not student_name.strip() or not student_class.strip():
                st.error("❌ **BẠN CHƯA ĐIỀN THÔNG TIN!** Vui lòng kéo lên đầu trang và nhập đầy đủ **Họ tên** và **Lớp** trước khi bấm Nộp bài.")
            else:
                st.balloons()
                score_p1, score_p2, score_p3 = 0.0, 0.0, 0.0
                
                # Chấm Phần I
                for q_num in range(1, 13):
                    u_ans = st.session_state.user_answers.get(f"p1_{q_num}", "").upper()
                    c_ans = answer_key.get(str(q_num).lower(), "").upper()
                    if u_ans and c_ans and u_ans == c_ans:
                        score_p1 += 0.25

                # Chấm Phần II
                p2_map = {1: 0.1, 2: 0.25, 3: 0.5, 4: 1.0}
                for q_num in range(13, 17):
                    correct_count = 0
                    for sub in ['a', 'b', 'c', 'd']:
                        u_ans = st.session_state.user_answers.get(f"p2_{q_num}_{sub}", "").lower()
                        c_ans = answer_key.get(f"{q_num}{sub}".lower(), "").lower()
                        if u_ans in ['đúng', 'd', 'true']: u_ans = 'đúng'
                        elif u_ans in ['sai', 's', 'false']: u_ans = 'sai'
                        if c_ans in ['đúng', 'd', 'true']: c_ans = 'đúng'
                        elif c_ans in ['sai', 's', 'false']: c_ans = 'sai'
                        
                        if u_ans and c_ans and u_ans == c_ans:
                            correct_count += 1
                    score_p2 += p2_map.get(correct_count, 0.0)

                # Chấm Phần III
                for q_num in range(17, 23):
                    u_ans = st.session_state.user_answers.get(f"p3_{q_num}", "").replace(',', '.')
                    c_ans = answer_key.get(str(q_num).lower(), "").replace(',', '.')
                    if u_ans and c_ans and u_ans == c_ans:
                        score_p3 += 0.5

                total_score = round(score_p1 + score_p2 + score_p3, 2)
                
                # GỬI KẾT QUẢ ĐIỂM VỀ GOOGLE SHEET (NẾU CÓ ĐƯỜNG LINK API)
                if WEB_APP_URL and "YOUR_SCRIPT_ID" not in WEB_APP_URL:
                    payload = {
                        "student_name": student_name.strip(),
                        "student_class": student_class.strip(),
                        "score_p1": round(score_p1, 2),
                        "score_p2": round(score_p2, 2),
                        "score_p3": round(score_p3, 2),
                        "total_score": total_score
                    }
                    try:
                        requests.post(WEB_APP_URL, json=payload)
                        st.success("✅ Đã tự động lưu kết quả vào Google Sheet của Giáo viên!")
                    except Exception:
                        pass

                st.success(f"🎉 **KẾT QUẢ BÀI LÀM - THÍ SINH: {student_name.upper()} (LỚP {student_class.upper()})**")
                st.subheader(f"🏆 Tổng điểm: {total_score} / 10.0")
                col1, col2, col3 = st.columns(3)
                col1.metric("Phần I (Trắc nghiệm)", f"{round(score_p1, 2)}đ / 3.0đ")
                col2.metric("Phần II (Đúng/Sai)", f"{round(score_p2, 2)}đ / 4.0đ")
                col3.metric("Phần III (Trả lời ngắn)", f"{round(score_p3, 2)}đ / 3.0đ")
    else:
        st.warning("⚠️ Hiện tại chưa có bài thi nào được đăng. Vui lòng liên hệ Giáo viên!")