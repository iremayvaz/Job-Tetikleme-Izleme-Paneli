import streamlit as st
import requests
import pymssql
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from pathlib import Path
from datetime import datetime
import time

# Session state ile login durumunu takip edin
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None
# Session state ile selected_row durumunu takip edin
if "selected_row" not in st.session_state:
    st.session_state.selected_row = None
# Session state ile file_path durumunu takip edin
if "file_path" not in st.session_state:
    st.session_state.file_path = None
# Session state ile rapor durumunu takip edin
if "report_ready" not in st.session_state:
    st.session_state.report_ready = False
# Session state ile görüntülenme durumunu takip edin
if "viewed" not in st.session_state:
    st.session_state.viewed = False
# Session state ile indirilme durumunu takip edin
if "downloaded" not in st.session_state:
    st.session_state.downloaded = False

def get_connection(): # SQL Server’a doğrudan bağlanmak için
    return pymssql.connect( 
    server='localhost',
    port=1433,
    user='sa',
    password='Your!StrongPass123',
    database='report'
)

def fetch_report_definitions(): # Rapor tanımlarını çekmek için
    conn = get_connection()
    rep_def =  pd.read_sql( 
        """SELECT
        report_name,
        report_freq,
        last_exec_date
        FROM dbo.ReportDefinition""", 
        conn)
    conn.close()
    return rep_def

def fetch_report_execution_log(): # Rapor loglarını çekmek için
    conn = get_connection()
    rep_log = pd.read_sql( 
        """
        SELECT
        rep_def.report_name,
        rep_log.run_date,
        rep_log.run_status,
        rep_log.executed_by
        FROM dbo.ReportExecutionLog AS rep_log
        INNER JOIN dbo.ReportDefinition AS rep_def
            ON rep_log.report_id = rep_def.report_id
        ORDER BY rep_log.run_date DESC
        """, 
        conn)
    conn.close()
    return rep_log

def fetch_report_execution_log_by_name(report_name): # Rapor loglarını rapor adına göre çekmek için
    conn = get_connection()
    rep_log_by_name = pd.read_sql( 
        """
        SELECT
        rep_def.report_name,
        rep_log.run_date,
        rep_log.run_status,
        rep_log.executed_by,
        rep_log.file_path
        FROM dbo.ReportExecutionLog AS rep_log
        INNER JOIN dbo.ReportDefinition AS rep_def
            ON rep_log.report_id = rep_def.report_id
        WHERE rep_def.report_name = %s
        ORDER BY rep_log.run_date DESC
        """, 
        conn, params=(report_name,))
    conn.close()
    return rep_log_by_name

def fetch_latest_file_path(report_name):
    # sadece en son başarılı (run_status=1) satırı getir
    conn = get_connection()
    df = pd.read_sql(
        """
        SELECT 
        TOP 1 rep_log.file_path
        FROM dbo.ReportExecutionLog AS rep_log
        INNER JOIN dbo.ReportDefinition AS rep_def
            ON rep_log.report_id = rep_def.report_id
        WHERE rep_def.report_name = %s
          AND rep_log.run_status = 1
          AND rep_log.file_path IS NOT NULL
        ORDER BY rep_log.run_date DESC
        """,
        conn,
        params=(report_name,),
    )
    conn.close()
    return df["file_path"].iloc[0] if not df.empty else None

def do_login():
    st.subheader("Giriş Yap")

    email = st.text_input("E-posta", key="login_email")
    password = st.text_input("Şifre", type="password", key="login_password")
    
    if st.button("Giriş Yap"):
        payload = {"executed_by": email, 
                   "password": password}
        try:
            res = requests.post("http://localhost:5678/webhook/login", 
                                json=payload, timeout=10)
            res.raise_for_status()
            data = res.json()
            
            if data.get("canLogin") == "can":
                st.session_state.logged_in = True
                st.session_state.user = data["user"]
                st.success("Giriş başarılı! Hoş geldin, " + data["user"])
                time.sleep(0.5) # Giriş başarılı mesajını göstermek için kısa bir bekleme
                st.rerun()
            else:
                st.warning("Kullanıcı bulunamadı. Lütfen önce kayıt olun.")
        except Exception as e:
            st.error(f"Giriş hatası: {e}")

def do_register():
    st.subheader("Kayıt Ol")
    
    email = st.text_input("E-posta", key="reg_email")
    password = st.text_input("Şifre", type="password", key="reg_password")
    unvan = st.text_input("Unvan (isim/pozisyon)", key="reg_unvan")
    
    if st.button("Kayıt Ol"):
        payload = {"executed_by": email, 
                   "password": password, 
                   "position": unvan}
        try:
            res = requests.post("http://localhost:5678/webhook/register", 
                                json=payload, timeout=10)
            res.raise_for_status()
            data = res.json()
            
            if data.get("can") == "registered":
                st.success("Kayıt başarılı! Lütfen giriş yapın.")
            else:
                st.error("Kayıt başarısız: " + data.get("can", "already registered"))
        except Exception as e:
            st.error(f"Kayıt hatası: {e}")

