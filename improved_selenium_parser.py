#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Selenium парсер AppExchange (2025) с точечными селекторами и проходом через shadow DOM.

Ищем:
- name:      .listing-title h1
- developer: .listing-title p
- image:     .listing-logo img
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
import requests
from PIL import Image
from io import BytesIO
import re
import time


# ---------- JS-хелперы для поиска по селектору через все shadowRoot ----------
_JS_QUERY_SELECTOR_DEEP = r"""
const selector = arguments[0];

function qsd(sel, root) {
  root = root || document;

  // Прямая попытка внутри текущего root
  if (root.querySelector) {
    const direct = root.querySelector(sel);
    if (direct) return direct;
  }

  // Обойти все элементы и «проколоть» их shadowRoot
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
  let node = walker.currentNode;
  while (node) {
    if (node.shadowRoot) {
      const found = qsd(sel, node.shadowRoot);
      if (found) return found;
    }
    node = walker.nextNode();
  }
  return null;
}
return qsd(selector, document);
"""

def find_element_deep(driver, selector: str, timeout: int = 25):
    """
    Возвращает первый элемент по CSS-селектору, проходя через все shadowRoot.
    Бросает TimeoutException, если не найден за отведённое время.
    """
    return WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script(_JS_QUERY_SELECTOR_DEEP, selector),
        message=f"Не найден элемент (включая shadow DOM): {selector}"
    )


def parse_appexchange_improved(url: str):
    """
    Парсит страницу листинга AppExchange.
    Достаёт: name (.listing-title h1), developer (.listing-title p), logo_url (.listing-logo img).
    """
    print(f"🔍 Старт парсинга: {url}")

    # ---- Настройки Chrome ----
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)

        # Мини-маскировка webdriver-флага
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # Переход
        driver.get(url)

        # Небольшой буфер на первичную инициализацию SPA/веб-компонентов
        time.sleep(2)

        # ===== NAME (.listing-title h1) =====
        app_name = None
        print("🔎 Ищем название по селектору .listing-title h1 (с учётом shadow DOM)...")
        try:
            name_el = find_element_deep(driver, ".listing-title h1", timeout=30)
            app_name = (name_el.text or "").strip()
            print(f"✅ Название: {app_name}")
        except TimeoutException:
            print("⚠️ Не нашли .listing-title h1 — используем <title> как запасной вариант")
            # fallback из <title>
            title = (driver.title or "").strip()
            if title:
                app_name = re.sub(r"\s*\|\s*(Salesforce\s+)?AppExchange.*$", "", title, flags=re.IGNORECASE).strip()
                if app_name:
                    print(f"ℹ️ Название из <title>: {app_name}")

        # Нормализация хвостов «| AppExchange»
        if app_name:
            app_name = re.sub(r"\s*\|\s*(Salesforce\s+)?AppExchange.*$", "", app_name, flags=re.IGNORECASE).strip()

        # ===== DEVELOPER (.listing-title p) =====
        developer = None
        print("🔎 Ищем разработчика по селектору .listing-title p ...")
        try:
            dev_el = find_element_deep(driver, ".listing-title p", timeout=15)
            developer = (dev_el.text or "").strip()
            print(f"✅ Разработчик (как есть): {developer}")
        except TimeoutException:
            print("⚠️ Не нашли .listing-title p — оставим Unknown Developer")

        # ===== LOGO (.listing-logo img) =====
        logo_url = None
        print("🔎 Ищем логотип по селектору .listing-logo img ...")
        try:
            img_el = find_element_deep(driver, ".listing-logo img", timeout=15)
            src = (img_el.get_attribute("src") or "").strip()
            if src:
                logo_url = ("https:" + src) if src.startswith("//") else src
                print(f"✅ Логотип: {logo_url}")
        except TimeoutException:
            print("⚠️ Не нашли .listing-logo img — пробуем meta og:image")
            try:
                og_img = driver.find_element("css selector", 'meta[property="og:image"]')
                logo_url = og_img.get_attribute("content")
                if logo_url:
                    print(f"ℹ️ Логотип из og:image: {logo_url}")
            except Exception:
                pass

        result = {
            "name": app_name or "Unknown App",
            "developer": developer or "Unknown Developer",
            "logo_url": logo_url,
            "success": bool(app_name)
        }

        print("🎯 Результат парсинга:")
        print(f"   Название:    {result['name']}")
        print(f"   Разработчик: {result['developer']}")
        print(f"   Логотип:     {result['logo_url']}")
        return result

    except Exception as e:
        print(f"❌ Ошибка парсинга: {e}")
        return {
            "name": "Parsing Error",
            "developer": "Unknown",
            "logo_url": None,
            "success": False,
            "error": str(e),
        }
    finally:
        if driver:
            driver.quit()


def download_logo(logo_url: str, target_size=(100, 100)):
    """
    Скачивает логотип и приводit к заданному максимуму размера (thumbnail).
    Возвращает PIL.Image или None.
    """
    if not logo_url:
        return None
    try:
        resp = requests.get(logo_url, timeout=10)
        if resp.status_code == 200:
            img = Image.open(BytesIO(resp.content))
            img.thumbnail(target_size)
            return img
    except Exception:
        pass
    return None


# ===== Тест =====
if __name__ == "__main__":
    test_url = "https://appexchange.salesforce.com/appxListingDetail?listingId=01dbaf61-02e0-4bc8-a8db-2ddbf30719ed"
    print("=== ТЕСТОВЫЙ ЗАПУСК SELENIUM ПАРСЕРА ===")
    result = parse_appexchange_improved(test_url)

    print("\n🎯 Финальный результат:")
    print(f"Название:    {result['name']}")
    print(f"Разработчик: {result['developer']}")
    print(f"Логотип:     {result['logo_url']}")
    print(f"Успех:       {result['success']}")
