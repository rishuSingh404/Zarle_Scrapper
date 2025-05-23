# streamlit_app.py

import os, json, tempfile
import streamlit as st
from streamlit_option_menu import option_menu
from scraper import run_scraper

# ─── Page / Theme ─────────────────────────────────────────────────────────────
st.set_page_config("Zarle Scraper", "🤖", "wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
.stApp { background-color:#121212; color:#EEE; }
[data-testid="stSidebar"]{background-color:#1F1F1F;padding-top:1rem;}
header{visibility:hidden;} .block-container{padding-top:0rem;}
.stFileUploader>label{width:100%;padding:1rem;background-color:#212121;
border:2px dashed #444;border-radius:8px;color:#CCC;}
button[kind="primary"]{background-color:#9C27B0!important;color:white!important;
font-weight:bold;border:none;border-radius:8px;padding:0.6em 1.4em;
transition:background-color .3s ease,transform .2s ease;}
button[kind="primary"]:hover{background-color:#BA68C8!important;transform:scale(1.03);}
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

    difficulty   = st.text_input("Difficulty",    value="Foundation (Topic-based)")
    area_text    = st.text_input("Area Text",     value="Quantitative Ability")
    chapter_name = st.text_input("Chapter Name",  value="Numbers")
    level        = st.number_input("Level (int)",  min_value=1, max_value=10, value=2)
    qtype        = st.number_input("Question Type (int)", min_value=1, max_value=10, value=1)

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

        # write to a temp file for download
        tmp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8")
        json.dump(data, tmp_out, ensure_ascii=False, indent=2)
        tmp_out.close()

        with open(tmp_out.name, "rb") as f:
            st.download_button(
                "⬇️  Download JSON",
                data=f,
                file_name=f"{chapter_name.replace(' ','_')}.json",
                mime="application/json",
            )
