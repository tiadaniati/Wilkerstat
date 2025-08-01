import pandas as pd
import streamlit as st
import os
import warnings
import folium
from streamlit_folium import folium_static
import geopandas as gpd
import random
import plotly.express as px
from PIL import Image
from sqlalchemy import types as sql_types


warnings.filterwarnings("ignore")

#=========================================================================
# HEADER
#=========================================================================
st.set_page_config(page_title="Monitoring Wilkerstat SE", page_icon=":bar_chart:", layout="wide")
st.markdown('<style>div.block-container{padding-left:5rem; padding-top:5rem;}</style>', unsafe_allow_html=True)

try:
    image = Image.open(r"Project_BPS/asset/orangfix.png")
    col1_img, col2_title = st.columns([0.5, 4])
    with col1_img:
        st.image(image, width=200)
    with col2_title:
        st.title("Monitoring Wilkerstat Sensus Ekonomi Jawa Barat 2026")
except FileNotFoundError:
    st.title("Monitoring Wilkerstat Sensus Ekonomi Jawa Barat 2026")
    st.warning("File gambar header tidak ditemukan. Pastikan path benar.")

#=========================================================================
# DATABASE CONNECTION (CHANGED)
#=========================================================================
@st.cache_resource
def get_db_connection():
    """Establishes a cached connection to the database via st.connection."""
    return st.connection("mysql", type="sql")

conn_st = get_db_connection()

#=========================================================================
# INITIAL DATA LOADING & METRICS
#=========================================================================
try:
    df_prov = pd.read_csv('Project_BPS/dataset/data_provinsi.csv')
    
    def metric_card(title, value):
        return f"""
        <div style="background-color: #E8B991; padding: 10px; border-radius: 20px; text-align: center; border: 0.5px solid #eee;">
            <div style="font-weight: bold; font-size: 16px; color: black">{title}</div>
            <div style="font-size: 32px; font-weight: 900; color: black;">{value}</div>
        </div>"""

    col1_metric, col2_metric, col3_metric = st.columns(3)
    with col1_metric:
        st.markdown(metric_card("Jumlah Kabupaten/Kota", df_prov['nama_kotakab'].nunique()), unsafe_allow_html=True)
    with col2_metric:
        st.markdown(metric_card("Jumlah Kecamatan", df_prov['jumlah_kec'].sum()), unsafe_allow_html=True)
    with col3_metric:
        st.markdown(metric_card("Jumlah Desa", df_prov['jumlah_desa'].sum()), unsafe_allow_html=True)

except FileNotFoundError:
    st.error("File 'data_provinsi.csv' tidak ditemukan. Metrik tidak dapat ditampilkan.")
    st.stop() 

#=========================================================================
# MAP
#=========================================================================
st.header("Map Wilayah Kabupaten/Kota")
map1, map2 = st.columns([5, 2])
kanan = map2
kiri = map1

geojson_file = 'Project_BPS/Geolocation/kabupaten.geojson'
key_on = 'KABKOTNO'
popup_fields = ['KABKOT']

with kiri:
    try:
        gdf = gpd.read_file(geojson_file)
        
        def generate_random_color():
            return "#{:06x}".format(random.randint(0, 0xFFFFFF))
        unique_keys = gdf[key_on].unique()
        color_dict = {key: generate_random_color() for key in unique_keys}

        map_center = [-6.9175, 107.6191] 
        zoom_lvl = 8

        m = folium.Map(location=map_center, zoom_start=zoom_lvl, tiles='cartoDB positron')
        
        folium.GeoJson(
            data=gdf,
            style_function=lambda feature: {
                'fillColor': color_dict.get(feature['properties'][key_on], 'gray'),
                'color': 'black',
                'weight': 0.5,
                'fillOpacity': 0.8
            },
            tooltip=folium.features.GeoJsonTooltip(fields=popup_fields)
        ).add_to(m)

        folium_static(m, width=None, height=650)
    
    except Exception as e:
        st.error(f"Gagal memuat file peta GeoJSON: {e}. Pastikan path file benar.")

with kanan:
    if 'gdf' in locals():
        st.markdown("### Legenda Wilayah")
        
        legend_data = pd.DataFrame({
            'Wilayah': [row[popup_fields[0]] for _, row in gdf.iterrows()],
            'Color': [color_dict[row[key_on]] for _, row in gdf.iterrows()]
        }).drop_duplicates().sort_values(by='Wilayah')

        legend_html = "<div style='max-height: 600px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; border-radius: 5px;'>"
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
    else:
        st.warning("Legenda tidak dapat ditampilkan karena peta gagal dimuat.")

#=========================================================================
# DATABASE
#======================================================================================================
st.title("Database Provinsi Jawa Barat")

try:
    df_prov.to_sql("data_provinsi", con=conn_st.engine, if_exists="replace", index=False, dtype={
        'kode_kotakab': sql_types.VARCHAR(100),
        'nama_kotakab': sql_types.VARCHAR(100),
        'jumlah_kec': sql_types.INT,
        'jumlah_desa': sql_types.INT
    })
  
except Exception as e:
    st.warning(f"Gagal mengunggah data referensi ke database: {e}")
try:
    df_from_db = conn_st.query("SELECT * FROM data_provinsi", ttl=600)
    
    rename_mapping = {
        'kode_kotakab': 'Kode Kabupaten/Kota', 
        'nama_kotakab': 'Nama Kabupaten/Kota', 
        'jumlah_kec': 'Jumlah Kecamatan', 
        'jumlah_desa': 'Jumlah Desa' 
    }
    df_from_db = df_from_db.rename(columns=rename_mapping)

    df_landmark = conn_st.query("SELECT * FROM rekap_total_landmark", ttl=600)
    df_landmark = df_landmark.rename(columns={'nama_kotakab': 'Nama Kabupaten/Kota', 'total_landmark': 'Total Landmark'})
    df_from_db = df_from_db.merge(df_landmark, on='Nama Kabupaten/Kota', how='left')
    df_from_db['Total Landmark'] = df_from_db['Total Landmark'].fillna(0).astype(int)

    filter_columns = ['Kode Kabupaten/Kota', 'Nama Kabupaten/Kota']
    cols = st.columns(len(filter_columns))  
    
    filtered_df = df_from_db.copy()

    for i, col_name in enumerate(filter_columns):
        with cols[i]:
            options = ['Semua'] + sorted(filtered_df[col_name].dropna().unique().tolist())
            selected = st.selectbox(f"Filter berdasarkan {col_name}", options, key=f"filter_{col_name}")
            if selected != 'Semua':
                filtered_df = filtered_df[filtered_df[col_name] == selected]

    st.dataframe(filtered_df)

except Exception as e:
    st.error(f"Gagal mengambil atau memfilter data dari database: {e}")
