import streamlit as st
import requests
import pymssql
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from pathlib import Path
from datetime import datetime
import time

st.set_page_config(
    page_title="Rapor Uygulaması",
    layout="wide",                
    initial_sidebar_state="auto"  
)

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
# Session state ile mail gönderilme durumunu takip edin
if "was_send" not in st.session_state:
    st.session_state.was_send = False

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
        rep_log.reporting_date,
        rep_log.run_time_seconds,
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
        rep_log.reporting_date,
        rep_log.run_time_seconds,
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

def fetch_latest_file_path(report_name): # En sonki başarılı rapor dosyasının yolunu çekmek için
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

def seconds_to_hhmmss(sec: int) -> str: # Veri tabanındaki run_time_seconds'ı saat ve dakikaya dönüştürmek için
    try:
        sec = int(sec)

        if sec <= 0: # sec is None or
            return "00:00:00"  # Eğer süre yoksa veya negatifse, 00:00:00 döndürür
        elif sec >= 3600: # Eğer süre 1 saatten fazlaysa
            h = sec // 3600 # 18432 / 3600 = 5 saat
            m = (sec % 3600) // 60 # 18432 % 3600 = 432 saniye, 432 // 60 = 7 dakika
            s = sec % 60 # 432 % 60 = 12 saniye
            return f"{h:02d}:{m:02d}:{s:02d}" # 05:07:12 formatında döndürür
        elif sec >= 60 and sec < 3600: # Eğer süre 1 dakikadan fazlaysa
            m = (sec % 3600) // 60 # 18432 % 3600 = 432 saniye, 432 // 60 = 7 dakika
            s = sec % 60 # 432 % 60 = 12 saniye
            return f"00:{m:02d}:{s:02d}" # 00:07:12 formatında döndürür
        else: # Eğer süre 1 dakikadan azsa
            return f"00:00:{sec:02d}" # 00:00:12 formatında döndürür
    
    except (TypeError, ValueError): # Eğer sec None veya geçersiz bir değer ise
        return "--"

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
            elif data.get("canLogin") == "wrong password":
                st.error( data["user"] + " için hatalı şifre. Lütfen tekrar deneyin.")
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
            
            if data.get("status") == "kaydedildi":
                st.success("Kayıt başarılı! Lütfen giriş yapın.")
            elif data.get("status") == "geçersiz":
                st.error("Lütfen geçerli bir e-posta adresi girin.")
            else:
                st.warning(email + data.get("status", "zaten kayıtlı"))
        except Exception as e:
            st.error(f"Kayıt hatası: {e}")

