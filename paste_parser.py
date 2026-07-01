# -*- coding: utf-8 -*-
"""
【神圣不可侵犯 — 粘贴答案解析器】
======================================
⚠️  parse_pasted_answers() + 辅助函数
    修改任何一个都会破坏模式 1 的已有功能

支持的格式（平台/学习通结果页复制文本）：

    1
    单选题
    |
    1 分
    |
    简单
    党的（   ）以来，中国特色社会主义进入新时代。
    A. 十七大
    B. 十八大
    ...
    正确答案： B
    你的作答： B
"""

import re


def parse_pasted_answers(raw_text):
    """
    解析用户粘贴的答题结果文本，返回 {题目文本: 答案} 映射。

    支持的格式（平台/学习通结果页复制文本）：

        1
        单选题
        |
        1 分
        |
        简单
        党的（   ）以来，中国特色社会主义进入新时代。
        A. 十七大
        B. 十八大
        ...
        正确答案： B
        你的作答： B
    """
    answer_db = {}  # {normalized_question: {"answer": "B", "text": "原始题目", "type": "single"}}

    # 按"正确答案"分割成块
    # 每块前半部分包含题目，后半部分包含答案
    parts = re.split(r'正确答案[:：\s]*', raw_text)

    for i in range(1, len(parts)):
        part = parts[i].strip()

        # 从前一个 part 提取题目文本
        prev_part = parts[i - 1]

        # 检测题型：只看 prev_part 中最后一个题型标记
        # （prev_part 可能包含多道题，只取离"正确答案"最近的）
        q_type = "choice"  # 默认选择题
        type_matches = list(re.finditer(
            r'(单选题|多选题|判断题|填空题|简答题|问答题|名词解释|论述题)', prev_part
        ))
        if type_matches:
            last_type = type_matches[-1].group(1)
            if '填空' in last_type:
                q_type = "fill"
            elif '判断' in last_type:
                q_type = "judge"

        # 提取题目文本（提前提取，填空题需要用来数空数）
        q_text = _extract_question_text_from_block(prev_part)

        # 提取答案行（第一行）
        answer_line = part.split('\n')[0].strip()

        if q_type == "fill":
            # 填空题格式：
            #   填空 1：
            #    货币
            #   你的作答：...
            # 或多空格式：
            #   填空 1：
            #    平行本位制    双本位制
            #   （有些多空答案只用1个空格分隔，如"现金 存款"）
            # 先数题目中有几个空（按"（）"计数）
            blank_count = q_text.count('（）') + q_text.count('（  ）') + q_text.count('（ ）')
            if blank_count < 1:
                blank_count = 1

            # 先去掉"你的作答"之后的内容
            answer_section = re.split(r'你的作答|你的答案', part)[0].strip()
            all_lines = [l for l in answer_section.split('\n')]
            # 跳过"填空 N："标签行，提取实际答案文本
            fill_answers = []
            raw_original_text = None  # 保留原始空格的答案文本（单输入框多空题原样填入）
            for line in all_lines:
                line_stripped = line.strip()
                if not line_stripped:
                    continue
                if re.match(r'^填空\s*\d+\s*[：:]\s*$', line_stripped):
                    continue
                cleaned = re.sub(r'^填空\s*\d+\s*[：:]\s*', '', line_stripped).strip()
                if not cleaned:
                    continue
                # 保存原始文本（保留内部空格，用于单输入框多空题原样填入）
                if raw_original_text is None:
                    raw_original_text = cleaned
                # 同一行可能有多个空，优先用2+空格分隔
                sub_parts = re.split(r'\s{2,}', cleaned)
                # 如果2+空格拆分不够且题目有多个空，尝试用1+空格拆分
                used_1space = False
                if len(sub_parts) < blank_count and blank_count > 1:
                    sub_parts_1s = re.split(r'\s+', cleaned)
                    if len(sub_parts_1s) >= blank_count:
                        sub_parts = sub_parts_1s
                        used_1space = True

                # 检测原始答案中的空白分隔符（不再需要，用raw_original_text代替）

                for sp in sub_parts:
                    sp = sp.strip()
                    if sp:
                        fill_answers.append(sp)
            # 多空答案用 || 分隔保存，附加 <<<RAW>>>原始文本（保留原始不一致空格）
            # _fill_text 单输入框时直接使用原始文本，不拆不拼
            base_answer = '||'.join(fill_answers) if fill_answers else None
            if base_answer and raw_original_text and len(fill_answers) > 1:
                answer = base_answer + '<<<RAW>>>' + raw_original_text
            else:
                answer = base_answer
        else:
            # 选择题/判断题：提取字母
            answer_match = re.findall(r'[A-Fa-f]', answer_line)
            if not answer_match:
                # 可能是"对"/"错"
                if '对' in answer_line or '正确' in answer_line or '√' in answer_line:
                    answer = 'A'
                elif '错' in answer_line or '错误' in answer_line or '×' in answer_line:
                    answer = 'B'
                else:
                    answer = None
            else:
                answer = ''.join(answer_match).upper()

            # 提取选项文本映射，根据答案字母获取选项文本内容
            # （解决平台每次重做选项顺序随机打乱的问题）
            option_map = _extract_options_from_block(prev_part)
            answer_texts = []
            for letter in answer:
                if letter in option_map:
                    answer_texts.append(option_map[letter])

        if not answer:
            continue

        if q_text and answer:
            q_normalized = _normalize_question(q_text)
            # 用 (标准化文本, 类型) 组合作为 key
            # 同一题目可能同时出现在填空和选择中（如第2题），需要分别保存
            db_key = f"{q_normalized}__{q_type}"
            answer_db[db_key] = {
                "answer": answer,
                "text": q_text,
                "type": q_type,
                "answer_texts": answer_texts if q_type != "fill" else [],
                "_q_normalized": q_normalized,  # 保留原始标准化文本用于匹配
            }

    return answer_db


