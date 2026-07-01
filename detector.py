# -*- coding: utf-8 -*-
"""题目识别器 - 识别答题页面的所有题目"""

import re
import time
from datetime import datetime

from selenium.webdriver.common.by import By


class QuestionDetector:
    """从答题页面识别所有题目"""

    def __init__(self, driver):
        self.driver = driver

    def detect_all(self):
        """检测页面上的所有题目，返回题目列表"""
        questions = []
        print("\n🔍 正在扫描页面题目...")

        # ---- iframe 检测与切换 ----
        self._try_switch_to_iframe()

        # ---- 滚动页面，确保所有题目加载 ----
        self._scroll_to_load_all()

        # 方法1：尝试多种常见的选择题容器选择器
        container_selectors = [
            # 平台/学习通特有结构
            "//div[contains(@class,'question-item')]",
            "//div[contains(@class,'questionItem')]",
            "//div[contains(@class,'qt-content') or contains(@class,'qt-item')]",
            "//div[contains(@class,'cy-qustion')]",
            "//div[contains(@class,'topic-item')]",
            # 通用 question/quiz/item
            "//div[contains(@class,'question') or contains(@class,'quiz') or contains(@class,'item')]",
            "//li[contains(@class,'question') or contains(@class,'quiz') or contains(@class,'item')]",
            "//div[contains(@class,'topic')]",
            "//div[contains(@class,'subject')]",
            # 通用
            "//fieldset",
            "//form//div[@class]",
        ]

        question_elements = []
        for sel in container_selectors:
            try:
                elems = self.driver.find_elements(By.XPATH, sel)
                for elem in elems:
                    try:
                        text = self._get_text_content(elem)
                        if text and self._is_question(text) and elem not in question_elements:
                            question_elements.append(elem)
                    except:
                        continue
                if question_elements:
                    break
            except:
                continue

        # 如果上面没找到，用更宽泛的扫描
        if not question_elements:
            print("   ⚠️ 未找到标准题目容器，使用深度扫描...")
            question_elements = self._deep_scan()

        print(f"   找到 {len(question_elements)} 个候选题目区域")

        # 解析每个题目区域
        for idx, q_elem in enumerate(question_elements):
            q_info = self._parse_single(q_elem, idx + 1)
            if q_info:
                questions.append(q_info)

        # ---- 质量检查：如果大部分题目文本太短，走 JS 备用检测 ----
        if questions:
            short_count = sum(1 for q in questions if len(q["text"]) < 5)
            if short_count > len(questions) * 0.5:
                print(f"   ⚠️ {short_count}/{len(questions)} 题文本过短，尝试 JS 备用检测...")
                questions = self._detect_via_javascript() or questions

        if not questions:
            print("   ⚠️ 未检测到任何题目！尝试 JS 检测...")
            questions = self._detect_via_javascript()
            if not questions:
                self._dump_page_debug()

        return questions

    def _try_switch_to_iframe(self):
        try:
            self.driver.switch_to.default_content()
        except:
            pass
        iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        if not iframes:
            return False

        for iframe in iframes:
            try:
                self.driver.switch_to.frame(iframe)
                body_text = self.driver.find_element(By.TAG_NAME, "body").text
                inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='radio'], input[type='checkbox'], input[type='text'], textarea")
                if len(body_text) > 50 or len(inputs) > 0:
                    return True
                self.driver.switch_to.default_content()
            except:
                self.driver.switch_to.default_content()
        return False

    def _scroll_to_load_all(self):
        """滚动页面确保所有题目内容加载（懒加载兼容）"""
        try:
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            for _ in range(10):  # 最多滚动10次
                self.driver.execute_script(
                    "window.scrollBy(0, window.innerHeight);"
                )
                time.sleep(0.5)
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
            # 滚回顶部
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.5)
        except:
            pass

    def _dump_page_debug(self):
        """导出页面结构调试信息到文件"""
        debug_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "page_debug.txt"
        )
        info = []
        info.append(f"=== 页面调试信息 ===")
        info.append(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        info.append(f"URL: {self.driver.current_url}")
        info.append(f"Title: {self.driver.title}")

        # iframe 信息
        iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        info.append(f"\n--- iframe 数量: {len(iframes)} ---")
        for i, iframe in enumerate(iframes[:5]):
            try:
                info.append(
                    f"  iframe[{i}]: id={iframe.get_attribute('id')}, "
                    f"class={iframe.get_attribute('class')}, "
                    f"src={iframe.get_attribute('src')}"
                )
            except:
                pass

        # 所有带 question/topic/item/quiz 类名的元素
        info.append(f"\n--- 候选题目元素 ---")
        selectors_to_try = [
            "//div[contains(@class,'question')]",
            "//div[contains(@class,'topic')]",
            "//div[contains(@class,'quiz')]",
            "//div[contains(@class,'item')]",
            "//div[contains(@class,'subject')]",
            "//div[contains(@class,'problem')]",
            "//li[contains(@class,'question')]",
            "//li[contains(@class,'item')]",
            "//fieldset",
        ]
        for sel in selectors_to_try:
            try:
                elems = self.driver.find_elements(By.XPATH, sel)
                if elems:
                    info.append(f"\n选择器 '{sel}' 找到 {len(elems)} 个元素:")
                    for i, elem in enumerate(elems[:10]):
                        try:
                            cls = elem.get_attribute("class") or ""
                            # 用 textContent 获取完整文本
                            text = self.driver.execute_script(
                                "return arguments[0].textContent;", elem
                            )
                            text_preview = (text or "").strip()[:200].replace('\n', ' | ')
                            info.append(f"  [{i}] class='{cls}'")
                            info.append(f"      text: {text_preview}")
                        except:
                            pass
            except:
                pass

        # 所有输入框
        info.append(f"\n--- 输入框（radio/checkbox/text）---")
        inputs = self.driver.find_elements(
            By.CSS_SELECTOR,
            "input[type='radio'], input[type='checkbox'], input[type='text'], textarea"
        )
        info.append(f"总输入框数: {len(inputs)}")
        for i, inp in enumerate(inputs[:20]):
            try:
                inp_type = inp.get_attribute("type")
                inp_id = inp.get_attribute("id") or ""
                inp_name = inp.get_attribute("name") or ""
                inp_value = inp.get_attribute("value") or ""
                # 获取父元素文本
                parent_text = self.driver.execute_script(
                    "return arguments[0].parentElement ? arguments[0].parentElement.textContent : '';",
                    inp
                )
                parent_preview = (parent_text or "").strip()[:100].replace('\n', ' | ')
                info.append(f"  [{i}] type={inp_type} id={inp_id} name={inp_name} value={inp_value}")
                info.append(f"      parent: {parent_preview}")
            except:
                pass

        # body 文本前3000字
        info.append(f"\n--- body 文本（前3000字）---")
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            info.append(body_text[:3000])
        except:
            info.append("(无法获取 body 文本)")

        with open(debug_file, "w", encoding="utf-8") as f:
            f.write('\n'.join(info))

        print(f"   📄 页面调试信息已保存到: {debug_file}")
        return debug_file

    def _detect_via_javascript(self):
        """
        JavaScript 备用检测：通过输入框（radio/checkbox/text）反向定位题目容器。
        比 CSS 类名匹配更可靠，适用于各种页面结构。
        """
        js_mark = """
        var inputs = document.querySelectorAll(
            'input[type="radio"], input[type="checkbox"], input[type="text"], textarea'
        );
        var seen = new Set();
        var count = 0;

        for (var i = 0; i < inputs.length; i++) {
            var inp = inputs[i];
            // 如果输入框本身已被标记过，跳过
            var container = inp;
            for (var j = 0; j < 10; j++) {
                container = container.parentElement;
                if (!container) break;
                if (seen.has(container)) break;
                var text = container.textContent || '';
                if (text.length > 15) {
                    // 检查是否像题目容器
                    var hasQuestion = text.indexOf('？') >= 0 || text.indexOf('?') >= 0 ||
                        text.indexOf('A.') >= 0 || text.indexOf('A、') >= 0 ||
                        text.indexOf('A)') >= 0 || text.indexOf('正确') >= 0 ||
                        text.indexOf('错误') >= 0 || text.indexOf('____') >= 0 ||
                        text.indexOf('（') >= 0;
                    if (hasQuestion) {
                        seen.add(container);
                        container.setAttribute('data-autoq', count.toString());
                        count++;
                        break;
                    }
                }
            }
        }
        return count;
        """
        try:
            count = self.driver.execute_script(js_mark)
            if count == 0:
                return []

            # 通过 data-autoq 属性找到标记的元素
            marked_elems = self.driver.find_elements(By.CSS_SELECTOR, "[data-autoq]")
            if not marked_elems:
                return []

            # 按标记顺序排序
            def get_sort_key(elem):
                try:
                    return int(elem.get_attribute("data-autoq") or 0)
                except:
                    return 0
            marked_elems.sort(key=get_sort_key)

            # 解析每个元素
            questions = []
            for idx, elem in enumerate(marked_elems):
                q_info = self._parse_single(elem, idx + 1)
                if q_info:
                    questions.append(q_info)

            return questions
        except Exception as e:
            print(f"   ⚠️ JS检测异常: {e}")
            return []

    def _is_question(self, text):
        """判断文本是否像一道题目"""
        if not text or len(text) < 4:
            return False
        indicators = ['？', '?', '(', ')', 'A.', 'B.', 'C.', 'D.', 'E.', 'F.',
                      'A、', 'B、', 'C、', 'D、', 'E、', 'F、', '正确', '错误',
                      '对', '错', '以下', '下列', '哪', '什么',
                      '_____', '___', '________']
        text_short = text[:100]
        has_indicator = any(i in text_short for i in indicators)
        has_number = bool(re.match(r'^\s*[\d一二三四五六七八九十]+[\.\、\s：:\)]', text))
        is_long_enough = len(text) > 10
        return (has_indicator or has_number) and is_long_enough

    def _deep_scan(self):
        """深度扫描页面寻找题目"""
        elements = []
        seen_texts = set()

        all_elems = self.driver.find_elements(By.XPATH,
            "//div | //li | //p | //td | //fieldset | //section")
        for elem in all_elems:
            try:
                # 用 textContent 获取完整文本
                text = self._get_text_content(elem)
                if text and self._is_question(text) and text[:80] not in seen_texts:
                    seen_texts.add(text[:80])
                    elements.append(elem)
            except:
                continue

        # 去除嵌套（保留最外层）
        filtered = []
        for elem in elements:
            is_child = False
            for other in elements:
                if elem != other:
                    try:
                        elem_text = self._get_text_content(elem)
                        other_text = self._get_text_content(other)
                        if elem_text and other_text and elem_text in other_text and len(other_text) > len(elem_text) * 1.5:
                            is_child = True
                            break
                    except:
                        continue
            if not is_child:
                filtered.append(elem)

        return filtered[:50]  # 最多50道题

    def _get_text_content(self, elem):
        """用 JavaScript textContent 获取元素完整文本（比 .text 更可靠，包含隐藏内容）"""
        try:
            text = self.driver.execute_script("return arguments[0].textContent;", elem)
            if text and len(text.strip()) >= len(elem.text.strip()):
                return text.strip()
        except:
            pass
        try:
            return elem.text.strip()
        except:
            return ""

    def _parse_single(self, q_elem, index):
        """解析单个题目元素"""
        try:
            # 优先用 JavaScript textContent 获取完整文本（包含不可见部分）
            q_text = self._get_text_content(q_elem)
            if not q_text or len(q_text) < 4:
                return None

            # 提取题目文本（去掉选项部分和元数据）
            clean_q = self._extract_question_text(q_text)

            # 验证：提取的文本不能是纯数字或太短
            if not clean_q or len(clean_q) < 3:
                return None
            if re.match(r'^\d+$', clean_q):
                return None
            if re.match(r'^共?\d+\s*道?题目?$', clean_q):
                return None

            # 识别题型和选项
            options = []
            option_texts = []
            inputs = []

            # 查找单选按钮
            radios = q_elem.find_elements(By.CSS_SELECTOR, "input[type='radio']")
            checkboxes = q_elem.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")

            if radios:
                inputs = radios
                q_type = "single"
            elif checkboxes:
                inputs = checkboxes
                q_type = "multi"
            else:
                # 可能是填空题或判断题
                text_inputs = q_elem.find_elements(By.CSS_SELECTOR,
                    "input[type='text'], input[type='number'], textarea")
                if text_inputs:
                    inputs = text_inputs
                    q_type = "fill"
                else:
                    q_type = "unknown"

            # 获取每个选项的文字和元素引用
            for inp in inputs:
                try:
                    opt_info = self._get_option_info(inp)
                    if opt_info:
                        options.append(opt_info["element"])
                        option_texts.append(opt_info["text"])
                except:
                    options.append(inp)
                    option_texts.append("")

            # 如果没有找到输入框但文字中有选项标记，记录为纯文本题
            if not options and q_type == "unknown":
                opts_from_text = re.findall(r'[A-F][\.、]\s*[^\nABCDEF]+', q_text)
                if opts_from_text:
                    q_type = "single_text"

            result = {
                "index": index,
                "element": q_elem,
                "text": clean_q[:300],
                "full_text": q_text[:500],
                "type": q_type,
                "options": options,
                "option_texts": option_texts,
            }
            return result

        except Exception as e:
            print(f"   ⚠️ 解析第 {index} 题失败: {e}")
            return None

    def _extract_question_text(self, full_text):
        """
        从完整文本中提取纯题目部分。
        平台格式示例：
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
        需要跳过题号/题型/分数/难度等元数据行，提取真正的题目正文。
        """
        lines = full_text.split('\n')

        # 元数据行模式（题号、题型、分数、难度、分隔符等）
        skip_patterns = [
            r'^\d+$',                                    # 纯数字题号: "1", "2"
            r'^(单选题|多选题|判断题|填空题|简答题|问答题|名词解释|论述题|单选|多选|判断|填空)$',
            r'^[\|\—\-]+$',                              # 分隔符: "|", "---"
            r'^\d+\s*分$',                               # 分数: "1 分", "2分"
            r'^\d+\s*/\s*\d+\s*分?$',                    # "1/1 分"
            r'^(简单|一般|困难|中等|容易)$',              # 难度
            r'^共?\d+\s*道?题目?$',                      # 头部: "共35道题目"
            r'^\d+道$',                                  # "35道"
            r'^题目$',                                   # 纯"题目"
            r'^\(.*\)$',                                 # "(单选题)" 等
            r'^\[\d+\s*分\]$',                           # "[1分]"
            r'^(第\s*\d+\s*题)$',                        # "第1题"
            r'^[A-F]\s*$',                               # 单独的选项字母 "A"
        ]

        q_lines = []
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # 跳过元数据行
            if any(re.match(p, line_stripped) for p in skip_patterns):
                continue

            # 遇到选项标记，停止
            if re.match(r'^[A-F][\.、\)\s]', line_stripped) or line_stripped in (
                'A.', 'A、', 'A)', 'B.', 'B、', 'B)',
                'C.', 'C、', 'C)', 'D.', 'D、', 'D)',
                'E.', 'E、', 'E)', 'F.', 'F、', 'F)',
            ):
                break

            # 判断题选项（单独的"正确"/"错误"/"对"/"错"行）
            if line_stripped in ('正确', '错误', '对', '错', '√', '×'):
                break

            # 遇到答案/作答标记，停止
            if any(kw in line_stripped for kw in [
                '正确答案', '参考答案', '你的作答', '你的答案',
                '标准答案', '解析', '得分', '分值'
            ]):
                break

            # 这才是题目正文
            q_lines.append(line_stripped)

        if q_lines:
            return ' '.join(q_lines)

        # 回退策略1：尝试原始正则
        patterns = [
            r'^([^A-D\n]*?)[\n\s]*(?=A[\.、])',
            r'^([^\n]*?[？?])[\s\S]*?',
            r'^([\d一二三四五六七八九十]+[\.\、\s：:\)][^\n]{5,200})',
        ]
        for p in patterns:
            m = re.search(p, full_text)
            if m:
                return m.group(1).strip()

        # 回退策略2：第一个非元数据行
        for line in lines:
            line_stripped = line.strip()
            if line_stripped and not any(re.match(p, line_stripped) for p in skip_patterns):
                return line_stripped[:150]

        # 最后手段
        return full_text.split('\n')[0][:150]

    def _get_option_info(self, input_elem):
        """获取选项的文本标签和可点击元素"""
        try:
            input_id = input_elem.get_attribute("id") or ""
            label_text = ""

            # 通过 label[for=id] 查找
            if input_id:
                try:
                    label = self.driver.find_element(By.CSS_SELECTOR,
                        f"label[for='{input_id}']")
                    label_text = label.text.strip()
                except:
                    pass

            # 通过父元素查找（用 textContent 获取更完整文本）
            if not label_text:
                try:
                    parent = input_elem.find_element(By.XPATH, "./..")
                    parent_text = self._get_text_content(parent)[:200].strip()
                    # 判断题：只保留"正确"/"错误"
                    for prefix in ["正确", "错误"]:
                        if parent_text.startswith(prefix):
                            label_text = prefix
                            break
                    # 如果父元素文本太长（可能包含了题目），尝试找兄弟文本节点
                    if not label_text and len(parent_text) > 5:
                        # 尝试获取父元素下非input子元素的文本
                        try:
                            children = parent.find_elements(By.XPATH, "./*[not(self::input)]")
                            child_texts = []
                            for child in children:
                                ct = self._get_text_content(child).strip()
                                if ct:
                                    child_texts.append(ct)
                            if child_texts:
                                label_text = " ".join(child_texts)[:100]
                        except:
                            pass
                        # 如果还是没找到，用父元素文本减去input的value
                        if not label_text:
                            label_text = parent_text[:100]
                except:
                    pass

            # 通过 value 属性查找（但排除纯数字——那是index不是文本）
            if not label_text:
                try:
                    val = input_elem.get_attribute("value") or ""
                    if val and not re.match(r'^\d+$', val):
                        label_text = val
                except:
                    pass

            return {
                "element": input_elem,
                "text": label_text,
            }
        except:
            return None