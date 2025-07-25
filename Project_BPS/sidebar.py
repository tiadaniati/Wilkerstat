import pandas as pd
import streamlit as st
from streamlit_option_menu import option_menu
import os
import warnings
import base64
warnings.filterwarnings("ignore")

#=========================================================================
#background dan sidebar

home_page = st.Page("home.py",title="Home", icon="🏠", default=True)
kota_banjar = st.Page("views/kota_banjar.py",title="Kota Banjar", icon="🌳")

chatbot_page = st.Page("chatbot.py",icon="👨‍🏫",title="Chatbot")
semua_lokasi = {
    "Kota Banjar": kota_banjar
}
query = st.sidebar.text_input("Cari Wilayah:","")
filter_lokasi = {k:v for k,v in semua_lokasi.items() if query.lower() in k.lower()}
lokasi_ditampilkan = list(filter_lokasi.values()) if query else list(semua_lokasi.values())
pg = st.navigation(
    {
        "Main Menu": [home_page,chatbot_page],
        "Lokasi Wilayah": lokasi_ditampilkan
    }
)
#=========================================================================

#=========================================================================
#Footnote sidebar
st.logo(r"Project_BPS/asset/logo_bps.png")
st.sidebar.image(r"Project_BPS/asset/wilkerstat3fix.png")
st.sidebar.text("© 2025")
pg.run()
#=========================================================================








