# scraper.py

import os
import uuid
import re
import time
import tempfile
import shutil
from urllib.parse import urljoin

import chromedriver_autoinstaller
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, JavascriptException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ─── Credentials from env ─────────────────────────────────────────────────────
USERNAME = os.getenv("T4E_USER")
PASSWORD = os.getenv("T4E_PASS")

# ─── Text cleanup rules ────────────────────────────────────────────────────────
REPLACEMENTS = [
    (r"\[",    ""), (r"\]",    ""),
    (r"\{",    ""), (r"\}",    ""),
    (r"□",     " of "), (r"–", "-"),
    (r"\+",    "+"),  (r"×",   "*"),
    (r"\\frac\{(\d+)\}\{(\d+)\}", r"\1/\2"),
]
def clean_text(s: str) -> str:
    for pat, rep in REPLACEMENTS:
        s = re.sub(pat, rep, s)
    return re.sub(r"\s{2,}", " ", s).strip()

# ─── Start headless Chrome with a unique user-data-dir each time ──────────────
def _start_driver():
    # Auto-install matching chromedriver onto PATH
    chromedriver_autoinstaller.install()

    # Create a fresh profile folder
    user_data_dir = tempfile.mkdtemp(prefix="chrome-user-data-")

    opts = Options()
    opts.headless = True
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,800")
    opts.add_argument(f"--user-data-dir={user_data_dir}")   # <— avoids “in use” conflict
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-background-networking")
    opts.add_argument("--disable-sync")
    opts.add_argument("--metrics-recording-only")
    # disable images
    opts.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2
    })
    opts.set_capability("pageLoadStrategy", "eager")

    # Dynamically locate the Chromium/Chrome binary
    chrome_path = (
        shutil.which("chromium-browser") or
        shutil.which("chromium") or
        shutil.which("google-chrome-stable") or
        shutil.which("google-chrome")
    )
    if not chrome_path:
        raise FileNotFoundError(
            "No Chrome/Chromium binary found on PATH. "
            "On Streamlit Cloud ensure you have an apt.txt installing chromium/chromedriver."
        )
    opts.binary_location = chrome_path

    drv = webdriver.Chrome(options=opts)
    drv.set_page_load_timeout(30)
    return drv

# ─── Login ─────────────────────────────────────────────────────────────────────
def _login(drv):
    drv.get("https://www.time4education.com")
    WebDriverWait(drv, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "a[data-bs-toggle='modal']"))
    ).click()
    WebDriverWait(drv, 10).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "#login"))
    )
    drv.find_element(By.NAME, "username").send_keys(USERNAME)
    drv.find_element(By.NAME, "password").send_keys(PASSWORD)
    try:
        drv.set_page_load_timeout(30)
        drv.find_element(By.CSS_SELECTOR, "input[type=submit]").click()
    except TimeoutException:
        pass
    finally:
        drv.set_page_load_timeout(10)
    WebDriverWait(drv, 15).until(lambda d: "course=MOCK25" in d.current_url)

# ─── Find solution URL ─────────────────────────────────────────────────────────
def _find_solution_url(drv, difficulty, area_text, chapter_name):
    drv.get("https://www.time4education.com/local/timecms/cat_sectionaltest.php")
    WebDriverWait(drv,7).until(EC.presence_of_element_located((By.ID,"ltestCat")))
    Select(drv.find_element(By.ID,"ltestCat")).select_by_visible_text(difficulty)

    WebDriverWait(drv,7).until(lambda d: len(
        d.find_element(By.ID,"areatype").find_elements(By.TAG_NAME,"option")
    )>1)
    Select(drv.find_element(By.ID,"areatype")).select_by_visible_text(area_text)

    tgt = chapter_name.strip().lower()
    while True:
        WebDriverWait(drv,7).until(EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR,"div.cat-tbl tbody tr")
        ))
        rows = drv.find_elements(By.CSS_SELECTOR,"div.cat-tbl tbody tr")
        for r in rows:
            if r.find_element(By.CSS_SELECTOR,"td:nth-child(2)").text.strip().lower() == tgt:
                return r.find_element(By.CSS_SELECTOR,"td:nth-child(4) a#solutionlink")\
                        .get_attribute("href")
        try:
            nxt = drv.find_element(By.ID,"nxtbtn")
            if nxt.is_displayed():
                drv.execute_script("arguments[0].click()", nxt)
                time.sleep(1)
                continue
        except NoSuchElementException:
            break
    raise RuntimeError(f"Chapter '{chapter_name}' not found")

# ─── Parse a single question ───────────────────────────────────────────────────
def _parse_question(drv, test_id, qnum):
    drv.execute_script(f"show_sol({test_id},{qnum});")
    time.sleep(0.2)

    raw = drv.find_element(By.ID,"qst").text.strip()
    question = clean_text(raw)

    opts = []
    for i in range(1,6):
        try:
            p = drv.find_element(By.ID,f"ccch{i}")
            if p.value_of_css_property("display")!="none":
                opts.append(clean_text(p.text.strip()))
        except NoSuchElementException:
            break

    drv.find_element(By.CSS_SELECTOR,"input.show-ans").click()
    time.sleep(0.1)
    correct_letter = None
    for idx, letter in enumerate("abcde",1):
        try:
            span = drv.find_element(By.ID,f"ch{idx}")
            fw = span.value_of_css_property("font-weight")
            if fw and ("700" in fw or "bold" in fw):
                correct_letter = letter
                break
        except NoSuchElementException:
            continue

    sol = None
    try:
        tog = drv.find_element(By.CSS_SELECTOR,"a[data-toggle='collapse']")
        if tog.get_attribute("aria-expanded")=="false":
            drv.execute_script("arguments[0].click()", tog)
            time.sleep(0.1)
        img = drv.find_element(By.CSS_SELECTOR,"div.panel-body img")
        sol = urljoin(drv.current_url, img.get_attribute("src"))
    except NoSuchElementException:
        pass

    answer = None
    if correct_letter:
        idx = ord(correct_letter) - ord('a')
        if 0 <= idx < len(opts):
            answer = opts[idx]

    return {
        "qnum": qnum,
        "question": question,
        "options": opts,
        "correctAnswer": answer,
        "explanation": sol
    }

# ─── Public API ────────────────────────────────────────────────────────────────
def run_scraper(difficulty: str, area_text: str, chapter_name: str, level: int, question_type: int):
    drv = _start_driver()
    try:
        _login(drv)
        sol_url = _find_solution_url(drv, difficulty, area_text, chapter_name)
        drv.get(sol_url)
        time.sleep(1)

        m = re.search(r"show_sol\((\d+),\s*1\)", drv.page_source)
        if not m:
            raise RuntimeError("Could not detect test ID")
        test_id = m.group(1)

        nav = drv.find_elements(By.CSS_SELECTOR,"li.varc-yellow a")
        total = len(nav)

        results = []
        for q in range(1, total+1):
            qd = _parse_question(drv, test_id, q)
            results.append({
                "questionId": str(uuid.uuid4()),
                "originalQuestionNumber": str(qd["qnum"]),
                "question": qd["question"],
                "options": qd["options"],
                "correctAnswer": qd["correctAnswer"],
                "explanation": qd["explanation"],
                "level": level,
                "questionType": question_type
            })
        return results
    finally:
        drv.quit()
