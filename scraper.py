# scrapper.py
import uuid
import json
import re
import time
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    NoSuchElementException,
    JavascriptException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# -------------------------
# 1) YOUR CREDENTIALS
# -------------------------
USERNAME = "HOCC5T177"
PASSWORD = "9354454550"

# -------------------------
# 2) SCRAPE PARAMETERS
# -------------------------
DIFFICULTY    = "Foundation (Topic-based)"
AREA_TEXT     = "Quantitative Ability"
CHAPTER_NAME  = "Numbers"
OUTPUT_JSON   = "numbers_foundation_q15_clean.json"
LEVEL         = 2
QUESTION_TYPE = 1

# -------------------------
# 3) URL CONSTANTS
# -------------------------
BASE           = "https://www.time4education.com"
SECTIONAL_PAGE = BASE + "/local/timecms/cat_sectionaltest.php"

# -------------------------
# 4) CLEANUP MAPPINGS
# -------------------------
REPLACEMENTS = [
    (r"\[",    ""),
    (r"\]",    ""),
    (r"\{",    ""),
    (r"\}",    ""),
    (r"□",      " of "),
    (r"–",      "-"),
    (r"\+",     "+"),
    (r"×",      "*"),
    (r"\\frac\{(\d+)\}\{(\d+)\}", r"\1/\2"),
]

def clean_text(s: str) -> str:
    for pattern, repl in REPLACEMENTS:
        s = re.sub(pattern, repl, s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()

# -------------------------
# 5) SELENIUM SETUP
# -------------------------
def start_driver():
    opts = Options()
    opts.add_argument("--headless")                 # classic headless
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.set_capability("pageLoadStrategy", "none") # don't wait for everything

    # Block heavy resources
    opts.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
        "profile.managed_default_content_settings.fonts": 2,
    })

    drv = webdriver.Chrome(options=opts)
    drv.set_page_load_timeout(60)   # give it more time in the cloud
    return drv

# -------------------------
# 6) LOGIN
# -------------------------
def selenium_login(drv):
    drv.get(BASE)
    WebDriverWait(drv, 7).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "a[data-bs-toggle='modal']"))
    ).click()
    WebDriverWait(drv, 7).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "form#login"))
    )
    drv.find_element(By.NAME, "username").send_keys(USERNAME)
    drv.find_element(By.NAME, "password").send_keys(PASSWORD)

    submit = drv.find_element(By.CSS_SELECTOR, "input[type=submit]")
    drv.set_page_load_timeout(60)
    try:
        submit.click()
    except TimeoutException:
        pass
    finally:
        drv.set_page_load_timeout(10)

    WebDriverWait(drv, 15).until(lambda d: "course=MOCK25" in d.current_url)
    print("✅ logged in")

# -------------------------
# 7) FIND SOLUTION PAGE
# -------------------------
def get_solution_page_url(drv):
    drv.get(SECTIONAL_PAGE)
    WebDriverWait(drv, 5).until(
        EC.presence_of_element_located((By.ID, "ltestCat"))
    )
    Select(drv.find_element(By.ID, "ltestCat")) \
        .select_by_visible_text(DIFFICULTY)

    WebDriverWait(drv, 5).until(
        lambda d: len(
            d.find_element(By.ID, "areatype")
             .find_elements(By.TAG_NAME, "option")
        ) > 1
    )
    Select(drv.find_element(By.ID, "areatype")) \
        .select_by_visible_text(AREA_TEXT)

    target = CHAPTER_NAME.strip().lower()
    while True:
        WebDriverWait(drv, 5).until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, "div.cat-tbl tbody tr")
            )
        )
        rows = drv.find_elements(By.CSS_SELECTOR, "div.cat-tbl tbody tr")
        for row in rows:
            if row.find_element(By.CSS_SELECTOR, "td:nth-child(2)").text \
                  .strip().lower() == target:
                link = row.find_element(
                    By.CSS_SELECTOR,
                    "td:nth-child(4) a#solutionlink"
                ).get_attribute("href")
                print(f"✅ Found '{CHAPTER_NAME}' → {link}")
                return link

        try:
            nxt = drv.find_element(By.ID, "nxtbtn")
            if nxt.is_displayed():
                drv.execute_script("arguments[0].click();", nxt)
                time.sleep(1)
                continue
        except NoSuchElementException:
            break

    raise RuntimeError(f"Could not find chapter '{CHAPTER_NAME}'")

