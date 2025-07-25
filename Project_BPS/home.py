import pandas as pd
import streamlit as st
from streamlit_option_menu import option_menu
import os
import warnings
import folium
from streamlit_folium import folium_static
import numpy as np
import json
import geopandas as gpd
import random
import matplotlib.pyplot as plt
import plotly.express as px
import base64
from PIL import Image
warnings.filterwarnings("ignore")

#=========================================================================
#Header
st.set_page_config(page_title="Monitoring Wilkerstat SE", page_icon=":bar_chart:", layout="wide")
st.markdown('<style>div.block-container{padding-left:5rem; padding-top:5rem;}<style>', unsafe_allow_html=True)
image = Image.open(r"/Users/jibrilnikki/Documents/Code/Project_BPS/asset/orangfix.png")
# Buat dua kolom: satu untuk gambar, satu untuk teks
col1, col2 = st.columns([0.5, 4])  # Rasio bisa diubah sesuai kebutuhan

with col1:
    st.image(image, width=200)  # Atur lebar sesuai tampilan yang kamu inginkan

with col2:
    st.title("Monitoring Wilkerstat Sensus Ekonomi Jawa Barat 2026")
#=========================================================================
os.chdir("/Users/jibrilnikki/Documents/Code/Project_BPS")
df = pd.read_csv("/Users/jibrilnikki/Documents/Code/Project_BPS/dataset/data_provinsi.csv")
#=========================================================================
#Visualisasi
df_prov = pd.read_csv('/Users/jibrilnikki/Documents/Code/Project_BPS/dataset/data_provinsi.csv')
def metric_card(title, value):
    return f"""
    <div style="
        background-color: #E8B991;
        padding: 10px;
        border-radius: 20px;
        text-align: center;
        border: 0.5px solid #eee;
    ">
        <div style="font-weight: bold; font-size: 16px; color: black">{title}</div>
        <div style="font-size: 32px; font-weight: 900; color: black;">{value}</div>
    </div>
    """

col1,col2,col3 = st.columns(3)

with col1:
    st.markdown(metric_card("Jumlah Kabupaten/Kota", df_prov['nama_kotakab'].nunique()), unsafe_allow_html=True)
with col2:
    st.markdown(metric_card("Jumlah Kecamatan", df_prov['jumlah_kec'].sum()), unsafe_allow_html=True)
with col3:
    st.markdown(metric_card("Jumlah Desa", df_prov['jumlah_desa'].sum()), unsafe_allow_html=True)
    
#=========================================================================
#Map dan legenda
st.header("Map Wilayah")
map1,map2 = st.columns([5,2])
kanan = map2
kiri = map1 
#legenda
with kanan:
    choice = ['Jumlah Kabupaten/Kota','Jumlah Kecamatan','Jumlah Desa']
    choice_selected = st.selectbox("",choice)
if choice_selected == 'Jumlah Kecamatan':
    geojson_file = '/Users/jibrilnikki/Documents/Code/Project_BPS/Geolocation/kecamatan.geojson'
    key_on = 'KECNO'
    popup_fields = ['KECAMATAN']
elif choice_selected == 'Jumlah Desa':
    geojson_file = '/Users/jibrilnikki/Documents/Code/Project_BPS/Geolocation/desa.geojson'
    key_on = 'DESANO'   
    popup_fields = ['DESA']
elif choice_selected == 'Jumlah Kabupaten/Kota':
    geojson_file = '/Users/jibrilnikki/Documents/Code/Project_BPS/Geolocation/kabupaten.geojson'
    key_on = 'KABKOTNO'
    popup_fields = ['KABKOT']
    
#map
with kiri:
    gdf = gpd.read_file(geojson_file)
    def generate_random_color():
        return "#{:06x}".format(random.randint(0, 0xFFFFFF))
    unique_keys = gdf[key_on].unique()
    color_dict = {key: generate_random_color() for key in unique_keys}

    selected_region = st.selectbox("Pilih wilayah", gdf[popup_fields[0]].unique())
    selected_geom = gdf[gdf[popup_fields[0]] == selected_region].geometry
    centroid = selected_geom.centroid.values[0]
    map_center = [centroid.y, centroid.x]
    zoom_lvl = 10  

    m = folium.Map(location=map_center, zoom_start=zoom_lvl, tiles='cartoDB positron')
    for _, row in gdf.iterrows():
        color = color_dict[row[key_on]]
        gj = folium.GeoJson(
            data=row.geometry.__geo_interface__,
            style_function=lambda x, color=color: {
                'fillColor': color,
                'color': 'black',
                'weight': 0.5,
                'fillOpacity': 0.8
            },
            tooltip=folium.Tooltip(row[popup_fields[0]])
        )
        gj.add_to(m)
    highlight_row = gdf[gdf[popup_fields[0]] == selected_region].iloc[0]
    highlight_geojson = folium.GeoJson(
        data=highlight_row.geometry.__geo_interface__,
        style_function=lambda x: {
            'fillColor': 'none',
            'color': 'red',
            'weight': 5,
            'fillOpacity': 0,
            'dashArray': '5, 5'
        },
        tooltip=folium.Tooltip(f"<b>{selected_region}</b>")
    )
    highlight_geojson.add_to(m)
    folium_static(m, width=1300, height=650)

