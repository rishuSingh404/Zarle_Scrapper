import uuid
import re
import time
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ─── Credentials ───────────────────────────────────────────────────────────────
USERNAME = "HOCC5T177"
PASSWORD = "9354454550"

# ─── Cleanup mappings ──────────────────────────────────────────────────────────
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
    for pat, rep in REPLACEMENTS:
        s = re.sub(pat, rep, s)
    return re.sub(r"\s{2,}", " ", s).strip()


# ─── Browser startup ───────────────────────────────────────────────────────────
def _start_driver():
    opts = Options()
    opts.headless = True
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,800")
    opts.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2
    })
    opts.set_capability("pageLoadStrategy", "eager")
    drv = webdriver.Chrome(options=opts)
    drv.set_page_load_timeout(30)
    return drv


# ─── Login helper ──────────────────────────────────────────────────────────────
def _login(drv):
    drv.get("https://www.time4education.com")
    WebDriverWait(drv, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "a[data-bs-toggle='modal']"))
    ).click()
    WebDriverWait(drv, 10).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#login")))
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


# ─── List difficulties ─────────────────────────────────────────────────────────
def list_difficulties() -> list[str]:
    drv = _start_driver()
    try:
        _login(drv)
        drv.get("https://www.time4education.com/local/timecms/cat_sectionaltest.php")
        sel = Select(WebDriverWait(drv,5).until(
            EC.presence_of_element_located((By.ID, "ltestCat"))
        ))
        return [o.text for o in sel.options if o.text.strip()]
    finally:
        drv.quit()


# ─── List areas (depends on difficulty) ────────────────────────────────────────
def list_areas(difficulty: str) -> list[str]:
    drv = _start_driver()
    try:
        _login(drv)
        drv.get("https://www.time4education.com/local/timecms/cat_sectionaltest.php")
        Select(WebDriverWait(drv,5).until((By.ID, "ltestCat"))).select_by_visible_text(difficulty)
        WebDriverWait(drv,5).until(
            lambda d: len(d.find_element(By.ID,"areatype").find_elements(By.TAG_NAME,"option"))>1
        )
        sel = Select(drv.find_element(By.ID, "areatype"))
        return [o.text for o in sel.options if o.text.strip()]
    finally:
        drv.quit()


# ─── List chapters (depends on difficulty+area) ────────────────────────────────
def list_chapters(difficulty: str, area: str) -> list[str]:
    drv = _start_driver()
    try:
        _login(drv)
        drv.get("https://www.time4education.com/local/timecms/cat_sectionaltest.php")
        Select(WebDriverWait(drv,5).until((By.ID, "ltestCat"))).select_by_visible_text(difficulty)
        WebDriverWait(drv,5).until(
            lambda d: len(d.find_element(By.ID,"areatype").find_elements(By.TAG_NAME,"option"))>1
        )
        Select(drv.find_element(By.ID, "areatype")).select_by_visible_text(area)

        WebDriverWait(drv,5).until(EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, "div.cat-tbl tbody tr")
        ))
        rows = drv.find_elements(By.CSS_SELECTOR, "div.cat-tbl tbody tr")
        return [row.find_element(By.CSS_SELECTOR, "td:nth-child(2)").text for row in rows]
    finally:
        drv.quit()


# ─── Scrape runner ─────────────────────────────────────────────────────────────
def run_scraper(
    difficulty: str,
    area_text: str,
    chapter_name: str,
    level: int,
    question_type: int
) -> list[dict]:
    drv = _start_driver()
    try:
        _login(drv)
        # find solution page
        url = _find_solution_url(drv, difficulty, area_text, chapter_name)
        drv.get(url)
        time.sleep(1)

        # extract test_id
        m = re.search(r"show_sol\((\d+),\s*1\)", drv.page_source)
        if not m:
            raise RuntimeError("Test ID not found")
        test_id = m.group(1)

        total = len(drv.find_elements(By.CSS_SELECTOR, "li.varc-yellow a"))
        results = []
        for q in range(1, total+1):
            data = _parse_question(drv, test_id, q)
            results.append({
                "questionId": str(uuid.uuid4()),
                "originalQuestionNumber": str(q),
                "question": data["question"],
                "options": data["options"],
                "correctAnswer": data["correctAnswer"],
                "explanation": data["explanation"],
                "level": level,
                "questionType": question_type
            })
        return results
    finally:
        drv.quit()


# ─── Internal: find solution link ───────────────────────────────────────────────
def _find_solution_url(drv, difficulty, area, chapter):
    drv.get("https://www.time4education.com/local/timecms/cat_sectionaltest.php")
    Select(WebDriverWait(drv,5).until((By.ID, "ltestCat"))).select_by_visible_text(difficulty)
    WebDriverWait(drv,5).until(
        lambda d: len(d.find_element(By.ID,"areatype").find_elements(By.TAG_NAME,"option"))>1
    )
    Select(drv.find_element(By.ID, "areatype")).select_by_visible_text(area)

    target = chapter.strip().lower()
    while True:
        WebDriverWait(drv,5).until(EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, "div.cat-tbl tbody tr")
        ))
        rows = drv.find_elements(By.CSS_SELECTOR, "div.cat-tbl tbody tr")
        for row in rows:
            if row.find_element(By.CSS_SELECTOR,"td:nth-child(2)").text.strip().lower() == target:
                return row.find_element(
                    By.CSS_SELECTOR,"td:nth-child(4) a#solutionlink"
                ).get_attribute("href")
        try:
            nxt = drv.find_element(By.ID, "nxtbtn")
            if nxt.is_displayed():
                drv.execute_script("arguments[0].click()", nxt)
                time.sleep(1)
                continue
        except NoSuchElementException:
            break
    raise RuntimeError(f"Chapter '{chapter}' not found")


# ─── Internal: parse one question ──────────────────────────────────────────────
def _parse_question(drv, test_id, qnum):
    drv.execute_script(f"show_sol({test_id},{qnum});")
    time.sleep(0.2)

    raw = drv.find_element(By.ID, "qst").text.strip()
    question = clean_text(raw)

    opts = []
    for i in range(1,6):
        try:
            p = drv.find_element(By.ID, f"ccch{i}")
            if p.value_of_css_property("display") != "none":
                opts.append(clean_text(p.text.strip()))
        except NoSuchElementException:
            break

    drv.find_element(By.CSS_SELECTOR, "input.show-ans").click()
    time.sleep(0.1)
    letter = None
    for idx,l in enumerate("abcde",1):
        try:
            span = drv.find_element(By.ID, f"ch{idx}")
            fw = span.value_of_css_property("font-weight")
            if fw and ("700" in fw or "bold" in fw):
                letter = l
                break
        except NoSuchElementException:
            continue

    sol = None
    try:
        tog = drv.find_element(By.CSS_SELECTOR, "a[data-toggle='collapse']")
        if tog.get_attribute("aria-expanded") == "false":
            drv.execute_script("arguments[0].click()", tog)
            time.sleep(0.1)
        img = drv.find_element(By.CSS_SELECTOR,"div.panel-body img")
        sol = urljoin(drv.current_url, img.get_attribute("src"))
    except NoSuchElementException:
        pass

    answer = None
    if letter:
        idx = ord(letter) - ord('a')
        if idx < len(opts):
            answer = opts[idx]

    return {"question": question, "options": opts, "correctAnswer": answer, "explanation": sol}
