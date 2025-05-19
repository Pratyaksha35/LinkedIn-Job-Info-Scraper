#linkedin selenium_scraper.py
# LinkedIn Job Scraper
# This script automates the process of logging into LinkedIn, navigating to job listings, and scraping job details.
# It uses Selenium for web automation and BeautifulSoup for parsing HTML.
# The script is designed to be run in a Python environment with the necessary libraries installed.
# It is important to note that web scraping may violate the terms of service of some websites, including LinkedIn.
# Ensure you have permission to scrape the website and comply with its robots.txt file.
# Import necessary libraries
# LinkedIn Job Scraper with Keyword Variable
import os
import csv
import time
import random
import datetime
import traceback

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ──────────────── Configuration ────────────────
USERNAME = "your linkedin email"
PASSWORD = "your password"
JOB_KEYWORD = "Python Developer"  # Change this to search different jobs
# ───────────────────────────────────────────────

def slow_typing(el, text):
    for c in text:
        el.send_keys(c)
        time.sleep(random.uniform(0.05, 0.15))

def find_description(driver, wait):
    candidates = [
        "div.jobs-search__job-details--container .jobs-description-content__text",
        "article.jobs-description__main",
        "[class*='jobs-description-content']",
    ]
    for sel in candidates:
        try:
            el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
            txt = el.text.strip()
            if len(txt) > 20:
                return txt
        except Exception:
            continue
    raise RuntimeError("❌ Could not locate job description.")

def extract_job_metadata(driver, short_wait):
    metadata = {
        "job_title": "N/A",
        "company_name": "N/A",
        "location": "N/A",
        "posted_time": "N/A",
        "location_type": "N/A",
        "contract_type": "N/A",
        "application_type": "Not Easy Apply",
        "job_link": driver.current_url,
    }

    try:
        title_element = short_wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.t-24.t-bold, h1.jobs-unified-top-card__job-title")))
        metadata["job_title"] = title_element.text.strip()
    except Exception:
        print("⚠️ Job title not found")

    try:
        company_element = driver.find_element(By.CSS_SELECTOR, "div.job-details-jobs-unified-top-card__company-name a, span.jobs-unified-top-card__company-name a")
        metadata["company_name"] = company_element.text.strip()
    except NoSuchElementException:
        try:
            company_element = driver.find_element(By.CSS_SELECTOR, "span.jobs-unified-top-card__company-name")
            metadata["company_name"] = company_element.text.strip()
        except NoSuchElementException:
            print("⚠️ Company name not found")

    try:
        desc = short_wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.job-details-jobs-unified-top-card__primary-description-container, div.jobs-unified-top-card__primary-description")))
        spans = desc.find_elements(By.CSS_SELECTOR, "span.tvm__text, span.jobs-unified-top-card__bullet")
        raw_texts = [s.text.strip() for s in spans if s.text.strip()]
        if raw_texts:
            for txt in raw_texts:
                lower = txt.lower()
                if any(unit in lower for unit in ["hour", "minute", "day", "week", "month", "posted"]):
                    if metadata["posted_time"] == "N/A":
                        metadata["posted_time"] = txt
                else:
                    metadata["location"] = metadata["location"] + " · " + txt if metadata["location"] != "N/A" else txt
    except Exception:
        print("⚠️ Description container not found")

    try:
        pills = driver.find_elements(By.CSS_SELECTOR, "button.job-details-preferences-and-skills span.ui-label, li.jobs-unified-top-card__job-insight span")
        for pill in pills:
            text = pill.text.strip().lower()
            if text in ["remote", "hybrid", "on-site"]:
                metadata["location_type"] = text.capitalize()
            elif text in ["full-time", "part-time", "internship", "contract", "temporary", "volunteer"]:
                metadata["contract_type"] = text.capitalize()
    except Exception:
        print("⚠️ Pills not found")

    try:
        apply_btn = driver.find_element(By.CSS_SELECTOR, "button.jobs-apply-button, button.jobs-apply-button--top-card")
        if "easy apply" in apply_btn.text.lower():
            metadata["application_type"] = "Easy Apply"
    except Exception:
        pass

    return metadata

def main():
    base = os.path.expanduser("~/Desktop/linkedin_scraper")
    os.makedirs(base, exist_ok=True)
    csv_path = os.path.join(base, "jobs.csv")
    write_headers = not os.path.exists(csv_path)

    service = Service(ChromeDriverManager().install())
    opts = webdriver.ChromeOptions()
    opts.add_argument("--start-maximized")
    driver = webdriver.Chrome(service=service, options=opts)
    wait = WebDriverWait(driver, 30)

    try:
        print("🔐 Logging in…")
        driver.get("https://www.linkedin.com/login")
        slow_typing(wait.until(EC.presence_of_element_located((By.ID, "username"))), USERNAME)
        slow_typing(wait.until(EC.presence_of_element_located((By.ID, "password"))), PASSWORD)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        wait.until(EC.url_contains("/feed"))
        print("✅ Logged in")

        # Navigate to job search
        print("🌐 Navigating to jobs…")
        search_url = f"https://www.linkedin.com/jobs/search/?keywords={JOB_KEYWORD.replace(' ', '%20')}"
        driver.get(search_url)
        jobs_list = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.scaffold-layout__list")))
        print("📋 Job list ready")

        fieldnames = [
            "job_title", "company_name", "location", "posted_time",
            "location_type", "contract_type", "application_type",
            "job_link", "description", "timestamp"
        ]
        csv_file = open(csv_path, "a", encoding="utf-8", newline="")
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        if write_headers:
            writer.writeheader()

        page = 1
        while True:
            print(f"➡️  Scraping page {page}…")
            for _ in range(8):
                driver.execute_script("arguments[0].scrollBy(0, 400);", jobs_list)
                time.sleep(0.3)

            cards = jobs_list.find_elements(By.CSS_SELECTOR, "li.scaffold-layout__list-item")
            print(f"🔍 Found {len(cards)} cards on page {page}")

            for i, card in enumerate(cards, start=1):
                try:
                    driver.execute_script("arguments[0].scrollIntoView(true);", card)
                    card.click()
                    time.sleep(2)

                    metadata = extract_job_metadata(driver, wait)
                    metadata["description"] = find_description(driver, wait)
                    metadata["timestamp"] = datetime.datetime.now().isoformat()

                    writer.writerow(metadata)
                    csv_file.flush()

                    print(f"✅ Page {page} • Job #{i} → {metadata['job_title']}")
                except Exception as e:
                    print(f"⚠️ Page {page} • Skipped job #{i}: {e}")

            try:
                next_btn = driver.find_element(By.XPATH, f"//button[span/text()='{page + 1}']")
                next_btn.click()
                page += 1
                time.sleep(1)
                jobs_list = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.scaffold-layout__list")))
            except Exception:
                print("🏁 Pagination ended or button not found.")
                break

    finally:
        csv_file.close()
        driver.quit()
        print("🛑 Done.")

if __name__ == "__main__":
    main()
# This script is intended for educational purposes only. Use it responsibly and ethically.