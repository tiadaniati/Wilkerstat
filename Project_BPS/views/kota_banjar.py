import streamlit as st
import pandas as pd
import os
import plotly.express as px
import folium
import geopandas as gpd
import random
from streamlit_folium import folium_static
import mysql.connector
from sqlalchemy import create_engine, types as sql_types
from folium.plugins import MarkerCluster

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Kota Banjar", page_icon="🌳", layout="wide")
st.markdown("""
    <h1 style='text-align: center; font-size: 60px;'>🔍 Monitoring Wilkerstat Sensus Ekonomi 2026</h1>
    <h2 style='text-align: center; font-size: 50px;'>Kota Banjar</h2>
""", unsafe_allow_html=True)

st.markdown("""
<style>
.main .block-container {
    max-width: 100%;
    padding-left: 2rem;
    padding-right: 2rem;
}
</style>
""", unsafe_allow_html=True)

#=========================================================================
# DATABASE CONNECTION (CHANGED)
#=========================================================================
@st.cache_resource
def get_db_connection():
    """Establishes a cached connection to the database."""
    return st.connection("mysql", type="sql")

conn_st = get_db_connection() 

#=========================================================================
# SESSION STATE
#=========================================================================
if 'uploaded_df' not in st.session_state:
    st.session_state['uploaded_df'] = None
if 'uploaded_filename' not in st.session_state:
    st.session_state['uploaded_filename'] = None

col1, col2 = st.columns((2, 1)) 

#=========================================================================
#Upload Data
#=========================================================================
with col2:
    st.header("Unggah Data")
    fl = st.file_uploader("Unggah Rekap Aktivitas", type=["csv", "txt", "xlsx", "xls"])
    upload_option = st.radio(
        "Pilih metode unggah ke database:",
        ["Ganti data sebelumnya (Ganti)", "Tambahkan ke data sebelumnya (Tambah)"]
    )

    if_exists_option = "replace" if "Ganti" in upload_option else "append"
    if fl is not None:
        filename = fl.name

        if st.session_state.get('uploaded_filename') != filename:
            st.write(f"📗 Memproses file: `{filename}`")
            try:
                if filename.endswith((".csv", ".txt")):
                    df = pd.read_csv(fl)
                else:
                    df = pd.read_excel(fl)

                column_map = {
                    'id': 'ID', 'nama_krt': 'Nama Petugas', 'iddesa':'Kode Wilayah Desa',
                    'deskripsi_project':'Nama SLS', 'latitude': 'Latitude', 'longitude':'Longitude',
                    'user_upload_at':'Waktu Submit'
                }
                df = df.rename(columns=column_map)
                
                required_cols = ['ID','Nama Petugas','Kode Wilayah Desa','Nama SLS','Latitude','Longitude','Waktu Submit']
                for col in required_cols:
                    if col not in df.columns:
                        df[col] = None
                df = df[required_cols]

                st.session_state['uploaded_df'] = df
                st.session_state['uploaded_filename'] = filename
                st.success("✅ File berhasil diproses.")

                try:
                    df.to_sql("_banjar", con=conn_st.engine, if_exists=if_exists_option, index=False, dtype={
                        'ID': sql_types.VARCHAR(255),
                        'Nama Petugas': sql_types.VARCHAR(255),
                        'Kode Wilayah Desa': sql_types.VARCHAR(255),
                        'Nama SLS': sql_types.VARCHAR(255),
                        'Latitude': sql_types.FLOAT,
                        'Longitude': sql_types.FLOAT,
                        'Waktu Submit': sql_types.DATETIME
                    })
                    st.success(f"✅ Data berhasil diunggah ke database dengan metode: `{if_exists_option}`.")
                except Exception as e:
                    st.warning(f"⚠️ Gagal mengunggah ke MySQL: {e}")
            
            except Exception as e:
                st.error(f"😥 Gagal memproses file: {e}")
                st.stop()

    if st.session_state['uploaded_df'] is not None:
        df = st.session_state['uploaded_df']  
        st.dataframe(df, height=250)

    elif fl is None and st.session_state['uploaded_df'] is None:
        st.info("📔 Menampilkan data template default karena belum ada file diunggah.")
        try:
            df = pd.read_csv(r"Project_BPS/dataset/template_data2.csv")
            st.dataframe(df, height=300)
            st.session_state['uploaded_df'] = df
        except FileNotFoundError:
            st.warning("Tampilan data template dilewati.")
            df = pd.DataFrame() 

