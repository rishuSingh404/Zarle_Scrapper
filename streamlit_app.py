# streamlit_app.py

import os, json, tempfile
import streamlit as st
from streamlit_option_menu import option_menu
from scraper import run_scraper, list_difficulties, list_areas, list_chapters

# ─── Page / Theme ─────────────────────────────────────────────────────────────
st.set_page_config("Zarle Scraper", "🤖", "wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
.stApp { background-color:#121212; color:#EEE; }
[data-testid="stSidebar"]{background-color:#1F1F1F;padding-top:1rem;}
header{visibility:hidden;} .block-container{padding-top:0rem;}
button[kind="primary"]{background-color:#9C27B0!important;}
</style>
""", unsafe_allow_html=True)

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="display:flex;flex-direction:column;align-items:center;height:200px">
        <img src="https://raw.githubusercontent.com/rishuSingh404/Zarle/main/logo.png" width="150">
    </div>
    <div style="color:white">
        <h3 style="margin-bottom:.2em">Zarle Scraper UI</h3>
        <p style="margin-top:0">Scrape T4E sectional solutions to JSON.</p>
    </div>
    """, unsafe_allow_html=True)

    selected = option_menu(
        menu_title=None,
        options=["Scrape Questions"],
        icons=["cloud-download"],
        default_index=0,
        orientation="vertical",
        styles={
            "container": {"padding": "0", "background-color": "#1F1F1F"},
            "icon": {"font-size": "20px", "color": "#9C27B0"},
            "nav-link": {"font-size": "16px", "color": "#ECECEC", "text-align": "left"},
            "nav-link-selected": {"background-color": "#9C27B0", "color": "#FFF", "font-weight": "bold"},
        },
    )

# ─── Scrape Questions Panel ───────────────────────────────────────────────────
if selected == "Scrape Questions":
    st.header("📥  Scrape Sectional Solutions")

    # 1) Difficulty dropdown with fallback
    try:
        options_diff = list_difficulties()
        difficulty = st.selectbox("Difficulty", options_diff)
    except Exception:
        difficulty = st.text_input("Difficulty", value="Foundation (Topic-based)")

    # 2) Area dropdown with fallback
    try:
        options_area = list_areas(difficulty)
        area_text = st.selectbox("Area", options_area)
    except Exception:
        area_text = st.text_input("Area Text", value="Quantitative Ability")

    # 3) Chapter dropdown with fallback
    try:
        options_ch = list_chapters(difficulty, area_text)
        chapter_name = st.selectbox("Chapter", options_ch)
    except Exception:
        chapter_name = st.text_input("Chapter Name", value="Numbers")

    level  = st.number_input("Level (int)", 1, 10, 2)
    qtype  = st.number_input("Question Type (int)", 1, 10, 1)

    run = st.button("Run Scraper  ⏳", type="primary")
    if run:
        with st.spinner("⏳ Scraping in progress…"):
            try:
                data = run_scraper(
                    difficulty=difficulty,
                    area_text=area_text,
                    chapter_name=chapter_name,
                    level=int(level),
                    question_type=int(qtype)
                )
            except Exception as e:
                st.error(f"❌ Error during scraping: {e}")
                st.stop()

        st.success(f"✅ Scraped {len(data)} questions successfully!")
        st.markdown("**Preview (first 3 questions):**")
        st.json(data[:3])

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w")
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp.close()

        with open(tmp.name, "rb") as f:
            st.download_button(
                "⬇️  Download JSON",
                data=f,
                file_name=f"{chapter_name.replace(' ','_')}.json",
                mime="application/json",
            )
