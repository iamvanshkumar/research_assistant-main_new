# research_assistant.py
import streamlit as st
import os
import google.generativeai as genai
import requests
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv
import sqlite3
from utilities import GEMINI_MODELS, init_session_state, encode_pdf
from gemini_interface import get_model, analyze_pdf_content, process_query_stream

# Load environment variables
load_dotenv()

# Load API Key
API_KEY = os.getenv("GEMINI_API_KEY")
OPENALEX_API_URL = "https://api.openalex.org/works?search="
CROSSREF_API_URL = "https://api.crossref.org/works?query="
SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

if not API_KEY:
    st.error("API key not found. Set GEMINI_API_KEY in a .env file or as an environment variable.")
    st.stop()

# Configure Gemini API
genai.configure(api_key=API_KEY)

# -------------------- APP CONFIGURATION --------------------
st.set_page_config(page_title="Bibliometric Analysis - Saudi Arabia & Global", layout="wide", page_icon="chart")

# -------------------- CUSTOM CSS --------------------
st.markdown(
    """
    <style>
        h1 {text-align: center; font-weight: bold; color: #FF9933; text-shadow: 2px 2px 4px rgba(0,0,0,0.2);}
        .stButton button {background-color: #138808; color: white; font-weight: bold; border-radius: 10px; transition: 0.3s;}
        .stButton button:hover {background-color: #FF9933; transform: scale(1.05);}
        .stDataFrame {border: 2px solid #000080; box-shadow: 2px 2px 10px rgba(0,0,0,0.1);}
        .logo {
            position: absolute;
            top: 20px;
            right: 20px;
            width: 50px;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# -------------------- LANGUAGE SELECTOR --------------------
language = st.sidebar.radio("Select Language / اختر اللغة", ["English", "العربية"])

def translate(text):
    translations = {
        "English": {
            "title": "Research Assistant",
            "search": "Enter Keywords:",
            "region_filter": "Select Region:",
            "fetch_data": "Fetch Research Data",
            "results": "Research Papers",
            "visualizations": "Visualizations",
            "archive": "Archived Data",
            "upload_pdf": "Upload Research Paper (PDF)",
            "analyze_pdf": "Analyze Paper",
            "ask_question": "Ask a question about the paper",
            "link_extraction": "Link Extraction"
        },
        "العربية": {
            "title": "مساعد البحث",
            "search": "أدخل الكلمات المفتاحية:",
            "region_filter": "اختر المنطقة:",
            "fetch_data": "جلب بيانات البحث",
            "results": "أوراق البحث",
            "visualizations": "التصورات البيانية",
            "archive": "البيانات المؤرشفة",
            "upload_pdf": "تحميل ورقة بحثية (PDF)",
            "analyze_pdf": "تحليل الورقة",
            "ask_question": "اطرح سؤالًا عن الورقة",
            "link_extraction": "استخراج الروابط"
        }
    }
    return translations[language].get(text, text)

# -------------------- DATABASE SETUP FOR ARCHIVE --------------------
conn = sqlite3.connect("archive.db")
c = conn.cursor()
c.execute("""
    CREATE TABLE IF NOT EXISTS research_archive (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        authors TEXT,
        institution TEXT,
        year TEXT,
        type TEXT,
        citations INTEGER,
        doi TEXT
    )
""")
conn.commit()

# -------------------- APP MAIN FUNCTION --------------------
def main():
    is_arabic = language == "العربية"
    st.title("Research Assistant" if not is_arabic else "مساعد البحث")
    init_session_state()

    with st.sidebar:
        st.header("Configuration" if not is_arabic else "الإعدادات")
        sidebar_tabs = st.tabs([translate("search"), translate("upload_pdf")])

        with sidebar_tabs[0]:
            # Model Selection Logic (kept original)
            selected_model_name = list(GEMINI_MODELS.keys())[0]
            model_id = GEMINI_MODELS[selected_model_name]
            st.session_state.selected_model = model_id

            # === FIX: Initialize model here (only once) ===
            if 'model' not in st.session_state or st.session_state.model is None:
                with st.spinner("Initializing Gemini 2.5 Flash..."):
                    try:
                        from gemini_interface import get_model
                        st.session_state.model = get_model()
                    except Exception as e:
                        st.error(f"Model init failed: {e}")
                        st.stop()
            # ===========================================

            # API Request Handling
            search_query = st.text_input(translate("search"), key="search_input")
            regions = ["All Saudi Arabia", "Riyadh", "Jeddah", "Makkah", "Madinah", "Jazan", "Eastern Province"]
            region_selected = st.selectbox(translate("region_filter"), regions)
            global_view = st.checkbox("View Global Research")
            fetch_button = st.button(translate("fetch_data"))

        with sidebar_tabs[1]:
            # File Upload Section
            st.subheader(translate("upload_pdf"))
            uploaded_file = st.file_uploader("", type=["pdf"])
            if uploaded_file is not None:
                pdf_content = encode_pdf(uploaded_file.read())
                st.session_state.pdf_content = pdf_content
                if st.button(translate("analyze_pdf")):
                    st.session_state.messages = []
                    st.session_state.start_analysis = True
                    st.session_state.notes = ""

                    with st.chat_message("assistant"):
                        response_placeholder = st.empty()
                        full_response = []

                        try:
                            for chunk in analyze_pdf_content(st.session_state.model, pdf_content):
                                full_response.append(chunk.text if hasattr(chunk, 'text') else "")
                                response_placeholder.markdown("".join(full_response))
                        except Exception as e:
                            st.error(f"Analysis failed: {e}")
                            st.stop()

                        final_response = "".join(full_response)
                        st.session_state.notes = final_response
                        st.session_state.messages.append({"role": "assistant", "content": final_response})

    # --- DATA FETCHING AND DISPLAY ---
    if fetch_button:
        with st.spinner("Fetching data..."):
            openalex_url = f"https://api.openalex.org/works?search={search_query}" if global_view else f"https://api.openalex.org/works?search={search_query},countries.sa"
            openalex_data = fetch_data(openalex_url)
            df_open_alexs = pd.DataFrame(process_open_alexs(openalex_data))

            crossref_url = f"{CROSSREF_API_URL}{search_query}"
            crossref_data = fetch_data(crossref_url)
            df_crossrefs = pd.DataFrame(process_crossrefs(crossref_data))

            semantic_scholar_params = {'query': search_query, 'fields': 'title,authors,year,venue,citationCount,url,openAccessPdf'}
            semantic_scholar_response = requests.get(SEMANTIC_SCHOLAR_API_URL, params=semantic_scholar_params).json()
            semantic_df = pd.DataFrame(process_semantic_scholars(semantic_scholar_response))

            if 'Citations' not in semantic_df.columns:
                semantic_df['Citations'] = 0

            df_open_alexs['Citations_OpenAlex'] = pd.to_numeric(df_open_alexs['Citations_OpenAlex'], errors='coerce').fillna(0)
            df_crossrefs['Citations'] = pd.to_numeric(df_crossrefs['Citations'], errors='coerce').fillna(0)
            semantic_df['Citations'] = pd.to_numeric(semantic_df['Citations'], errors='coerce').fillna(0)

            combined_df = pd.concat([df_open_alexs, df_crossrefs, semantic_df], ignore_index=True)
            combined_df['Overall_Citations'] = combined_df['Citations_OpenAlex'].fillna(combined_df['Citations'])
            top_10_combined = combined_df.sort_values('Overall_Citations', ascending=False).head(10)

        tab1, tab2, tab3, tab4 = st.tabs([translate('results'), translate('visualizations'), translate('archive'), 'Consolidated Top 10'])

        with tab1:
            research_paper_tabs = st.tabs(['OpenAlex Results', 'CrossRef Results', 'Semantic Scholar Results'])
            with research_paper_tabs[0]:
                st.dataframe(df_open_alexs)
            with research_paper_tabs[1]:
                st.dataframe(df_crossrefs)
            with research_paper_tabs[2]:
                st.dataframe(semantic_df)

        with tab2:
            st.subheader("OpenAlex Visualizations")
            create_visualizations_openalex(df_open_alexs)
            st.subheader("CrossRef Visualizations")
            create_visualizations_crossref(df_crossrefs)
            st.subheader("Semantic Scholar Visualizations")
            create_visualizations_semantic_scholar(semantic_df)

        with tab3:
            st.dataframe(pd.read_sql("SELECT * FROM research_archive", conn))

        with tab4:
            st.dataframe(top_10_combined)

    # --- PDF Q&A ---
    if st.session_state.get("start_analysis") and st.session_state.pdf_content:
        st.markdown("---")
        st.subheader(translate("ask_question"))

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if prompt := st.chat_input(translate("ask_question")):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                response_placeholder = st.empty()
                full_response = []

                for chunk in process_query_stream(
                    st.session_state.model,
                    st.session_state.pdf_content,
                    st.session_state.notes or "",
                    prompt
                ):
                    full_response.append(chunk.text if hasattr(chunk, 'text') else "")
                    response_placeholder.markdown("".join(full_response))

                final_response = "".join(full_response)
                st.session_state.messages.append({"role": "assistant", "content": final_response})

def fetch_data(url):
    try:
        response = requests.get(url).json()
        return response
    except Exception as e:
        print(f'Error fetching data from URL:{e}')
        return {}

def process_open_alexs(data):
    research_papers = []
    for entry in data.get('results', []):
        paper_doi_link = entry.get("doi", 'N/A') if entry.get("doi") else 'N/A'
        authors_list = []
        for authorships_entry in (entry.get("authorships") or []):
            if "author" in authorships_entry and "display_name" in authorships_entry["author"]:
                authors_list.append(authorships_entry["author"]["display_name"])
            else:
                authors_list.append("Unknown")
        authors = ', '.join(authors_list)
        institutions_list = []
        for authorships_entry in (entry.get("authorships") or []):
            if "institutions" in authorships_entry:
                for inst in authorships_entry["institutions"]:
                    institutions_list.append(inst.get("display_name", "Unknown"))
            else:
                institutions_list.append("Unknown")
        institution = ', '.join(institutions_list)
        paper = {
            'Title': entry.get('title', 'N/A'),
            'Authors': authors,
            'Institution': institution,
            'Year': entry.get('publication_year', "N/A"),
            'Type': entry.get("type", "journal-article"),
            'Citations_OpenAlex': entry.get("cited_by_count", None),
            'DOI': paper_doi_link
        }
        research_papers.append(paper)
    return research_papers

def process_crossrefs(data):
    research_papers = []
    if 'message' in data and 'items' in data['message']:
        for entry in data['message']['items']:
            authors = ', '.join(f"{author.get('family', '')}, {author.get('given', '')}" for author in entry.get('author', []))
            paper = {
                'Title': entry.get('title', ['N/A'])[0],
                'Authors': authors,
                'Institution': 'N/A',
                'Year': entry.get('published-print', {}).get('date-parts', [['N/A']])[0][0] if entry.get('published-print') else 'N/A',
                'Type': entry.get('type', 'N/A'),
                'Citations': entry.get('is-referenced-by-count', 0),
                'DOI': entry.get('DOI', 'N/A')
            }
            research_papers.append(paper)
    return research_papers

def process_semantic_scholars(data):
    papers = []
    for result in data.get('data', []):
        if result:
            authors = ', '.join([author['name'] for author in result.get('authors', [])])
            paper = {
                'Title': result.get('title', 'N/A'),
                'Authors': authors,
                'Institution': result.get('venue', 'N/A'),
                'Year': result.get('year', 'N/A'),
                'Citations': result.get('citationCount', 0),
                'url': result.get('url', 'N/A'),
                'download_pdf': result.get('openAccessPdf', {}).get('url', 'N/A') if result.get('openAccessPdf') else 'N/A'
            }
            papers.append(paper)
    return papers

def create_visualizations_openalex(df):
    yearly_publications = df.groupby('Year').size().reset_index(name='Count')
    yearly_publications = yearly_publications[yearly_publications['Year'] != 'N/A']
    yearly_publications['Year'] = pd.to_numeric(yearly_publications['Year'], errors='coerce')
    yearly_publications = yearly_publications.dropna(subset=['Year']).sort_values('Year')
    fig_yearly_publications = px.bar(yearly_publications, x='Year', y='Count', title='Yearly Publications')
    st.plotly_chart(fig_yearly_publications)

    yearly_citations = df.groupby('Year')['Citations_OpenAlex'].sum().reset_index()
    yearly_citations = yearly_citations[yearly_citations['Year'] != 'N/A']
    yearly_citations['Year'] = pd.to_numeric(yearly_citations['Year'], errors='coerce')
    yearly_citations = yearly_citations.dropna(subset=['Year']).sort_values('Year')
    fig_yearly_citations = px.line(yearly_citations, x='Year', y='Citations_OpenAlex', title='Citations Per Year')
    st.plotly_chart(fig_yearly_citations)

def create_visualizations_crossref(df):
    yearly_publications = df.groupby('Year').size().reset_index(name='Count')
    yearly_publications = yearly_publications[yearly_publications['Year'] != 'N/A']
    yearly_publications['Year'] = pd.to_numeric(yearly_publications['Year'], errors='coerce')
    yearly_publications = yearly_publications.dropna(subset=['Year']).sort_values('Year')
    fig_yearly_publications = px.bar(yearly_publications, x='Year', y='Count', title='Yearly Publications')
    st.plotly_chart(fig_yearly_publications)

    yearly_citations = df.groupby('Year')['Citations'].sum().reset_index()
    yearly_citations = yearly_citations[yearly_citations['Year'] != 'N/A']
    yearly_citations['Year'] = pd.to_numeric(yearly_citations['Year'], errors='coerce')
    yearly_citations = yearly_citations.dropna(subset=['Year']).sort_values('Year')
    fig_yearly_citations = px.line(yearly_citations, x='Year', y='Citations', title='Citations Per Year')
    st.plotly_chart(fig_yearly_citations)

def create_visualizations_semantic_scholar(df):
    yearly_publications = df.groupby('Year').size().reset_index(name='Count')
    yearly_publications = yearly_publications[yearly_publications['Year'] != 'N/A']
    yearly_publications['Year'] = pd.to_numeric(yearly_publications['Year'], errors='coerce')
    yearly_publications = yearly_publications.dropna(subset=['Year']).sort_values('Year')
    fig_yearly_publications = px.bar(yearly_publications, x='Year', y='Count', title='Yearly Publications')
    st.plotly_chart(fig_yearly_publications)

    yearly_citations = df.groupby('Year')['Citations'].sum().reset_index()
    yearly_citations = yearly_citations[yearly_citations['Year'] != 'N/A']
    yearly_citations['Year'] = pd.to_numeric(yearly_citations['Year'], errors='coerce')
    yearly_citations = yearly_citations.dropna(subset=['Year']).sort_values('Year')
    fig_yearly_citations = px.line(yearly_citations, x='Year', y='Citations', title='Citations Per Year')
    st.plotly_chart(fig_yearly_citations)

if __name__ == "__main__":
    main()
