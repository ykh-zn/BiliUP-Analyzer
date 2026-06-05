# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 启动爬虫（默认 UID: 527299525）
python run_crawler.py
python run_crawler.py --uid 1392230290

# 启动数据看板
python run_dashboard.py
```

## 架构

**爬虫** (`crawler/bilibili_selenium.py`)：
- Selenium + Edge WebDriver 模拟浏览器爬取 B站视频数据
- 首次运行需手动扫码登录，cookies 持久化到 `data/cookies.json`
- 多选择器容错机制适配 B站页面结构变化（`VIDEO_CARD_SELECTORS`、`DURATION_SELECTORS` 等）
- 数据输出到 `data/raw/UID_{uid}/` 下的 JSON 文件

**看板** (`dashboard/app.py`)：
- Streamlit + Plotly 交互式数据看板，3 个 Tab：数据总览、图表分析、标签词云
- 支持从看板启动爬虫（subprocess）、导出 Excel/Markdown 报告
- 路径基于 `__file__` 计算 project_root，确保子进程正确执行

**数据流**：爬虫写 JSON → 看板读取 JSON → 展示/导出

## 关键技术点

- 爬虫用 `presence_of_all_elements_located` 遍历多个元素解决 B站同一选择器返回空元素的问题（如时长字段页面有 21 个匹配元素，第 1 个为空）
- `find_element_by_selectors` / `find_elements_by_selectors` 是核心容错函数，所有选择器列表定义在文件顶部
- 看板中 `generate_excel` 用 `BytesIO` + `xlsxwriter` 内存生成 Excel，不落盘
