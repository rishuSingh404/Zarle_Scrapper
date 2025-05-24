# scraper.py
import os
import uuid
import re
import time
from urllib.parse import urljoin

import chromedriver_autoinstaller
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ─── Credentials from env (for Streamlit) ─────────────────────────────────────
USERNAME = os.getenv("T4E_USER")
PASSWORD = os.getenv("T4E_PASS")

# ─── Public API: called by streamlit_app.py ─────────────────────────────────────
def run_scraper(difficulty: str,
                area_text: str,
                chapter_name: str,
                level: int,
                question_type: int) -> list[dict]:
    """
    Runs the full scrape and returns a list of question dicts.
    """
    driver = _start_driver()
    try:
        _login(driver)
        sol_url = _find_solution_url(driver, difficulty, area_text, chapter_name)
        driver.get(sol_url)
        time.sleep(1)

        m = re.search(r"show_sol\((\d+),\s*1\)", driver.page_source)
        if not m:
            raise RuntimeError("Could not detect test ID")
        test_id = m.group(1)

        nav = driver.find_elements(By.CSS_SELECTOR, "li.varc-yellow a")
        total = len(nav)

        results = []
        for q in range(1, total + 1):
            results.append(_parse_question(driver, test_id, q))
        return [{
            "questionId": str(uuid.uuid4()),
            "originalQuestionNumber": str(item["qnum"]),
            "question": item["question"],
            "options": item["options"],
            "correctAnswer": item["correctAnswer"],
            "explanation": item["explanation"],
            "level": level,
            "questionType": question_type
        } for item in results]
    finally:
        driver.quit()

# ─── Internal helpers ───────────────────────────────────────────────────────────
def _start_driver():
    # install matching chromedriver
    path = chromedriver_autoinstaller.install()
    service = Service(path)

    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.set_capability("pageLoadStrategy", "none")
    opts.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
        "profile.managed_default_content_settings.fonts": 2,
    })
    optsbinary = os.getenv("CHROME_BIN", "/usr/bin/chromium")
    opts.binary_location = optsbinary

    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(60)
    return driver

def _login(driver):
    driver.get("https://www.time4education.com")
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "a[data-bs-toggle='modal']"))
    ).click()
    WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "form#login"))
    )
    driver.find_element(By.NAME, "username").send_keys(USERNAME)
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    try:
        driver.set_page_load_timeout(30)
        driver.find_element(By.CSS_SELECTOR, "input[type=submit]").click()
    except TimeoutException:
        pass
    finally:
        driver.set_page_load_timeout(10)
    WebDriverWait(driver, 15).until(lambda d: "course=MOCK25" in d.current_url)

def _find_solution_url(driver, difficulty, area_text, chapter_name):
    driver.get("https://www.time4education.com/local/timecms/cat_sectionaltest.php")
    WebDriverWait(driver, 7).until(EC.presence_of_element_located((By.ID, "ltestCat")))
    Select(driver.find_element(By.ID, "ltestCat")).select_by_visible_text(difficulty)
    WebDriverWait(driver, 7).until(
        lambda d: len(d.find_element(By.ID, "areatype").find_elements(By.TAG_NAME, "option")) > 1
    )
    Select(driver.find_element(By.ID, "areatype")).select_by_visible_text(area_text)

    tgt = chapter_name.strip().lower()
    while True:
        WebDriverWait(driver,7).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR,"div.cat-tbl tbody tr"))
        )
        rows = driver.find_elements(By.CSS_SELECTOR,"div.cat-tbl tbody tr")
        for r in rows:
            if r.find_element(By.CSS_SELECTOR,"td:nth-child(2)").text.strip().lower() == tgt:
                return r.find_element(By.CSS_SELECTOR,"td:nth-child(4) a#solutionlink")\
                        .get_attribute("href")
        try:
            nxt = driver.find_element(By.ID,"nxtbtn")
            if nxt.is_displayed():
                driver.execute_script("arguments[0].click()", nxt)
                time.sleep(1)
                continue
        except NoSuchElementException:
            break
    raise RuntimeError(f"Chapter '{chapter_name}' not found")

def _parse_question(driver, test_id, qnum):
    driver.execute_script(f"show_sol({test_id},{qnum});")
    time.sleep(0.2)

    raw = driver.find_element(By.ID,"qst").text.strip()
    question = _clean_text(raw)

    opts = []
    for i in range(1,6):
        try:
            p = driver.find_element(By.ID,f"ccch{i}")
            if p.value_of_css_property("display")!="none":
                opts.append(_clean_text(p.text.strip()))
        except NoSuchElementException:
            break

    driver.find_element(By.CSS_SELECTOR,"input.show-ans").click()
    time.sleep(0.1)
    correct = None
    for idx, letter in enumerate("abcde",1):
        try:
            span = driver.find_element(By.ID,f"ch{idx}")
            fw = span.value_of_css_property("font-weight")
            if fw and ("700" in fw or "bold" in fw):
                correct = letter
                break
        except NoSuchElementException:
            continue

    sol = None
    try:
        tog = driver.find_element(By.CSS_SELECTOR,"a[data-toggle='collapse']")
        if tog.get_attribute("aria-expanded")=="false":
            driver.execute_script("arguments[0].click()", tog)
            time.sleep(0.1)
        img = driver.find_element(By.CSS_SELECTOR,"div.panel-body img")
        sol = urljoin(driver.current_url, img.get_attribute("src"))
    except NoSuchElementException:
        pass

    answer = None
    if correct:
        idx = ord(correct) - ord('a')
        if 0 <= idx < len(opts):
            answer = opts[idx]

    return {
        "qnum": qnum,
        "question": question,
        "options": opts,
        "correctAnswer": answer,
        "explanation": sol
    }

def _clean_text(s: str) -> str:
    REPLACEMENTS = [
        (r"\[", ""), (r"\]", ""),
        (r"\{", ""), (r"\}", ""),
        (r"□", " of "), (r"–", "-"),
        (r"\+", "+"),  (r"×", "*"),
        (r"\\frac\{(\d+)\}\{(\d+)\}", r"\1/\2"),
    ]
    for pat, rep in REPLACEMENTS:
        s = re.sub(pat, rep, s)
    return re.sub(r"\s{2,}", " ", s).strip()
