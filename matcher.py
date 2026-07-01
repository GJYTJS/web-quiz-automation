# -*- coding: utf-8 -*-
"""
【神圣不可侵犯 — 题目匹配器】
======================================
⚠️  match_page_question()
    修改会破坏模式 1 的已有功能
"""

import difflib
import re

from paste_parser import _normalize_question


def match_page_question(page_q_text, answer_db, threshold=0.3, page_q_type=None):
    """
    将页面上的题目与答案数据库匹配。
    返回: (answer, score) 或 (None, score)
    page_q_type: 页面题目的类型 ("fill", "single", "multi", "judge")，用于优先匹配同类型答案
    """
    page_normalized = _normalize_question(page_q_text)

    if not page_normalized or len(page_normalized) < 3:
        return None, 0, []

    best_match = None
    best_score = 0

    for db_key, db_info in answer_db.items():
        score = 0
        db_type = db_info.get("type", "choice")
        # 用 _q_normalized 字段做匹配（db_key 现在包含 __type 后缀）
        db_q = db_info.get("_q_normalized", db_key)

        # 类型匹配加成/惩罚：防止填空题匹配到选择题答案（如把"C"填进输入框）
        if page_q_type and db_type:
            if page_q_type == "fill" and db_type == "fill":
                score += 0.05      # 填空→填充：加分优先
            elif page_q_type == "judge" and db_type == "judge":
                score += 0.05      # 判断→判断：加分优先
            elif page_q_type in ("single", "multi") and db_type in ("single", "multi"):
                score += 0.03      # 选择→选择：加分
            elif page_q_type == "fill" and db_type in ("single", "multi"):
                score -= 0.5       # 填空题匹配到选择题答案：严重惩罚！
            elif page_q_type in ("single", "multi") and db_type == "fill":
                score -= 0.3       # 选择题匹配到填空答案：惩罚

        # 方法1: 整体相似度
        score = max(score, difflib.SequenceMatcher(None, page_normalized, db_q).ratio())

        # 方法2: 包含关系
        if page_normalized in db_q or db_q in page_normalized:
            score = max(score, 0.9)

        # 方法3: 取题目核心部分（前30/50字符）比较
        for length in [30, 50, 80]:
            page_key = page_normalized[:length]
            db_key_short = db_q[:length]
            if page_key and db_key_short:
                key_score = difflib.SequenceMatcher(None, page_key, db_key_short).ratio()
                score = max(score, key_score)

        # 方法4: 最长公共子串
        sm = difflib.SequenceMatcher(None, page_normalized, db_q)
        match_blocks = sm.get_matching_blocks()
        longest_match = 0
        for block in match_blocks:
            longest_match = max(longest_match, block.size)
        # 如果最长公共子串超过15个字符，说明很可能匹配
        if longest_match >= 15:
            ratio = longest_match / min(len(page_normalized), len(db_q))
            score = max(score, min(ratio, 0.95))

        # 方法5: 关键短语匹配 - 提取连续中文片段
        page_phrases = re.findall(r'[一-龥]{4,}', page_normalized)
        db_phrases = re.findall(r'[一-龥]{4,}', db_q)
        if page_phrases and db_phrases:
            page_kw_set = set(page_phrases)
            db_kw_set = set(db_phrases)
            overlap = len(page_kw_set & db_kw_set)
            total = len(page_kw_set | db_kw_set)
            if total > 0:
                kw_score = overlap / total
                score = max(score, kw_score * 0.85)

        # 方法6: 子串包含关键词
        for phrase in page_phrases:
            if len(phrase) >= 6 and phrase in db_q:
                score = max(score, 0.8)
        for phrase in db_phrases:
            if len(phrase) >= 6 and phrase in page_normalized:
                score = max(score, 0.8)

        if score > best_score:
            best_score = score
            best_match = db_info

    if best_score >= threshold and best_match:
        return best_match["answer"], best_score, best_match.get("answer_texts", [])
    return None, best_score, []