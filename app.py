import streamlit as st
import pandas as pd
import pdfplumber
import io
import re
import os
import json
from PIL import Image

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Hệ Thống Quizz Thi Trực Tuyến", 
    layout="wide", 
    page_icon="🎓"
)

# --- CSS GIAO DIỆN ---
st.markdown("""
<style>
    .stApp { background-color: #f8fafc; }
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

# --- THƯ MỤC LƯU TRỮ ĐỀ THI DÙNG CHUNG ---
STORAGE_DIR = "quiz_storage"
PDF_SAVE_PATH = os.path.join(STORAGE_DIR, "current_quiz.pdf")
KEY_SAVE_PATH = os.path.join(STORAGE_DIR, "answer_key.json")

if not os.path.exists(STORAGE_DIR):
    os.makedirs(STORAGE_DIR)

# --- KIỂM TRA CHẾ ĐỘ (GIÁO VIÊN HAY HỌC SINH) ---
query_params = st.query_params
is_student_mode = query_params.get("mode") == "student"

# --- HÀM CẮT ẢNH NÂNG CẤP CẮT TỪ ĐẦU CÂU N ĐẾN ĐẦU CÂU N+1 ---
@st.cache_data(show_spinner="Đang xử lý chuẩn hóa đề thi...")
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

# --- LƯU TRẠNG THÁI BÀI LÀM CỦA HỌC SINH ---
if 'user_answers' not in st.session_state:
    st.session_state.user_answers = {}

# --- GIAO DIỆN TẢI FILE DÀNH CHO GIÁO VIÊN ---
if not is_student_mode:
    with st.sidebar:
        st.title("⚙️ Bảng Quản Lý Dành Cho Giáo Viên")
        uploaded_pdf = st.file_uploader("1. Tải file Đề (PDF):", type=["pdf"])
        uploaded_excel = st.file_uploader("2. Tải file Đáp án (Excel):", type=["xlsx", "xls"])
        
        if st.button("💾 ĐĂNG BÀI THI CHO HỌC SINH", type="primary", use_container_width=True):
            if uploaded_pdf and uploaded_excel:
                # 1. Lưu file PDF vào server
                pdf_bytes = uploaded_pdf.read()
                with open(PDF_SAVE_PATH, "wb") as f:
                    f.write(pdf_bytes)
                
                # 2. Đọc và Lưu file Đáp án JSON vào server
                df = pd.read_excel(uploaded_excel)
                q_col, a_col = df.columns[0], df.columns[1]
                key_dict = {}
                for _, row in df.iterrows():
                    k = str(row[q_col]).strip().lower()
                    v = str(row[a_col]).strip()
                    key_dict[k] = v
                
                with open(KEY_SAVE_PATH, "w", encoding="utf-8") as f:
                    json.dump(key_dict, f, ensure_ascii=False, indent=2)
                
                st.cache_data.clear() # Xóa cache cũ
                st.success("🎉 Đã xuất bản đề thi thành công! Học sinh đã có thể làm bài qua đường link.")
            else:
                st.error("Vui lòng tải đủ cả file PDF đề thi và Excel đáp án!")

# --- HIỂN THỊ LINK & HƯỚNG DẪN DÀNH CHO GIÁO VIÊN ---
if not is_student_mode:
    st.title("🎓 TRANG QUẢN LÝ ĐỀ THI - DÀNH CHO GIÁO VIÊN")
    
    # Lấy đường dẫn URL thực tế của ứng dụng
    student_url = f"https://your-app-domain.streamlit.app/?mode=student" # Thay tên miền thực tế ứng dụng của bạn vào đây
    
    if os.path.exists(PDF_SAVE_PATH) and os.path.exists(KEY_SAVE_PATH):
        st.success("✅ Hiện tại ĐÃ CÓ đề thi được lưu trên hệ thống.")
        st.info("📌 **ĐƯỜNG LINK GỬI CHO HỌC SINH (KHÔNG CẦN ĐĂNG NHẬP):**")
        st.code(student_url, language="markdown")
        st.caption("⚠️ Học sinh bấm vào link trên sẽ trực tiếp vào giao diện làm bài thi, hoàn toàn không thấy thanh cấu hình hay đáp án.")
    else:
        st.warning("👈 Vui lòng tải file **Đề (PDF)**, **Đáp án (Excel)** ở thanh bên trái và bấm nút **'ĐĂNG BÀI THI CHO HỌC SINH'**.")

# --- GIAO DIỆN BÀI THI DÀNH CHO HỌC SINH ---
if is_student_mode:
    st.title("🎓 ĐỀ THI TRẮC NGHIỆM TỔNG HỢP - CHUẨN BỘ GD&ĐT")
    # Ẩn Sidebar hoàn toàn khi học sinh làm bài
    st.markdown("<style>section[data-testid='stSidebar'] {display: none;}</style>", unsafe_allow_html=True)
    
    if os.path.exists(PDF_SAVE_PATH) and os.path.exists(KEY_SAVE_PATH):
        # Tự động đọc file Đề từ Server
        with open(PDF_SAVE_PATH, "rb") as f:
            pdf_bytes = f.read()
            
        # Tự động đọc Đáp án từ Server
        with open(KEY_SAVE_PATH, "r", encoding="utf-8") as f:
            answer_key = json.load(f)
            
        q_images = extract_question_images(pdf_bytes)
        
        # PHẦN I
        st.markdown('<div class="part-header">PHẦN I. Thí sinh trả lời từ câu 1 đến câu 12 (Trắc nghiệm 4 lựa chọn)</div>', unsafe_allow_html=True)
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
        st.markdown('<div class="part-header">PHẦN II. Thí sinh trả lời từ câu 13 đến câu 16 (Trắc nghiệm Đúng / Sai)</div>', unsafe_allow_html=True)
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
        st.markdown('<div class="part-header">PHẦN III. Thí sinh trả lời từ câu 17 đến câu 22 (Trả lời ngắn)</div>', unsafe_allow_html=True)
        for q_num in range(17, 23):
            if q_num in q_images:
                st.markdown("<div class='quiz-card'>", unsafe_allow_html=True)
                st.markdown(f"<div class='q-title'>Câu {q_num}</div>", unsafe_allow_html=True)
                st.image(q_images[q_num], use_container_width=True)
                ans_key = f"p3_{q_num}"
                user_val = st.text_input(
                    f"Nhập đáp án dạng số cho Câu {q_num}:", 
                    value=st.session_state.user_answers.get(ans_key, ""), 
                    key=ans_key
                )
                if user_val:
                    st.session_state.user_answers[ans_key] = user_val.strip()
                st.markdown("</div>", unsafe_allow_html=True)

        # NÚT NỘP BÀI VÀ CHẤM ĐIỂM TỰ ĐỘNG
        st.markdown("---")
        if st.button("📝 NỘP BÀI VÀ CHẤM ĐIỂM TỰ ĐỘNG", type="primary", use_container_width=True):
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
            st.success(f"🎉 **TỔNG ĐIỂM BÀI LÀM: {total_score} / 10.0**")
            col1, col2, col3 = st.columns(3)
            col1.metric("Điểm Phần I", f"{round(score_p1, 2)}đ / 3.0đ")
            col2.metric("Điểm Phần II", f"{round(score_p2, 2)}đ / 4.0đ")
            col3.metric("Điểm Phần III", f"{round(score_p3, 2)}đ / 3.0đ")
    else:
        st.warning("⚠️ Hiện tại chưa có bài thi nào được đăng. Vui lòng liên hệ Giáo viên!")