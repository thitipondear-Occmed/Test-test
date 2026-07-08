import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import time
import os
from datetime import datetime

# ==============================================================================
# 🎯 [ปรับเพิ่ม] ตั้งค่าคอนฟิกหน้าจอให้แผ่กว้างเต็มจอ 100% (Wide Mode)
# ==============================================================================
st.set_page_config(
    page_title="Pneumoconiosis Interpretation Record",
    page_icon="📝",
    layout="wide"  # 👈 ตัวเปิดสวิตช์ให้ภาพและปุ่มกดแผ่เต็มหน้าจอคอมพิวเตอร์ครับคุณหมอ
)

# --- การตั้งค่าคอนฟิกและพาธข้อมูล ---
MASTER_KEY_PATH = 'master_key_crossover.csv'  # ไฟล์ Master Key
ASSETS_DIR = 'streamlit_assets'  # โฟลเดอร์เก็บไฟล์ภาพ

# --- 1. ฟังก์ชันเชื่อมต่อและบันทึกข้อมูลลง Google Sheets ---
@st.cache_resource
def get_gspread_client():
    # ดึงค่าเปิดสิทธิ์การใช้งานจาก st.secrets ของ Streamlit Cloud
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
        
        # เพิ่มข้อมูล exp_years เข้าไปในแถวข้อมูลที่จะบันทึกลงคลาวด์
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

# --- 2. ตั้งค่าการจัดการ State ของหน้าจอ Streamlit ---
if 'step' not in st.session_state:
    st.session_state.step = 'LOGIN'
if 'current_index' not in st.session_state:
    st.session_state.current_index = 0
if 'case_start_time' not in st.session_state:
    st.session_state.case_start_time = None

