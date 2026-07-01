# Web Quiz Automation

> **⚠️ Technical Demo** — This project is a browser automation technical demonstration.
> It showcases CDP/Selenium hybrid driving, DOM robust parsing, and fuzzy matching strategies.
> Use responsibly and in compliance with platform terms of service.

Browser automation toolkit for web-based quiz systems, built with **Selenium WebDriver** and **Chrome DevTools Protocol (CDP)**.

## Features

- **Multi-engine architecture** — Hybrid CDP + Selenium driver for reliable DOM interaction
- **Smart question matching** — 6-level fuzzy matching strategy (text → substring → fuzzy → fallback)
- **Cross-platform form filling** — Radio buttons, checkboxes, text inputs, and rich editors
- **Result page parser** — Extract correct answers from structured/unstructured result pages
- **AI-powered answering** — Optional LLM integration for unanswerable questions
- **Modular design** — 11 independent modules with clean interfaces

## Architecture

```
main.py              ← Entry point & mode selection
├── browser.py       ← Browser manager (Edge CDP / Selenium)
├── detector.py      ← DOM question detector
├── answer_filler.py ← Answer filling with shuffled-option resistance
├── matcher.py       ← Question matching (6-level fuzzy)
├── paste_parser.py  ← Clipboard text parser
├── result_parser.py ← Result page analyzer
├── answer_engine.py ← LLM integration
├── submit_helper.py ← Form submission helper
└── config.py        ← Configuration loader
```

## Modes

| Mode | Description |
|------|-------------|
| Mode 1 | Paste answer text → auto-match and fill |
| Mode 2 | AI-powered auto-answering |
| Mode 3 | Full-auto: random fill → parse → correct |
| Mode 4 | Parse result page and save correct answers |

## Technical Highlights

### Shuffled-Option Resistance
Quiz platforms often randomize option ordering. The matcher uses a 4-tier fallback:
1. Exact text match
2. Substring match
3. Fuzzy string matching
4. Letter-backup (A/B/C/D)

### Hybrid CDP/Selenium
CDP provides stable DOM access without Selenium's flaky waits, while Selenium handles navigation and alerts. The driver auto-falls back when CDP is unavailable.

### Raw Space Preservation
Fill-in-the-blank questions preserve original whitespace using `<RAW>` markers, handling the multi-blank edge case where input count doesn't match blank count.

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure API key:
   ```bash
   cp config.example.json config.json
   # Edit config.json with your API key
   ```

3. Run:
   ```bash
   python main.py
   ```

## Requirements

- Python 3.10+
- Microsoft Edge or Google Chrome
- Selenium WebDriver (bundled with Edge Chromium)

## License

MIT