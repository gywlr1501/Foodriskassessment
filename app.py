import streamlit as st
import psycopg2
from datetime import datetime
import pandas as pd
import plotly.express as px

# --- 0. DB 보안 연결 및 테이블 생성 ---
@st.cache_resource
def init_connection():
    return psycopg2.connect(
        host=st.secrets["supabase"]["host"],
        port=st.secrets["supabase"]["port"],
        dbname=st.secrets["supabase"]["dbname"],
        user=st.secrets["supabase"]["user"],
        password=st.secrets["supabase"]["password"],
        sslmode="require"  # 보안 연결 강제 설정
    )
def init_db():
    conn = init_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS issue_logs (
        issue_id SERIAL PRIMARY KEY,
        issue_title TEXT NOT NULL,
        issue_source TEXT,
        category TEXT,
        occurrence_time TIMESTAMP,
        recognition_time TIMESTAMP,
        time_gap TEXT,
        risk_level TEXT,
        status TEXT,
        action_taken TEXT,
        created_at TIMESTAMP,
        updated_at TIMESTAMP
    )
    """)
    conn.commit()
    cursor.close()

init_db()

def get_db_connection():
    return init_connection()
# --- 1. 웹 화면 상단 구성 ---
st.set_page_config(page_title="식품 리스크 관리", layout="wide")
st.title("🚨 식품 리스크 관리 대시보드")

conn = get_db_connection()
try:
    query = "SELECT * FROM issue_logs ORDER BY issue_id DESC"
    df = pd.read_sql_query(query, conn)
except Exception as e:
    st.error(f"데이터를 불러오는 중 문제가 발생했습니다: {e}")
    df = pd.DataFrame()

# --- 2. 탭 구성 ---
tab1, tab2, tab3, tab4 = st.tabs(["📝 신규 이슈 등록", "📋 리스크 목록 조회", "🛠️ 데이터 수정/삭제", "📊 통계 및 분석"])

# ==========================================
# 탭 1: 신규 이슈 등록
# ==========================================
with tab1:
    st.header("새로운 이슈 등록")
    with st.form("issue_form", clear_on_submit=True):
        issue_title = st.text_input("이슈명 (A사 샐러드 식중독균 검출 등)")
        issue_source = st.text_input("출처 (뉴스 링크, 식약처 공문 번호 등)")
        
        col1, col2 = st.columns(2)
        with col1:
            category = st.text_input("분류 (예: 잔류농약, 이물질 등)")
        with col2:
            risk_level = st.text_input("리스크 등급")
            
        status = st.text_input("대응 상태 (예: 확인 중, 1차 보고 완료 등)")
        
        st.write("⏱️ 타임라인 ")
        col3, col4 = st.columns(2)
        with col3:
            st.markdown("**[발생/보도 시점]**")
            occurrence_date = st.date_input("날짜 선택 (달력)")
            occurrence_time_str = st.text_input("시간 입력 (예: 14:00)", value="00:00")
            
        with col4:
            st.markdown("**[인지/접수 시점]**")
            recognition_date = st.date_input("날짜 선택 (달력)", datetime.today())
            current_time_str = datetime.now().strftime("%H:%M")
            recognition_time_str = st.text_input("접수 시간 (예: 15:30)", value=current_time_str)
            
        action_taken = st.text_area("대처 내용 (현재 조치사항)")
        
        submitted = st.form_submit_button("DB에 저장하기")
        
        if submitted:
            if not issue_title:
                st.error("이슈명은 필수 입력 사항입니다!")
            else:
                try:
                    occ_time_obj = datetime.strptime(occurrence_time_str.strip(), "%H:%M").time()
                    rec_time_obj = datetime.strptime(recognition_time_str.strip(), "%H:%M").time()
                    
                    occ_dt = datetime.combine(occurrence_date, occ_time_obj)
                    rec_dt = datetime.combine(recognition_date, rec_time_obj)
                    
                    # 초 단위까지 포함하도록 수정
                    occurrence_datetime = occ_dt.strftime("%Y-%m-%d %H:%M")
                    recognition_datetime = rec_dt.strftime("%Y-%m-%d %H:%M")
                    
                    gap = rec_dt - occ_dt
                    total_seconds = int(gap.total_seconds())
                    
                    if total_seconds < 0:
                        st.warning("인지 시점이 발생 시점보다 빠를 수 없습니다!")
                    else:
                        hours, remainder = divmod(total_seconds, 3600)
                        minutes, _ = divmod(remainder, 60)
                        time_gap = f"{hours}시간 {minutes}분" if hours > 0 else f"{minutes}분"
                        
                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                        
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        # sqlite3의 ? 대신 psycopg2의 %s 사용
                        cursor.execute('''
                            INSERT INTO issue_logs 
                            (issue_title, issue_source, category, occurrence_time, recognition_time, time_gap, risk_level, status, action_taken, created_at, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ''', (issue_title, issue_source, category, occurrence_datetime, recognition_datetime, time_gap, risk_level, status, action_taken, now_str, now_str))
                        
                        conn.commit()
                        st.success(f"✅ '{issue_title}' 이슈가 성공적으로 클라우드 DB에 저장되었습니다!")
                        st.rerun()
                        
                except ValueError:
                    st.error("시간 형식이 잘못되었습니다. 'HH:MM' 양식에 맞춰주세요.")

# ==========================================
# 탭 2: 리스크 목록 조회
# ==========================================
with tab2:
    st.header("📋 등록된 리스크 이슈 목록")
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.info("아직 등록된 이슈가 없습니다.")

# ==========================================
# 탭 3: 데이터 수정 및 삭제 (Audit 강화)
# ==========================================
with tab3:
    st.header("🛠️ 데이터 수정 및 삭제")
    if not df.empty:
        issue_ids = df['issue_id'].tolist()
        selected_id = st.selectbox("작업할 이슈의 ID(고유번호)를 선택하세요", issue_ids)
        current_data = df[df['issue_id'] == selected_id].iloc[0]
        
        st.markdown(f"### 📌 선택된 이슈: {current_data['issue_title']}")
        st.info("🔒 시간 기록은 데이터 객관성 유지를 위해 임의로 수정 불가.")
        
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.markdown(f"**🔹 발생 시점:** {current_data['occurrence_time']}")
            st.markdown(f"**🔹 인지 시점:** {current_data['recognition_time']} (소요: {current_data['time_gap']})")
        with col_t2:
            created_time = current_data.get('created_at', '기록 없음 (과거 데이터)')
            updated_time = current_data.get('updated_at', '기록 없음 (과거 데이터)')
            st.markdown(f"**🔸 시스템 최초 등록:** {created_time}")
            st.markdown(f"**🔸 최근 수정 기록:** {updated_time}")
        st.markdown("---")
        
        action = st.radio("어떤 작업을 진행하시겠습니까?", ["수정하기", "삭제하기"])
        
        if action == "삭제하기":
            if st.button("🚨 영구 삭제 확인", key="delete_btn"):
                conn = get_db_connection()
                cursor = conn.cursor()
                # 클라우드 DB의 SERIAL(Integer)에 맞춰서 정수형 변환 후 %s 사용
                cursor.execute("DELETE FROM issue_logs WHERE issue_id = %s", (int(selected_id),))
                conn.commit()
                st.success("데이터가 삭제되었습니다!")
                st.rerun()
                
        elif action == "수정하기":
            with st.form("update_form"):
                u_title = st.text_input("이슈명 수정", value=current_data['issue_title'])
                u_source = st.text_input("출처 수정", value=current_data['issue_source'] if pd.notna(current_data['issue_source']) else "")
                
                col_u1, col_u2 = st.columns(2)
                with col_u1:
                    u_category = st.text_input("분류 수정", value=current_data['category'] if pd.notna(current_data['category']) else "")
                with col_u2:
                    u_risk = st.text_input("리스크 등급 수정", value=current_data['risk_level'] if pd.notna(current_data['risk_level']) else "")
                    
                u_status = st.text_input("대응 상태 수정", value=current_data['status'] if pd.notna(current_data['status']) else "")
                current_action = current_data['action_taken'] if pd.notna(current_data['action_taken']) else ""
                u_action = st.text_area("대처 내용 수정", value=current_action)
                
                if st.form_submit_button("수정 내용 DB에 반영"):
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE issue_logs 
                        SET issue_title = %s, issue_source = %s, category = %s, risk_level = %s, status = %s, action_taken = %s, updated_at = %s
                        WHERE issue_id = %s
                    """, (u_title, u_source, u_category, u_risk, u_status, u_action, now_str, int(selected_id)))
                    conn.commit()
                    st.success("데이터가 성공적으로 수정되었으며, 수정 이력(시간)이 업데이트되었습니다!")
                    st.rerun()
    else:
        st.info("수정/삭제할 데이터가 없습니다.")

