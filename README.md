# Bilibili 爬虫

基于 Selenium + B站 API 的视频数据爬取工具，通过 Streamlit 交互式看板进行数据可视化分析。

## 功能

- Selenium 扫码登录获取 cookies，后续请求全部走 `requests` + B站 API
- 抓取 UP 主基本信息（粉丝数、获赞数、总播放量）及全部视频列表分页采集
- 每条视频提取：标题、简介、视频时长、标签、播放量、弹幕数、点赞、投币、收藏、转发、评论数、发布时间
- Streamlit 交互式看板，5 个 Tab：数据概览、内容策略、互动分析、生命周期、标签分析
- 从看板直接启动爬虫，实时日志显示，支持中途停止
- 支持删除已爬取的 UP 主数据
- 支持导出 Markdown 报告、Excel（原始数据）、原始 JSON

## 依赖

| 包 | 用途 |
|---|---|
| `selenium` | 浏览器自动化，首次登录获取 cookies |
| `requests` | B站 API 请求 |
| `pandas` | 数据处理与导出 Excel |
| `streamlit` | 交互式数据看板 |
| `plotly` | 交互式图表 |
| `wordcloud` | 标签词云生成 |
| `matplotlib` | 词云渲染 |
| `numpy` | 数值计算 |
| `xlsxwriter` | Excel 格式与样式 |

```bash
pip install -r requirements.txt
```

> 需要 **Edge 浏览器**，脚本默认调用 Edge WebDriver。

## 项目结构

```
bilibili_crawler/
├── crawler/
│   └── bilibili_selenium.py     # 爬虫主程序
├── dashboard/
│   └── app.py                   # Streamlit 看板
├── data/
│   ├── cookies.json             # 登录凭证（gitignore）
│   └── raw/                     # 爬取的原始数据
├── run_crawler.py               # 爬虫启动入口
├── run_dashboard.py             # 看板启动入口
├── requirements.txt
└── .gitignore
```

## 快速开始

### 第一步：爬取数据

```bash
# 默认 UID
python run_crawler.py

# 指定 UID
python run_crawler.py --uid 1392230290
```

首次运行浏览器自动打开 B 站首页，扫码登录后自动保存 cookies。数据保存至 `data/raw/UID_{uid}/`。

### 第二步：查看看板

```bash
python run_dashboard.py
```

浏览器自动打开 Streamlit 看板，可选择已有 UP 主查看分析，或输入新 UID 直接爬取。

### 看板功能

| Tab | 内容 |
|-----|------|
| 数据概览 | UP 主信息卡片、统计摘要、播放量 Top10、二八定律 |
| 内容策略 | 时长分析、发布时间热力图、互动率分布、点赞投币比、收藏率 Top10 |
| 互动分析 | 互动指标相关性、评论率分析、月度趋势 |
| 生命周期 | 累计播放量增长、发布间隔、爆款识别 |
| 标签分析 | 标签词云、高频标签、标签对播放量影响、共现网络、标签趋势 |

侧边栏支持导出 Markdown 报告、Excel 和原始 JSON。