if 'uploaded_df' in st.session_state and st.session_state['uploaded_df'] is not None:
    df = st.session_state['uploaded_df']

#=========================================================================
#Map
#=========================================================================
with col1:
    st.header("Peta Lokasi")
    

    def fetch_uploaded_data():
        """Fetches uploaded location data from the database."""
        try:
            df_query = conn_st.query("SELECT * FROM uploaded_kota_banjar;", ttl=600)
            return df_query
        except Exception as e:
            st.warning(f"Tidak dapat mengambil data dari DB untuk peta: {e}")
            return pd.DataFrame()

    df_uploaded = fetch_uploaded_data()

    geojson_file = 'Project_BPS/Geolocation/map_kota_banjar.geojson'
    try:
        gdf = gpd.read_file(geojson_file)
    except Exception as e:
        st.error(f"⚠️ Gagal membaca file GeoJSON: {e}.")
        gdf = gpd.GeoDataFrame() 

    m = folium.Map(
        location=[-7.374585, 108.558189],
        zoom_start=13,
        tiles='OpenStreetMap'
    )

    if not gdf.empty:
        folium.GeoJson(
            data=gdf,
            style_function=lambda feature: {
                'fillColor': 'blue', 'color': 'black', 'weight': 0.9, 'fillOpacity': 0
            },
            tooltip=folium.features.GeoJsonTooltip(fields=['nmkab', 'nmkec'])
        ).add_to(m)

    if not df_uploaded.empty:
        st.info(f"Menampilkan {len(df_uploaded)} lokasi dari database.")
        marker_cluster = MarkerCluster(name="Lokasi Petugas").add_to(m)
        df_uploaded.dropna(subset=['Latitude', 'Longitude'], inplace=True)

        marker_cluster = MarkerCluster(name="Lokasi Petugas").add_to(m)

        df_uploaded.dropna(subset=['Latitude', 'Longitude'], inplace=True)

        for idx, row in df_uploaded.iterrows():
            try:
                lat = float(row['Latitude']); lon = float(row['Longitude'])
                popup_html = f"""
                <b>Petugas:</b> {row.get('Nama Petugas', 'N/A')}<br>
                <b>Lokasi:</b> {row.get('Nama SLS', 'N/A')}<br>
                <b>Waktu:</b> {row.get('Waktu Submit', 'N/A')}<br>
                <b>Koordinat:</b> ({lat}, {lon})
                """
                folium.Marker(
                    location=[lat, lon], 
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=f"{row.get('Nama Petugas', 'N/A')} - {row.get('Nama SLS', 'N/A')}",
                    icon=folium.Icon(color='blue', icon='info-sign')
                ).add_to(marker_cluster)
            except (ValueError, TypeError):
                pass

    folium.LayerControl().add_to(m)    
    folium_static(m, width=None, height=650)

#=========================================================================
# FILTER DATA UNGGAHAN 
#=========================================================================
st.subheader("Total Data yang Telah Diunggah")
petugas_col, wilayah_desa_col, sls_col = st.columns(3)

df_for_filter = df_uploaded.copy() 

with petugas_col:
    petugas = st.multiselect("Nama Petugas:", df_for_filter['Nama Petugas'].unique())
df2 = df_for_filter if not petugas else df_for_filter[df_for_filter['Nama Petugas'].isin(petugas)]

with wilayah_desa_col:
    wilayah_desa = st.multiselect("Kode Wilayah Desa:", df2['Kode Wilayah Desa'].unique())
df3 = df2 if not wilayah_desa else df2[df2['Kode Wilayah Desa'].isin(wilayah_desa)]

with sls_col:    
    sls = st.multiselect("Nama SLS:", df3['Nama SLS'].unique())
df_filtered_uploaded = df3 if not sls else df3[df3['Nama SLS'].isin(sls)]

st.dataframe(df_filtered_uploaded, height=250)

#=========================================================================
#Metric card statistik & SQL Section
#=========================================================================
def metric_card(title, value):
    return f"""
    <div style="background-color: #E8B991; padding: 20px; margin: 5px; border-radius: 20px; text-align: center; border: 1px solid #eee;">
        <div style="font-weight: bold; font-size: 27px; color: black">{title}</div>
        <div style="font-size: 25px; font-weight: 900; color: black;">{value}</div>
    </div>"""