# --- 3. หน้าจอที่ 1: ลงทะเบียนประวัติแพทย์ (Demographic Information) ---
if st.session_state.step == 'LOGIN':
    st.title("📝 แบบบันทึกผลการอ่านภาพถ่ายรังสีทรวงอก")
    st.subheader("(Chest X-ray Interpretation Record Form)")
    st.write("---")
    
    st.markdown("### ข้อมูลทั่วไป (Demographic Information)")
    doc_id = st.text_input("รหัสแพทย์ผู้ทดสอบ (Doctor ID):", placeholder="เช่น Doc_01").strip()
    
    specialty = st.radio("1. วิชาชีพ/ตำแหน่งปัจจุบัน:", ["แพทย์ทั่วไป", "แพทย์ประจำบ้านอาชีวเวชศาสตร์", "แพทย์อาชีวเวชศาสตร์"])
    training = st.radio("2. หลักสูตรที่ผ่านการอบรมการแปลผลฟิล์มในมาตรฐาน ILO:", ["ไม่เคยอบรม", "อบรม ILO ระยะสั้น 3 วัน", "AIR Pneumo"])
    
    # [ปรับเพิ่ม] ช่องกรอกตัวเลขประสบการณ์หลังผ่านการอบรม
    exp_years = st.number_input(
        "3. มีประสบการณ์หลังการอบรมคัดกรองโรคปอดฝุ่นทรายกี่ปี (ปี):", 
        min_value=0, 
        max_value=50, 
        value=0, 
        step=1
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
            
            # ส่งข้อมูลไปบันทึกพร้อมค่าประสบการณ์ปี
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
            
            # ตรรกะการสลับกลุ่มและเครื่องมือช่วย (Crossover Logic Matrix)
            if st.session_state.group == "กลุ่มที่ 1":
                target_set = 'A' if st.session_state.period == 1 else 'B'
                ai_assisted = False if st.session_state.period == 1 else True
            else: # กลุ่มที่ 2
                target_set = 'B' if st.session_state.period == 1 else 'A'
                ai_assisted = True if st.session_state.period == 1 else False
            
            df_exam = df_master[df_master['Assigned_Set'] == target_set].sort_values(by='Exam_ID').reset_index(drop=True)
            
            st.session_state.exam_cases = df_exam.to_dict(orient='records')
            st.session_state.current_set = target_set
            st.session_state.ai_assisted = ai_assisted
            st.session_state.step = 'EXAM'
            st.session_state.current_index = 0
            st.session_state.case_start_time = time.time()  # สตาร์ทเวลาข้อแรก
            st.rerun()
        else:
            st.error(f"ไม่พบไฟล์เฉลย {MASTER_KEY_PATH} ในระบบ")

# --- 5. หน้าจอที่ 3: ระบบทำข้อสอบ (เลย์เอาต์หน้าจอเดียวจบ ไม่ต้องเลื่อนเมาส์) ---
elif st.session_state.step == 'EXAM':
    cases = st.session_state.exam_cases
    idx = st.session_state.current_index
    total_cases = len(cases)
    
    if idx < total_cases:
        current_case = cases[idx]
        exam_id = current_case['Exam_ID']
        
        # แสดงแถบความก้าวหน้าด้านบนสุดของจอ
        st.progress((idx) / total_cases)
        st.subheader(f"📋 ข้อที่ {idx + 1} / {total_cases} (รหัสเคส: {exam_id})")
        
        if st.session_state.case_start_time is None:
            st.session_state.case_start_time = time.time()
            
        set_folder = f"set_{st.session_state.current_set.lower()}"
        
        # เตรียมพาธรูปภาพ
        raw_img_path = os.path.join(ASSETS_DIR, set_folder, "raw_images", f"{exam_id}.png")
        if not os.path.exists(raw_img_path):
            raw_img_path = os.path.join(ASSETS_DIR, set_folder, "raw_images", f"{exam_id}.dcm")
            
        gradcam_img_path = os.path.join(ASSETS_DIR, set_folder, "gradcam_images", f"{exam_id}.png")

        # 🛠️ [จุดเปลี่ยนสำคัญ] แบ่งจอหลักเป็น ซ้าย (กว้าง 2.8 ส่วน) และ ขวา (กว้าง 1.0 ส่วน)
        main_col1, main_col2 = st.columns([2.8, 1.0])

        # 🏞️ ฝั่งซ้าย: สำหรับแสดงรูปภาพอย่างเดียว
        with main_col1:
            if st.session_state.ai_assisted:
                st.info("💡 รอบนี้มี AI assist ช่วยแปลผล (ภาพขวาคือ Grad-CAM)")
                # แบ่งฝั่งซ้ายย่อยออกเป็น 2 คอลัมน์เพื่อวาง Raw คู่กับ Grad-cam
                sub_col1, sub_col2 = st.columns(2)
                with sub_col1:
                    if os.path.exists(raw_img_path):
                        st.image(raw_img_path, caption="ภาพเอกซเรย์ปกติ (Raw Image)", use_container_width=True)
                    else:
                        st.error(f"⚠️ ไม่พบภาพดิบ: {raw_img_path}")
                with sub_col2:
                    if os.path.exists(gradcam_img_path):
                        st.image(gradcam_img_path, caption="ผลวิเคราะห์โดย AI (Grad-CAM)", use_container_width=True)
                    else:
                        st.error(f"⚠️ ไม่พบภาพ Grad-CAM: {gradcam_img_path}")
            else:
                st.warning("🔒 รอบนี้ไม่มี AI assist ช่วยแปลผล (วินิจฉัยด้วยตนเอง)")
                if os.path.exists(raw_img_path):
                    # แสดงภาพดิบเดี่ยวๆ ขนาดใหญ่เต็มพื้นที่ฝั่งซ้าย
                    st.image(raw_img_path, caption="ภาพเอกซเรย์ปกติ (Raw Image)", use_container_width=True)
                else:
                    st.error(f"⚠️ ไม่พบภาพ: {raw_img_path}")

        # 📥 ฝั่งขวา: กล่องควบคุมการตอบคำถาม (Control Panel) อยู่ระดับเดียวกับรูป ไม่ต้องเลื่อนจอลงมา
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
            
            st.write("") # เพิ่มช่องว่างเล็กน้อย
            st.write("")
            
            # ปุ่มยืนยันปรับให้กว้างเต็มคอลัมน์ขวาเพื่อกดง่ายขึ้น
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
                        st.session_state.case_start_time = None  # ล้างเวลาเพื่อเริ่มข้อถัดไป
                        st.rerun()
                        
    else:
        st.session_state.step = 'FINISHED'
        st.rerun()

# --- 6. หน้าจอสุดท้าย: เสร็จสิ้นการทดสอบ ---
elif st.session_state.step == 'FINISHED':
    st.title("🎉 การทดสอบเสร็จสมบูรณ์")
    st.write("---")
    st.balloons()
    st.success(f"ระบบคลาวด์ได้บันทึกผลการวินิจฉัยและเวลาความเร็วของแพทย์รหัส {st.session_state.doc_id} เรียบร้อยแล้วครับคุณหมอ")
    
    st.markdown("""
    ### 📝 ขั้นตอนสุดท้าย
    ขอความกรุณาคุณหมอคลิกตอบแบบสอบถามความพึงพอใจต่อบริบททางคลินิกผ่านระบบ **Healthcare System Usability Scale (HSUS)** ตามลิงก์ที่คุณหมอผู้ทำวิจัยแนบไว้ให้ด้านล่างนี้ได้เลยครับ ขอบพระคุณมากครับ
    """)
    
    if st.button("กลับสู่หน้าหลักระบบ (Logout)"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.session_state.step = 'LOGIN'
        st.rerun()