def trigger_job():
    st.subheader("Job Tetikle")
    
    rep_def_df = fetch_report_definitions()
    
    gb = GridOptionsBuilder.from_dataframe(rep_def_df) # DataFrame’den bir grid ayarları (options) nesnesi oluşturur
    gb.configure_selection(selection_mode="single", # sadece tek bir satır seçebilir
                       use_checkbox=True) # her satırın başı checkbox
    grid_opts = gb.build() # GridOptionsBuilder ile oluşturulan grid ayarlarını kullanarak bir AgGrid bileşeni oluşturur.

    resp = AgGrid(
        rep_def_df,
        gridOptions=grid_opts,
        height=300,
        update_mode=GridUpdateMode.SELECTION_CHANGED, # kullanıcı satır seçtiğinde tekrar çalışır
        theme="alpine"
    )

    selected_data = resp.get("selected_data")
    
    if (selected_data is None or len(selected_data) == 0):
        st.info("Lütfen bir satır seçin.")
        st.stop()
    else:
        row = selected_data.iloc[0]
        st.session_state.selected_row = row

        raw_date = row.get("last_exec_date")
        dt = datetime.fromisoformat(raw_date)
        last_exec_date = dt.strftime("%Y-%m-%d %H:%M:%S")

        st.write("Seçili Rapor:", row["report_name"])
        st.write("Son Raporlanma tarihi:", last_exec_date)

        freq = row.get("report_freq", "")
        st.write("**Raporlanma Sıklığı:**", "Günlük" if freq=="daily" else "Aylık" if freq=="monthly" else freq)
        
        if st.button("Job Tetikle"):
            report_payload = {
            "report_name":    row["report_name"],
            "period":         row["report_freq"],
            "last_exec_date": last_exec_date,
            "executed_by":    st.session_state.user
            }
            
            try:
                res = requests.post("http://localhost:5678/webhook/trigger-job", 
                                    json=report_payload, timeout=10)
                res.raise_for_status()
                data = res.json()
            
                if data.get("file_path"):
                    st.session_state.file_path = data.get("file_path")
                    st.session_state.report_ready = True
                    st.success("Raporlama başarılı!")
                else:
                    st.error("Raporlama başarısız: " + st.session_state.selected_row["report_name"])
            except Exception as e:
                st.error(f"Raporlama hatası: {e}")
    

def download_file():
    st.subheader("Dökümanı İndir")

    if st.session_state.file_path and st.session_state.report_ready:
        file_path = Path(st.session_state.file_path)
        if file_path.exists():
            with open(file_path, "rb") as f:
                st.download_button(
                    label="Dökümanı İndir",
                    data=f,
                    file_name=file_path.name,
                    mime="application/octet-stream"
                )
            st.success("Rapor başarıyla indirildi!")
        else:
            st.error("Rapor dosyası bulunamadı.")
    else:
        st.info("Henüz bir rapor oluşturulmadı.") 

def open_report_file(payload): # Dökümanı görüntülemek için
    try:
        r = requests.post(
            "http://localhost:5678/webhook/open-report-file",
            json=payload,
            timeout=10
        )

        r.raise_for_status()
        data = r.json()

        st.success(f"Dosya konumu {data["status"]}.")
    except Exception as e:
        st.error("Dosya konumu görüntülenemedi. Hata: " + str(e))

def view_file():
    st.subheader("Dökümanı Görüntüle")

    if st.session_state.selected_row["report_name"]:
        file_path = fetch_latest_file_path(st.session_state.selected_row["report_name"])
        if file_path:
            if st.button(label="Dökümanı Görüntüle", 
              on_click=open_report_file, 
              args=(file_path,)):
                st.session_state.viewed = True

                
def see_log(report_name=None):
    st.subheader("Rapor Logları")

    #report_name = st.selectbox("Rapor Seçin", options=fetch_report_definitions()["report_name"].unique().tolist())
    
    if report_name:
        log_df = fetch_report_execution_log_by_name(report_name)
        if not log_df.empty:
            st.write(log_df)
        else:
            st.info("Bu rapor için henüz bir log bulunmamaktadır.")
    else:
        st.info("Lütfen bir rapor seçin.")

def report_panel():
    st.title("Rapor Paneli")
    
# Uygulama akışı
st.title("📊 Rapor Uygulaması")
if not st.session_state.logged_in:
    do_login()
    st.markdown("---")
    do_register()
else:
    report_panel()
    
    
    trigger_job()
    see_log(st.session_state.selected_row["report_name"] if st.session_state.selected_row is not None else None)
    download_file()
    view_file()
    
