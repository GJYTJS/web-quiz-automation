# 全自动答题机器人知识库

## 位置
`C:\Users\10046\Desktop\全自动答题\`

## 文件结构
```
auto_answer_bot.py    ← 入口（双击此文件，兼容 bat）
├── config.py         ← 配置加载
├── browser.py        ← 浏览器管理（Edge / CDP）
├── detector.py       ← 题目识别器
├── paste_parser.py   ← ⛔ 答案粘贴解析（神圣不可侵犯）
├── matcher.py        ← ⛔ 题目匹配器（神圣不可侵犯）
├── answer_filler.py  ← ⛔ 答案填写器（神圣不可侵犯）
├── answer_engine.py  ← AI 答题引擎
├── result_parser.py  ← 结果页解析器
├── submit_helper.py  ← 提交操作器
└── main.py           ← 主流程/模式选择/主循环
```

## 运行
- 双击 `全自动答题.bat` 启动
- Python：`.workbuddy` 的 3.13.12
- 编码：`chcp 65001`，不要输出 emoji（GBK 崩）

## 模式1 铁律 — 这5个函数不能动
修改任何一个都会破坏已有功能：
- `parse_pasted_answers()` → paste_parser.py — 粘贴文本→答案
- `match_page_question()` → matcher.py — 6种匹配+类型惩罚
- `AnswerFiller.fill()` → answer_filler.py — 分发填写
- `AnswerFiller._fill_choice()` → answer_filler.py — 选项乱序对抗
- `AnswerFiller._fill_text()` → answer_filler.py — 填空题原始空格保留

## 已解决的三个核心难题
1. 选择题选项打乱 → 答案文本内容匹配（非字母索引）
2. 填空题多空格 → `<<<RAW>>>` 原始文本保留，单输入框原样填入
3. 多选题不只ABCD → 文本匹配不受字母限制

## 答案文件管理
粘贴答案后自动保存为 `answers_{名字}.json`，支持：加载、删除(`d N`)、重命名(`r N`)、搜索(`s kw`)
