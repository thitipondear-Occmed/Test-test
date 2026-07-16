import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import time
import os
from datetime import datetime

# ==============================================================================
# 🎯 การตั้งค่าคอนฟิกหน้าจอให้แผ่กว้างเต็มจอ 100% (Wide Mode)
# ==============================================================================
st.set_page_config(
    page_title="Pneumoconiosis Interpretation Record",
    page_icon="📝",
    layout="wide"
)

# --- การตั้งค่าคอนฟิกและพาธข้อมูล ---
MASTER_KEY_PATH = 'master_key_crossover.csv'  # ไฟล์ Master Key
ASSETS_DIR = 'streamlit_assets'  # โฟลเดอร์เก็บไฟล์ภาพ

# ==============================================================================
# 🔍 [ปรับเพิ่มใหม่] ฟังก์ชันหน้าต่าง Popup สำหรับซูมภาพดิบให้ใหญ่เต็มตา
# ==============================================================================
@st.dialog("🔍 ภาพเอกซเรย์ทรวงอกขนาดขยายใหญ่พิเศษ (Zoom Raw Image)")
def open_zoom_modal(img_path):
    st.image(img_path, use_container_width=True)
    st.markdown("<p style='text-align: center; color: #888;'>💡 คลิกพื้นที่ด้านนอก หรือกดเครื่องหมาย X มุมขวาบนเพื่อปิดหน้าต่างซูม</p>", unsafe_allow_html=True)


# --- 1. ฟังก์ชันเชื่อมต่อและบันทึกข้อมูลลง Google Sheets ---
@st.cache_resource
def get_gspread_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

def save_doctor_profile_to_sheets(doc_id, specialty, training, exp_years, group, period):
    try:
        client = get_gspread_client()
        sheet = client.open_by_url(st.secrets["google_sheets_url"])
        worksheet = sheet.worksheet("doctor_profiles")
        
        row_data = [
            doc_id, specialty, training, exp_years, group, period, 
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ]
        worksheet.append_row(row_data)
        return True
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการเชื่อมต่อ Google Sheets: {e}")
        return False

def save_interpretation_log_to_sheets(doc_id, period, img_set, exam_id, ai_on, decision, time_spent):
    try:
        client = get_gspread_client()
        sheet = client.open_by_url(st.secrets["google_sheets_url"])
        worksheet = sheet.worksheet("interpretation_logs")
        
        row_data = [
            doc_id, period, img_set, exam_id, int(ai_on), decision, 
            round(time_spent, 4), datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ]
        worksheet.append_row(row_data)
        return True
    except Exception as e:
        st.error(f"ไม่สามารถบันทึก Log ลง Google Sheets ได้: {e}")
        return False

