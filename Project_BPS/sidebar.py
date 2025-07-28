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
kab_bogor = st.Page("views/kab_bogor.py",title="Kabupaten Bogor", icon="🌲")
kab_sukabumi = st.Page("views/kab_sukabumi.py",title="Kabupaten Sukabumi", icon="🏞")
kab_cianjur = st.Page("views/kab_cianjur.py",title="Kabupaten Cianjur", icon="🌋")
kab_bandung = st.Page("views/kab_bandung.py",title="Kabupaten Bandung", icon="🏙")
kab_garut = st.Page("views/kab_garut.py",title="Kabupaten Garut", icon="🍃")
kab_tasikmalaya = st.Page("views/kab_tasikmalaya.py",title="Kabupaten Tasikmalaya", icon="🌤")
kab_ciamis = st.Page("views/kab_ciamis.py",title="Kabupaten Ciamis", icon="🌾")
kab_kuningan = st.Page("views/kab_kuningan.py",title="Kabupaten Kuningan", icon="⛰")
kab_cirebon = st.Page("views/kab_cirebon.py",title="Kabupaten Cirebon", icon="🏯")
kab_majalengka = st.Page("views/kab_majalengka.py",title="Kabupaten Majalengka", icon="🌻")
kab_sumedang = st.Page("views/kab_sumedang.py",title="Kabupaten Sumedang", icon="🏔")
kab_indramayu = st.Page("views/kab_indramayu.py",title="Kabupaten Indramayu", icon="🌅")
kab_subang = st.Page("views/kab_subang.py",title="Kabupaten Subang", icon="🌽")
kab_purwakarta = st.Page("views/kab_purwakarta.py",title="Kabupaten Purwakarta", icon="🚞")
kab_karawang = st.Page("views/kab_karawang.py",title="Kabupaten Karawang", icon="🏭")
kab_bekasi = st.Page("views/kab_bekasi.py",title="Kabupaten Bekasi", icon="🏘")
kab_bandungbarat = st.Page("views/kab_bandungbarat.py",title="Kabupaten Bandung Barat", icon="🛤")
kota_bogor = st.Page("views/kota_bogor.py",title="Kota Bogor", icon="🏞")
kota_sukabumi = st.Page("views/kota_sukabumi.py",title="Kota Sukabumi", icon="🏔")
kota_bandung = st.Page("views/kota_bandung.py",title="Kota Bandung", icon="🎓")
kota_bekasi = st.Page("views/kota_bekasi.py",title="Kota Bekasi", icon="🏢")
kota_depok = st.Page("views/kota_depok.py",title="Kota Depok", icon="🌆")
kota_tasikmalaya = st.Page("views/kota_tasikmalaya.py",title="Kota Tasikmalaya", icon="🌇")


chatbot_page = st.Page("chatbot.py",icon="👨‍🏫",title="Chatbot")
semua_lokasi = {
    "Kota Banjar": kota_banjar,
    "Kabupaten Bandung": kab_bandung,
    "Kabupaten Ciamis": kab_ciamis
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








