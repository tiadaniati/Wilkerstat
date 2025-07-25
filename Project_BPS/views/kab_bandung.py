import streamlit as st
import pandas as pd
import os
import plotly.express as px
import folium
import geopandas as gpd
import random
from streamlit_folium import folium_static
import mysql.connector
from folium.plugins import MarkerCluster

st.markdown("""
    <h1 style='text-align: center; font-size: 60px;'>🔍 Monitoring Wilkerstat Sensus Ekonomi 2026</h1>
    <h2 style='text-align: center; font-size: 50px;'>Kabupaten Bandung</h2>
""", unsafe_allow_html=True)
st.set_page_config(page_title="Kabupaten Bandung", page_icon="🌳", layout="wide")
#=========================================================================
from sqlalchemy import create_engine, types as sql_types

user = 'root'
password = 'Mandala38'
host = 'localhost'
database = 'wilkerstat'

# Buat koneksi ke database
engine = create_engine(f'mysql+mysqlconnector://{user}:{password}@{host}/{database}')
#=========================================================================
if 'uploaded_df' not in st.session_state:
    st.session_state['uploaded_df'] = None
if 'uploaded_filename' not in st.session_state:
    st.session_state['uploaded_filename'] = None

col1, col2 = st.columns((2))
#=========================================================================
#Upload Data
with col2:

    st.header("Unggah Data")
    fl = st.file_uploader("Unggah Rekap Aktivitas", type=["csv", "txt", "xlsx", "xls"])
    upload_option = st.radio(
        "Pilih metode unggah ke database:",
        ["Ganti data sebelumnya (Ganti)", "Tambahkan ke data sebelumnya (Tambah)"]
    )

    if_exists_option = "replace" if upload_option == "Ganti data sebelumnya (Ganti)" else "append"
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
                    'id': 'ID',
                    'nama_krt': 'Nama Petugas',
                    'iddesa':'Kode Wilayah Desa',
                    'deskripsi_project':'Nama SLS',
                    'latitude': 'Latitude',
                    'longitude':'Longitude',
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
#===============================
                try:
                    df.to_sql("uploaded_kabupaten_bandung", con=engine, if_exists=if_exists_option, index=False, dtype={
                        'Kode Petugas': sql_types.VARCHAR(50),
                        'Nama Petugas': sql_types.VARCHAR(100),
                        'Nama Desa': sql_types.VARCHAR(100),
                        'Waktu Submit': sql_types.DATETIME(),
                        'Total Landmark': sql_types.INTEGER()
                    })
                    st.success(f"✅ Data berhasil diunggah ke database dengan metode: `{if_exists_option}`.")
                except Exception as e:
                    st.warning(f"⚠️ Gagal mengunggah ke MySQL: {e}")
            
            except Exception as e:
                st.error(f"😥 Gagal memproses file: {e}")
                st.stop()
#===============================
   #Display data sesudah di upload
    if 'uploaded_df' in st.session_state:
        df = st.session_state['uploaded_df']  
        st.dataframe(df, height=250)

    #Kalau ngga ada file
    elif fl is None and 'uploaded_df' not in st.session_state:
        os.chdir("D:\Dashboad\Dashboad\Project_BPS")
        df = pd.read_csv(r"/Users/jibrilnikki/Documents/Code/Project_BPS/dataset/template_data.csv")

        df.rename(columns={
            'NAMA USER': 'NAMA_USER',
            'KODE WILAYAH': 'KODE_WILAYAH',
            'NAMA WILAYAH': 'NAMA_WILAYAH',
            'CREATED AT': 'CREATED_AT',
            'TOTAL LANDMARK': 'TOTAL_LANDMARK'
        }, inplace=True)

        df['Kode User'] = df['KODE_WILAYAH'] + df['PROJECT KATEGORI/Kode SLS']
        df = df[['Kode User', 'NAMA_USER', 'NAMA_WILAYAH', 'CREATED_AT', 'TOTAL_LANDMARK']]
        df.rename(columns={
            'Kode User': 'Kode Petugas',
            'NAMA_USER': 'Nama Petugas',
            'NAMA_WILAYAH': 'Nama Desa',
            'CREATED_AT': 'Waktu Submit',
            'TOTAL_LANDMARK': 'Total Landmark'
        }, inplace=True)

        st.session_state['uploaded_df'] = df
        st.session_state['uploaded_filename'] = "template_data.csv"

        st.info("📔 Menampilkan data template default karena belum ada file diunggah.")
        st.dataframe(df, height=300)
if 'uploaded_df' in st.session_state:
    df = st.session_state['uploaded_df']
