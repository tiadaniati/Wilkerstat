import os
import streamlit as st
from dotenv import load_dotenv

from langchain_community.utilities import SQLDatabase
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
import google.generativeai as genai
import re 

load_dotenv()
print(f"Is GOOGLE_API_KEY loaded? {os.getenv('GOOGLE_API_KEY') is not None}")
print(f"Value of GOOGLE_API_KEY: {os.getenv('GOOGLE_API_KEY')}")



MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "tia1234")
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "wilkerstat")


@st.cache_resource
def get_database_connection():
    try:
        mysql_uri = f"mysql+mysqlconnector://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
        db = SQLDatabase.from_uri(mysql_uri)
        #st.success(f"✅ Berhasil terhubung ke database MySQL: {MYSQL_DATABASE}")
        #with st.sidebar:
        #st.write("Skema Database:")
        #st.code(db.get_table_info(), language='sql')
        return db
    except Exception as e:
        st.error(f"Kesalahan saat menghubungkan ke MySQL: {e}")
        st.stop() 

db = get_database_connection()

@st.cache_resource
def get_llm():
    try:
        llm = ChatGoogleGenerativeAI(model="models/gemini-2.5-flash", temperature=0)
        #st.success(f"✅ Menggunakan model Google Gemini: {llm.model}")
        return llm
    except Exception as e:
        st.error(f"Kesalahan saat menginisialisasi AI: {e}")
        st.stop()

llm = get_llm()



def get_schema(_):
    return db.get_table_info()

#SQL template percakapan
sql_query_generation_template = """Berdasarkan skema tabel di bawah ini, tulis kueri SQL yang akan menjawab pertanyaan pengguna.
Jika pertanyaan meminta jumlah baris dalam tabel tertentu, pastikan kueri SQL menggunakan COUNT(*).
Contoh: Jika pertanyaannya "Berapa banyak kecamatan yang ada?", kueri harus "SELECT COUNT(*) FROM nama_kecamatan;"

{schema}

Pertanyaan: {question}
Kueri SQL:"""

sql_query_prompt = ChatPromptTemplate.from_template(sql_query_generation_template)

sql_chain = (
    RunnablePassthrough.assign(schema=get_schema)
    | sql_query_prompt
    | llm
    | StrOutputParser()
)


def run_query(query):
    if query.strip().upper() == 'TIDAK_TERKAIT_SQL':
        return "Maaf, saya hanya bisa menjawab pertanyaan yang terkait dengan database Anda."

    cleaned_query = query.strip()

    cleaned_query = cleaned_query.replace("Kueri SQL:", "").replace("SQL Query:", "").strip()

    match = re.search(r"```sql\s*(.*?)\s*```", cleaned_query, re.DOTALL)
    if match:
        cleaned_query = match.group(1).strip()
    else:
        cleaned_query = cleaned_query.replace("```", "").strip()

    lines = []
    for line in cleaned_query.splitlines():
        line = line.strip()
        if line and not line.startswith('--'): 
            lines.append(line)
    cleaned_query = " ".join(lines) 

    if cleaned_query and not cleaned_query.endswith(';'):

        if not re.search(r'\b(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|SHOW)\b', cleaned_query, re.IGNORECASE) is None:
             cleaned_query += ';' 

    try:
        if not cleaned_query.strip(): 
            return "Maaf, kueri SQL yang dihasilkan kosong atau tidak valid setelah pembersihan."

        result = db.run(cleaned_query)
        return result
    except Exception as e:
        return f"Kueri SQL: '{cleaned_query}'. Terjadi kesalahan: {e}"

# Final Answer Generation Chain
final_answer_template = """Anda adalah asisten chatbot yang ramah dan membantu.
Berdasarkan pertanyaan pengguna, skema database, kueri SQL yang dieksekusi (jika ada), dan hasilnya, berikan jawaban yang jelas dan ringkas dalam bahasa alami.
Jika hasil kueri adalah pesan kesalahan, sampaikan itu dengan sopan.
Jika kueri SQL menghasilkan pesan 'Maaf, saya hanya bisa menjawab pertanyaan yang terkait dengan database Anda.', sampaikan pesan tersebut.
**Jangan ulangi kueri SQL atau skema database dalam jawaban akhir Anda.**
**Jangan sertakan informasi debug, format Markdown (seperti `sql), atau pemikiran internal Anda.**

Skema:
{schema}

Pertanyaan: {question}
Kueri SQL:
{query}
Hasil SQL:
{response}

Jawaban Bahasa Alami:"""

final_answer_prompt = ChatPromptTemplate.from_template(final_answer_template)


@st.cache_resource
def get_full_chatbot_chain():
    return (
        RunnablePassthrough.assign(query=sql_chain)
        | RunnablePassthrough.assign(
            schema=get_schema,
            response=lambda x: run_query(x["query"])
        )
        | final_answer_prompt
        | llm
        | StrOutputParser()
    )

full_chatbot_chain = get_full_chatbot_chain()

# --- Streamlit ---

st.set_page_config(page_title="Chatbot Wilkerstat", layout="centered")
st.title("Chatbot Wilkerstat💬")
st.markdown("Tanyakan pertanyaan tentang database Wilkerstat!")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Tanyakan sesuatu tentang data Wilkerstat"):

    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Berpikir..."):
            try:
                response = full_chatbot_chain.invoke({"question": prompt})
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
            except Exception as e:
                error_message = f"Maaf, ada masalah saat memproses permintaan Anda: {e}"
                st.error(error_message)
                st.session_state.messages.append({"role": "assistant", "content": error_message})


if st.button("Hapus Riwayat Chat"):
    st.session_state.messages = []
    st.rerun()