def _extract_question_text_from_block(block_text):
    """从结果块中提取纯题目文本（最后一个难度标记到第一个选项之间）"""
    lines = block_text.strip().split('\n')

    # 找最后一个难度标记的位置（因为 block 可能包含多道题）
    last_difficulty_idx = -1
    for idx, line in enumerate(lines):
        line_stripped = line.strip()
        if line_stripped in ("简单", "一般", "困难", "中等"):
            last_difficulty_idx = idx

    if last_difficulty_idx < 0:
        # 没有难度标记，尝试从最后一个题型标记开始
        last_type_idx = -1
        for idx, line in enumerate(lines):
            line_stripped = line.strip()
            if line_stripped in ("单选题", "多选题", "判断题", "填空题", "简答题"):
                last_type_idx = idx
        if last_type_idx >= 0:
            last_difficulty_idx = last_type_idx
        else:
            return ""

    q_lines = []
    for line in lines[last_difficulty_idx + 1:]:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # 遇到选项标记停止
        if re.match(r'^[A-F][\.、\)\s]', line_stripped) or line_stripped in (
            'A.', 'A、', 'A)', 'A', 'B.', 'B、', 'B)', 'B',
            'C.', 'C、', 'C)', 'C', 'D.', 'D、', 'D)', 'D',
            'E.', 'E、', 'E)', 'E', 'F.', 'F、', 'F)', 'F',
        ):
            break

        # 判断题选项
        if line_stripped in ('正确', '错误', '对', '错', '√', '×'):
            break

        # 填空题的"* 答案"提示行
        if line_stripped.startswith('* 答案') or line_stripped.startswith('*答案'):
            continue

        # 遇到"你的作答"等标记，停止
        if '你的作答' in line_stripped or '你的答案' in line_stripped:
            break

        # 遇到"填空 N"标签（填空题末尾附加的标签，可能是独立行也可能是题目行末尾）
        if re.match(r'^填空\s*\d+\s*$', line_stripped):
            break

        # 去掉行尾的"填空 N"标签（如"（）是国家权力...第一现象。填空 1"）
        line_stripped = re.sub(r'填空\s*\d+\s*$', '', line_stripped).strip()
        if not line_stripped:
            continue

        q_lines.append(line_stripped)

    return ' '.join(q_lines)


def _extract_options_from_block(block_text):
    """从题块文本中提取选项，返回 {字母: 选项文本} 映射

    兼容两种格式：
    1. 字母和文本分行：
       A.
       通货膨胀
    2. 字母和文本同行：
       A. 通货膨胀
    """
    options = {}
    lines = block_text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # 匹配 A. / A、 / A) / A: 等
        m = re.match(r'^([A-F])[\.、\)\s:：]+(.*)$', line)
        if m:
            letter = m.group(1)
            text = m.group(2).strip()
            # 如果选项文本在下一行
            if not text and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                # 确保下一行不是另一个选项或特殊标记
                if next_line and not re.match(r'^[A-F][\.、\)\s:：]', next_line) \
                   and not next_line.startswith('正确答案') \
                   and not next_line.startswith('你的作答') \
                   and not next_line.startswith('暂无解析'):
                    text = next_line
                    i += 1
            if text:
                options[letter] = text
        i += 1
    return options


def _normalize_question(text):
    """标准化题目文本，用于模糊匹配"""
    # 移除所有空白字符
    text = re.sub(r'\s+', '', text)
    # 统一全角/半角括号和标点
    text = text.replace('（', '(').replace('）', ')')
    text = text.replace('，', ',').replace('：', ':').replace('；', ';')
    text = text.replace('"', '"').replace('"', '"')
    text = text.replace(''', "'").replace(''', "'")
    # 移除题号前缀（各种格式：1. 1、 1） 1: 等）
    text = re.sub(r'^[\d一二三四五六七八九十百]+[\.\、\s\):：\)）]*', '', text)
    # 移除题型标记
    for kw in ['单选题', '多选题', '判断题', '填空题', '简答题', '问答题', '名词解释', '论述题']:
        text = text.replace(kw, '')
    # 移除分数和难度相关
    text = re.sub(r'\|[\d分简单一般困难中等]*', '', text)
    text = re.sub(r'\d+\s*分', '', text)
    for diff in ['简单', '一般', '困难', '中等', '容易']:
        text = text.replace(diff, '')
    # 移除页码标记（如"1页"、"2页"）
    text = re.sub(r'\d+页', '', text)
    # 移除"暂无解析"等标记
    text = re.sub(r'暂无解析', '', text)
    # 移除题号+竖线分隔符（如"1|"）
    text = re.sub(r'^\d+\|', '', text)
    # 移除剩余的纯数字题号
    text = re.sub(r'^\d+', '', text)
    return text.strip()