#=========================================================================
#Map
with col1:
    st.header("Peta Lokasi")
    
    conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Mandala38",
    database="wilkerstat"
    )

    def table_exists(conn, table_name):
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT COUNT(*)
            FROM information_schema.tables 
            WHERE table_schema = '{conn.database}'
            AND table_name = '{table_name}'
        """)
        return cursor.fetchone()[0] == 1

    if table_exists(conn, 'uploaded_kabupaten_bandung'):
        df_uploaded = pd.read_sql("SELECT * FROM uploaded_kabupaten_bandung", conn)
    else:
        df_uploaded = pd.DataFrame(columns=[
            'ID', 'Nama Petugas', 'Kode Wilayah Desa', 'Nama SLS', 'Latitude', 'Longitude', 'Waktu Submit'
        ])

    geojson_file = '/Users/jibrilnikki/Documents/Code/Project_BPS/Geolocation/kabupaten.geojson'
    key_on = 'KABKOTNO'
    popup_fields = ['KABKOT']

    try:
        gdf = gpd.read_file(geojson_file)
    except Exception as e:
        st.error(f"⚠️ Gagal membaca file GeoJSON: {e}.")
        gdf = gpd.GeoDataFrame() 

    m = folium.Map(location=[-7.083649033745665, 107.62193910200422], tiles='OpenStreetMap', zoom_start=13)

    if not gdf.empty:
        def generate_random_color():
            return "#{:06x}".format(random.randint(0, 0xFFFFFF))
        
        unique_keys = gdf[key_on].unique()
        color_dict = {key: generate_random_color() for key in unique_keys}
        
        folium.GeoJson(
            data=gdf,
            style_function=lambda feature: {
                'fillColor': color_dict.get(feature['properties'][key_on], 'gray'),
                'color': 'black',
                'weight': 0.9,
                'fillOpacity': 0
            },
            tooltip=folium.features.GeoJsonTooltip(fields=popup_fields)
        ).add_to(m)

    if not df_uploaded.empty:
        st.info(f"Menampilkan {len(df_uploaded)} lokasi dari database.")
        marker_cluster = MarkerCluster(name="Lokasi Petugas").add_to(m)

        df_uploaded.dropna(subset=['Latitude', 'Longitude'], inplace=True)

        for idx, row in df_uploaded.iterrows():
            try:
                lat = float(row['Latitude'])
                lon = float(row['Longitude'])

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

st.subheader("Total Data yang Telah Diunggah")

petugas_col, wilayah_desa_col, sls_col = st.columns(3)

with petugas_col:
    petugas = st.multiselect("Nama Petugas:", df_uploaded['Nama Petugas'].unique())

df2 = df_uploaded if not petugas else df[df_uploaded['Nama Petugas'].isin(petugas)]

with wilayah_desa_col:
    wilayah_desa = st.multiselect("Kode Wilayah Desa:", df2['Kode Wilayah Desa'].unique())

df3 = df2 if not wilayah_desa else df2[df2['Kode Wilayah Desa'].isin(wilayah_desa)]

with sls_col:    
    sls = st.multiselect("Nama SLS:", df3['Nama SLS'].unique())

df_filtered = df3 if not sls else df3[df3['Nama SLS'].isin(sls)]

st.dataframe(df_filtered,height=250)
#=========================================================================
#Metric card statistik
def metric_card(title, value):
    return f"""
    <div style="
        background-color: #E8B991;
        padding: 20px;
        margin: 5px;
        border-radius: 20px;
        text-align: center;
        border: 1px solid #eee;
    ">
        <div style="font-weight: bold; font-size: 27px; color: black">{title}</div>
        <div style="font-size: 25px; font-weight: 900; color: black;">{value}</div>
    </div>
    """


stat1,stat2,stat3 = st.columns((2,3,3))

df_bandung = pd.read_csv("/Users/jibrilnikki/Documents/Code/Project_BPS/dataset/kab_bandung.csv")

if df is not None and not df.empty:
    landmark = df.groupby(['Kode Wilayah Desa','Nama SLS']).size().reset_index(name='total_landmark')
else:
    st.warning("⚠️ Tidak ada data yang tersedia untuk dihitung total landmark.")
    landmark = pd.DataFrame(columns=['Kode Wilayah Desa', 'Nama SLS', 'total_landmark'])

#=========================================================================
#SQL

# Baca file CSV
df = pd.read_csv(r"/Users/jibrilnikki/Documents/Code/Project_BPS/dataset/kab_bandung.csv")
print(df[['kdkec', 'kddesa', 'kdsls']].head())
df = df.rename(columns={
    'iddesa': 'Kode Wilayah Desa',
    'nmsls': 'Nama SLS'
})

# Kirim ke tabel di MySQL
from sqlalchemy import create_engine, types as sql_types

# Buat engine
engine = create_engine("mysql+mysqlconnector://root:Mandala38@localhost/wilkerstat")

# Upload data ke MySQL, atur tipe agar tidak hilang 0 depan
df.to_sql("kabupaten_bandung", con=engine, if_exists="replace", index=False, dtype={
    'idsubsls': sql_types.VARCHAR(20),
    'iddesa': sql_types.VARCHAR(20),
    'kdprov': sql_types.VARCHAR(10),
    'nmprov': sql_types.VARCHAR(100),
    'kdkab': sql_types.VARCHAR(10),
    'nmkab': sql_types.VARCHAR(100),
    'kdkec': sql_types.VARCHAR(10),
    'nmkec': sql_types.VARCHAR(100),
    'kddesa': sql_types.VARCHAR(10),
    'nmdesa': sql_types.VARCHAR(100),
    'kdsls': sql_types.VARCHAR(10),
    'nmsls': sql_types.VARCHAR(100),
    'nama_ketua': sql_types.VARCHAR(100),
    'total_landmark': sql_types.INT()
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

st.title("Database Kabupaten Bandung")

conn = get_connection()
cursor = conn.cursor(dictionary=True)

rename_mapping = {
    'idsubsls': 'Kode Wilayah SLS', 
    'iddesa' : 'Kode Wilayah Desa',
    'kdprov': 'Kode Provinsi', 
    'nmprov': 'Nama Provinsi', 
    'kdkab': 'Kode Kabupaten/Kota', 
    'nmkab': 'Nama Kabupaten/Kota', 
    'kdkec': 'Kode Kecamatan', 
    'nmkec': 'Nama Kecamatan', 
    'kddesa': 'Kode Desa', 
    'nmdesa': 'Nama Desa',
    'kdsls': 'Kode SLS',
    'nmsls': 'Nama SLS',
    'nama_ketua' : 'Nama Ketua SLS'
}

df = df.rename(columns=rename_mapping)


df = pd.merge(df, landmark, on=['Kode Wilayah Desa', 'Nama SLS'], how='left')

df = df.rename(columns={'total_landmark':'Total Landmark'})

cursor.execute("SELECT * FROM kabupaten_bandung")
rows = cursor.fetchall()

st.subheader("Filter Data")

col11, col22, col33, col44, col55 = st.columns(5)

# Kode Wilayah SLS
with col11:
    kode_sls = st.multiselect("Kode Wilayah SLS:", df['Kode Wilayah SLS'].unique())
df2 = df if not kode_sls else df[df['Kode Wilayah SLS'].isin(kode_sls)]

# Nama Kecamatan
with col22:
    kecamatan = st.multiselect("Nama Kecamatan:", df2['Nama Kecamatan'].unique())
df3 = df2 if not kecamatan else df2[df2['Nama Kecamatan'].isin(kecamatan)]

# Nama Desa
with col33:    
    desa = st.multiselect("Nama Desa:", df3['Nama Desa'].unique())
df4 = df3 if not desa else df3[df3['Nama Desa'].isin(desa)]

# Nama Ketua SLS
with col44:  
    ketuasls = st.multiselect("Nama Ketua SLS:", df4['Nama Ketua SLS'].unique())
df_filtered = df4 if not ketuasls else df4[df4['Nama Ketua SLS'].isin(ketuasls)]

st.dataframe(df_filtered)

#visual
df['status'] = df['Total Landmark'] >= 4


with stat1:
    st.markdown(metric_card("Jumlah Kecamatan", df_bandung['nmkec'].nunique()), unsafe_allow_html=True)
    st.markdown(metric_card("Jumlah Desa", df_bandung['nmdesa'].nunique()), unsafe_allow_html=True)
    st.markdown(metric_card("Jumlah SLS", df_bandung['idsubsls'].nunique()), unsafe_allow_html=True)
    st.markdown(metric_card("Total SLS Sukses", df['status'].sum()), unsafe_allow_html=True)
    st.markdown(metric_card("Total Landmark", round(df['Total Landmark'].sum())), unsafe_allow_html=True)

with stat2:
    total_sls_acc = df['status'].sum()
    jumlah_sls = df_bandung['idsubsls'].nunique()

    sls_belum_acc = jumlah_sls - total_sls_acc

    data = {
        'Category': ['Total SLS Sukses', 'Total SLS Belum Sukses'],
        'Count': [total_sls_acc, sls_belum_acc]
    }
    df_pie = pd.DataFrame(data)

    fig = px.pie(df_pie,
                values='Count',
                names='Category',
                title='Persentase Status SLS Tervalidasi Sukses VS Belum Sukses',
                color='Category',
                color_discrete_map={
                    "Total SLS Sukses": "#A5C09A",
                    "Total SLS Belum Sukses": "#ff5757"
                }
    )  
    fig.update_layout(
        width=800,  
        height=600,  
        title_font_size=25, 
        title={
            'text': '<b>Persentase Status SLS Tervalidasi Sukses VS Belum Sukses</b><br><span style="font-weight:normal; font-size:20px">SLS dengan ≥4 landmark dianggap sukses Wilkerstat SE.</span>'        
        },
        legend=dict(
            font=dict(size=20)  
        ) 
    )
    st.plotly_chart(fig,use_container_width=False)

with stat3:
    grouped = df.groupby('Nama Desa')['Total Landmark'].sum().reset_index()
    grouped['Total Landmark'] = grouped['Total Landmark'].round()
    grouped = grouped.sort_values(by='Total Landmark', ascending=True)

    fig = px.bar(
        grouped,
        x='Total Landmark',
        y='Nama Desa',
        title='Jumlah Landmark Terlapor per Desa',
        hover_data=['Nama Desa', 'Total Landmark']
        )
    fig.update_traces(marker_color='#E8B991')
    fig.update_layout(
        width=800,  
        height=600,  
        title_font_size=25, 
        legend=dict(
            font=dict(size=20)  
        ) 
    )
    st.plotly_chart(fig, use_container_width=True)
