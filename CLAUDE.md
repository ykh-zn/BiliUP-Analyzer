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
- Selenium **仅用于首次登录获取 cookies**，数据爬取全部走 `requests` + B站 API
- 核心 API：`x/web-interface/view/detail`（一个请求拿到视频详情+Card+标签+相关推荐+评论）
- WBI 签名：视频列表 API `x/space/wbi/arc/search` 需要 WBI 签名（`mixinKeyEncTab` + MD5）
- UP 主总播放数通过 `x/space/upstat` API 获取（仅第一个视频时调用一次）
- 请求间隔 `random.uniform(0.1, 0.2)` 秒
- 数据输出到 `data/raw/UID_{uid}/` 下三个 JSON 文件

**看板** (`dashboard/app.py`)：
- Streamlit + Plotly 交互式数据看板，5 个 Tab：数据概览、内容策略、互动分析、生命周期、标签分析
- 支持从看板启动爬虫（subprocess + threading + Queue 实现实时日志）
- 日志倒序显示（最新在上），15 行，250px 高度
- 进程中可停止爬取（红色停止按钮）
- `PYTHONIOENCODING=utf-8` 解决 Windows GBK 编码问题
- 导出 Markdown 报告、Excel（原始数据）、原始 JSON
- 路径基于 `__file__` 计算 project_root，确保子进程正确执行

**数据流**：爬虫写 JSON → 看板读取 JSON → 展示/导出

## 数据文件

| 文件 | 内容 |
|------|------|
| `data/cookies.json` | Selenium 登录后保存的 cookies |
| `data/raw/UID_{uid}/basic_data.json` | UP 主基础信息（昵称、粉丝、获赞、播放数等） |
| `data/raw/UID_{uid}/video_data.json` | 视频列表（看板读取，字段与看板列一一对应） |
| `data/raw/UID_{uid}/raw_data.json` | 完整 API 原始响应（View+Card+Tags+Related+Reply） |

## 关键技术点

- WBI 签名：`enc_wbi()` 函数，`MIXIN_KEY_ENC_TAB` 索引表 + `img_key + sub_key` 拼接后取前 32 位作为 mixin_key
- 看板 subprocess 爬虫：`threading.Thread` 读取 stdout → `Queue` → Streamlit 轮询显示，0.5s 刷新
- 看板中 `generate_excel` 用 `BytesIO` + `xlsxwriter` 将原始 video_data.json 转为格式化 Excel
- Windows 下 subprocess 需设 `env['PYTHONIOENCODING'] = 'utf-8'` 否则日志乱码
