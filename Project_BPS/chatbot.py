import os
import streamlit as st
from dotenv import load_dotenv
from langchain_community.utilities import SQLDatabase
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
import re

load_dotenv()

APPLICATION_CONTEXT = """
Anda adalah AI asisten untuk Wilkerstat, yang membantu menganalisis data monitoring sensus.
Tugas Anda adalah memahami pertanyaan pengguna dalam bahasa natural dan mengubahnya menjadi kueri SQL yang akurat untuk mengambil informasi dari database.

Berikut adalah panduan dan aturan penting untuk Anda ikuti:

1.  **Terminologi Penting yang Harus Dipahami:**
    * **Fleksibilitas Kata Kunci**: Pengguna mungkin tidak tahu istilah teknis. Ketika pengguna menyebut kata **'data'**, **'database'**, atau **'informasi'**, seringkali yang mereka maksud adalah **'tabel'** atau isi dari tabel. Perlakukan kata-kata ini sebagai sinonim.
        * Contoh: Pertanyaan "kamu punya data apa saja?" harus ditafsirkan sebagai permintaan untuk menampilkan daftar tabel yang tersedia.
    * **"Landmark"**: Satu baris data di tabel `uploaded_...` dianggap sebagai satu landmark yang dicatat petugas.
    * **"SLS Sukses"**: Sebuah Satuan Lingkungan Setempat (SLS) dianggap "sukses" jika memiliki 4 atau lebih landmark.
    * Jika pengguna bertanya secara umum seperti **"lihat semua data", "kamu punya data apa saja?", "tampilkan semuanya", atau permintaan serupa yang tidak spesifik**, JANGAN mencoba menggabungkan atau menampilkan isi tabel.
    * Sebagai gantinya, tugas Anda adalah **menampilkan DAFTAR NAMA TABEL** yang ada di database.
    * Gunakan kueri SQL: `SHOW TABLES;` untuk tujuan ini.

2.  **Pola Penamaan Tabel:**
    * Tabel wilayah resmi (berisi daftar SLS) mengikuti pola `kota_[nama]` atau `kab_[nama]`. Contoh: `kota_banjar`, `kab_bandung`.
    * Tabel unggahan petugas (berisi data landmark) mengikuti pola `uploaded_[nama_tabel_wilayah]`. Contoh: `uploaded_kota_banjar`, `uploaded_kab_bandung`.

3.  **Hubungan Antar Tabel:**
    * Setiap tabel wilayah (misal: `kota_banjar`) dapat digabungkan dengan tabel unggahannya (`uploaded_kota_banjar`) menggunakan kolom `Nama SLS` dan `Kode Wilayah Desa` untuk analisis lebih lanjut.

4.  **Cara Menjawab Pertanyaan:**
    * **Pertanyaan Spesifik**: Jika pengguna bertanya tentang wilayah tertentu (misal: "progres di Ciamis"), identifikasi tabel yang relevan dari nama wilayah itu (`kab_ciamis` dan `uploaded_kab_ciamis`), lalu buat kueri SQL yang sesuai.
    * **Pertanyaan Umum**: Jika pengguna bertanya secara umum ("lihat semua datamu"), cara terbaik untuk merespons adalah dengan menjalankan kueri yang menampilkan semua nama tabel yang tersedia di database.

Contoh Pertanyaan dan Kueri yang Diharapkan:
- Pertanyaan: "Berapa persen SLS yang sudah sukses di Kota Banjar?"
- Logika: Hitung jumlah SLS dari `kota_banjar` yang memiliki landmark >= 4 di `uploaded_kota_banjar`, lalu bandingkan dengan total SLS di `kota_banjar`.
- Kueri SQL yang mungkin:
  SELECT (
      (SELECT COUNT(*) FROM (
          SELECT k.`Nama SLS`
          FROM kota_banjar k
          JOIN uploaded_kota_banjar u ON k.`Nama SLS` = u.`Nama SLS` AND k.`Kode Wilayah Desa` = u.`Kode Wilayah Desa`
          GROUP BY k.`Nama SLS`, k.`Kode Wilayah Desa`
          HAVING COUNT(u.ID) >= 4
      ) AS subquery) * 100.0 / COUNT(*)
  ) AS persentase_sukses
  FROM kota_banjar;
"""

