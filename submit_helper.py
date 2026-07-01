# -*- coding: utf-8 -*-
"""提交操作器 — 处理各种提交/重做操作"""

import re
import time

from selenium.webdriver.common.by import By


class SubmitHelper:
    """处理各种提交/重做操作"""

    def __init__(self, driver):
        self.driver = driver

    def find_and_click_submit(self):
        """查找并点击提交按钮"""
        btn = self._find_by_selectors([
            "//button[contains(text(), '提交')]",
            "//button[contains(text(), '交卷')]",
            "//button[contains(text(), '完成')]",
            "//button[contains(text(), '确定')]",
            "//input[@value='提交']",
            "//input[@value='交卷']",
            "//input[@type='submit']",
            "//button[@type='submit']",
            "//*[contains(@class,'submit')]",
            "//*[contains(@id,'submit')]",
        ])
        if btn:
            return True
        # 兜底：动态扫描页面按钮
        return self._scan_and_click(
            keywords=["提交", "交卷", "完成", "submit", "hand in"],
            hint="提交",
        )

    def confirm_dialog_if_any(self):
        # 先试原生 alert/confirm 弹窗（浏览器级，非 DOM）
        try:
            alert = self.driver.switch_to.alert
            text = alert.text
            alert.accept()
            print(f"   ✅ 已确认原生弹窗: {text[:40]}")
            time.sleep(1)
            return True
        except:
            pass

        # DOM 弹窗按钮
        btn = self._find_by_selectors([
            "//button[contains(text(), '确定') or contains(text(), '确认') or contains(text(), '交卷') or contains(text(), 'OK') or contains(text(), '是') or contains(text(), 'Yes') or contains(text(), '好的')]",
            "//div[@role='dialog']//button",
            "//button[contains(@class,'btn-primary')]",
            "//button[contains(@class,'swal2-confirm')]",
        ])
        if btn:
            return True
        # 兜底：dialog/alert 确认
        return self._scan_and_click(
            keywords=["确定", "确认", "交卷", "好的", "OK", "是", "Yes", "知道了"],
            hint="确认",
        )

    def click_retry(self):
        print("\n🔄 寻找「再答一次/再测一次」...")
        btn = self._find_by_selectors([
            "//*[self::a or self::button or self::span][contains(text(), '再答一次') or contains(text(), '再做一次') or contains(text(), '重新答题') or contains(text(), '重做') or contains(text(), '再次')]",
        ])
        if btn:
            return True
        # 兜底
        result = self._scan_and_click(
            keywords=["再答一次", "再测一次", "重新答题", "重做", "再次答题", "再来一次", "retry", "try again"],
            hint="再答/再测",
        )
        if result:
            return True
        print("   ⚠️ 未找到，请手动点击后回车...")
        input()
        return True

    # ─── 内部方法 ────────────────────────────────

    def _find_by_selectors(self, selectors, timeout=1):
        """按预定义选择器列表查找，找到即点击"""
        for sel in selectors:
            try:
                btn = self.driver.find_element(By.XPATH, sel)
                if btn.is_displayed() and self._click(btn):
                    return True
            except:
                continue
        return False

    def _click(self, btn):
        """CDP 直接派发鼠标事件（穿透弹窗覆盖层）"""
        try:
            rect = btn.rect
            x = rect['x'] + rect['width'] / 2
            y = rect['y'] + rect['height'] / 2
            self.driver.execute_cdp_cmd('Input.dispatchMouseEvent', {
                'type': 'mousePressed', 'x': x, 'y': y,
                'button': 'left', 'clickCount': 1,
            })
            self.driver.execute_cdp_cmd('Input.dispatchMouseEvent', {
                'type': 'mouseReleased', 'x': x, 'y': y,
                'button': 'left', 'clickCount': 1,
            })
            return True
        except Exception as e:
            print(f"   ⚠️ CDP点击失败: {type(e).__name__}")

        # 兜底：JS点击
        try:
            self.driver.execute_script("arguments[0].click();", btn)
            return True
        except:
            return False

    def _scan_and_click(self, keywords, hint=""):
        """
        兜底策略：遍历页面上所有可点击元素，按关键词 + 特征打分，点最高分者。
        不依赖预定义选择器，适应任何页面结构。
        """
        candidates = []

        # 收集所有候选按钮
        all_buttons = self.driver.find_elements(By.XPATH,
            "//button | //input[@type='button' or @type='submit'] | "
            "//a[contains(@class,'btn')] | //a[contains(@class,'button')] | "
            "//*[@role='button'] | //*[contains(@class,'submit')] | "
            "//*[contains(@class,'confirm')] | //*[contains(@class,'primary')]"
        )
        for btn in all_buttons:
            try:
                if not btn.is_displayed():
                    continue
                text = (btn.text or btn.get_attribute("value") or "").strip()
                bid = (btn.get_attribute("id") or "").lower()
                bclass = (btn.get_attribute("class") or "").lower()
                btype = (btn.get_attribute("type") or "").lower()

                score = 0.0
                text_lower = text.lower()

                # 文本关键词匹配（最高权重）
                for kw in keywords:
                    if kw.lower() in text_lower:
                        score += 10.0
                    # 子串匹配（"确" 匹配 "确定"）
                    if len(kw) >= 2 and kw.lower()[:2] in text_lower:
                        score += 3.0

                # CSS/ID 特征加分
                for cls_part in ["submit", "confirm", "primary", "btn-ok", "hand-in"]:
                    if cls_part in bclass or cls_part in bid:
                        score += 5.0

                # type=submit 加分
                if btype == "submit":
                    score += 3.0

                # 页面底部优先（通常提交按钮在底部）
                try:
                    loc = btn.location
                    page_h = self.driver.execute_script(
                        "return document.body.scrollHeight")
                    if page_h > 0 and loc["y"] > page_h * 0.5:
                        score += 2.0
                except:
                    pass

                if score > 0:
                    candidates.append((score, text, btn))
            except:
                continue

        if not candidates:
            print(f"   ⚠️ 动态扫描也未找到「{hint}」按钮")
            return False

        # 按分数降序，逐个尝试点击直到成功
        candidates.sort(key=lambda x: -x[0])
        for score, text, btn in candidates:
            print(f"   🎯 动态扫描 → 尝试「{text}」(score={score:.0f})")
            if self._click(btn):
                return True
        print(f"   ⚠️ 所有候选按钮点击均失败（均已消失）")
        return False