# -------------------------
# 8) PARSE ONE QUESTION
# -------------------------
def parse_current_q(drv, qnum):
    raw_q = drv.find_element(By.ID, "qst").text.strip()
    text = clean_text(raw_q)

    opts = []
    for i in range(1, 6):
        try:
            p = drv.find_element(By.ID, f"ccch{i}")
            if p.value_of_css_property("display") != "none":
                opts.append(clean_text(p.text.strip()))
        except NoSuchElementException:
            break

    drv.find_element(By.CSS_SELECTOR, "input.show-ans").click()
    time.sleep(0.1)

    correct_letter = None
    for idx, letter in enumerate("abcde", start=1):
        try:
            span = drv.find_element(By.ID, f"ch{idx}")
            fw = span.value_of_css_property("font-weight")
            if fw and (fw == "700" or "bold" in fw):
                correct_letter = letter
                break
        except NoSuchElementException:
            continue

    sol_img = None
    try:
        toggle = drv.find_element(By.CSS_SELECTOR, "a[data-toggle='collapse']")
        if toggle.get_attribute("aria-expanded") == "false":
            drv.execute_script("arguments[0].click()", toggle)
            time.sleep(0.1)
        img = drv.find_element(By.CSS_SELECTOR, "div.panel-body img")
        sol_img = urljoin(drv.current_url, img.get_attribute("src"))
    except NoSuchElementException:
        pass

    correct_text = None
    if correct_letter:
        idx = ord(correct_letter) - ord('a')
        if 0 <= idx < len(opts):
            correct_text = opts[idx]

    return {
        "qnum": qnum,
        "question": text,
        "options": opts,
        "correctAnswer": correct_text,
        "explanation": sol_img
    }

# -------------------------
# 9) WRITE JSON
# -------------------------
def write_json(data):
    formatted = []
    for item in data:
        formatted.append({
            "questionId": str(uuid.uuid4()),
            "originalQuestionNumber": str(item["qnum"]),
            "question": item["question"],
            "options": item["options"],
            "correctAnswer": item["correctAnswer"],
            "explanation": item["explanation"],
            "level": LEVEL,
            "questionType": QUESTION_TYPE
        })
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(formatted, f, ensure_ascii=False, indent=2)
    print(f"✅ Clean JSON written to {OUTPUT_JSON}")

# -------------------------
# 10) MAIN
# -------------------------
def main():
    drv = start_driver()
    try:
        selenium_login(drv)
        sol_url = get_solution_page_url(drv)
        print("🟢 Opening:", sol_url)
        drv.get(sol_url)
        time.sleep(1)

        m = re.search(r"show_sol\((\d+),\s*1\)", drv.page_source)
        if not m:
            raise RuntimeError("Test ID not found")
        test_id = m.group(1)

        nav = drv.find_elements(By.CSS_SELECTOR, "li.varc-yellow a")
        total = len(nav)

        results = [ parse_current_q(drv, 1) ]
        print("✓ scraped Q1")

        for q in range(2, total + 1):
            try:
                drv.execute_script(f"show_sol({test_id},{q});")
            except JavascriptException:
                drv.find_element(By.ID, "nxtbtn") \
                   .click()
            time.sleep(0.3)
            results.append(parse_current_q(drv, q))
            print(f"✓ scraped Q{q}")

        write_json(results)
    finally:
        drv.quit()

if __name__ == "__main__":
    main()