with kanan:
    legend_data = pd.DataFrame({
        'Wilayah': [row[popup_fields[0]] for _, row in gdf.iterrows()],
        'Color': [color_dict[row[key_on]] for _, row in gdf.iterrows()]
    }).drop_duplicates()

    st.markdown("### Legenda Wilayah")

    legend_html = """
    <div style='max-height: 400px; overflow-y: auto; border: 1px solid #ddd; padding: 10px;'>
    """

    for _, row in legend_data.iterrows():
        legend_html += (
            f"<div style='display: flex; align-items: center; margin-bottom: 5px;'>"
            f"<div style='width: 20px; height: 20px; background-color:{row['Color']}; "
            f"margin-right:10px; border:1px solid #000;'></div>"
            f"<span>{row['Wilayah']}</span>"
            f"</div>"
        )

    legend_html += "</div>"

    st.markdown(legend_html, unsafe_allow_html=True)
#=========================================================================

#=========================================================================
#SQL
import pandas as pd
from sqlalchemy import create_engine

# Ganti sesuai info login MySQL kamu
user = 'root'
password = 'Mandala38'
host = 'localhost'
database = 'wilkerstat'

# Buat koneksi ke database
engine = create_engine(f'mysql+mysqlconnector://{user}:{password}@{host}/{database}')

# Baca file CSV
df = pd.read_csv(r"/Users/jibrilnikki/Documents/Code/Project_BPS/dataset/data_provinsi.csv", dtype={
    'kode_kotakab': str,
    'nama_kotakab': str,
    'jumlah_kec': int,
    'jumlah_desa': int
})
print(df[['kode_kotakab', 'nama_kotakab', 'jumlah_kec','jumlah_desa']].head())

# Kirim ke tabel di MySQL
from sqlalchemy import create_engine, types as sql_types

# Buat engine
engine = create_engine("mysql+mysqlconnector://root:Mandala38@localhost/wilkerstat")

# Upload data ke MySQL, atur tipe agar tidak hilang 0 depan
df.to_sql("data_provinsi", con=engine, if_exists="replace", index=False, dtype={
    'kode_kotakab': sql_types.VARCHAR(100),
    'nama_kotakab': sql_types.VARCHAR(100),
    'jumlah_kec': sql_types.INT,
    'jumlah_desa': sql_types.INT
})

print("Data berhasil diunggah ke MySQL.")


import mysql.connector

# Koneksi ke MySQL
def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Mandala38",
        database="wilkerstat"
    )

st.title("Database Provinsi Jawa Barat")

conn = get_connection()
cursor = conn.cursor(dictionary=True)

rename_mapping = {
    'kode_kotakab': 'Kode Kabupaten/Kota', 
    'nama_kotakab': 'Nama Kabupaten/Kota', 
    'jumlah_kec': 'Jumlah Kecamatan', 
    'jumlah_desa': 'Jumlah Desa' 
}

df_display = df.rename(columns=rename_mapping)

df = df.rename(columns=rename_mapping)

# Ambil data dari MySQL
cursor.execute("SELECT * FROM data_provinsi")
rows = cursor.fetchall()

#st.subheader("🔍 Filter Data")

filter_columns = ['Kode Kabupaten/Kota', 'Nama Kabupaten/Kota', 'Jumlah Kecamatan', 'Jumlah Desa']
cols = st.columns(len(filter_columns))  

filters = {}

for i, col in enumerate(filter_columns):
    if col in df.columns:
        options = ['Semua'] + sorted(df[col].dropna().unique())
        selected = cols[i].selectbox(col, options, key=f"filter_{col}")
        if selected != 'Semua':
            filters[col] = selected

filtered_df = df.copy()
for col, val in filters.items():
    filtered_df = filtered_df[filtered_df[col] == val]

st.dataframe(filtered_df)