stat1, stat2, stat3 = st.columns((2, 3, 3))

try:
    df_banjar_csv = pd.read_csv("Project_BPS/dataset/kota_banjar.csv")
except FileNotFoundError:
    st.error("File referensi tidak ditemukan. Statistik tidak dapat ditampilkan.")
    st.stop()

if not df_uploaded.empty:
    landmark = df_uploaded.groupby(['Kode Wilayah Desa', 'Nama SLS']).size().reset_index(name='total_landmark')
else:
    landmark = pd.DataFrame(columns=['Kode Wilayah Desa', 'Nama SLS', 'total_landmark'])


st.title("Database Kota Banjar")

df_ref = df_banjar_csv.copy()

kolom_kode = ['idsubsls', 'iddesa', 'kdprov', 'kdkab', 'kdkec', 'kddesa', 'kdsls']
for kolom in kolom_kode:
    if kolom in df_ref.columns:
        df_ref[kolom] = df_ref[kolom].astype(str)
        
for kolom in ['kdkec', 'kddesa']:
    df_ref[kolom] = df_ref[kolom].str.zfill(3)

for kolom in ['kdsls']:
    df_ref[kolom] = df_ref[kolom].str.zfill(4)

try:
    df_ref.to_sql("kota_banjar", con=conn_st.engine, if_exists="replace", index=False, dtype={
        'idsubsls': sql_types.VARCHAR(20), 'iddesa': sql_types.VARCHAR(20), 'kdprov': sql_types.VARCHAR(10),
        'nmprov': sql_types.VARCHAR(100), 'kdkab': sql_types.VARCHAR(10), 'nmkab': sql_types.VARCHAR(100),
        'kdkec': sql_types.VARCHAR(10), 'nmkec': sql_types.VARCHAR(100), 'kddesa': sql_types.VARCHAR(10),
        'nmdesa': sql_types.VARCHAR(100), 'kdsls': sql_types.VARCHAR(10), 'nmsls': sql_types.VARCHAR(100),
        'nama_ketua': sql_types.VARCHAR(100), 'total_landmark': sql_types.INT()
    })

except Exception as e:
    st.warning(f"Gagal me-refresh data 'kota_banjar' di DB: {e}")

try:
    df = conn_st.query("SELECT * FROM kota_banjar;", ttl=600)
    
    rename_mapping = {
        'idsubsls': 'Kode Wilayah SLS', 'iddesa' : 'Kode Wilayah Desa', 'kdprov': 'Kode Provinsi', 
        'nmprov': 'Nama Provinsi', 'kdkab': 'Kode Kabupaten/Kota', 'nmkab': 'Nama Kabupaten/Kota', 
        'kdkec': 'Kode Kecamatan', 'nmkec': 'Nama Kecamatan', 'kddesa': 'Kode Desa', 
        'nmdesa': 'Nama Desa', 'kdsls': 'Kode SLS', 'nmsls': 'Nama SLS', 'nama_ketua' : 'Nama Ketua SLS'
    }
    df = df.rename(columns=rename_mapping)
except Exception as e:
    st.error(f"Gagal mengambil data 'kota_banjar' dari DB: {e}")

df['Kode Wilayah Desa'] = df['Kode Wilayah Desa'].astype(str)
landmark['Kode Wilayah Desa'] = landmark['Kode Wilayah Desa'].astype(str)

df['Kode Wilayah Desa'] = df['Kode Wilayah Desa'].astype(str)
landmark['Kode Wilayah Desa'] = landmark['Kode Wilayah Desa'].astype(str)

df_merged = pd.merge(df, landmark, on=['Kode Wilayah Desa', 'Nama SLS'], how='left')
df_merged['total_landmark'] = df_merged['total_landmark'].fillna(0)
df_merged = df_merged.rename(columns={'total_landmark':'Total Landmark'})

df_merged['Kecamatan'] = ' [' + df_merged['Kode Kecamatan'].astype(str) + ']' + ' '+ df_merged['Nama Kecamatan'].astype(str)
df_merged['Kabupaten/Kota'] = ' [' + df_merged['Kode Kabupaten/Kota'].astype(str) + ']'+ ' '+ df_merged['Nama Kabupaten/Kota'].astype(str)
df_merged['Desa'] = ' [' + df_merged['Kode Desa'].astype(str) + ']' + ' '+ df_merged['Nama Desa'].astype(str) 
df_merged['SLS'] = '[' + df_merged['Kode SLS'].astype(str) + ']' + ' ' + df_merged['Nama SLS'].astype(str)