# ==========================================
# 탭 4: 통계 및 분석
# ==========================================
with tab4:
    st.header("📊 리스크 통계 대시보드")
    
    if not df.empty:
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.subheader("📌 분류별 이슈 발생 비율")
            category_counts = df['category'].value_counts().reset_index()
            category_counts.columns = ['분류', '건수']
            fig1 = px.pie(category_counts, names='분류', values='건수', hole=0.4)
            st.plotly_chart(fig1, use_container_width=True)
            
        with col_chart2:
            st.subheader("🚨 리스크 등급별 발생 건수")
            risk_counts = df['risk_level'].value_counts().reset_index()
            risk_counts.columns = ['리스크 등급', '건수']
            fig2 = px.bar(risk_counts, x='리스크 등급', y='건수', color='리스크 등급')
            st.plotly_chart(fig2, use_container_width=True)
            
        st.markdown("---")
        st.subheader("📈 일자별 리스크 발생 추이")
        df['date_only'] = pd.to_datetime(df['occurrence_time']).dt.date
        daily_counts = df.groupby('date_only').size().reset_index(name='건수')
        
        fig3 = px.line(daily_counts, x='date_only', y='건수', markers=True)
        fig3.update_xaxes(type='category') 
        st.plotly_chart(fig3, use_container_width=True)
        
    else:

        st.info("통계를 낼 데이터가 아직 없습니다. 이슈를 최소 1개 이상 등록해 주세요!")
