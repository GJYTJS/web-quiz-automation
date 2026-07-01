# -*- coding: utf-8 -*-
"""主流程 — 入口、模式选择、主循环"""

import glob
import json
import os
import re
import sys
import time
from datetime import datetime

from answer_engine import AnswerEngine
from answer_filler import AnswerFiller
from browser import BrowserManager
from config import load_config
from detector import QuestionDetector
from matcher import match_page_question
from paste_parser import parse_pasted_answers
from result_parser import ResultParser
from submit_helper import SubmitHelper


def print_banner():
    print("\n" + "=" * 60)
    print("     全自动答题 v4.0 -- 多模式")
    print("=" * 60)
    print("  模式1: 粘贴答案文本（推荐）")
    print("  模式2: AI自动答题")
    print("  模式3: 全自动答题（乱填→解析→满分）")
    print("  模式4: 解析结果页正确答案并保存")
    print("  (模式1/2由你手动提交，模式3全自动)")
    print("=" * 60 + "\n")


def ai_auto_mode(driver, detector, filler, submitter, engine):
    """模式2：AI自动答题"""
    print("\n" + "▶" * 30)
    print("  【AI自动答题模式】")
    print("▶" * 30)

    print("\n🔍 正在识别题目...")
    questions = detector.detect_all()

    if not questions:
        print("⚠️  未识别到题目！")
        input("按回车返回菜单...")
        return

    print(f"\n✅ 共识别到 {len(questions)} 道题目\n")

    filled_count = 0
    for q in questions:
        q_type = q.get("type", "unknown")
        type_label = {"single": "单选", "multi": "多选", "fill": "填空",
                      "judge": "判断", "unknown": "未知"}.get(q_type, "?")
        print(f"\n📝 第{q['index']}/{len(questions)} 题 [{type_label}]: {q['text'][:60]}...")

        success, answer = engine.answer(
            q["text"],
            options=q.get("option_texts"),
            q_type=q_type,
            full_text=q.get("full_text", ""),
        )
        if success:
            # 获取AI返回的答案文本（用于选项文本匹配）
            answer_texts = getattr(engine, '_last_answer_texts', [])
            display = answer[:50]
            if answer_texts:
                display += f" ({', '.join(t[:15] for t in answer_texts)})"
            print(f"   🤖 AI答案: {display}")
            filler.fill(driver, q, answer, answer_texts=answer_texts)
            filled_count += 1
            print(f"   ✅ 已填写")
        else:
            print(f"   ❌ 答题失败: {answer}")
        time.sleep(1)

    print(f"\n✅ 答题完成！共 {filled_count}/{len(questions)} 题")

    print("\n" + "-" * 40)
    print("✅ 所有答案已填写完毕！")
    print("请在浏览器中检查填写情况，然后手动点击提交按钮。")
    print("-" * 40)
    input("提交完成后，按回车继续...")
    print("✅ 已继续")


def _refresh_file_list(answer_dir, max_show):
    files = sorted(glob.glob(os.path.join(answer_dir, "answers_*.json")),
                   key=os.path.getmtime, reverse=True)
    return files, files[:max_show], max(0, len(files) - max_show)


def _count_answers(fpath):
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            return len(json.load(f))
    except:
        return "?"


