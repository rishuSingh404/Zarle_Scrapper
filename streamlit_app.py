import streamlit as st
import tempfile, json
from scraper import run_scraper  # see below

# ─── UI Setup ──────────────────────────────────────────────────────────────────
st.set_page_config("T4E Scraper", "🤖", "wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
.stApp { background-color:#121212; color:#EEE; }
[data-testid="stSidebar"]{background-color:#1F1F1F;}
button[kind="primary"]{background-color:#9C27B0!important;}
</style>
""", unsafe_allow_html=True)

st.sidebar.title("Time4Edu Scraper")
difficulty   = st.sidebar.selectbox("Difficulty", ["Foundation (Topic-based)", "Advanced", "..."])
area_text    = st.sidebar.selectbox("Area", ["Quantitative Ability", "Verbal Ability", "..."])
chapter_name = st.sidebar.text_input("Chapter Name", value="Numbers")

run = st.sidebar.button("Run Scraper", type="primary")

# ─── Main ─────────────────────────────────────────────────────────────────────
if run:
    with st.spinner("Scraping… this may take 30s"):
        try:
            data = run_scraper(difficulty, area_text, chapter_name)
        except Exception as e:
            st.error(f"❌ Error: {e}")
        else:
            st.success(f"✅ {len(data)} questions scraped.")
            st.json(data[:3])  # preview first 3

            # download button
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w")
            json.dump(data, tmp, ensure_ascii=False, indent=2)
            tmp.close()
            st.download_button(
                "⬇ Download full JSON",
                data=open(tmp.name, "rb"),
                file_name=f"{chapter_name}.json",
                mime="application/json",
            )
