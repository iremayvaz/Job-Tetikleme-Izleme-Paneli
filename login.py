import streamlit as st
import requests
import pymssql
import pandas as pd

conn = pymssql.connect( # Docker üzerinde çalışan SQL Server’a bağlanır.
    server='localhost',
    port=1433,
    user='sa',
    password='Your!StrongPass123',
    database='report'
)

# Session state ile login durumunu takip edin
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None

def do_login():
    st.subheader("Giriş Yap")
    email = st.text_input("E-posta", key="login_email")
    password = st.text_input("Şifre", type="password", key="login_password")
    if st.button("Giriş Yap"):
        payload = {"executed_by": email, "password": password}
        try:
            res = requests.post("http://localhost:5678/webhook/login", json=payload, timeout=10)
            res.raise_for_status()
            data = res.json()
            if data.get("canLogin") == "can":
                st.session_state.logged_in = True
                st.session_state.user = data["user"]
                st.success("Giriş başarılı! Hoş geldin, " + data["user"])
                st.write("Streamlit version:", st.__version__)

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
        payload = {"executed_by": email, "password": password, "position": unvan}
        try:
            res = requests.post("http://localhost:5678/webhook/register", json=payload, timeout=10)
            res.raise_for_status()
            data = res.json()
            if data.get("can"):
                st.success("Kayıt başarılı! Lütfen giriş yapın.")
            else:
                st.error("Kayıt başarısız: " + data.get("can", "already registered"))
        except Exception as e:
            st.error(f"Kayıt hatası: {e}")

def report_panel():
    st.title("Rapor Paneli")
    # … buraya rapor paneli bileşenlerinizi ekleyin …

# Uygulama akışı
st.title("📊 Rapor Uygulaması")
if not st.session_state.logged_in:
    do_login()
    st.markdown("---")
    do_register()
else:
    report_panel()