def save_hsus_responses_to_sheets(doc_id, ratings_dict, open_answers_list):
    try:
        client = get_gspread_client()
        sheet = client.open_by_url(st.secrets["google_sheets_url"])
        worksheet = sheet.worksheet("hsus_responses")
        
        row_data = [doc_id] + [ratings_dict[f"Q{i}"] for i in range(1, 21)] + open_answers_list + [datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
        worksheet.append_row(row_data)
        return True
    except Exception as e:
        st.error(f"ไม่สามารถบันทึกแบบประเมิน HSUS ลงระบบได้: {e}")
        return False

# --- 2. ตั้งค่าการจัดการ State ของหน้าจอ Streamlit ---
if 'step' not in st.session_state:
    st.session_state.step = 'LOGIN'
if 'current_index' not in st.session_state:
    st.session_state.current_index = 0
if 'case_start_time' not in st.session_state:
    st.session_state.case_start_time = None

# --- 3. หน้าจอที่ 1: ลงทะเบียนประวัติแพทย์ ---
if st.session_state.step == 'LOGIN':
    st.title("📝 แบบบันทึกผลการอ่านภาพถ่ายรังสีทรวงอก")
    st.subheader("(Chest X-ray Interpretation Record Form)")
    st.write("---")
    
    st.markdown("### ข้อมูลทั่วไป (Demographic Information)")
    doc_id = st.text_input("รหัสแพทย์ผู้ทดสอบ (Doctor ID):", placeholder="เช่น Doc_01").strip()
    
    specialty = st.radio("1. วิชาชีพ/ตำแหน่งปัจจุบัน:", ["แพทย์ทั่วไป", "แพทย์ประจำบ้านอาชีวเวชศาสตร์", "แพทย์อาชีวเวชศาสตร์"])
    training = st.radio("2. หลักสูตรที่ผ่านการอบรมการแปลผลฟิล์มในมาตรฐาน ILO:", ["ไม่เคยอบรม", "อบรม ILO ระยะสั้น 3 วัน", "AIR Pneumo"])
    
    exp_years = st.number_input(
        "3. มีประสบการณ์หลังการอบรมคัดกรองโรคปอดฝุ่นทรายกี่ปี (ปี):", 
        min_value=0, max_value=50, value=0, step=1
    )
    
    st.write("---")
    st.markdown("### การจัดกลุ่มทดลอง (Experimental Settings)")
    period = st.selectbox("รอบการทดลอง (Experimental Period):", [1, 2], help="รอบที่ 1 หรือ รอบที่ 2 หลังผ่าน Washout period")
    group = st.selectbox("กลุ่มการทดลองที่ได้รับสุ่ม (Assigned Group):", ["กลุ่มที่ 1", "กลุ่มที่ 2"])
    
    if st.button("เริ่มขั้นตอนคำชี้แจง (Next)", type="primary"):
        if doc_id:
            st.session_state.doc_id = doc_id
            st.session_state.specialty = specialty
            st.session_state.training = training
            st.session_state.exp_years = exp_years
            st.session_state.group = group
            st.session_state.period = period
            
            with st.spinner("กำลังลงทะเบียนข้อมูลเข้าสู่คลาวด์..."):
                if save_doctor_profile_to_sheets(doc_id, specialty, training, exp_years, group, period):
                    st.session_state.step = 'INSTRUCTIONS'
                    st.rerun()
        else:
            st.error("กรุณากรอกรหัส Doctor ID ก่อนเข้าสู่ระบบครับคุณหมอ")

# --- 4. หน้าจอที่ 2: คำชี้แจงเกณฑ์วินัยและวิธีการตรวจ ---
elif st.session_state.step == 'INSTRUCTIONS':
    st.title("📋 คำชี้แจงและเกณฑ์การวินิจฉัย")
    st.write("---")
    st.markdown(f"**รหัสแพทย์:** {st.session_state.doc_id} | **รอบที่:** {st.session_state.period} | **กลุ่มที่:** {st.session_state.group}")
    
    st.markdown("""
    ### 📌 เกณฑ์การตัดสินใจ (Criteria for Interpretation)
    ขอให้ท่านพิจารณาภาพถ่ายรังสีทรวงอก (CXR) ที่ปรากฏบนหน้าจอ และระบุคำตอบว่าภาพดังกล่าว **"ปกติ (Normal)"** หรือ **"ผิดปกติ (Abnormal)"**
    
    * **นิยามความผิดปกติ (Abnormal):** หมายถึง ภาพถ่ายรังสีทรวงอกที่เข้าได้กับ **โรคนิวโมโคนิโอสิส (Pneumoconiosis)** โดยมีรอยโรคระดับความหนาแน่น (Profusion) ตั้งแต่ **1/0 ขึ้นไป** ตามมาตรฐาน ILO Classification
    
    ### ⏱️ ระบบจับเวลาอัตโนมัติ
    * ระบบจะทำการ **จับเวลาโดยอัตโนมัติ** ทันทีที่ภาพฟิล์มแสดงผลขึ้นบนหน้าจอ
    * เมื่อท่านตัดสินใจได้แล้ว ให้เลือกตัวเลือกคำตอบและกดปุ่ม **'ยืนยัน (Confirm)'** ระบบจะทำการหยุดเวลาและเปลี่ยนเป็นข้อถัดไปโดยอัตโนมัติ
    """)
    
    if st.button("เข้าสู่สนามสอบ (Start Test)", type="primary"):
        if os.path.exists(MASTER_KEY_PATH):
            df_master = pd.read_csv(MASTER_KEY_PATH)
            
            if st.session_state.group == "กลุ่มที่ 1":
                target_set = 'A' if st.session_state.period == 1 else 'B'
                ai_assisted = False if st.session_state.period == 1 else True
            else:
                target_set = 'B' if st.session_state.period == 1 else 'A'
                ai_assisted = True if st.session_state.period == 1 else False
            
            df_exam = df_master[df_master['Assigned_Set'] == target_set].sort_values(by='Exam_ID').reset_index(drop=True)
            
            st.session_state.exam_cases = df_exam.to_dict(orient='records')
            st.session_state.current_set = target_set
            st.session_state.ai_assisted = ai_assisted
            st.session_state.step = 'EXAM'
            st.session_state.current_index = 0
            st.session_state.case_start_time = time.time()
            st.rerun()
        else:
            st.error(f"ไม่พบไฟล์เฉลย {MASTER_KEY_PATH} ในระบบ")

# --- 5. หน้าจอที่ 3: ระบบทำข้อสอบ (เลย์เอาต์หน้าจอเดียวจบ) ---
elif st.session_state.step == 'EXAM':
    cases = st.session_state.exam_cases
    idx = st.session_state.current_index
    total_cases = len(cases)
    
    if idx < total_cases:
        current_case = cases[idx]
        exam_id = current_case['Exam_ID']
        
        st.progress((idx) / total_cases)
        st.subheader(f"📋 ข้อที่ {idx + 1} / {total_cases} (รหัสเคส: {exam_id})")
        
        if st.session_state.case_start_time is None:
            st.session_state.case_start_time = time.time()
            
        set_folder = f"set_{st.session_state.current_set.lower()}"
        
        raw_img_path = os.path.join(ASSETS_DIR, set_folder, "raw_images", f"{exam_id}.png")
        if not os.path.exists(raw_img_path):
            raw_img_path = os.path.join(ASSETS_DIR, set_folder, "raw_images", f"{exam_id}.dcm")
            
        gradcam_img_path = os.path.join(ASSETS_DIR, set_folder, "gradcam_images", f"{exam_id}.png")

        main_col1, main_col2 = st.columns([2.8, 1.0])

        with main_col1:
            if st.session_state.ai_assisted:
                st.info("💡 รอบนี้มี AI assist ช่วยแปลผล (ภาพขวาคือ Grad-CAM)")
                sub_col1, sub_col2 = st.columns(2)
                with sub_col1:
                    if os.path.exists(raw_img_path):
                        st.image(raw_img_path, caption="ภาพเอกซเรย์ปกติ (Raw Image)", use_container_width=True)
                        # 🔍 [ปรับเพิ่มใหม่] ปุ่มกด Zoom ภาพดิบในรอบที่มี AI ช่วย
                        if st.button("🔍 ซูมขยายภาพดิบ (Zoom Image)", key=f"zoom_btn_ai_{exam_id}", use_container_width=True):
                            open_zoom_modal(raw_img_path)
                    else:
                        st.error(f"⚠️ ไม่พบภาพดิบ: {raw_img_path}")
                with sub_col2:
                    if os.path.exists(gradcam_img_path):
                        st.image(gradcam_img_path, caption="ผลวิเคราะห์โดย AI (Grad-CAM)", use_container_width=True)
                        # 📊 [ปรับเพิ่มใหม่] แสดงค่าประสิทธิภาพความแม่นยำของ Model ใต้รูป Grad-CAM
                        st.markdown("<p style='text-align: center; color: #4A90E2; font-size: 0.9rem; font-weight: 500; margin-top: 4px;'>เครื่องมือนี้มีค่า Accuracy = 74.31%, Sensitivity = 73.50%, Specificity = 74.82</p>", unsafe_allow_html=True)
                    else:
                        st.error(f"⚠️ ไม่พบภาพ Grad-CAM: {gradcam_img_path}")
            else:
                st.warning("🔒 รอบนี้ไม่มี AI assist ช่วยแปลผล (วินิจฉัยด้วยตนเอง)")
                if os.path.exists(raw_img_path):
                    st.image(raw_img_path, caption="ภาพเอกซเรย์ปกติ (Raw Image)", use_container_width=True)
                    # 🔍 [ปรับเพิ่มใหม่] ปุ่มกด Zoom ภาพดิบในรอบปกติ (วินิจฉัยด้วยตนเอง)
                    if st.button("🔍 ซูมขยายภาพดิบ (Zoom Image)", key=f"zoom_btn_normal_{exam_id}", use_container_width=True):
                        open_zoom_modal(raw_img_path)
                else:
                    st.error(f"⚠️ ไม่พบภาพ: {raw_img_path}")

        with main_col2:
            st.markdown("### 📋 ทำแบบประเมิน")
            st.write("---")
            
            decision_raw = st.radio(
                "🔍 ผลการอ่านฟิล์มของท่าน:", 
                ["ปกติ (Normal)", "ผิดปกติ (Abnormal)"], 
                index=0, 
                key=f"radio_{exam_id}"
            )
            
            decision_val = 1 if "ผิดปกติ" in decision_raw else 0
            
            st.write("")
            st.write("")
            
            if st.button("ยืนยันคำตอบ (Confirm) ➡️", type="primary", key=f"btn_{exam_id}", use_container_width=True):
                end_time = time.time()
                time_spent = end_time - st.session_state.case_start_time
                
                with st.spinner("กำลังส่งผลคำตอบ..."):
                    if save_interpretation_log_to_sheets(
                        doc_id=st.session_state.doc_id,
                        period=st.session_state.period,
                        img_set=st.session_state.current_set,
                        exam_id=exam_id,
                        ai_on=st.session_state.ai_assisted,
                        decision=decision_val,
                        time_spent=time_spent
                    ):
                        st.session_state.current_index += 1
                        st.session_state.case_start_time = None
                        st.rerun()
                        
    else:
        if st.session_state.period == 2:
            st.session_state.step = 'SURVEY'
        else:
            st.session_state.step = 'FINISHED'
        st.rerun()

# --- 6. หน้าจอที่ 4: ระบบบันทึกแบบประเมินความพึงพอใจ HSUS ---
elif st.session_state.step == 'SURVEY':
    st.title("📋 แบบสอบถามประเมินความสามารถในการใช้งานระบบ AI ช่วยคัดกรองโรคนิวโมโคนิโอสิส")
    st.subheader("(Healthcare Systems Usability Scale - HSUS Evaluation)")
    st.write("คำชี้แจง: โปรดทำเลือกคะแนนในหัวข้อที่ตรงกับความคิดเห็นของท่านมากที่สุด (5 = เห็นด้วยอย่างยิ่ง, 1 = ไม่เห็นด้วยอย่างยิ่ง)")
    st.write("---")
    
    hsus_questions = {
        "ด้านที่ 1: ประโยชน์ต่อความปลอดภัยและประสิทธิผลในการตัดสินใจ": [
            (1, "ระบบ AI ช่วยให้ฉันทำงานคัดกรองได้รวดเร็วและมีประสิทธิภาพมากขึ้น"),
            (2, "ระบบ AI ช่วยให้การส่งต่อข้อมูลหรือปรึกษาแพทย์ผู้เชี่ยวชาญทำได้ง่ายขึ้น"),
            (3, "ฉันสามารถดูแลกลุ่มเสี่ยง/ผู้ป่วยโรคนิวโมโคนิโอสิสได้ดีขึ้นเมื่อใช้ระบบนี้"),
            (4, "การตัดสินใจวินิจฉัยหรือระบุระยะของโรคทำได้ง่ายขึ้นเมื่อมีผลอ่านจาก AI ประกอบ"),
            (5, "ระบบ AI ช่วยปรับปรุงผลลัพธ์การคัดกรองผู้ป่วยให้แม่นยำขึ้น"),
            (6, "ระบบ AI ช่วยป้องกันข้อผิดพลาดในการอ่านฟิล์ม (Human Error)"),
            (7, "ระบบ AI แสดงผลสรุปความเสี่ยงหรือความผิดปกติของปอดได้อย่างชัดเจน")
        ],
        "ด้านที่ 2: การบูรณาการเข้ากับกระบวนการทำงาน": [
            (8, "ระบบ AI เข้ากันได้ดีกับขั้นตอนการตรวจคัดกรองปกติของฉัน (ไม่เพิ่มขั้นตอนยุ่งยาก)"),
            (9, "ข้อมูลผลการวิเคราะห์ที่แสดงบนหน้าจอเข้าใจได้ง่าย"),
            (10, "การใช้งานโปรแกรมในการเปิดดูภาพทำได้ง่ายและลื่นไหล"),
            (11, "ฉันสามารถจดจำวิธีใช้งานระบบนี้ได้ง่ายโดยไม่ต้องเรียนรู้ใหม่บ่อยๆ"),
            (12, "การจัดวางหน้าจอ (Interface) ทำให้มองเห็นจุดที่ AI สงสัย (Heatmap) ได้ชัดเจน"),
            (13, "ฉันสามารถมองหาผลการอ่านที่ต้องการได้อย่างรวดเร็ว")
        ],
        "ด้านที่ 3: ประสิทธิผลของงานและภาระงาน": [
            (14, "ระบบ AI ช่วยคัดกรองเบื้องต้น ทำให้ฉันจัดลำดับความสำคัญเคสที่มีความผิดปกติได้ดีขึ้น"),
            (15, "ฉันเข้าใจว่าระบบประมวลผลหรือให้คะแนนความเสี่ยงมาได้อย่างไร"),
            (16, "ผลการอ่านของ AI สอดคล้องกับมาตรฐานทางคลินิก (เช่น มาตรฐาน ILO)"),
            (17, "ระบบมีข้อมูลประกอบการตัดสินใจครบถ้วนตามที่ฉันต้องการ"),
            (18, "ฉันเชื่อมั่นในความน่าเชื่อถือของผลการคัดกรองที่ได้จากระบบ AI")
        ],
        "ด้านที่ 4: การควบคุมโดยผู้ใช้": [
            (19, "ระบบ AI ทำหน้าที่ 'สนับสนุนการตัดสินใจของฉัน' มากกว่าที่จะ 'บังคับให้เชื่อตาม'"),
            (20, "การแจ้งเตือนหรือการแสดงผลของ AI ไม่รบกวนสมาธิในการอ่านฟิล์มของฉัน")
        ]
    }
    
    ratings_output = {}
    options = [5, 4, 3, 2, 1]
    
    for section, qs in hsus_questions.items():
        st.markdown(f"#### 📊 {section}")
        for q_num, q_text in qs:
            ratings_output[f"Q{q_num}"] = st.radio(
                f"**ข้อที่ {q_num}:** {q_text}", 
                options, 
                index=1, 
                horizontal=True, 
                key=f"hsus_q_{q_num}"
            )
        st.write("---")
        
    st.markdown("#### 📝 ส่วนที่ 3: ความคิดเห็นเพิ่มเติม")
    
    # คำถามปลายเปิดข้อที่ 1
    st.markdown("**1. ในภาพรวม ท่านคิดว่า AI ระบบนี้ช่วย 'ลดภาระงาน' ในการคัดกรองโรคนิวโมโคนิโอสิสได้หรือไม่ และในขั้นตอนใดมากที่สุด?**")
    has_open_1 = st.radio("รูปแบบคำตอบข้อ 1:", ["ไม่มีข้อคิดเห็น (None)", "ต้องการพิมพ์แสดงความคิดเห็น..."], horizontal=True, key="has_open_1")
    if has_open_1 == "ต้องการพิมพ์แสดงความคิดเห็น...":
        text_1 = st.text_area("ระบุความคิดเห็นของท่าน:", placeholder="พิมพ์ความคิดเห็นที่นี่...", key="open_q_1").strip()
        open_1 = text_1 if text_1 else "ไม่มีข้อคิดเห็น"
    else:
        open_1 = "ไม่มีข้อคิดเห็น"
    st.write("")

    # คำถามปลายเปิดข้อที่ 2
    st.markdown("**2. ท่านพบปัญหาใดในการใช้งานที่ทำให้ 'เสียเวลา' หรือรู้สึกว่าเป็นภาระเพิ่มขึ้นหรือไม่?**")
    has_open_2 = st.radio("รูปแบบคำตอบข้อ 2:", ["ไม่มีข้อคิดเห็น (None)", "ต้องการพิมพ์แสดงความคิดเห็น..."], horizontal=True, key="has_open_2")
    if has_open_2 == "ต้องการพิมพ์แสดงความคิดเห็น...":
        text_2 = st.text_area("ระบุปัญหาที่ท่านพบ:", placeholder="พิมพ์ปัญหาที่นี่...", key="open_q_2").strip()
        open_2 = text_2 if text_2 else "ไม่มีข้อคิดเห็น"
    else:
        open_2 = "ไม่มีข้อคิดเห็น"
    st.write("")

    # คำถามปลายเปิดข้อที่ 3
    st.markdown("**3. ข้อเสนอแนะเพื่อปรับปรุงระบบให้เหมาะสมกับการทำงานจริงมากขึ้น**")
    has_open_3 = st.radio("รูปแบบคำตอบข้อ 3:", ["ไม่มีข้อคิดเห็น (None)", "ต้องการพิมพ์ระบุข้อเสนอแนะ..."], horizontal=True, key="has_open_3")
    if has_open_3 == "ต้องการพิมพ์ระบุข้อเสนอแนะ...":
        text_3 = st.text_area("ระบุข้อเสนอแนะของท่าน:", placeholder="พิมพ์ข้อเสนอแนะที่นี่...", key="open_q_3").strip()
        open_3 = text_3 if text_3 else "ไม่มีข้อคิดเห็น"
    else:
        open_3 = "ไม่มีข้อคิดเห็น"
        
    st.write("---")
    
    if st.button("ส่งแบบประเมินและเสร็จสิ้นกระบวนการวิจัย 📥", type="primary", use_container_width=True):
        open_answers = [open_1, open_2, open_3]
        with st.spinner("กำลังทำการส่งคะแนน HSUS เข้าคลาวด์..."):
            if save_hsus_responses_to_sheets(st.session_state.doc_id, ratings_output, open_answers):
                st.session_state.step = 'FINISHED'
                st.rerun()

# --- 7. หน้าจอสุดท้าย: เสร็จสิ้นการทดสอบ ---
elif st.session_state.step == 'FINISHED':
    st.title("🎉 การทดสอบเสร็จสมบูรณ์")
    st.write("---")
    st.balloons()
    
    if st.session_state.period == 2:
        st.success(f"ระบบคลาวด์ได้ทำการบันทึกผลการวินิจฉัย และผลประเมินความพึงพอใจ HSUS ของแพทย์รหัส {st.session_state.doc_id} เสร็จเรียบร้อยครบทุกกระบวนการวิจัยแล้วครับ ขอบพระคุณคุณหมอเป็นอย่างสูงครับ")
    else:
        st.success(f"ระบบคลาวด์ได้บันทึกผลการวินิจฉัยรอบที่ 1 ของแพทย์รหัส {st.session_state.doc_id} เรียบร้อยแล้วครับ เจอกันใหม่อีกครั้งหลังผ่าน Washout period ครับคุณหมอ")
    
    if st.button("กลับสู่หน้าหลักระบบ (Logout)"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.session_state.step = 'LOGIN'
        st.rerun()