def _pick_answer_file(answer_dir):
    """交互式选择已保存的答案文件，或粘贴新答案。返回 answer_db 或 None(贴新)"""
    max_show = 15
    all_files, files, more = _refresh_file_list(answer_dir, max_show)
    if not all_files:
        return None

    while True:
        print(f"\n已保存的答案文件 (共{len(all_files)}个{', 显示最近{}个'.format(max_show) if more else ''}):")
        for i, f in enumerate(files, 1):
            mtime = datetime.fromtimestamp(os.path.getmtime(f)).strftime("%m/%d %H:%M")
            count = _count_answers(f)
            name = os.path.basename(f).replace("answers_", "").replace(".json", "")
            print(f"  {i:>2}. [{mtime}] {name} ({count}题)")

        print("\n  命令：")
        print("    编号 → 加载该文件")
        print("    N    → 粘贴新答案")
        if files:
            print("    d N  → 删除第N个")
            print("    r N  → 重命名第N个")
            if more:
                print("    s kw → 搜索关键词（如 s 数学）")
        choice = input("\n> ").strip()

        if choice.upper() == "N":
            return None

        # 删除: d3 / d 3 / dn3
        dm = re.match(r'^[Dd]\s*N?\s*(\d+)$', choice)
        if dm:
            idx = int(dm.group(1)) - 1
            if 0 <= idx < len(files):
                os.remove(files[idx])
                print(f"🗑️  已删除 #{dm.group(1)}")
                all_files, files, more = _refresh_file_list(answer_dir, max_show)
                continue
            print("❌ 编号无效")
            continue

        # 重命名: r1 / r 1 / rn1
        rm = re.match(r'^[Rr]\s*N?\s*(\d+)$', choice)
        if rm:
            idx = int(rm.group(1)) - 1
            if 0 <= idx < len(files):
                old_path = files[idx]
                new_name = input("新名称: ").strip()
                if new_name:
                    safe = re.sub(r'[\\/:*?"<>|]', '_', new_name)
                    new_path = os.path.join(answer_dir, f"answers_{safe}.json")
                    os.rename(old_path, new_path)
                    print(f"✏️  已重命名")
                    all_files, files, more = _refresh_file_list(answer_dir, max_show)
                    continue
                print("❌ 名称不能为空")
                continue
            print("❌ 编号无效")
            continue

        # 搜索: s 关键词
        sm = re.match(r'^[Ss]\s+(.+)$', choice)
        if sm:
            kw = sm.group(1)
            hits = [f for f in all_files if kw in os.path.basename(f)]
            if hits:
                files = hits
                more = 0
                continue
            print(f"❌ 未找到含「{kw}」的文件")
            continue

        # 加载
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(files):
                try:
                    with open(files[idx], "r", encoding="utf-8") as f:
                        db = json.load(f)
                    print(f"✅ 已加载: {os.path.basename(files[idx])} ({len(db)} 题)")
                    return db
                except Exception as e:
                    print(f"❌ 加载失败: {e}")
                    continue

        print("❌ 无效输入")
        continue


