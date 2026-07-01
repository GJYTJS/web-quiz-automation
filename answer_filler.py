# -*- coding: utf-8 -*-
"""
【神圣不可侵犯 — 答案填写器】
======================================
⚠️  AnswerFiller 类的以下 3 个方法修改会破坏模式1：
    - fill()
    - _fill_choice()
    - _fill_text()
"""

import difflib
import random
import re
import time

from selenium.common.exceptions import ElementClickInterceptedException


class AnswerFiller:
    """将答案填写到页面上"""

    @staticmethod
    def _extract_option_texts_from_full(full_text):
        """从题目完整文本中用正则提取选项文本，作为 _get_option_info 失败时的兜底"""
        if not full_text:
            return {}
        # 兼容两种格式：
        # 1) A. 选项文本   （同行）
        # 2) A、\n选项文本  （分行）
        # 用 DOTALL 让 . 匹配换行，lookahead 到下一个选项标记或答案标记
        pattern = r'([A-F])\s*[\.、）)]\s*(.*?)(?=\s*[A-F]\s*[\.、）)]|\s*正确答案|\s*你的作答|\s*$)'
        matches = re.findall(pattern, full_text, re.DOTALL)
        result = {}
        for letter, content in matches:
            content = content.strip()
            # 清理掉多余的换行和空格
            content = re.sub(r'\s+', '', content)
            if content:
                result[letter] = content
        return result

    @staticmethod
    def fill(driver, q_info, answer, answer_texts=None):
        """根据答案类型自动填写"""
        q_type = q_info["type"]
        options = q_info["options"]
        option_texts = q_info.get("option_texts", [])
        full_text = q_info.get("full_text", "")

        # 检测 option_texts 是否有效：
        # 无效情况 = 全空 / 全是纯数字 / 全相同 / 全是"选项X"
        def _option_texts_invalid(ot_list):
            if not ot_list:
                return True
            non_empty = [t for t in ot_list if t and t.strip()]
            if len(non_empty) < len(ot_list):
                return True  # 有空值
            # 全是纯数字（0,1,2,3 是radio的value不是文本）
            if all(re.match(r'^\d+$', t.strip()) for t in ot_list):
                return True
            # 全相同（如全是"选项A"）
            if len(set(t.strip() for t in ot_list)) == 1 and len(ot_list) > 1:
                return True
            return False

        if _option_texts_invalid(option_texts):
            parsed = AnswerFiller._extract_option_texts_from_full(full_text)
            if parsed:
                # 用解析结果重建 option_texts
                new_texts = []
                for i in range(len(options)):
                    letter = chr(65 + i)
                    new_texts.append(parsed.get(letter, ""))
                if any(new_texts):
                    option_texts = new_texts

        try:
            if q_type == "single":
                AnswerFiller._fill_choice(driver, options, option_texts, answer, multi=False, answer_texts=answer_texts)
            elif q_type == "multi":
                AnswerFiller._fill_choice(driver, options, option_texts, answer, multi=True, answer_texts=answer_texts)
            elif q_type == "fill":
                AnswerFiller._fill_text(options, answer)
            elif q_type == "single_text":
                print(f"      ⚠️ 文本型选择题，无法自动点击，请手动选: {answer}")
            else:
                print(f"      ⚠️ 未知题型: {q_type}")
        except Exception as e:
            print(f"      ❌ 填写失败: {e}")

    @staticmethod
    def _fill_choice(driver, options, option_texts, answer, multi=False, answer_texts=None):
        """填写选择题"""
        ans_upper = answer.upper().strip()

        # 清理页面选项文本：去除末尾的UI噪音（上传图片附件（0/9）等）
        def _clean_ot(text):
            if not text:
                return ""
            t = text.strip()
            # 去除"上传图片附件（N/M）"等UI文字
            t = re.sub(r'上传图片附件.*$', '', t)
            # 去除末尾的"查看解析"等
            t = re.sub(r'(查看解析|查看答案|收起解析).*$', '', t)
            return t.strip()

        clean_option_texts = [_clean_ot(ot) for ot in option_texts]

        # 调试输出
        print(f"      🔍 页面选项: {clean_option_texts}")
        print(f"      🔍 答案文本: {answer_texts}")

        # ===== 优先：用答案选项文本内容匹配页面选项 =====
        target_indices = []
        match_method = "none"
        matched_count = 0
        if answer_texts:
            # 单选题只取第一个答案，避免 AI 多返回导致多选
            effective_answers = answer_texts[:1] if not multi else answer_texts
            for at_idx, at in enumerate(effective_answers):
                at_clean = at.strip()
                best_idx = -1
                best_sim = 0
                for i, ot in enumerate(clean_option_texts):
                    if not ot:
                        continue
                    ot_clean = ot.strip()
                    # 完全匹配 → 直接命中
                    if at_clean == ot_clean:
                        best_idx = i
                        best_sim = 1.0
                        break
                    # 答案是选项的子串（选项有UI噪音残留时常见）→ 强匹配
                    if at_clean in ot_clean:
                        best_idx = i
                        best_sim = 0.95
                        continue
                    # 选项是答案的子串
                    if ot_clean in at_clean:
                        sim = len(ot_clean) / len(at_clean) if len(at_clean) > 0 else 0
                        if sim > best_sim:
                            best_idx = i
                            best_sim = sim
                        continue
                    # 模糊匹配（阈值提高到0.78，防止"通货膨胀率"误匹配到"实际利率"）
                    sim = difflib.SequenceMatcher(None, at_clean, ot_clean).ratio()
                    if sim > best_sim and sim > 0.78:
                        best_idx = i
                        best_sim = sim
                if best_idx >= 0:
                    target_indices.append(best_idx)
                    matched_count += 1
                    match_method = "text"

            # 多选题：如果部分答案文本没匹配到，用字母索引补充
            if multi and matched_count < len(answer_texts):
                letters = set(re.findall(r'[A-F]', ans_upper))
                for l in letters:
                    idx = ord(l) - ord('A')
                    if 0 <= idx < len(options) and idx not in target_indices:
                        target_indices.append(idx)
                        match_method = "text+letter"

        # ===== 回退：用字母索引 =====
        if not target_indices:
            match_method = "letter-fallback"
            letters = set(re.findall(r'[A-F]', ans_upper))
            cn_map = {"一": "A", "二": "B", "三": "C", "四": "D", "五": "E", "六": "F"}
            for cn in re.findall(r'[一二三四]', answer):
                letters.add(cn_map.get(cn, ""))
            if "对" in answer or "正确" in answer or "√" in answer or "T" in ans_upper:
                letters = {"A"}
            elif "错" in answer or "错误" in answer or "×" in answer or "F" in ans_upper:
                letters = {"B"}
            # 文本匹配兜底
            if not letters:
                for i, ot in enumerate(clean_option_texts):
                    if ot and any(w in ans for w in ot.split()[:2]
                                  for ans in [answer, ans_upper]):
                        letters.add(chr(65 + i))
            target_indices = sorted({ord(L) - ord('A') for L in letters if 0 <= ord(L) - ord('A') < len(options)})

        if not target_indices:
            match_method = "random"
            target_indices = [random.randint(0, len(options)-1)]

        target_indices = sorted(set(target_indices))
        clicked_letters = [chr(65 + idx) for idx in target_indices]
        print(f"      🔍 匹配方式: {match_method} → 实际点击: {','.join(clicked_letters)}")

        # 多选题：先清除所有已选中的checkbox，避免残留选中导致反选
        if multi:
            for i, el in enumerate(options):
                if i not in target_indices:
                    try:
                        is_checked = el.is_selected()
                        if is_checked:
                            driver.execute_script("arguments[0].click();", el)
                            time.sleep(0.1)
                    except:
                        pass

        clicked = 0
        for idx in target_indices:
            if idx < len(options):
                try:
                    el = options[idx]
                    # 确保元素可见且可点击
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                    time.sleep(0.2)
                    # 多选题：只在未选中时点击（避免点反）
                    if multi:
                        try:
                            if el.is_selected():
                                continue  # 已经选中，不再点
                        except:
                            pass
                    driver.execute_script("arguments[0].click();", el)
                    clicked += 1
                    time.sleep(0.3)
                except ElementClickInterceptedException:
                    try:
                        el.click()
                        clicked += 1
                    except:
                        pass
                except Exception:
                    try:
                        el.click()
                        clicked += 1
                    except:
                        pass

        return clicked

    @staticmethod
    def _fill_text(inputs, answer):
        """填写填空题（支持多空）"""
        clean = answer
        for prefix in ["【答案】", "答案：", "答：", "Answer:", "答案"]:
            if prefix in clean:
                clean = clean.split(prefix)[-1].strip()
        clean = clean.split("\n")[0].strip()[:200]

        # 多空答案分割
        # 检查是否有原始文本标记（parse_pasted_answers 保存的原始答案，保留原始不一致空格）
        raw_text = None
        raw_marker = re.search(r'<<<RAW>>>(.+)', clean)
        if raw_marker:
            raw_text = raw_marker.group(1).strip()
            clean = clean[:raw_marker.start()]

        # 优先按 || 分割（parse_pasted_answers 内部格式）
        if '||' in clean:
            blanks = clean.split('||')
        else:
            # 按 | ; ； 分割
            blanks = re.split(r'[|;；]', clean)
        if len(blanks) == 1:
            # 尝试按 2 个以上空格分割
            blanks = re.split(r'\s{2,}', clean)
        blanks = [b.strip() for b in blanks if b.strip()]

        if not blanks:
            return

        # 调试输出：填空题填写详情
        raw_info = f" 原始文本=[{raw_text}]" if raw_text else ""
        print(f"      📝 填空: {len(blanks)}个答案 / {len(inputs)}个输入框 → {blanks}{raw_info}")

        if len(inputs) >= len(blanks):
            # 输入框数量 ≥ 空数：每个输入框填一个答案
            for idx, inp in enumerate(inputs):
                try:
                    inp.clear()
                    ans = blanks[idx] if idx < len(blanks) else blanks[-1]
                    inp.send_keys(ans)
                except:
                    pass
        else:
            # 输入框数量 < 空数（常见于平台单输入框多空题）：
            # 优先使用原始文本直接填入（保留原始不一致空格），不拆不拼
            for idx, inp in enumerate(inputs):
                try:
                    inp.clear()
                    if idx == 0:
                        if raw_text:
                            # 直接用原始文本，空格数完全原样
                            inp.send_keys(raw_text)
                            print(f"      📝 输入框{idx+1}填入(原始): [{raw_text}]")
                        else:
                            # 没有原始文本标记，用2空格合并
                            merged = '  '.join(blanks)
                            inp.send_keys(merged)
                            print(f"      📝 输入框{idx+1}填入: [{merged}]")
                    else:
                        # 后续输入框留空或循环
                        ans = blanks[idx] if idx < len(blanks) else blanks[-1]
                        inp.send_keys(ans)
                        print(f"      📝 输入框{idx+1}填入: [{ans}]")
                except:
                    pass