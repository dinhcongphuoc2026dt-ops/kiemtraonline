import streamlit as st
import pandas as pd
import io
import os
import json
import requests
import base64

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Hệ Thống Thi Trắc Nghiệm Trực Tuyến", 
    layout="wide", 
    page_icon="🎓"
)

# 🔗 DÁN LINK GOOGLE WEB APP SCRIPT CỦA THẦY/CÔ VÀO ĐÂY:
WEB_APP_URL = "https://script.google.com/macros/s/AKfycbxdJTfcS9TZqkogncwxjVag27V2zgbPZGkW0qfhQd7JgIdzC3Mt32wo_CZfgYx2Xu1fjQ/exec"

# --- CSS TỐI ƯU GIAO DIỆN CHIA ĐÔI MÀN HÌNH ---
st.markdown("""
<style>
    .stApp { background-color: #f1f5f9; }
    
    /* Thẻ thông tin học sinh */
    .student-info-card {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 16px 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        border-left: 5px solid #2563eb;
        margin-bottom: 15px;
    }
    
    /* Khung phiếu làm bài bên phải */
    .answer-box {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 18px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
        border: 1px solid #cbd5e1;
        margin-bottom: 16px;
    }

    /* Tiêu đề từng phần */
    .part-header-sm {
        background: linear-gradient(135deg, #1e40af, #2563eb);
        color: white;
        padding: 10px 16px;
        border-radius: 8px;
        font-weight: bold;
        font-size: 16px !important;
        margin-top: 15px;
        margin-bottom: 15px;
    }
    
    .q-number {
        font-weight: bold;
        color: #1e3a8a;
        font-size: 16px !important;
        margin-bottom: 6px;
    }

    /* Định dạng Radio button gọn gàng */
    .stRadio label p, .stRadio div[role="radiogroup"] p {
        font-size: 16px !important;
        font-weight: 600 !important;
        color: #0f172a !important;
    }

    .stTextInput input {
        font-size: 16px !important;
    }
    
    /* Sticky cho khung PDF bên trái khi cuộn */
    @media (min-width: 992px) {
        div[data-testid="stColumn"]:first-child {
            position: sticky;
            top: 1rem;
            height: calc(100vh - 2rem);
        }
    }
</style>
""", unsafe_allow_html=True)

STORAGE_DIR = "quiz_storage"
PDF_SAVE_PATH = os.path.join(STORAGE_DIR, "current_quiz.pdf")
KEY_SAVE_PATH = os.path.join(STORAGE_DIR, "answer_key.json")

if not os.path.exists(STORAGE_DIR):
    os.makedirs(STORAGE_DIR)

# --- XỬ LÝ CHẾ ĐỘ HỌC SINH / GIÁO VIÊN ---
is_student_mode = False
try:
    is_student_mode = st.query_params.get("mode") == "student"
except Exception:
    try:
        params = st.experimental_get_query_params()
        mode_val = params.get("mode", [""])
        is_student_mode = mode_val[0] == "student" if isinstance(mode_val, list) else mode_val == "student"
    except Exception:
        is_student_mode = False

if 'user_answers' not in st.session_state:
    st.session_state.user_answers = {}

# ==========================================
# ⚙️ GIAO DIỆN GIÁO VIÊN
# ==========================================
if not is_student_mode:
    with st.sidebar:
        st.title("⚙️ Tải Đề & Đáp Án")
        uploaded_pdf = st.file_uploader("1. Chọn file Đề (PDF):", type=["pdf"])
        uploaded_excel = st.file_uploader("2. Chọn file Đáp án (Excel):", type=["xlsx", "xls"])
        
        if st.button("💾 XUẤT BẢN ĐỀ THI", type="primary"):
            if uploaded_pdf and uploaded_excel:
                with open(PDF_SAVE_PATH, "wb") as f:
                    f.write(uploaded_pdf.read())
                
                df = pd.read_excel(uploaded_excel)
                q_col, a_col = df.columns[0], df.columns[1]
                key_dict = {str(row[q_col]).strip().lower(): str(row[a_col]).strip() for _, row in df.iterrows()}
                
                with open(KEY_SAVE_PATH, "w", encoding="utf-8") as f:
                    json.dump(key_dict, f, ensure_ascii=False, indent=2)
                
                st.success("🎉 Đã xuất bản đề thi thành công!")
            else:
                st.error("Vui lòng tải đủ cả file PDF và Excel!")

    st.title("🎓 HỆ THỐNG QUẢN LÝ ĐỀ THI (GIÁO VIÊN)")
    
    student_url = f"https://kiemtraonline.streamlit.app/?mode=student"
    
    if os.path.exists(PDF_SAVE_PATH) and os.path.exists(KEY_SAVE_PATH):
        st.success("✅ Đề thi đã sẵn sàng trên hệ thống.")
        st.info("📌 **ĐƯỜNG LINK GỬI CHO HỌC SINH:**")
        st.code(student_url, language="markdown")
    else:
        st.warning("👈 Vui lòng tải file Đề (PDF) và Đáp án (Excel) ở thanh bên trái!")

