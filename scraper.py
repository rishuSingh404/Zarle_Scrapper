# scraper.py

import os
import uuid
import re
import time
from urllib.parse import urljoin

import chromedriver_autoinstaller  # new!
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
    (r"\+",    "+"), (r"×",   "*"),
    (r"\\frac\{(\d+)\}\{(\d+)\}", r"\1/\2"),
]
def clean_text(s: str) -> str:
    for pat, rep in REPLACEMENTS:
        s = re.sub(pat, rep, s)
    return re.sub(r"\s{2,}", " ", s).strip()

# ─── Updated start_driver() uses chromedriver_autoinstaller ───────────────────
def _start_driver():
    # install a matching chromedriver (will be placed on PATH)
    chromedriver_autoinstaller.install()

    opts = Options()
    opts.headless = True
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1280,800")
    # on Streamlit Cloud the binary is chromium-browser; locally you can install chromium too
    opts.binary_location = "/usr/bin/chromium-browser"

    # disable images for speed
    opts.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2
    })
    # return once DOMContentLoaded
    opts.set_capability("pageLoadStrategy", "eager")

    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(30)
    return driver

# ─── Login ─────────────────────────────────────────────────────────────────────
def _login(driver):
    driver.get("https://www.time4education.com")
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "a[data-bs-toggle='modal']"))
    ).click()
    WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#login")))
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

# ─── Find solution URL ─────────────────────────────────────────────────────────
def _find_solution_url(driver, difficulty, area_text, chapter_name):
    driver.get("https://www.time4education.com/local/timecms/cat_sectionaltest.php")
    Select(WebDriverWait(driver,7).until(
        EC.presence_of_element_located((By.ID, "ltestCat"))
    )).select_by_visible_text(difficulty)

    WebDriverWait(driver, 7).until(lambda d: len(
        d.find_element(By.ID, "areatype").find_elements(By.TAG_NAME, "option")
    ) > 1)
    Select(driver.find_element(By.ID, "areatype")).select_by_visible_text(area_text)

    tgt = chapter_name.strip().lower()
    while True:
        WebDriverWait(driver, 7).until(EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, "div.cat-tbl tbody tr")))
        rows = driver.find_elements(By.CSS_SELECTOR, "div.cat-tbl tbody tr")
        for r in rows:
            if r.find_element(By.CSS_SELECTOR, "td:nth-child(2)").text.strip().lower() == tgt:
                return r.find_element(
                    By.CSS_SELECTOR, "td:nth-child(4) a#solutionlink"
                ).get_attribute("href")
        try:
            nxt = driver.find_element(By.ID, "nxtbtn")
            if nxt.is_displayed():
                driver.execute_script("arguments[0].click()", nxt)
                time.sleep(1)
                continue
        except NoSuchElementException:
            break
    raise RuntimeError(f"Chapter '{chapter_name}' not found")

# ─── Parse a single question ───────────────────────────────────────────────────
def _parse_question(driver, test_id, qnum):
    driver.execute_script(f"show_sol({test_id},{qnum});")
    time.sleep(0.2)

    raw = driver.find_element(By.ID, "qst").text.strip()
    question = clean_text(raw)

    opts = []
    for i in range(1, 6):
        try:
            p = driver.find_element(By.ID, f"ccch{i}")
            if p.value_of_css_property("display") != "none":
                opts.append(clean_text(p.text.strip()))
        except NoSuchElementException:
            break

    driver.find_element(By.CSS_SELECTOR, "input.show-ans").click()
    time.sleep(0.1)
    correct_letter = None
    for idx, letter in enumerate("abcde", 1):
        try:
            span = driver.find_element(By.ID, f"ch{idx}")
            fw = span.value_of_css_property("font-weight")
            if fw and ("700" in fw or "bold" in fw):
                correct_letter = letter
                break
        except NoSuchElementException:
            continue

    sol = None
    try:
        tog = driver.find_element(By.CSS_SELECTOR, "a[data-toggle='collapse']")
        if tog.get_attribute("aria-expanded") == "false":
            driver.execute_script("arguments[0].click()", tog)
            time.sleep(0.1)
        img = driver.find_element(By.CSS_SELECTOR, "div.panel-body img")
        sol = urljoin(driver.current_url, img.get_attribute("src"))
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
            qd = _parse_question(driver, test_id, q)
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
        driver.quit()
