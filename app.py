import os, platform, subprocess
from pathlib import Path
from datetime import datetime
import streamlit as st
import pandas as pd
import pymssql # SQL Server’a doğrudan bağlanmak için 
import requests # HTTP istekleri (POST, GET vb.) atmak için
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
# Streamlit içinde etkileşimli bir tablo/grid sunmak için
# AgGrid: tablonun kendisi
# GridOptionsBuilder: tablo ayarlarını oluşturmak
# GridUpdateMode: tablo güncelleme tetikleme modları

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

def send_file_by_email(report_name, file_path, to_email): # E-posta göndermek için
    try:
        payload = {
            "report_name": report_name,
            "file_path": file_path,
            "to_email": to_email
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

st.set_page_config(layout="wide", page_title="Rapor Paneli")
st.title("Rapor Paneli")

conn = pymssql.connect( # Docker üzerinde çalışan SQL Server’a bağlanır.
    server='localhost',
    port=1433,
    user='sa',
    password='Your!StrongPass123',
    database='report'
)

df = pd.read_sql( # Veritabanından SQL sorgusunu çalıştırır ve sonucu bir Pandas DataFrame’e (df) dönüştürür.
    """SELECT
    report_name,
    report_freq,
    last_exec_date
    FROM dbo.ReportDefinition""", 
    conn)

gb = GridOptionsBuilder.from_dataframe(df) # DataFrame’den bir grid ayarları (options) nesnesi oluşturur
gb.configure_selection(selection_mode="single", # sadece tek bir satır seçebilir
                       use_checkbox=True) # her satırın başı checkbox
grid_opts = gb.build() # GridOptionsBuilder ile oluşturulan grid ayarlarını kullanarak bir AgGrid bileşeni oluşturur.

resp = AgGrid(
    df,
    gridOptions=grid_opts,
    height=300,
    update_mode=GridUpdateMode.SELECTION_CHANGED, # kullanıcı satır seçtiğinde tekrar çalışır
    theme="alpine"
)

if "file_path" not in st.session_state:
    st.session_state.file_path = None

if "report_ready" not in st.session_state:
    st.session_state.report_ready = False

if "selected_row" not in st.session_state:
    st.session_state.selected_row = None

if "to_email" not in st.session_state:
    st.session_state.to_email = None

if "open_report" not in st.session_state:
    st.session_state.open_report = False

if "show_mail_button" not in st.session_state:
    st.session_state.show_mail_button = False

selected_data = resp.get("selected_data")

if (selected_data is None or len(selected_data) == 0) and st.session_state.show_mail_button is False :
    st.info("Lütfen bir satır seçin.")
    st.stop()
else:
    if st.session_state.show_mail_button is False:
        st.session_state.selected_row = selected_data.iloc[0] # Seçilen satırı session state'e kaydeder

        raw_date = st.session_state.selected_row["last_exec_date"]
        dt = datetime.fromisoformat(raw_date)
        last_exec_date = dt.strftime("%Y-%m-%d %H:%M:%S")

        st.write("Seçili Rapor:", st.session_state.selected_row["report_name"])
        st.write("Son Raporlanma tarihi:", last_exec_date)

        if st.session_state.selected_row["report_freq"] == "daily":
            st.write("Raporlanma Sıklığı: Günlük")
        elif st.session_state.selected_row["report_freq"] == "monthly":
            st.write("Raporlanma Sıklığı: Aylık")

        report_payload = {
            "report_name":    st.session_state.selected_row["report_name"],
            "period":         st.session_state.selected_row["report_freq"],
            "last_exec_date": last_exec_date
        }
    
if st.button(label="Raporu Tetikle") and st.session_state.show_mail_button is False:
    try:
        r1 = requests.post(
            "http://localhost:5678/webhook/trigger-job",
            json=report_payload,
            timeout=10
        )

        r1.raise_for_status()
        data1 = r1.json()

        st.session_state.file_path = data1.get("file_path")

        st.session_state.report_ready = True
    
    except Exception as e:
        st.error("Hata: " + str(e))

if st.session_state.get("report_ready") and st.session_state.file_path and Path(st.session_state.file_path).exists() and st.session_state.show_mail_button is False:
    # Dökumanı görüntüleme
    st.success("Rapor başarıyla oluşturuldu:")
    st.write(f"Dosya: `{st.session_state.file_path}`")

    if st.button(label="Dökümanı Görüntüle", 
              on_click=open_report_file, 
              args=(st.session_state.file_path,)):
        st.session_state.open_report = True

if st.session_state.get("report_ready") and st.session_state.file_path and Path(st.session_state.file_path).exists() or st.session_state.open_report:
    # E-posta gönderme 
    to_email = st.text_input("Lütfen e-posta adresinizi girin:")
        
    submit_email = st.button(label="Mail Gönder",
                                         on_click=send_file_by_email,
                                         args=(st.session_state.selected_row["report_name"], 
                                               st.session_state.file_path, 
                                               to_email,))
    
    st.session_state.show_mail_button = True

    if submit_email:  
        if to_email:
            st.session_state.show_mail_button = False
        else:
            st.warning("Lütfen geçerli bir e-posta adresi girin.")

                