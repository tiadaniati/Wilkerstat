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
Anda adalah AI yang membantu menganalisis data monitoring Sensus Ekonomi 2026 untuk Kota Banjar.
Berikut adalah konteks tentang tabel dalam database:

1.  **`kota_banjar`**: Ini adalah tabel referensi utama. Isinya adalah daftar semua wilayah administratif resmi di Kota Banjar, seperti Kecamatan, Desa, dan Satuan Lingkungan Setempat (SLS). Setiap baris adalah satu SLS.
2.  **`uploaded_kota_banjar`**: Tabel ini berisi data yang diunggah oleh petugas lapangan. Setiap baris di tabel ini merepresentasikan satu "Landmark" atau titik lokasi yang berhasil dicatat oleh petugas. Kolom utamanya adalah 'Nama Petugas', 'Nama SLS', 'Latitude', dan 'Longitude'.

Aturan Bisnis Penting:
-   **"Landmark"**: Satu baris data di tabel `uploaded_kota_banjar` dianggap sebagai satu landmark yang telah dicatat.
-   **"SLS Sukses"**: Sebuah SLS dianggap "sukses" atau "tervalidasi" jika memiliki 4 atau lebih landmark. Untuk menghitungnya, Anda perlu menggabungkan tabel `kota_banjar` dengan `uploaded_kota_banjar` berdasarkan 'Nama SLS' dan 'Kode Wilayah Desa', lalu hitung jumlah landmark untuk setiap SLS.
-   **Hubungan Tabel**: Kedua tabel dapat digabungkan menggunakan kolom `Nama SLS` dan `Kode Wilayah Desa`.

Contoh Pertanyaan dan Kueri yang Diharapkan:
- Pertanyaan: "Berapa jumlah SLS yang sudah sukses?"
- Logika: Hitung jumlah SLS yang memiliki total landmark >= 4.
- Kueri SQL yang mungkin:
  SELECT COUNT(*) FROM (
      SELECT k.`Nama SLS`
      FROM kota_banjar k
      JOIN uploaded_kota_banjar u ON k.`Nama SLS` = u.`Nama SLS` AND k.`Kode Wilayah Desa` = u.`Kode Wilayah Desa`
      GROUP BY k.`Nama SLS`, k.`Kode Wilayah Desa`
      HAVING COUNT(u.ID) >= 4
  ) AS subquery;

- Pertanyaan: "Siapa petugas yang paling banyak mengunggah landmark?"
- Logika: Hitung jumlah baris di `uploaded_kota_banjar` dikelompokkan berdasarkan 'Nama Petugas'.
- Kueri SQL yang mungkin:
  SELECT `Nama Petugas`, COUNT(*) as total_landmark
  FROM uploaded_kota_banjar
  GROUP BY `Nama Petugas`
  ORDER BY total_landmark DESC
  LIMIT 1;
"""

@st.cache_resource
def get_database_connection():
    """Menggunakan st.connection untuk koneksi yang konsisten dengan aplikasi utama."""
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
    """Inisialisasi model LLM dari Google Gemini."""
    try:

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            st.error("GOOGLE_API_KEY tidak ditemukan. Harap atur di file .env atau secrets.toml Streamlit.")
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
    """Membersihkan, menjalankan kueri SQL, dan menangani error."""
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
    """Membangun chain lengkap dari pertanyaan hingga jawaban akhir."""
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
st.markdown("Tanyakan apa saja tentang data Wilkerstat Kota Banjar!")


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
        with st.spinner("Sedang berpikir... 🧠"):
            try:
                response = full_chatbot_chain.invoke({
                    "question": prompt
                })
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
            except Exception as e:
                error_message = f"Maaf, terjadi masalah saat memproses permintaan Anda: {e}"
                st.error(error_message)
                st.session_state.messages.append({"role": "assistant", "content": error_message})

if st.button("Hapus Riwayat Chat"):
    st.session_state.messages = []
    st.rerun()