def trigger_job():
    rep_def_df = fetch_report_definitions()
    
    gb = GridOptionsBuilder.from_dataframe(rep_def_df) 
    gb.configure_column("report_name",    header_name="Job",        minWidth=150, maxWidth=200)
    gb.configure_column("report_freq",  header_name="Sıklık",        minWidth=100, maxWidth=120)
    gb.configure_column("last_exec_date", header_name="Son Çalıştırılma T.",   minWidth=200, maxWidth=250)

    gb.configure_selection(selection_mode="single", # sadece tek bir satır seçebilir
                           use_checkbox=True) # her satırın başı checkbox
    
    gb.configure_pagination(paginationAutoPageSize=True) # Sayfalama 
    grid_opts = gb.build()

    resp = AgGrid(
        rep_def_df,
        gridOptions=grid_opts,
        height=500,
        width="%100",
        update_mode=GridUpdateMode.SELECTION_CHANGED, # kullanıcı satır seçtiğinde tekrar çalışır
        theme="alpine"
    )

    selected_data = resp.get("selected_data")
    
    if (selected_data is None or len(selected_data) == 0): # Seçim yapılmadıysa
        st.info("Lütfen bir satır seçin.")
        st.stop()
    else: # Seçim yapıldıysa
        row = selected_data.iloc[0]
        st.session_state.selected_row = row

        raw_date = row.get("last_exec_date")
        dt = datetime.fromisoformat(raw_date)
        last_exec_date = dt.strftime("%Y-%m-%d %H:%M:%S")

        b1, b2 = st.columns([3, 1])

        with b1:
            st.write("Seçili Rapor:", row["report_name"])
            st.write("Son Raporlanma tarihi:", last_exec_date)

            freq = row.get("report_freq", "")
            st.write("**Raporlanma Sıklığı:**", "Günlük" if freq=="daily" else "Aylık" if freq=="monthly" else freq)
        
        with b2:
            if st.button(label="Job Tetikle", use_container_width=True):
                report_payload = {
                "report_name"   : row["report_name"],
                "period"        : row["report_freq"],
                "last_exec_date": last_exec_date,
                "executed_by"   : st.session_state.user
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
    if st.session_state.selected_row["report_name"]:
        file_path = fetch_latest_file_path(st.session_state.selected_row["report_name"])
        if file_path and Path(file_path).exists():
            with open(file_path, "rb") as f:
                if st.download_button(
                    label="Dökümanı İndir",
                    data=f,
                    file_name=Path(file_path).name,
                    mime="application/octet-stream",
                    use_container_width=True
                ):
                    st.session_state.downloaded = True
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
   if st.session_state.selected_row["report_name"]:
        file_path = fetch_latest_file_path(st.session_state.selected_row["report_name"])
        if file_path:
            if st.button(label="Dökümanı Görüntüle", 
                         on_click=open_report_file, 
                         args=(file_path,),
                         use_container_width=True):
                st.session_state.viewed = True


def see_log(report_name=None):
    log_df = fetch_report_execution_log_by_name(report_name)

    if log_df.empty: # Log kaydı yoksa
        st.info("Bu rapor için henüz bir log bulunmamaktadır.")
        return
    
    #  Reporting_date kolonu sonradan eklendiği için
    #  NaT'leri boş string yapar
    log_df["reporting_date"] = (
        log_df["reporting_date"]
          .dt.strftime("%d/%m/%Y %H:%M:%S")
          .fillna("--")                        
    ) 

    # Okunabilirlik için süreyi
    # hh:mm:ss formatına çevirir
    log_df["run_time_seconds"] = log_df["run_time_seconds"].apply(seconds_to_hhmmss)

    gb = GridOptionsBuilder.from_dataframe(log_df)

    gb.configure_column("report_name",      header_name="Job",          minWidth=100, maxWidth=250)
    gb.configure_column("run_date",         header_name="Başl. T.",     minWidth=150, maxWidth=170)
    gb.configure_column("reporting_date",   header_name="Bitiş T.",     minWidth=150, maxWidth=170)
    gb.configure_column("run_time_seconds", header_name="Süre",         minWidth=100, maxWidth=100)
    gb.configure_column("run_status",       header_name="D.",           minWidth=70,  maxWidth=80)
    gb.configure_column("executed_by",      header_name="Çalıştıran",   minWidth=240, maxWidth=250)
    gb.configure_column("file_path",        header_name="Dosya Yolu",   minWidth=400, maxWidth=600)
    
    gb.configure_pagination(paginationAutoPageSize=True)
    grid_options = gb.build()

    AgGrid(
        log_df,
        gridOptions=grid_options,
        theme="alpine",
        height=685,
        width="%100",
        fit_columns_on_grid_load=True,
        enable_enterprise_modules=False,
        update_mode=GridUpdateMode.NO_UPDATE,
    )

def send_file_by_email(report_name, file_path, to_email): # E-posta göndermek için
    try:
        payload = {
            "report_name": report_name,
            "file_path"  : file_path,
            "to_email"   : to_email
        }
        
        r = requests.post(
            "http://localhost:5678/webhook/send-file-by-email",
            json=payload,
            timeout=10
        )

        r.raise_for_status()
        data = r.json()

        if data["status"] == "gönderildi":
            st.success(f"Dosya {to_email}'e {data["status"]}.")
        elif data["status"] == "hatalı":
            st.error(f"{to_email}   .")
    except Exception as e:
        st.error("Mail gönderilemedi. Hata: " + str(e))

def send_mail():
    if st.session_state.selected_row["report_name"]:
        file_path = fetch_latest_file_path(st.session_state.selected_row["report_name"])
        if file_path:
            if st.button(label="E-postayı Gönder",
                         on_click=send_file_by_email,
                         args=(st.session_state.selected_row["report_name"], 
                               file_path, 
                               st.session_state.user,),
                         use_container_width=True):
                st.session_state.was_send = True
            
        else:
            st.error("Rapor dosyası bulunamadı.")
    else:
        st.info("Henüz bir rapor oluşturulmadı.")

def report_panel(): # Üst panel
    col1, col2 = st.columns([8, 1])
    with col1:
        st.title("Rapor Paneli")
    with col2:
        st.markdown("Kullanıcı : " + (st.session_state.user if st.session_state.logged_in else "Giriş Yapmadı"))

# Uygulama akışı
report_panel()  
st.markdown("---")

# Sayfayı iki eşit sütuna bölüyoruz
col1, col2 = st.columns([1, 1])

if not st.session_state.logged_in: # Kullanıcı giriş yapmadıysa
    with col1: # sayfanın solu (Kullanıcı kayıt olma)
        do_register()
    with col2: # sayfanın sağı (Kullanıcı giriş yapma)
        do_login()
else: # Kullanıcı giriş yaptıysa   
    # Sayfa bölünmesini güncelliyoruz
    col1, col2 = st.columns([2, 5])

    with col1: # sayfanın solu
        trigger_job()
        # sayfanın solundaki rapor tablosunun altını 3'e bölüyoruz
        # okunabilirlik için
        b1, b2, b3 = st.columns(3)
        with b1: # Dökümanı indirme
            download_file()
        with b2: # Dökümanı görüntüleme
            view_file()
        with b3: # E-posta gönderme
            send_mail()
    
    with col2: # sayfanın sağı (Seçilen Job'ın loglarını görüntüleme)
        see_log(st.session_state.selected_row["report_name"] if st.session_state.selected_row is not None else None)