def _paste_new_answers(answer_dir):
    """粘贴文本 → 解析 → 命名保存"""
    print("\n" + "=" * 60)
    print("📋 请粘贴答题结果文本（含「正确答案：B」等标记）")
    print("   粘贴完后，在新行输入 END 结束")
    print("=" * 60)

    lines = []
    print("\n开始粘贴（输入 END 结束）：")
    while True:
        line = input()
        if line.strip().upper() == 'END':
            break
        lines.append(line)

    raw_text = '\n'.join(lines)
    if not raw_text.strip():
        print("❌ 没有输入任何文本！")
        return None

    print("\n🔍 正在解析答案文本...")
    raw_db = parse_pasted_answers(raw_text)
    if not raw_db:
        print("❌ 未解析出任何答案（请确认文本包含「正确答案：」）")
        return None

    answer_db = {}
    for k, v in raw_db.items():
        answer_db[k] = {
            "answer": v["answer"],
            "text": v["text"],
            "type": v.get("type", "choice"),
            "answer_texts": v.get("answer_texts", []),
            "_q_normalized": v.get("_q_normalized", k),
        }

    print(f"\n✅ 解析出 {len(answer_db)} 道题：")
    for i, (_, info) in enumerate(answer_db.items(), 1):
        label = {"single": "单选", "multi": "多选", "fill": "填空", "judge": "判断"}.get(info.get("type", "choice"), "选择")
        print(f"  {i:>2}. [{label}] {info['answer'][:20]}  ←  {info['text'][:40]}")

    name = input("\n给这份答案起个名字（直接回车=用时间戳）: ").strip()
    if not name:
        name = datetime.now().strftime("%m%d_%H%M")
    safe = re.sub(r'[\\/:*?"<>|]', '_', name) if name else datetime.now().strftime("%m%d_%H%M")
    save_path = os.path.join(answer_dir, f"answers_{safe}.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(answer_db, f, ensure_ascii=False, indent=2)
    print(f"💾 已保存: answers_{safe}.json")

    return answer_db


def _fill_with_answers(driver, detector, filler, answer_db, auto=False):
    """用 answer_db 识别页面题目并填写。auto=True 时不等待手动确认。"""
    questions = detector.detect_all()
    if not questions:
        print("⚠️  未识别到题目，按回车重试...")
        input()
        questions = detector.detect_all()
        if not questions:
            print("❌ 仍然无法识别。")
            return

    print(f"\n✅ 识别到 {len(questions)} 道题")

    matched_count = 0
    unmatched = []
    for q in questions:
        page_text = q["text"]
        answer, score, answer_texts = match_page_question(page_text, answer_db, page_q_type=q.get("type"))
        if answer:
            print(f"📝 第{q['index']}题 [匹配度:{score:.0%}] → {answer[:20]}", end="")
            AnswerFiller.fill(driver, q, answer, answer_texts=answer_texts)
            print(" ✅")
            matched_count += 1
        else:
            print(f"📝 第{q['index']}题 → ❌ 未匹配 (最高:{score:.0%})")
            unmatched.append(q)
        time.sleep(0.3)

    print(f"\n📊 {matched_count}/{len(questions)} 题已填写")

    if unmatched:
        print(f"\n⚠️  {len(unmatched)} 题未匹配：")
        for q in unmatched:
            print(f"  第{q['index']}题: {q['text'][:50]}")
        print("\n可手动作答或切AI模式补答")

    if not auto:
        print("\n✅ 填写完毕，请检查后手动提交。")
        input("提交完成后按回车继续...")


def _fill_random_one(driver, questions):
    """只随机填一道题（交卷用，填一题就能看所有正确答案）"""
    import random as _random
    if not questions:
        return
    q = _random.choice(questions)
    q_type = q.get("type")
    try:
        if q_type == "single":
            idx = _random.randint(0, len(q["options"]) - 1) if q["options"] else 0
            AnswerFiller._fill_choice(driver, q["options"], q.get("option_texts", []),
                                      chr(65 + idx), multi=False)
        elif q_type == "multi":
            idx = _random.randint(0, len(q["options"]) - 1) if q["options"] else 0
            AnswerFiller._fill_choice(driver, q["options"], q.get("option_texts", []),
                                      chr(65 + idx), multi=True)
        elif q_type == "fill":
            for inp in q["options"]:
                try:
                    inp.clear()
                    inp.send_keys(" ")
                except:
                    pass
        elif q_type == "judge":
            v = _random.choice(["对", "错"])
            AnswerFiller._fill_choice(driver, q["options"], q.get("option_texts", []),
                                      v, multi=False)
        print(f"   📝 随机填了第{q['index']}题 ({q_type})")
    except Exception as e:
        print(f"   ⚠️ 随机填写失败: {e}")
        time.sleep(0.15)


def full_auto_mode(driver, detector, filler, submitter):
    """
    模式3：全自动答题
    第1轮：乱填 → 提交 → 确认弹窗 → 个人解析 → 解析正确答案 → 返回 → 再测一次 → 填正确答案 → 满分提交
    """
    print("\n" + "▸" * 30)
    print("  【全自动答题模式（乱填→解析→满分）】")
    print("▸" * 30)

    questions = detector.detect_all()
    if not questions:
        print("❌ 未识别到题目")
        return
    print(f"\n📊 共 {len(questions)} 题")
    # 保存题目原文，第二轮用来文本匹配
    round1_questions = [(q["text"], q.get("type", "choice")) for q in questions]

    # ===== 第1轮：随机填一道题 =====
    print("\n--- 第1轮：随机填一道题 ---")
    _fill_random_one(driver, questions)
    time.sleep(1)

    # ===== 提交第1轮 =====
    print("\n--- 提交第1轮 ---")
    if not submitter.find_and_click_submit():
        print("❌ 找不到提交按钮，按回车重试（我将检查页面结构）")
        input()
        return
    time.sleep(2)

    # 第一层弹窗确认
    if not submitter.confirm_dialog_if_any():
        print("   ⏸️ 确认弹窗未找到，按回车让我检查页面...")
        input()
    time.sleep(2)

    # 第二层弹窗确认
    if not submitter.confirm_dialog_if_any():
        print("   ⏸️ 第二层弹窗未找到，按回车让我检查...")
        input()
    time.sleep(3)

    # ===== 切换到个人解析，获取正确答案 =====
    print("\n--- 解析正确答案 ---")
    time.sleep(2)
    parser = ResultParser(driver)
    # 先手动切到"个人解析" tab（ResultParser 的自动切换可能漏掉这个词）
    if not _try_click_result_tab(driver, ["个人结果解析", "个人解析", "解析", "答题详情", "查看解析", "结果"]):
        print("   ⏸️ 找不到结果tab，按回车让我检查页面...")
        input()
    time.sleep(2)

    raw_answers = parser.parse_correct_answers(question_count=len(questions))
    if not raw_answers:
        print("📄 页面文本 → 直接读取 body 文本再试...")
        # 强制用文本模式解析
        raw_answers = parser._parse_platform_format(len(questions))
    if not raw_answers:
        print("⚠️  未解析到正确答案，手动复制后可用模式1")
        return

    print(f"   ✅ 解析到 {len(raw_answers)} 题正确答案")

    # 用第一轮检测到的题目原文建库，按题号配对
    # 格式同模式1的 answer_db → 直接喂给 _fill_with_answers
    answer_db = {}
    for i, ra in enumerate(raw_answers):
        idx = ra["question_index"]
        q_type = ra.get("type", "choice")
        answer = ra["correct_answer"]
        real_text = round1_questions[idx - 1][0] if 1 <= idx <= len(round1_questions) else f"第{idx}题"
        # 从结果页 raw_text 提取选项文本（如果有）
        answer_texts = []
        raw_ctx = ra.get("raw_text", "")
        if raw_ctx:
            from answer_filler import AnswerFiller as _AF
            opts = _AF._extract_option_texts_from_full(raw_ctx)
            for letter in answer:
                if letter in opts:
                    answer_texts.append(opts[letter])
        key = f"{real_text}__{q_type}"
        answer_db[key] = {
            "answer": answer,
            "text": real_text,
            "type": q_type,
            "answer_texts": answer_texts,
            "_q_normalized": real_text,
        }
    print(f"   📝 建库完成，第二轮走文本匹配")

    # ===== 返回答题页 / 再测一次 =====
    print("\n--- 返回答题页 ---")
    # 先试浏览器返回（平台结果页点左上返回箭头 = 回到测验）
    try:
        driver.back()
        print("   🔙 已浏览器返回")
        time.sleep(3)
    except:
        pass

    # 找再做一次按钮
    _try_click_result_tab(driver, ["再做一次", "再答一次", "重新答题", "重做", "再次答题", "再来一次"])
    time.sleep(1)

    if not submitter.click_retry():
        print("⚠️  未找到再测按钮，请手动操作后按回车...")
        input()
    time.sleep(3)

    # 点击「开始作答」
    _try_click_result_tab(driver, ["开始作答", "开始答题", "开始"])
    time.sleep(3)

    # ===== 第2轮：直接复用模式1的填写流程 =====
    print("\n--- 第2轮：填写正确答案 ---")
    time.sleep(3)

    _fill_with_answers(driver, detector, filler, answer_db, auto=True)

    # ===== 提交第2轮（满分） =====
    print("\n--- 提交第2轮 ---")
    time.sleep(1)
    if submitter.find_and_click_submit():
        time.sleep(2)
        submitter.confirm_dialog_if_any()
        time.sleep(1)
        submitter.confirm_dialog_if_any()
        print("\n🎉 全自动答题完成！满分提交！")
    else:
        print("\n⚠️  答案已填好，请手动提交")
        input()

    input("\n按回车继续...")


def _try_click_result_tab(driver, keywords, search_all="button,a,span"):
    """在结果页寻找并点击指定关键词的 tab/按钮"""
    for kw in keywords:
        try:
            btn = driver.find_element(By.XPATH,
                f"//*[self::button or self::a or self::span][contains(text(), '{kw}')]")
            if btn.is_displayed():
                driver.execute_script("arguments[0].scrollIntoView({block:'center'}); arguments[0].click();", btn)
                time.sleep(1)
                print(f"   📑 已点击「{kw}」")
                return True
        except:
            pass
    return False


def paste_answer_mode(driver, detector, filler, submitter):
    """模式1：粘贴答案文本 → 自动匹配填写（支持答案文件管理）"""
    print("\n" + "▸" * 30)
    print("  【粘贴答案文本模式】")
    print("▸" * 30)

    answer_dir = os.path.dirname(os.path.abspath(__file__))

    # 答案文件管理
    answer_db = _pick_answer_file(answer_dir)
    if answer_db is None:
        answer_db = _paste_new_answers(answer_dir)
    if not answer_db:
        return

    _fill_with_answers(driver, detector, filler, answer_db)


def parse_result_page(driver):
    """模式4：解析当前个人结果页的正确答案并保存"""
    print("\n" + "▸" * 30)
    print("  【解析个人结果页】")
    print("▸" * 30)

    # 用 result_parser 提取正确答案（内部会切到解析tab）
    from result_parser import ResultParser
    from paste_parser import _normalize_question as _norm_q
    parser = ResultParser(driver)
    raw = parser.parse_correct_answers()
    if not raw:
        print("❌ 页面未找到正确答案，请确认已在个人结果解析页")
        return

    # 读全页文本，按题号+题型切块
    full_text = driver.execute_script("return document.body.textContent;") or ""
    type_pattern = r'(?:^|\n)\s*(\d+)\s*\n\s*(单选题|多选题|判断题|填空题)'
    blocks = list(re.finditer(type_pattern, full_text))
    block_map = {}
    for i, m in enumerate(blocks):
        q_num = int(m.group(1))
        next_start = blocks[i + 1].start() if i + 1 < len(blocks) else len(full_text)
        block_map[q_num] = full_text[m.end():next_start].strip()

    # 转成 answer_db 格式（含题目文本和选项文本）
    answer_db = {}
    for ra in raw:
        idx = ra["question_index"]
        q_type = ra.get("type", "choice")
        answer = ra["correct_answer"]

        # 优先用全页块提取，降级到 raw_ctx
        block = block_map.get(idx, "")
        if block:
            q_text, option_texts = _extract_from_block(block)
        else:
            raw_ctx = ra.get("raw_text", "")[:500]
            q_text, option_texts = _parse_raw_context(raw_ctx)

        if not q_text:
            q_text = f"第{idx}题"

        type_label = {"single": "单选", "multi": "多选", "judge": "判断", "fill": "填空"}.get(q_type, "选择")
        display_opts = ", ".join(t[:15] for t in option_texts[:4])
        print(f"  {idx:>2}. [{type_label}] {answer:15s}  {q_text[:50]}  [{display_opts}]")

        key = f"{q_text}__{q_type}"
        # 只保存正确答案的选项文本，不是全部（否则模式1 _fill_choice 取 answer_texts[:1] 永远取到A）
        answer_texts_for_db = []
        if option_texts:
            letters = re.findall(r'[A-F]', answer.upper())
            for l in letters:
                idx = ord(l) - ord('A')
                if 0 <= idx < len(option_texts) and option_texts[idx]:
                    answer_texts_for_db.append(option_texts[idx])
        answer_db[key] = {
            "answer": answer,
            "text": q_text,
            "type": q_type,
            "answer_texts": answer_texts_for_db or option_texts,
            "_q_normalized": _norm_q(q_text),
        }

    print(f"\n✅ 共 {len(answer_db)} 题")
    name = input("\n保存为（回车=时间戳）: ").strip()
    if not name:
        name = datetime.now().strftime("%m%d_%H%M")
    safe = re.sub(r'[\\/:*?"<>|]', '_', name)
    save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"answers_{safe}.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(answer_db, f, ensure_ascii=False, indent=2)
    print(f"💾 已保存: answers_{safe}.json")
    print("\n💡 选模式1加载此文件，自动匹配填写")


def _extract_from_block(block_text):
    """从全页切出的每题完整块中提取题目文本和选项"""
    if not block_text:
        return "", []

    lines = block_text.split('\n')

    # 找第一个选项标记
    opt_start = -1
    for i, line in enumerate(lines):
        if re.match(r'[A-F]\s*[\.、\)\s:：]', line.strip()):
            opt_start = i
            break

    # 提取题目：跳过 metadata 行（| 、分 、页码、难度）
    q_lines = []
    for line in lines[:opt_start] if opt_start >= 0 else lines:
        s = line.strip()
        if not s or s.startswith('|') or '分' in s or re.match(r'^\d+页$', s):
            continue
        if s in ('简单', '一般', '困难', '中等', '容易'):
            continue
        q_lines.append(s)
    q_text = ' '.join(q_lines).strip()

    # 提取选项
    options = []
    if opt_start >= 0:
        flat = ' '.join(line.strip() for line in lines[opt_start:])
        parts = re.split(r'(?=[A-F]\s*[\.、\)\s:：])', flat)
        for p in parts:
            p = p.strip()
            pm = re.match(r'[A-F]\s*[\.、\)\s:：]+(.*)', p)
            if pm:
                txt = pm.group(1).strip()
                txt = re.sub(r'正确答案.*|你的作答.*|暂无解析.*|\d+页', '', txt).strip()
                if txt:
                    options.append(txt)

    return q_text, options


def _parse_raw_context(raw_ctx):
    """从 raw_text 提取题目文本和选项文本
    修复：不依赖难度标记、不依赖换行，直接在扁平文本上搜索
    """
    if not raw_ctx:
        return "", []

    # 以最后一个"正确答案"为锚点（raw_ctx 可能包含上一题的正确答案）
    parts = raw_ctx.rsplit('正确答案', 1)
    ctx = parts[0].strip()
    if not ctx:
        return "", []

    # 直接搜所有"数字+题型"标记，取最后一个
    type_matches = list(re.finditer(r'(\d+)\s*(单选题|多选题|判断题|填空题)', ctx))
    cut = 0
    if type_matches:
        cut = type_matches[-1].end()  # 从题型标记的最后开始

    text = ctx[cut:]

    q_text = ''
    options = []

    # 找第一个选项标记 A. / A、 / A)
    m = re.search(r'[A-F]\s*[\.、\)\s:：]', text)
    if m:
        q_text = text[:m.start()].strip()
        # 清理杂音
        q_text = re.sub(r'简单|一般|困难|中等|容易', '', q_text)
        q_text = re.sub(r'\d+页', '', q_text)
        q_text = re.sub(r'\d+\s*分', '', q_text)
        q_text = q_text.replace('|', '').strip()

        # 提取选项
        opt_str = text[m.start():]
        parts = re.split(r'(?=[A-F]\s*[\.、\)\s:：])', opt_str)
        for p in parts:
            p = p.strip()
            pm = re.match(r'[A-F]\s*[\.、\)\s:：]+(.*)', p)
            if pm:
                txt = pm.group(1).strip()
                txt = re.sub(r'正确答案.*|你的作答.*|暂无解析.*|\d+页', '', txt).strip()
                if txt:
                    options.append(txt)
    else:
        q_text = text

    return q_text, options


def run_one_round(driver, config, cli_mode=None):
    """执行一轮答题，返回后可继续下一轮"""
    engine = AnswerEngine(config)
    detector = QuestionDetector(driver)
    filler = AnswerFiller()
    submitter = SubmitHelper(driver)
    parser = ResultParser(driver)

    # 选择模式
    if cli_mode in ("1", "2", "3", "4"):
        mode = cli_mode
        print(f"\n📋 自动选择模式 {mode}")
    else:
        print("\n" + "=" * 60)
        print("请选择答题模式：")
        print("  1️⃣  粘贴答案文本（你粘贴结果→自动匹配填写）⭐推荐")
        print("  2️⃣  AI自动答题（AI直接回答并填写）")
        print("  3️⃣  全自动答题（乱填→解析→满分）✨")
        print("  4️⃣  解析个人结果页（手动交卷后点此提取正确答案）")
        mode = input("\n请输入模式编号 (1/2/3/4): ").strip()

    if mode not in ("1", "2", "3", "4"):
        print("❌ 无效选择，跳过本轮")
        return

    # 按模式分流
    if mode == "1":
        paste_answer_mode(driver, detector, filler, submitter)
    elif mode == "2":
        ai_auto_mode(driver, detector, filler, submitter, engine)
    elif mode == "3":
        full_auto_mode(driver, detector, filler, submitter)
    elif mode == "4":
        parse_result_page(driver)


def main():
    print_banner()

    # CLI 参数
    cli_url = None
    cli_mode = None
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg.startswith("--url="):
            cli_url = arg.split("=", 1)[1]
        elif arg == "--mode" and i < len(sys.argv) - 1:
            cli_mode = sys.argv[i + 1]

    # 加载配置
    try:
        config = load_config()
    except FileNotFoundError:
        print("❌ 找不到 config.json")
        input("按回车退出...")
        return

    if "你的API密钥" in config.get("api_key", ""):
        print("❌ 请先在 config.json 中填入 API Key！")
        input("按回车退出...")
        return

    # 输入网址
    if cli_url:
        url = cli_url
        print(f"\n🌐 目标网址: {url[:80]}{'...' if len(url)>80 else ''}")
    else:
        url = input("请输入答题网址（URL）: ").strip()
        if not url:
            print("❌ 网址不能为空")
            return
    if not url.startswith("http"):
        url = "https://" + url
    print("🚀 正在启动 Edge 浏览器...\n")

    # 启动浏览器
    browser = BrowserManager(headless=False)
    try:
        driver = browser.start()
        print("✅ Edge 启动成功")
    except Exception as e:
        print(f"❌ 浏览器启动失败: {e}")
        input("按回车退出...")
        return

    # 打开网址
    try:
        browser.open_url(url)
        print(f"✅ 已打开网页")
        print("⏳ 等待页面加载（10秒）...")
        time.sleep(10)
    except Exception as e:
        print(f"❌ 打开网页失败: {e}")
        browser.quit()
        input("按回车退出...")
        return

    # ===== 等待登录 =====
    print("\n" + "-" * 60)
    print("⚠️  如果需要登录，请在浏览器中完成登录操作")
    print("    登录成功后，按回车键继续...")
    print("-" * 60)
    input()

    # ===== 主循环：可连续答题 =====
    while True:
        # 执行一轮
        run_one_round(driver, config, cli_mode)

        # 本轮完成，问下一步
        print("\n" + "=" * 60)
        print("🎉 本轮答题完成！")
        print("=" * 60)
        print("  1️⃣  继续答题（同一页面，重新选模式）")
        print("  2️⃣  打开新网址（在浏览器中导航到新答题页）")
        print("  3️⃣  退出")
        print("-" * 60)
        choice = input("请选择 (1/2/3): ").strip()

        if choice == "1":
            # 同一页面继续，直接进入下一轮
            print("\n🔄 准备下一轮答题...")
            continue

        elif choice == "2":
            # 打开新网址
            new_url = input("请输入新的答题网址: ").strip()
            if new_url:
                if not new_url.startswith("http"):
                    new_url = "https://" + new_url
                print(f"\n🌐 正在打开: {new_url[:80]}...")
                try:
                    browser.open_url(new_url)
                    print("⏳ 等待页面加载（8秒）...")
                    time.sleep(8)
                    print("✅ 页面已打开")
                except Exception as e:
                    print(f"❌ 打开失败: {e}")
            continue

        elif choice == "3":
            print("\n👋 正在退出...")
            browser.quit()
            print("👋 已退出，再见！")
            break

        else:
            print("❌ 无效选择，默认继续...")
            continue