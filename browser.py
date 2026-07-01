# -*- coding: utf-8 -*-
"""浏览器管理器 — 支持新启动和 CDP 远程连接"""

import time

from selenium import webdriver
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from webdriver_manager.microsoft import EdgeChromiumDriverManager


class BrowserManager:
    """浏览器管理 — 支持新启动和 CDP 远程连接"""

    def __init__(self, headless=False, cdp_port=None, user_data_dir=None):
        self.driver = None
        self.headless = headless
        self.cdp_port = cdp_port
        self.user_data_dir = user_data_dir

    def start(self):
        if self.cdp_port:
            return self._connect_cdp()

        options = EdgeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1367,900")
        options.add_argument("--remote-debugging-port=9222")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        if self.user_data_dir:
            options.add_argument(f"--user-data-dir={self.user_data_dir}")

        self.driver = webdriver.Edge(
            service=EdgeService(EdgeChromiumDriverManager().install()),
            options=options,
        )
        self._hide_webdriver()
        return self.driver

    def _connect_cdp(self):
        """通过 CDP 连接到已有浏览器（省去启动浏览器时间）"""
        opts = EdgeOptions()
        opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{self.cdp_port}")
        self.driver = webdriver.Edge(options=opts)
        return self.driver

    def _hide_webdriver(self):
        self.driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

    def open_url(self, url):
        self.driver.get(url)

    def wait(self, seconds):
        time.sleep(seconds)

    def scroll_to_top(self):
        self.driver.execute_script("window.scrollTo(0, 0);")

    def scroll_to_bottom(self):
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

    def quit(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass