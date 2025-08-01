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
from sqlalchemy import inspect
from folium.plugins import MarkerCluster

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Kabupaten Bandung Barat", page_icon="🛤", layout="wide")
st.markdown("""
    <h1 style='text-align: center; font-size: 60px;'>🔍 Monitoring Wilkerstat Sensus Ekonomi 2026</h1>
    <h2 style='text-align: center; font-size: 50px;'>Kabupaten Bandung Barat</h2>
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
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'uploaded_df' not in st.session_state:
        st.session_state.uploaded_df = None
    if 'uploaded_filename' not in st.session_state:
        st.session_state.uploaded_filename = None

    CREDENTIALS = {
        "admin3217": "berkibar"
    }

    if not st.session_state.authenticated:
        st.title("Unggah Data")
        st.write("Silahkan login dahulu untuk upload file.")
        
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login", type="primary"):
            if username in CREDENTIALS and CREDENTIALS[username] == password:
                st.session_state.authenticated = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("😕 Username atau password salah.")

    else:
        with st.sidebar:
            st.success(f"Selamat datang, **{st.session_state.username}**!")
            if st.button("Logout"):
                st.session_state.authenticated = False
                st.session_state.username = None
                st.session_state.uploaded_df = None
                st.session_state.uploaded_filename = None
                st.rerun()

        st.header("Unggah Data")
        st.write("Anda berhasil login. Sekarang Anda bisa mengunggah file.")
        
        fl = st.file_uploader(
            "Unggah Rekap Aktivitas", 
            type=["csv", "txt", "xlsx", "xls"]
        )

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
                        'id': 'ID', 'iddesa':'Kode Wilayah Desa',
                        'deskripsi_project':'Nama SLS', 'latitude': 'Latitude', 'longitude':'Longitude',
                        'user_upload_at':'Waktu Submit', 'wid': 'WID', 'nm_project': 'Nama Project'
                    }
                    df = df.rename(columns=column_map)
                    
                    required_cols = ['ID','WID','Nama Project','Kode Wilayah Desa','Nama SLS','Latitude','Longitude','Waktu Submit']
                    for col in required_cols:
                        if col not in df.columns:
                            df[col] = None
                    df = df[required_cols]

                    st.session_state['uploaded_df'] = df
                    st.session_state['uploaded_filename'] = filename
                    st.success("✅ File berhasil diproses.")

                    try:
                        df.to_sql("uploaded_kab_bandungbarat", con=conn_st.engine, if_exists=if_exists_option, index=False, dtype={
                            'ID': sql_types.VARCHAR(255),
                            'WID': sql_types.VARCHAR(255),
                            'Nama Project': sql_types.VARCHAR(255),
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

        if st.session_state['uploaded_df'] is not None:
            st.write("Tampilan Data:")
            st.dataframe(st.session_state['uploaded_df'], height=300)
        else:
            st.info("📔 Menampilkan data template default karena belum ada file diunggah.")
            try:
                df_template = pd.read_csv(r"Project_BPS/dataset/template_data2.csv")
                st.dataframe(df_template, height=300)
                st.session_state['uploaded_df'] = df_template 
            except FileNotFoundError:
                st.warning("File template tidak ditemukan, tampilan data dilewati.")

#=========================================================================
#Map
#=========================================================================
with col1:
    st.header("Peta Lokasi")
    
    def fetch_uploaded_data():
        """Fetches uploaded location data from the database."""
        try:
            df_query = conn_st.query("SELECT * FROM uploaded_kab_bandungbarat;", ttl=600)
            return df_query
        except Exception as e:
            st.warning(f"Tidak dapat mengambil data dari DB untuk peta: {e}")
            return pd.DataFrame()

    df_uploaded = fetch_uploaded_data()

    geojson_file = 'Project_BPS/Geolocation/map_kab_bandung_barat.geojson'
    try:
        gdf = gpd.read_file(geojson_file)
    except Exception as e:
        st.error(f"⚠️ Gagal membaca file GeoJSON: {e}.")
        gdf = gpd.GeoDataFrame() 

    m = folium.Map(
        location=[-6.880013456237037, 107.41851262909165],
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
up1,up2,up3,up4= st.columns(4)

df_for_filter = df_uploaded.copy() 
df_for_filter['Nama Project'] = df_for_filter['Nama Project'].apply(lambda x: str(x).zfill(6)[:4])
with up1:
    wid = st.multiselect("WID:", df_for_filter['WID'].unique())
df1 = df_for_filter if not wid else df_for_filter[df_for_filter['WID'].isin(wid)]

with up2:
    projek = st.multiselect("Nama Project:", df1['Nama Project'].unique())
df2 = df1 if not projek else df1[df1['Nama Project'].isin(projek)]

with up3:
    wilayah_desa = st.multiselect("Kode Wilayah Desa:", df2['Kode Wilayah Desa'].unique())
df3 = df2 if not wilayah_desa else df2[df2['Kode Wilayah Desa'].isin(wilayah_desa)]

with up4:    
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
    df_bandungbrt_csv = pd.read_csv("Project_BPS/dataset/kab_bandung barat.csv")
except FileNotFoundError:
    st.error("File referensi tidak ditemukan. Statistik tidak dapat ditampilkan.")
    st.stop()

if not df_uploaded.empty:
    landmark = df_uploaded.groupby(['Kode Wilayah Desa', 'Nama SLS']).size().reset_index(name='total_landmark')
else:
    landmark = pd.DataFrame(columns=['Kode Wilayah Desa', 'Nama SLS', 'total_landmark'])



st.title("Database Kabupaten Bandung Barat")

df_ref = df_bandungbrt_csv.copy()
df_ref['petugas_kode'] = df_ref['petugas_kode'].apply(
    lambda x: str(int(float(x))) if pd.notna(x) else x
)
df_ref['pengawas_kode'] = df_ref['pengawas_kode'].apply(
    lambda x: str(int(float(x))) if pd.notna(x) else x
)

kolom_kode = ['idsubsls', 'iddesa', 'kdprov', 'kdkab', 'kdkec', 'kddesa', 'kdsls']
for kolom in kolom_kode:
    if kolom in df_ref.columns:
        df_ref[kolom] = df_ref[kolom].astype(str)
        
for kolom in ['kdkec', 'kddesa']:
    df_ref[kolom] = df_ref[kolom].str.zfill(3)

for kolom in ['kdsls']:
    df_ref[kolom] = df_ref[kolom].str.zfill(4)

try:
    df_ref.to_sql("kab_bandungbarat", con=conn_st.engine, if_exists="replace", index=False, dtype={
        'idsls': sql_types.VARCHAR(20), 'iddesa': sql_types.VARCHAR(20), 'kdprov': sql_types.VARCHAR(10),
        'nmprov': sql_types.VARCHAR(100), 'kdkab': sql_types.VARCHAR(10), 'nmkab': sql_types.VARCHAR(100),
        'kdkec': sql_types.VARCHAR(10), 'nmkec': sql_types.VARCHAR(100), 'kddesa': sql_types.VARCHAR(10),
        'nmdesa': sql_types.VARCHAR(100), 'kdsls': sql_types.VARCHAR(10), 'nama_sls': sql_types.VARCHAR(100),
        'petugas_kode': sql_types.VARCHAR(100), 'petugas_nama': sql_types.VARCHAR(100), 'pengawas_kode': sql_types.VARCHAR(100), 
        'pengawas_nama': sql_types.VARCHAR(100), 'nama_ketua': sql_types.VARCHAR(100), 'total_landmark': sql_types.INT()
    })

except Exception as e:
    st.warning(f"Gagal me-refresh data 'kab_bandungbarat' di DB: {e}")

try:
    df = conn_st.query("SELECT * FROM kab_bandungbarat;", ttl=600)
    
    rename_mapping = {
        'idsls': 'Kode Wilayah SLS', 'iddesa' : 'Kode Wilayah Desa', 'kdprov': 'Kode Provinsi', 
        'nmprov': 'Nama Provinsi', 'kdkab': 'Kode Kabupaten/Kota', 'nmkab': 'Nama Kabupaten/Kota', 
        'kdkec': 'Kode Kecamatan', 'nmkec': 'Nama Kecamatan', 'kddesa': 'Kode Desa', 
        'nmdesa': 'Nama Desa', 'kdsls': 'Kode SLS', 'nama_sls': 'Nama SLS', 'petugas_kode' : 'Kode Petugas',
        'petugas_nama': 'Nama Petugas', 'pengawas_kode': 'Kode Pengawas', 'pengawas_nama': 'Nama Pengawas'
    }
    df = df.rename(columns=rename_mapping)
except Exception as e:
    st.error(f"Gagal mengambil data 'kab_bandungbarat' dari DB: {e}")

df['Kode Wilayah Desa'] = df['Kode Wilayah Desa'].astype(str)
landmark['Kode Wilayah Desa'] = landmark['Kode Wilayah Desa'].astype(str)

df_merged = pd.merge(df, landmark, on=['Kode Wilayah Desa', 'Nama SLS'], how='left')
df_merged['total_landmark'] = df_merged['total_landmark'].fillna(0)
df_merged = df_merged.rename(columns={'total_landmark':'Total Landmark'})

df_merged['Kecamatan'] = ' [' + df_merged['Kode Kecamatan'].astype(str) + ']' + ' '+ df_merged['Nama Kecamatan'].astype(str)
df_merged['Kabupaten/Kota'] = ' [' + df_merged['Kode Kabupaten/Kota'].astype(str) + ']'+ ' '+ df_merged['Nama Kabupaten/Kota'].astype(str)
df_merged['Desa'] = ' [' + df_merged['Kode Desa'].astype(str) + ']' + ' '+ df_merged['Nama Desa'].astype(str) 
df_merged['SLS'] = '[' + df_merged['Kode SLS'].astype(str) + ']' + ' ' + df_merged['Nama SLS'].astype(str)


def update_rekap_total_landmark(df_merged, nama_kotakab, conn_engine):
    try:
        total_landmark = df_merged['Total Landmark'].sum()

        df_current = pd.DataFrame([{
            'nama_kotakab': nama_kotakab,
            'total_landmark': int(total_landmark)
        }])

        inspector = inspect(conn_engine)
        tables = inspector.get_table_names()

        if 'rekap_total_landmark' in tables:
            query = "SELECT * FROM rekap_total_landmark"
            df_existing = pd.read_sql(query, conn_engine)

            df_final = pd.concat([df_existing, df_current], ignore_index=True)
            df_final = df_final.drop_duplicates(subset=['nama_kotakab'], keep='last')
        else:
            df_final = df_current

        df_final.to_sql('rekap_total_landmark', con=conn_engine, if_exists='replace', index=False, dtype={
            'nama_kotakab': sql_types.VARCHAR(100),
            'total_landmark': sql_types.INT
        })
    except Exception as e:
        st.error(f"Gagal memperbarui rekap_total_landmark untuk {nama_kotakab}: {e}")

update_rekap_total_landmark(df_merged, "Kabupaten Bandung Barat", conn_st.engine)

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
    'Kode Petugas',
    'Nama Petugas',
    'Kode Pengawas',
    'Nama Pengawas',
    'Total Landmark'
]
filtered_df = filtered_df[tampilan_kolom]

st.dataframe(filtered_df)


df_merged['status'] = df_merged['Total Landmark'] >= 4

with stat1:
    st.markdown(metric_card("Jumlah Kecamatan", df_bandungbrt_csv['nmkec'].nunique()), unsafe_allow_html=True)
    st.markdown(metric_card("Jumlah Desa", df_bandungbrt_csv['nmdesa'].nunique()), unsafe_allow_html=True)
    st.markdown(metric_card("Jumlah SLS", df_bandungbrt_csv['idsls'].nunique()), unsafe_allow_html=True)
    st.markdown(metric_card("Total SLS ≥ 4", df_merged['status'].sum()), unsafe_allow_html=True)
    st.markdown(metric_card("Total Landmark", round(df_merged['Total Landmark'].sum())), unsafe_allow_html=True)

with stat2:
    total_sls_acc = df_merged['status'].sum()
    jumlah_sls = df_bandungbrt_csv['idsls'].nunique()
    sls_belum_acc = jumlah_sls - total_sls_acc
    data_pie = {'Category': ['Total SLS ≥ 4', 'Total SLS < 4'], 'Count': [total_sls_acc, sls_belum_acc]}
    df_pie = pd.DataFrame(data_pie)
    fig = px.pie(df_pie, values='Count', names='Category',
                title='Persentase Status SLS Tervalidasi ≥4 VS < 4',
                color='Category', color_discrete_map={"Total SLS ≥ 4": "#A5C09A", "Total SLS < 4": "#ff5757"})
    fig.update_layout(width=800, height=600, title_font_size=25, 
        title={'text': '<b>Persentase Status SLS Tervalidasi ≥ 4 VS < 4 </b><br><span style="font-weight:normal; font-size:20px"></span>'},
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
