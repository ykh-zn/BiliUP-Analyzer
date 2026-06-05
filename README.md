# Bilibili 爬虫

基于 Selenium 的 B 站视频数据爬取工具，支持自动抓取 UP 主全部视频信息，通过 Streamlit 交互式看板进行数据可视化分析。

## 功能

- 模拟浏览器自动登录，支持 cookies 持久化
- 抓取 UP 主基本信息（粉丝数、获赞数、总播放量）及全部视频列表分页采集
- 每条视频提取：标题、简介、视频时长、标签、播放量、弹幕数、点赞、投币、收藏、转发、评论数、发布时间
- Streamlit 交互式看板：数据概览、图表分析、标签词云
- 支持导出 Excel 报告和 Markdown 报告

## 依赖

| 包 | 用途 |
|---|---|
| `selenium` | 浏览器自动化，模拟登录与翻页 |
| `pandas` | 数据清洗、统计、导出 Excel |
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
│   ├── raw/                     # 爬取的原始数据
│   └── output/                  # 分析报告输出
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
| 数据概览 | UP 主信息卡片、统计摘要、播放量 Top10 |
| 视频分析 | 月度趋势、播放量分布、互动率箱线图、发布时间分布、播放量 vs 投币率散点图、视频数据表格 |
| 标签分析 | 标签词云、高频标签 Top20、标签对播放量的影响 |

侧边栏支持导出 Excel 报告和 Markdown 报告。
