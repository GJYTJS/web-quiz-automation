# -*- coding: utf-8 -*-
"""AI 答题引擎（模式2用）— 支持多种 API 格式 + 重试退避"""

import re
import time

import requests

from answer_filler import AnswerFiller


class AnswerEngine:
    """AI 答题引擎（模式2用）— 支持多种 API 格式 + 重试退避"""

    _RETRY_DELAYS = [3, 8, 20]
    _RATE_LIMIT_WORDS = ["rate", "limit", "too many", "429", "quota"]

    def __init__(self, config):
        self.config = config
        self.model = config["model"]
        self._is_reasoner = "reasoner" in self.model.lower()
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['api_key']}",
        })

    def _is_rate_limited(self, text):
        lt = text.lower()
        return any(w in lt for w in self._RATE_LIMIT_WORDS)

    def _call_api(self, prompt, system_prompt=None):
        """调用 API，带退避重试。返回 (success, content_or_error)"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 2048 if self._is_reasoner else 1024,
        }
        if not self._is_reasoner:
            payload["temperature"] = 0.0

        for attempt in range(len(self._RETRY_DELAYS) + 1):
            try:
                resp = self.session.post(self.config["api_url"], json=payload, timeout=120)
                resp.raise_for_status()
                result = resp.json()
                break
            except requests.exceptions.Timeout:
                return False, "API 超时，尝试将题目分组重试"
            except requests.exceptions.HTTPError as e:
                body = e.response.text[:300] if e.response else ""
                if self._is_rate_limited(body):
                    if attempt < len(self._RETRY_DELAYS):
                        d = self._RETRY_DELAYS[attempt]
                        print(f"  ⏳ 频率限制，{d}s 后重试 ({attempt+1}/{len(self._RETRY_DELAYS)})...")
                        time.sleep(d)
                        continue
                    return False, "API 频率限制，稍后再试"
                return False, f"API {e.response.status_code}: {body}"
            except Exception as e:
                return False, str(e)
        else:
            return False, "API 多次重试均失败"

        try:
            content = result["choices"][0]["message"]["content"].strip()
            return True, content
        except (KeyError, IndexError):
            return False, f"API 返回格式异常: {str(result)[:300]}"

    def answer(self, question, options=None, q_type=None, full_text=None):
        """
        调用 AI 回答，返回 (success, answer_str)。
        answer_str 格式同 _clean_answer，同时设置 _last_answer_texts 供文本匹配。
        """
        self._last_answer_texts = []
        if not question or len(question.strip()) < 3:
            return False, "题目过短"

        clean_options = AnswerEngine._build_option_map(options, full_text)
        prompt = self._build_prompt(question.strip(), clean_options, q_type)
        system_prompt = "你是一个精准的答题助手。请仔细分析题目，给出正确答案，只输出答案本身，不要任何解释。"

        ok, raw = self._call_api(prompt, system_prompt)
        if not ok:
            return False, raw

        cleaned = self._clean_answer(raw, q_type)

        # 选择题格式校验重试
        if q_type in ("single", "multi") and not re.search(r'[A-Fa-f]', cleaned):
            retry_p = prompt + "\n\n⚠️ 上次格式不对。只输出选项字母，如 B 或 ABC。"
            _, raw = self._call_api(retry_p, system_prompt)
            cleaned = self._clean_answer(raw, q_type)

        # 多选题单选项重试
        if q_type == "multi" and len(re.findall(r'[A-Fa-f]', cleaned)) <= 1:
            retry_p = prompt + "\n\n⚠️ 这是多选题，通常有 2+ 个正确选项，请全部列出（如 ACD）。"
            _, raw = self._call_api(retry_p, system_prompt)
            cleaned = self._clean_answer(raw, q_type)

        # 记录答案文本供选项乱序匹配
        if q_type in ("single", "multi") and clean_options:
            letters = re.findall(r'[A-Fa-f]', cleaned)
            self._last_answer_texts = [clean_options.get(l.upper(), "") for l in letters if l.upper() in clean_options]

        return True, cleaned

    @staticmethod
    def _build_option_map(options, full_text):
        """{字母: 文本}，options 无效时从 full_text 正则提取"""
        def _valid(opts):
            if not opts:
                return False
            non_empty = [o for o in opts if o and o.strip()]
            if len(non_empty) < len(opts):
                return False
            if all(re.match(r'^\d+$', o.strip()) for o in opts):
                return False
            if len(set(o.strip() for o in opts)) == 1 and len(opts) > 1:
                return False
            return True

        if _valid(options):
            return {chr(65 + i): o.strip() for i, o in enumerate(options)}
        if full_text:
            parsed = AnswerFiller._extract_option_texts_from_full(full_text)
            if parsed:
                return parsed
        return {}

    @staticmethod
    def _build_prompt(question, options, q_type):
        labels = {"single": "单选题", "multi": "多选题", "fill": "填空题", "judge": "判断题"}
        label = labels.get(q_type, "")
        prompt = f"【{label}】\n{question}" if label else question

        if options:
            prompt += "\n\n选项："
            for k in sorted(options):
                prompt += f"\n{k}. {options[k]}"

        prompt += "\n\n"
        if q_type == "single":
            prompt += (
                "选出唯一正确答案。\n"
                "输出格式：只输出一个字母，如 B\n"
                "示例：题目问「中国首都是哪个城市」，选项A.上海 B.北京 C.广州 D.深圳 → 输出: B"
            )
        elif q_type == "multi":
            prompt += (
                "这是多选题，请选出所有正确的选项。请逐个判断每个选项是否正确。\n"
                "输出格式：所有正确选项的字母连在一起，如 ACD\n"
                "示例：题目「下列哪些是中国直辖市」，选项A.北京 B.广州 C.上海 D.深圳 → 输出: AC"
            )
        elif q_type == "judge":
            prompt += (
                "请判断题目说法是否正确。\n"
                "输出格式：只输出「对」或「错」，不要输出其他文字\n"
                "示例1：题目「地球是太阳系最大的行星」→ 输出: 错\n"
                "示例2：题目「水在标准大气压下100摄氏度沸腾」→ 输出: 对"
            )
        elif q_type == "fill":
            prompt += (
                "请根据题目给出填空答案。\n"
                "如果有多个空，每个空的答案用 || 分隔。\n"
                "输出格式示例1（单空）：题目「中国的首都是____」→ 输出: 北京\n"
                "输出格式示例2（多空）：题目「1+1=____，2+2=____」→ 输出: 2||4\n"
                "注意：只输出答案内容，不要加引号、序号或解释。"
            )
        return prompt

    @staticmethod
    def _clean_answer(raw, q_type):
        if not q_type:
            return raw.strip()
        answer = raw.strip()

        for p in ["【答案】", "答案：", "答：", "Answer:", "答案"]:
            if answer.startswith(p):
                answer = answer[len(p):].strip()
                break

        for m in ["【解析】", "解析：", "解析:", "\n解析", "\n说明", "\n解释", "\n原因"]:
            idx = answer.find(m)
            if idx >= 0:
                answer = answer[:idx].strip()

        answer = answer.split('\n')[0].strip().strip('"\'""''「」')

        if q_type in ("single", "multi"):
            letters = re.findall(r'[A-Fa-f]', answer)
            return ''.join(letters).upper() if letters else answer
        if q_type == "judge":
            if re.search(r'不(对|正确|是)|并非|不是|错误|否|×|×|F(?!R)', answer):
                answer = '错'
            elif re.search(r'^对$|^正确$|√|^是$|^T$|^true$', answer, re.IGNORECASE):
                answer = '对'
            elif '错' in answer or 'false' in answer.lower():
                answer = '错'
            elif '对' in answer or '正确' in answer or '√' in answer or '是' in answer:
                answer = '对'
            else:
                answer = answer[:1] if answer else '对'
        if q_type == "fill":
            answer = re.sub(r'填空\s*\d+\s*[：:]', '', answer).strip()
            answer = re.sub(r'[【】\[\]]', '', answer).strip()
        return answer