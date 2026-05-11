import os
from playwright.sync_api import sync_playwright

def run_cuj(page):
    file_path = "file://" + os.path.abspath("Branded_Card_Final.html")
    page.goto(file_path)
    page.wait_for_load_state("networkidle")
    page.screenshot(path="branded_verification_final.png", full_page=True)
    print(f"Screenshot saved to branded_verification_final.png")

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(viewport={'width': 1280, 'height': 800})
    page = context.new_page()
    run_cuj(page)
    browser.close()