@st.cache_resource
def get_database_connection():
    try:
        db_conn = st.connection("mysql", type="sql")
        db = SQLDatabase(engine=db_conn.engine)
        return db
    except Exception as e:
        st.error(f"Kesalahan saat menghubungkan ke MySQL melalui st.connection: {e}")
        st.stop()

db = get_database_connection()

@st.cache_resource
def get_llm():
    try:
        api_key = st.secrets.get("GOOGLE_API_KEY", os.getenv("GOOGLE_API_KEY"))
        if not api_key:
            st.error("GOOGLE_API_KEY tidak ditemukan :((")
            st.stop()
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0, google_api_key=api_key)
        return llm
    except Exception as e:
        st.error(f"Kesalahan saat menginisialisasi AI: {e}")
        st.stop()

llm = get_llm()

def get_schema(_):
    return db.get_table_info()

sql_query_generation_template = """Berdasarkan skema tabel dan konteks aplikasi di bawah ini, tulis satu kueri SQL yang akan menjawab pertanyaan pengguna.
Hanya hasilkan kueri SQL dan tidak ada yang lain.

Konteks Aplikasi:
{app_context}

Skema Database:
{schema}

Pertanyaan: {question}
Kueri SQL:"""

sql_query_prompt = ChatPromptTemplate.from_template(sql_query_generation_template)

sql_chain = (
    RunnablePassthrough.assign(
        schema=get_schema,
        app_context=lambda _: APPLICATION_CONTEXT
    )
    | sql_query_prompt
    | llm
    | StrOutputParser()
)

def run_query(query: str) -> str:
    cleaned_query = query.strip()
    match = re.search(r"```sql\s*(.*?)\s*```", cleaned_query, re.DOTALL)
    if match:
        cleaned_query = match.group(1).strip()
    else:
        cleaned_query = cleaned_query.replace("```", "").strip()

    if not cleaned_query:
        return "Maaf, kueri SQL yang dihasilkan kosong."

    try:
        return db.run(cleaned_query)
    except Exception as e:
        return f"Terjadi kesalahan saat menjalankan kueri.\nKueri: '{cleaned_query}'\nError: {e}"

final_answer_template = """Anda adalah asisten chatbot yang ramah dan membantu untuk aplikasi Wilkerstat.
Berdasarkan pertanyaan pengguna, konteks aplikasi, kueri SQL yang dieksekusi, dan hasilnya, berikan jawaban yang jelas dan ringkas dalam Bahasa Indonesia.
Jika hasil kueri adalah pesan kesalahan, sampaikan itu dengan sopan.
Jangan ulangi kueri SQL atau skema database dalam jawaban akhir Anda.

Konteks Aplikasi:
{app_context}

Pertanyaan:
{question}

Kueri SQL yang Dijalankan:
{query}

Hasil dari Kueri SQL:
{response}

Jawaban Akhir (Bahasa Indonesia):"""

final_answer_prompt = ChatPromptTemplate.from_template(final_answer_template)

@st.cache_resource
def get_full_chatbot_chain():
    return (
        RunnablePassthrough.assign(
            query=sql_chain 
        )
        | RunnablePassthrough.assign(
            schema=get_schema,
            app_context=lambda _: APPLICATION_CONTEXT,
            response=lambda x: run_query(x["query"]) 
        )
        | final_answer_prompt 
        | llm 
        | StrOutputParser()
    )

full_chatbot_chain = get_full_chatbot_chain()

st.set_page_config(page_title="Chatbot Wilkerstat", layout="centered", page_icon="💬")
st.title("Chatbot Wilkerstat 💬")
st.markdown("Tanyakan apa saja tentang data Wilkerstat!")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Contoh: Berapa persen SLS yang sudah sukses?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Sedang berpikir..."):
            try:
                response = full_chatbot_chain.invoke({"question": prompt})
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
            except Exception as e:
                error_message = f"Maaf, terjadi masalah saat memproses permintaan Anda: {e}"
                st.error(error_message)
                st.session_state.messages.append({"role": "assistant", "content": error_message})

if st.button("Hapus Riwayat Chat"):
    st.session_state.messages = []
    st.rerun()