st.subheader("Filter Data")
col11, col22, col33, col44 = st.columns(4)
filtered_df = df_merged

with col11:
    sls_options = sorted(df_merged['Kode Wilayah SLS'].unique())
    selected_sls = st.multiselect("Kode Wilayah SLS:", sls_options)
    if selected_sls:
        filtered_df = filtered_df[filtered_df['Kode Wilayah SLS'].isin(selected_sls)]

with col22:
    kecamatan_options = sorted(filtered_df['Kecamatan'].unique())
    selected_kecamatan = st.multiselect("Kecamatan:", kecamatan_options)
    if selected_kecamatan:
        filtered_df = filtered_df[filtered_df['Kecamatan'].isin(selected_kecamatan)]

with col33:
    desa_options = sorted(filtered_df['Desa'].unique())
    selected_desa = st.multiselect("Desa:", desa_options)
    if selected_desa:
        filtered_df = filtered_df[filtered_df['Desa'].isin(selected_desa)]
with col44:
    sls_option = sorted(filtered_df['SLS'].unique())
    selected_sls = st.multiselect("SLS:", sls_option)
    if selected_sls:
        filtered_df = filtered_df[filtered_df['SLS'].isin(selected_sls)]

tampilan_kolom = [
    'Kode Wilayah SLS',
    'Kode Wilayah Desa',
    'Nama Provinsi',
    'Kabupaten/Kota',
    'Kecamatan',
    'Desa',
    'SLS',
    'Total Landmark'
]
filtered_df = filtered_df[tampilan_kolom]

st.dataframe(filtered_df)


df_merged['status'] = df_merged['Total Landmark'] >= 4

with stat1:
    st.markdown(metric_card("Jumlah Kecamatan", df_banjar_csv['nmkec'].nunique()), unsafe_allow_html=True)
    st.markdown(metric_card("Jumlah Desa", df_banjar_csv['nmdesa'].nunique()), unsafe_allow_html=True)
    st.markdown(metric_card("Jumlah SLS", df_banjar_csv['idsubsls'].nunique()), unsafe_allow_html=True)
    st.markdown(metric_card("Total SLS Sukses", df_merged['status'].sum()), unsafe_allow_html=True)
    st.markdown(metric_card("Total Landmark", round(df_merged['Total Landmark'].sum())), unsafe_allow_html=True)

with stat2:
    total_sls_acc = df_merged['status'].sum()
    jumlah_sls = df_banjar_csv['idsubsls'].nunique()
    sls_belum_acc = jumlah_sls - total_sls_acc
    data_pie = {'Category': ['Total SLS Sukses', 'Total SLS Belum Sukses'], 'Count': [total_sls_acc, sls_belum_acc]}
    df_pie = pd.DataFrame(data_pie)
    fig = px.pie(df_pie, values='Count', names='Category',
                title='Persentase Status SLS Tervalidasi Sukses VS Belum Sukses',
                color='Category', color_discrete_map={"Total SLS Sukses": "#A5C09A", "Total SLS Belum Sukses": "#ff5757"})
    fig.update_layout(width=800, height=600, title_font_size=25, 
        title={'text': '<b>Persentase Status SLS Tervalidasi Sukses VS Belum Sukses</b><br><span style="font-weight:normal; font-size:20px">SLS dengan ≥4 landmark dianggap sukses Wilkerstat SE.</span>'},
        legend=dict(font=dict(size=20)))
    st.plotly_chart(fig, use_container_width=False)

with stat3:
    grouped = df_merged.groupby('Nama Desa')['Total Landmark'].sum().reset_index()
    grouped['Total Landmark'] = grouped['Total Landmark'].round()
    grouped = grouped.sort_values(by='Total Landmark', ascending=True)
    fig = px.bar(grouped, x='Total Landmark', y='Nama Desa', title='Jumlah Landmark Terlapor per Desa',
                 hover_data=['Nama Desa', 'Total Landmark'])
    fig.update_traces(marker_color='#E8B991')
    fig.update_layout(width=800, height=600, title_font_size=25, legend=dict(font=dict(size=20)))
    st.plotly_chart(fig, use_container_width=True)