# ==========================================
# 🎓 GIAO DIỆN HỌC SINH (CHIA ĐÔI MÀN HÌNH)
# ==========================================
if is_student_mode:
    st.markdown("<style>section[data-testid='stSidebar'] {display: none;}</style>", unsafe_allow_html=True)
    
    st.title("🎓 ĐỀ THI TRẮC NGHIỆM TRỰC TUYẾN")
    
    if os.path.exists(PDF_SAVE_PATH) and os.path.exists(KEY_SAVE_PATH):
        # 1. THÔNG TIN HỌC SINH
        st.markdown("""
        <div class="student-info-card">
            <b style="color: #1e40af; font-size: 18px;">👤 THÔNG TIN THÍ SINH</b> (Điền đầy đủ trước khi nộp bài)
        </div>
        """, unsafe_allow_html=True)
        
        col_name, col_class = st.columns(2)
        with col_name:
            student_name = st.text_input("Họ và tên học sinh (*):", placeholder="Ví dụ: Nguyễn Văn A")
        with col_class:
            student_class = st.text_input("Lớp (*):", placeholder="Ví dụ: 12A1")

        st.markdown("---")

        # ĐỌC FILE PDF ĐỀ THI
        with open(PDF_SAVE_PATH, "rb") as f:
            pdf_bytes = f.read()
        with open(KEY_SAVE_PATH, "r", encoding="utf-8") as f:
            answer_key = json.load(f)

        pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')

        # 2. BỐ CỤC CHIA ĐÔI MÀN HÌNH (CỘT TRÁI: ĐỀ THI | CỘT PHẢI: PHIẾU BÀI LÀM)
        col_left, col_right = st.columns([1.25, 1.0])

        # ------------------------------------
        # CỘT TRÁI: TRÌNH XEM ĐỀ THI PHÓNG TO / THU NHỎ
        # ------------------------------------
        with col_left:
            st.subheader("📄 ĐỀ THI (Dùng nút +, - để phóng to/thu nhỏ)")
            
            # Khung hiển thị PDF trực tiếp có sẵn thanh công cụ Zoom/Fit/Scroll
            pdf_display_html = f'''
            <div style="border: 2px solid #2563eb; border-radius: 10px; overflow: hidden; background: #525659;">
                <iframe src="data:application/pdf;base64,{pdf_b64}#toolbar=1&navpanes=0&view=FitH" 
                        width="100%" 
                        height="820px" 
                        style="border:none;">
                </iframe>
            </div>
            '''
            st.markdown(pdf_display_html, unsafe_allow_html=True)
            
            # Nút dự phòng mở toàn màn hình
            btn_full = f'''
            <div style="margin-top: 10px; text-align: center;">
                <a href="data:application/pdf;base64,{pdf_b64}" target="_blank" style="
                    display: inline-block;
                    background-color: #2563eb;
                    color: #ffffff;
                    padding: 8px 16px;
                    text-decoration: none;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 15px;
                    box-shadow: 0 2px 6px rgba(37, 99, 235, 0.3);
                ">🔍 Mở Đề Thi Toàn Màn Hình Trang Mới ↗️</a>
            </div>
            '''
            st.markdown(btn_full, unsafe_allow_html=True)

        # ------------------------------------
        # CỘT PHẢI: PHIẾU TRẢ LỜI ĐÁP ÁN
        # ------------------------------------
        with col_right:
            st.subheader("📝 PHIẾU TRẢ LỜI")
            
            # PHẦN I
            st.markdown('<div class="part-header-sm">PHẦN I. Trắc nghiệm 4 lựa chọn (Câu 1 - 12)</div>', unsafe_allow_html=True)
            for q_num in range(1, 13):
                st.markdown("<div class='answer-box'>", unsafe_allow_html=True)
                ans_key = f"p1_{q_num}"
                selected = st.radio(
                    f"Câu {q_num}:", 
                    ["A", "B", "C", "D"], 
                    horizontal=True, 
                    key=ans_key,
                    index=["A","B","C","D"].index(st.session_state.user_answers.get(ans_key)) if ans_key in st.session_state.user_answers else None
                )
                if selected:
                    st.session_state.user_answers[ans_key] = selected
                st.markdown("</div>", unsafe_allow_html=True)

            # PHẦN II
            st.markdown('<div class="part-header-sm">PHẦN II. Trắc nghiệm Đúng / Sai (Câu 13 - 16)</div>', unsafe_allow_html=True)
            for q_num in range(13, 17):
                st.markdown("<div class='answer-box'>", unsafe_allow_html=True)
                st.markdown(f"<div class='q-number'>Câu {q_num}:</div>", unsafe_allow_html=True)
                cols = st.columns(2)
                for idx, sub in enumerate(['a', 'b', 'c', 'd']):
                    ans_key = f"p2_{q_num}_{sub}"
                    with cols[idx % 2]:
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
            st.markdown('<div class="part-header-sm">PHẦN III. Trả lời ngắn (Câu 17 - 22)</div>', unsafe_allow_html=True)
            for q_num in range(17, 23):
                st.markdown("<div class='answer-box'>", unsafe_allow_html=True)
                ans_key = f"p3_{q_num}"
                user_val = st.text_input(
                    f"Đáp án Câu {q_num}:", 
                    value=st.session_state.user_answers.get(ans_key, ""), 
                    key=ans_key,
                    placeholder="Nhập số..."
                )
                if user_val:
                    st.session_state.user_answers[ans_key] = user_val.strip()
                st.markdown("</div>", unsafe_allow_html=True)

            # NÚT NỘP BÀI
            st.markdown("---")
            if st.button("📝 NỘP BÀI VÀ CHẤM ĐIỂM", type="primary", use_container_width=True):
                if not student_name.strip() or not student_class.strip():
                    st.error("❌ **BẠN CHƯA ĐIỀN THÔNG TIN!** Nhập Họ tên & Lớp ở đầu trang.")
                else:
                    score_p1, score_p2, score_p3 = 0.0, 0.0, 0.0
                    
                    # 1. Chấm Phần I
                    for q_num in range(1, 13):
                        u_ans = st.session_state.user_answers.get(f"p1_{q_num}", "").upper()
                        c_ans = answer_key.get(str(q_num).lower(), "").upper()
                        if u_ans and c_ans and u_ans == c_ans:
                            score_p1 += 0.25

                    # 2. Chấm Phần II
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

                    # 3. Chấm Phần III
                    for q_num in range(17, 23):
                        u_ans = st.session_state.user_answers.get(f"p3_{q_num}", "").replace(',', '.')
                        c_ans = answer_key.get(str(q_num).lower(), "").replace(',', '.')
                        if u_ans and c_ans and u_ans == c_ans:
                            score_p3 += 0.5

                    total_score = round(score_p1 + score_p2 + score_p3, 2)
                    
                    # 4. GỬI KẾT QUẢ VỀ GOOGLE SHEET
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
                            res = requests.post(WEB_APP_URL, json=payload).json()
                            if res.get("result") == "already_submitted":
                                st.error(f"🚫 **THÍ SINH {student_name.upper()} ({student_class.upper()}) ĐÃ NỘP BÀI TRƯỚC ĐÓ!**")
                            elif res.get("result") == "success":
                                try: st.balloons()
                                except Exception: pass
                                st.success(f"🎉 **NỘP BÀI THÀNH CÔNG! THÍ SINH: {student_name.upper()} ({student_class.upper()})**")
                                st.subheader(f"🏆 Tổng điểm: {total_score} / 10.0")
                                col1, col2, col3 = st.columns(3)
                                col1.metric("Phần I", f"{round(score_p1, 2)}đ / 3.0đ")
                                col2.metric("Phần II", f"{round(score_p2, 2)}đ / 4.0đ")
                                col3.metric("Phần III", f"{round(score_p3, 2)}đ / 3.0đ")
                        except Exception:
                            st.error("Lỗi kết nối Google Sheet. Vui lòng thử lại!")
                    else:
                        try: st.balloons()
                        except Exception: pass
                        st.success(f"🎉 **ĐÃ NỘP BÀI THÀNH CÔNG! THÍ SINH: {student_name.upper()} ({student_class.upper()})**")
                        st.subheader(f"🏆 Tổng điểm: {total_score} / 10.0")
    else:
        st.warning("⚠️ Hiện tại chưa có bài thi nào được đăng. Vui lòng liên hệ Giáo viên!")