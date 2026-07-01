# -*- coding: utf-8 -*-
"""结果页解析器 - 从提交后的结果页提取正确答案"""

import re
import time

from selenium.webdriver.common.by import By


class ResultParser:
    """解析答题结果页面，提取每道题的正确答案"""

    def __init__(self, driver):
        self.driver = driver

    def parse_correct_answers(self, question_count=None):
        print("\n📊 解析结果页的正确答案...")
        answers = []
        time.sleep(3)
        self._try_switch_result_tab()

        for name, fn in [
            ("平台格式", self._parse_platform_format),
            ("结构解析", self._parse_by_quiz_structure),
        ]:
            try:
                result = fn(question_count)
                if result:
                    print(f"   ✅ 解析到 {len(result)} 题（策略: {name}）")
                    answers = result
                    break
            except Exception as e:
                print(f"   ⚠️ {name} 失败: {e}")

        if not answers:
            print("   ⚠️ 自动解析失败")
        return answers

    def _try_switch_result_tab(self):
        """尝试切换到结果详情tab"""
        tab_selectors = [
            "//a[contains(text(),'个人结果解析')]",
            "//a[contains(text(),'解析')]",
            "//a[contains(text(),'个人解析')]",
            "//a[contains(text(),'结果')]",
            "//span[contains(text(),'解析')]",
            "//span[contains(text(),'个人解析')]",
            "//li[contains(text(),'解析')]",
            "*//button[contains(text(),'查看答案')]",
            "*//a[contains(text(),'答案')]",
        ]
        for sel in tab_selectors:
            try:
                elem = self.driver.find_element(By.XPATH, sel)
                if elem.is_displayed():
                    self.driver.execute_script("arguments[0].click();", elem)
                    print(f"   📑 已切换到结果解析视图")
                    time.sleep(2)
                    return True
            except:
                continue
        return False

    def _parse_platform_format(self, qc):
        """平台专用解析：从整页文本中按'正确答案'和'你的作答'标记提取"""
        try:
            full_text = self.driver.execute_script(
                "return document.body.textContent;") or ""
        except:
            try:
                full_text = self.driver.find_element(By.TAG_NAME, "body").text
            except:
                return []

        if not full_text or len(full_text) < 50:
            return []

        self.raw_result_text = full_text[:8000]

        results = []

        # 找所有题号+题型标记：\n数字\n题型\n
        type_pattern = r'(?:^|\n)\s*(\d+)\s*\n\s*(单选题|多选题|判断题|填空题|简答题|问答题|名词解释|论述题)'
        type_matches = list(re.finditer(type_pattern, full_text))

        # 找所有"正确答案：...你的作答"对
        # 正确答案后面可能跟字母、对/错、或中文文本（填空题）
        answer_pattern = r'正确答案[：:]\s*(.*?)(?=你的作答|暂无解析|(?:\n\s*\d+\s*\n\s*(?:单选题|多选题|判断题|填空题))|\Z)'
        answer_matches = list(re.finditer(answer_pattern, full_text, re.DOTALL))

        for i, ans_m in enumerate(answer_matches):
            raw_answer = ans_m.group(1).strip()

            # 清理：去掉"填空 N："标签
            raw_answer = re.sub(r'填空\s*\d+\s*[：:]', '', raw_answer).strip()
            # 去掉多余空白和换行，但保留多空格分隔的多空答案
            raw_answer = re.sub(r'\n', ' ', raw_answer)
            raw_answer = raw_answer.strip()

            if not raw_answer:
                continue

            # 找对应的题号和题型（在答案位置之前最近的题号+题型标记）
            q_num = i + 1
            q_type_str = ""
            ans_pos = ans_m.start()
            for tm in reversed(type_matches):
                if tm.start() < ans_pos:
                    q_num = int(tm.group(1))
                    q_type_str = tm.group(2)
                    break

            # 如果题号没找到，用序号
            if not q_type_str:
                q_num = i + 1

            # 判断题型
            if '单选' in q_type_str:
                q_type = 'single'
            elif '多选' in q_type_str:
                q_type = 'multi'
            elif '判断' in q_type_str:
                q_type = 'judge'
            elif '填空' in q_type_str:
                q_type = 'fill'
            else:
                # 从答案内容推断
                if raw_answer in ('正确', '错误', '对', '错', '√', '×', 'T', 'F'):
                    q_type = 'judge'
                else:
                    # 去掉逗号空格再判断（处理 "A, B, C" 逗号分隔格式）
                    clean = re.sub(r'[,\s]', '', raw_answer)
                    if re.match(r'^[A-Fa-f]+$', clean):
                        q_type = 'multi' if len(clean) > 1 else 'single'
                    else:
                        q_type = 'fill'

            # 标准化答案格式
            if q_type == 'judge':
                if raw_answer in ('正确', '对', '√', 'T'):
                    raw_answer = '对'
                elif raw_answer in ('错误', '错', '×', 'F'):
                    raw_answer = '错'
            elif q_type in ('single', 'multi'):
                raw_answer = re.sub(r'[,\s]', '', raw_answer).upper()

            results.append({
                "question_index": q_num,
                "correct_answer": raw_answer,
                "type": q_type,
                "raw_text": full_text[max(0, ans_m.start() - 200):ans_m.end() + 50][:300],
            })

        return results

    def _parse_by_quiz_structure(self, qc):
        """策略4：按测验整体结构解析"""
        results = []
        try:
            # 滚动到底部确保全部加载
            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)

            body = self.driver.find_element(By.TAG_NAME, "body").text

            # 分割成可能的题目块
            blocks = re.split(r'\n\s*\n', body)
            for block in blocks:
                if not block.strip():
                    continue
                # 寻找带答案标记的块
                if any(kw in block for kw in ['答案', '正确', 'Answer']):
                    # 提取题目编号
                    num_m = re.search(r'(\d+)[\.\、\s]', block)
                    q_num = int(num_m.group(1)) if num_m else len(results) + 1
                    # 提取答案
                    ans_m = re.search(
                        r'(?:正确|参考|标准)?答案[：:\s]*([A-Fa-f对错√×T F\d]+)', block)
                    if ans_m:
                        results.append({
                            "question_index": q_num,
                            "correct_answer": ans_m.group(1).upper(),
                            "type": "choice",
                        })
        except Exception as e:
            print(f"   ⚠️ 结构解析异常: {e}")

        return results