import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import re
import os
import subprocess
import sys
import time
from collections import Counter
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import numpy as np

# ============================== 页面配置 ==============================
st.set_page_config(
    page_title="B站数据分析看板",
    page_icon="📊",
    layout="wide",
)

# ============================== 数据处理函数 ==============================
RAW_DIR = os.path.join('.', 'data', 'raw')


def convert_count(value):
    """将含"万"字的数字字符串转为整数"""
    value_str = str(value).strip()
    if "万" in value_str:
        num_part = re.sub(r'[^\d.]', '', value_str)
        return int(float(num_part) * 10000) if num_part else 0
    else:
        try:
            return int(float(value_str))
        except:
            return 0


def get_available_uids():
    """扫描 raw 目录获取已有 UID 列表"""
    if not os.path.isdir(RAW_DIR):
        return []
    uids = []
    for d in os.listdir(RAW_DIR):
        if d.startswith('UID_'):
            uid = d[4:]
            basic_path = os.path.join(RAW_DIR, d, 'basic_data.json')
            if os.path.exists(basic_path):
                try:
                    with open(basic_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    nickname = data[0].get('昵称', uid) if data else uid
                    uids.append((uid, nickname))
                except:
                    uids.append((uid, uid))
    return uids


def load_basic_data(uid):
    """加载 UP 主基础数据"""
    path = os.path.join(RAW_DIR, f'UID_{uid}', 'basic_data.json')
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if not data:
        return None
    return data[0]


def load_video_data(uid):
    """加载视频数据并做类型转换"""
    path = os.path.join(RAW_DIR, f'UID_{uid}', 'video_data.json')
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if not data:
        return None
    df = pd.DataFrame(data)

    # 数值列转换
    num_cols = ['播放量', '弹幕数', '点赞量', '投币数', '收藏量', '转发量']
    for col in num_cols:
        if col in df.columns:
            df[col] = df[col].apply(convert_count).astype(int)
        else:
            df[col] = 0

    # 评论数（可能不存在）
    if '评论数' in df.columns:
        df['评论数'] = df['评论数'].apply(convert_count).astype(int)
    else:
        df['评论数'] = 0

    # 时间列
    if '发布(更改)时间' in df.columns:
        df['发布(更改)时间'] = pd.to_datetime(df['发布(更改)时间'])

    # 互动率
    for col, rate_name in [('弹幕数', '弹幕率'), ('投币数', '投币率'),
                           ('收藏量', '收藏率'), ('转发量', '转发率')]:
        df[rate_name] = (df[col] / df['播放量'].replace(0, 1)).round(5)

    return df


# ============================== Plotly 图表函数 ==============================
def plot_top10_views(df):
    """播放量 Top10 水平柱状图"""
    top10 = df.nlargest(10, '播放量').iloc[::-1]
    fig = go.Figure(go.Bar(
        x=top10['播放量'],
        y=[t[:25] + '...' if len(str(t)) > 25 else t for t in top10['标题']],
        orientation='h',
        marker_color='#00a1d6',
        text=top10['播放量'],
        textposition='outside',
    ))
    fig.update_layout(
        title='播放量 Top 10',
        xaxis_title='播放量',
        yaxis_title='',
        height=500,
        margin=dict(l=200),
    )
    return fig


def plot_monthly_trend(df):
    """月度趋势：发布数 + 平均播放量（双 Y 轴）"""
    df_m = df.copy()
    df_m['发布年月'] = df_m['发布(更改)时间'].dt.to_period('M')
    monthly = df_m.groupby('发布年月').agg(
        发布数=('标题', 'count'),
        平均播放量=('播放量', 'mean'),
    ).reset_index()
    monthly['发布年月'] = monthly['发布年月'].astype(str)
    monthly['平均播放量'] = monthly['平均播放量'].round(0).astype(int)

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(x=monthly['发布年月'], y=monthly['发布数'],
               name='发布数', marker_color='#fb7299', opacity=0.7),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=monthly['发布年月'], y=monthly['平均播放量'],
                   name='平均播放量', mode='lines+markers',
                   line=dict(color='#00a1d6', width=2.5)),
        secondary_y=True,
    )
    fig.update_layout(title='月度趋势', height=450)
    fig.update_xaxes(title_text='月份')
    fig.update_yaxes(title_text='发布数', secondary_y=False)
    fig.update_yaxes(title_text='平均播放量', secondary_y=True)
    return fig


def plot_views_distribution(df):
    """播放量分布直方图（对数刻度）"""
    views = df[df['播放量'] > 0]['播放量']
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=views, nbinsx=30, marker_color='#00a1d6', opacity=0.7, name='视频数',
    ))
    fig.add_vline(x=views.mean(), line_dash='dash', line_color='red',
                  annotation_text=f'均值: {views.mean():.0f}')
    fig.add_vline(x=views.median(), line_dash='dash', line_color='orange',
                  annotation_text=f'中位数: {views.median():.0f}')
    fig.update_layout(
        title='播放量分布',
        xaxis=dict(title='播放量', type='log'),
        yaxis_title='视频数',
        height=400,
    )
    return fig


def plot_engagement_boxplot(df):
    """互动率箱线图"""
    rate_cols = ['弹幕率', '投币率', '收藏率', '转发率']
    fig = go.Figure()
    colors = ['#00a1d6', '#fb7299', '#ffb81c', '#6dc781']
    for col, color in zip(rate_cols, colors):
        fig.add_trace(go.Box(y=df[col], name=col, marker_color=color))
    fig.update_layout(title='互动率分布', yaxis_title='比率', height=400)
    return fig


def plot_hourly_distribution(df):
    """发布时间分布（按小时）"""
    df_h = df.copy()
    df_h['小时'] = df_h['发布(更改)时间'].dt.hour
    hour_dist = df_h['小时'].value_counts().sort_index()
    fig = go.Figure(go.Bar(
        x=hour_dist.index, y=hour_dist.values,
        marker_color='#fb7299',
    ))
    fig.update_layout(
        title='发布时间分布（按小时）',
        xaxis=dict(title='小时', dtick=1),
        yaxis_title='视频数',
        height=400,
    )
    return fig


def plot_views_vs_coinrate(df):
    """播放量 vs 投币率散点图"""
    color_col = '评论数' if '评论数' in df.columns and df['评论数'].sum() > 0 else '弹幕数'
    fig = px.scatter(
        df, x='播放量', y='投币率', color=color_col,
        color_continuous_scale='purpor',
        hover_data=['标题'],
        title='播放量 vs 投币率',
    )
    fig.update_layout(height=500)
    return fig


def generate_wordcloud(tags_series):
    """生成标签词云"""
    all_tags = []
    for tags_str in tags_series.dropna():
        if tags_str:
            all_tags.extend([t.strip() for t in str(tags_str).split(',') if t.strip()])
    if not all_tags:
        return None
    tag_text = ' '.join(all_tags)
    wc = WordCloud(
        font_path='C:/Windows/Fonts/msyh.ttc',
        width=800, height=400,
        background_color='white',
        max_words=100,
        colormap='viridis',
    ).generate(tag_text)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wc, interpolation='bilinear')
    ax.axis('off')
    return fig


def plot_top_tags(df, top_n=20):
    """高频标签 Top N 柱状图"""
    if '标签' not in df.columns:
        return None
    all_tags = []
    for tags_str in df['标签'].dropna():
        if tags_str:
            all_tags.extend([t.strip() for t in str(tags_str).split(',') if t.strip()])
    if not all_tags:
        return None
    tag_counts = Counter(all_tags).most_common(top_n)
    tags, counts = zip(*tag_counts)
    fig = go.Figure(go.Bar(
        x=list(counts)[::-1], y=list(tags)[::-1],
        orientation='h', marker_color='#00a1d6',
    ))
    fig.update_layout(
        title=f'高频标签 Top {top_n}',
        xaxis_title='出现次数',
        height=500,
        margin=dict(l=150),
    )
    return fig


def plot_tag_impact(df, top_n=10):
    """标签与播放量关系：有该标签 vs 无该标签的平均播放量"""
    if '标签' not in df.columns:
        return None
    all_tags = []
    for tags_str in df['标签'].dropna():
        if tags_str:
            all_tags.extend([t.strip() for t in str(tags_str).split(',') if t.strip()])
    if not all_tags:
        return None
    top_tags = [t for t, _ in Counter(all_tags).most_common(top_n)]
    results = []
    for tag in top_tags:
        has_tag = df[df['标签'].str.contains(tag, na=False)]['播放量'].mean()
        no_tag = df[~df['标签'].str.contains(tag, na=False)]['播放量'].mean()
        results.append({'标签': tag, '有标签': has_tag, '无标签': no_tag})
    df_r = pd.DataFrame(results)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df_r['标签'], y=df_r['有标签'], name='有该标签', marker_color='#00a1d6'))
    fig.add_trace(go.Bar(x=df_r['标签'], y=df_r['无标签'], name='无该标签', marker_color='#cccccc'))
    fig.update_layout(
        title=f'Top {top_n} 标签对播放量的影响',
        barmode='group',
        yaxis_title='平均播放量',
        height=450,
    )
    return fig


# ============================== 导出功能 ==============================
def generate_excel(uid, basic, df):
    """生成 Excel 报告，返回 bytes"""
    from io import BytesIO
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        center_format = workbook.add_format({"align": "center", "valign": "vcenter"})
        percent_format = workbook.add_format({'num_format': '0.000%', 'align': 'center'})
        int_format = workbook.add_format({'num_format': '#,##0', 'align': 'center'})
        header_fmt = workbook.add_format({
            'align': 'center', 'valign': 'vcenter', 'bold': True,
            'fg_color': '#7BC4E8', 'font_color': '#FFFFFF', 'border': 1
        })
        row_even_fmt = workbook.add_format({
            'align': 'center', 'valign': 'vcenter',
            'fg_color': '#E8F4FD', 'border': 1
        })
        row_odd_fmt = workbook.add_format({
            'align': 'center', 'valign': 'vcenter',
            'fg_color': '#F5FAFE', 'border': 1
        })
        section_fmt = workbook.add_format({
            'align': 'center', 'valign': 'vcenter', 'bold': True,
            'fg_color': '#5BA3D9', 'font_color': '#FFFFFF', 'border': 1
        })
        percent_fmt_even = workbook.add_format({'num_format': '0.000%', 'align': 'center', 'fg_color': '#E8F4FD', 'border': 1})
        percent_fmt_odd = workbook.add_format({'num_format': '0.000%', 'align': 'center', 'fg_color': '#F5FAFE', 'border': 1})
        int_fmt_even = workbook.add_format({'num_format': '#,##0', 'align': 'center', 'fg_color': '#E8F4FD', 'border': 1})
        int_fmt_odd = workbook.add_format({'num_format': '#,##0', 'align': 'center', 'fg_color': '#F5FAFE', 'border': 1})

        # 表一: 描述统计
        stats1 = df[['播放量', '弹幕数', '投币数', '收藏量', '转发量']].describe()
        stats1.to_excel(writer, sheet_name='Data_Describe', index=True, index_label='Metrics', float_format='%.0f')
        ws1 = writer.sheets['Data_Describe']
        nrows1, ncols1 = stats1.shape
        ws1.set_column(0, ncols1, 12, center_format)
        ws1.set_row(0, None, header_fmt)
        for r in range(nrows1):
            ws1.set_row(r + 1, None, row_even_fmt if r % 2 == 0 else row_odd_fmt)

        # 表二: 播放量Top排行+互动率
        top_100 = df.sort_values('播放量', ascending=False).iloc[:100].copy()
        top_100.index = range(1, len(top_100) + 1)
        metric_keys = ['弹幕率', '投币率', '收藏率', '转发率']
        stats2 = top_100[['播放量', '弹幕数', '投币数', '收藏量', '转发量', '弹幕率', '投币率', '收藏率', '转发率']]
        stats2.to_excel(writer, sheet_name='top_100', index=True, index_label='播放量排名')
        ws2 = writer.sheets['top_100']
        nrows2, ncols2 = stats2.shape
        ws2.set_column(0, 1, 12, center_format)
        ws2.set_column(1, 5, 14, int_format)
        for col_name in metric_keys:
            if col_name in stats2.columns:
                col_idx = stats2.columns.get_loc(col_name) + 1
                ws2.set_column(col_idx, col_idx, 12, percent_format)
        ws2.set_row(0, None, header_fmt)
        for r in range(nrows2):
            ws2.set_row(r + 1, None, row_even_fmt if r % 2 == 0 else row_odd_fmt)

        # 表三: 月度统计
        df_m = df.copy()
        df_m['发布年月'] = df_m['发布(更改)时间'].dt.to_period('M')
        monthly_stats = df_m.groupby('发布年月').agg(
            发布视频数=('标题', 'count'),
            平均播放量=('播放量', 'mean'),
            播放量中位数=('播放量', 'median'),
        ).reset_index()
        monthly_stats['发布年月'] = monthly_stats['发布年月'].astype(str)
        monthly_stats['平均播放量'] = monthly_stats['平均播放量'].round(0).astype(int)
        monthly_stats['播放量中位数'] = monthly_stats['播放量中位数'].astype(int)
        monthly_stats.to_excel(writer, sheet_name='Monthly_Stats', index=False)
        ws3 = writer.sheets['Monthly_Stats']
        nrows3, ncols3 = monthly_stats.shape
        ws3.set_column(0, ncols3, 14, center_format)
        ws3.set_row(0, None, header_fmt)
        for r in range(nrows3):
            ws3.set_row(r + 1, None, row_even_fmt if r % 2 == 0 else row_odd_fmt)

        # 表四: 各指标TOP5
        top_view = df.nlargest(5, '播放量')[['标题', '播放量']]
        top_dm = df.nlargest(5, '弹幕率')[['标题', '弹幕率', '弹幕数']]
        top_coin = df.nlargest(5, '投币率')[['标题', '投币率', '投币数']]
        top_fav = df.nlargest(5, '收藏率')[['标题', '收藏率', '收藏量']]
        top5_data = [
            ('播放量 Top 5', top_view, False),
            ('弹幕率 Top 5', top_dm, True),
            ('投币率 Top 5', top_coin, True),
            ('收藏率 Top 5', top_fav, True),
        ]
        ws_top = workbook.add_worksheet('Top5_排行榜')
        current_row = 0
        for sec_title, df_top, has_rate in top5_data:
            ncols = len(df_top.columns)
            ws_top.merge_range(current_row, 0, current_row, ncols - 1, sec_title, section_fmt)
            for c in range(ncols):
                ws_top.write(current_row, c, sec_title if c == 0 else '', section_fmt)
            current_row += 1
            for c, col_name in enumerate(df_top.columns):
                ws_top.write(current_row, c, col_name, header_fmt)
            current_row += 1
            for r in range(len(df_top)):
                row_fmt = row_even_fmt if r % 2 == 0 else row_odd_fmt
                pf = percent_fmt_even if r % 2 == 0 else percent_fmt_odd
                inf = int_fmt_even if r % 2 == 0 else int_fmt_odd
                ws_top.write(current_row, 0, df_top.iloc[r, 0], row_fmt)
                if has_rate:
                    ws_top.write(current_row, 1, df_top.iloc[r, 1], pf)
                else:
                    ws_top.write(current_row, 1, int(df_top.iloc[r, 1]), inf)
                if ncols >= 3:
                    ws_top.write(current_row, 2, int(df_top.iloc[r, 2]), inf)
                current_row += 1
            current_row += 1
        ws_top.set_column(0, 0, 50, center_format)
        ws_top.set_column(1, 1, 14, center_format)
        ws_top.set_column(2, 2, 14, center_format)

    return output.getvalue()


def generate_markdown(uid, basic, df):
    """生成 Markdown 报告，返回字符串"""
    lines = []
    lines.append(f'# UID:{uid} 数据分析报告\n')
    lines.append(f'**总视频数**: {len(df)}\n')
    lines.append('## 基础数据\n')
    lines.append(f'- 昵称: {basic.get("昵称", "")}')
    lines.append(f'- 粉丝数: {int(basic.get("粉丝数", 0)):,}')
    if basic.get('获赞数'):
        lines.append(f'- 获赞数: {int(basic.get("获赞数", 0)):,}')
    if basic.get('播放数'):
        lines.append(f'- 播放数: {int(basic.get("播放数", 0)):,}')
    lines.append('\n## 播放量统计\n')
    lines.append('| 指标 | 数值 |')
    lines.append('|------|------|')
    lines.append(f'| 均值 | {df["播放量"].mean():.0f} |')
    lines.append(f'| 中位数 | {df["播放量"].median():.0f} |')
    lines.append(f'| 最高 | {df["播放量"].max()} |')
    lines.append(f'| 最低 | {df["播放量"].min()} |')
    lines.append('\n## 播放量 Top 5\n')
    for i, (_, row) in enumerate(df.nlargest(5, '播放量').iterrows(), 1):
        lines.append(f'{i}. **{row["标题"]}** — {row["播放量"]:,} 播放')
    lines.append('\n## 月度趋势\n')
    df_m = df.copy()
    df_m['发布年月'] = df_m['发布(更改)时间'].dt.to_period('M')
    monthly = df_m.groupby('发布年月').agg(
        发布数=('标题', 'count'),
        平均播放量=('播放量', 'mean'),
    ).reset_index()
    monthly['发布年月'] = monthly['发布年月'].astype(str)
    monthly['平均播放量'] = monthly['平均播放量'].round(0).astype(int)
    lines.append('| 月份 | 发布数 | 平均播放量 |')
    lines.append('|------|--------|------------|')
    for _, row in monthly.iterrows():
        lines.append(f'| {row["发布年月"]} | {row["发布数"]} | {row["平均播放量"]:,} |')
    return '\n'.join(lines)


# ============================== 侧边栏 ==============================
st.sidebar.title("B站数据分析看板")

# 获取已有 UID 列表
uid_list = get_available_uids()
uid_options = [f"{nickname} ({uid})" for uid, nickname in uid_list]

selected_uid = None
if uid_options:
    selected = st.sidebar.selectbox("选择已有 UP 主", uid_options)
    selected_uid = selected.split('(')[-1].rstrip(')')

st.sidebar.divider()

# 手动输入 UID 爬取
st.sidebar.subheader("爬取新 UP 主")
new_uid = st.sidebar.text_input("输入 B站 UID")
crawl_btn = st.sidebar.button("开始爬取", disabled=not new_uid)

# 爬虫状态
if crawl_btn and new_uid:
    st.session_state['crawling'] = True
    st.session_state['crawl_uid'] = new_uid

if st.session_state.get('crawling'):
    st.sidebar.info(f"正在爬取 UID: {st.session_state['crawl_uid']} ...")
    # 使用绝对路径，避免工作目录问题
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script_path = os.path.join(project_root, 'crawler', 'bilibili_selenium.py')
    log_area = st.sidebar.empty()
    log_lines = []
    try:
        proc = subprocess.Popen(
            [sys.executable, script_path, '--uid', st.session_state['crawl_uid']],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace',
            cwd=project_root,
        )
        for line in proc.stdout:
            log_lines.append(line.strip())
            log_area.text_area("爬取日志", '\n'.join(log_lines[-20:]), height=300)
        proc.wait()
        if proc.returncode == 0:
            st.sidebar.success("爬取完成！")
            selected_uid = st.session_state['crawl_uid']
            uid_list = get_available_uids()
        else:
            st.sidebar.error(f"爬取失败，返回码: {proc.returncode}")
            st.sidebar.text_area("错误日志", '\n'.join(log_lines[-10:]), height=200)
    except Exception as e:
        st.sidebar.error(f"启动爬虫失败: {e}")
    st.session_state['crawling'] = False
    st.rerun()


# ============================== 主页面 ==============================
# 导出功能（需要先加载数据）
if selected_uid:
    basic = load_basic_data(selected_uid)
    df = load_video_data(selected_uid)
    if basic is not None and df is not None:
        st.sidebar.divider()
        st.sidebar.subheader("数据导出")
        # Excel 下载
        excel_bytes = generate_excel(selected_uid, basic, df)
        st.sidebar.download_button(
            label="下载 Excel 报告",
            data=excel_bytes,
            file_name=f"UID_{selected_uid}_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        # Markdown 下载
        md_content = generate_markdown(selected_uid, basic, df)
        st.sidebar.download_button(
            label="下载 Markdown 报告",
            data=md_content,
            file_name=f"UID_{selected_uid}_report.md",
            mime="text/markdown",
        )

if not selected_uid:
    st.info("请在左侧选择一个 UP 主，或输入新的 UID 进行爬取")
    st.stop()

# 数据已在导出部分加载，这里只需检查
if basic is None or df is None:
    st.error(f"UID {selected_uid} 的数据加载失败")
    st.stop()

# 页面标题
st.title(f"📊 {basic.get('昵称', selected_uid)} 的 B站数据分析")

# Tab 布局
tab1, tab2, tab3 = st.tabs(["📋 数据概览", "📈 视频分析", "🏷️ 标签分析"])

# ============================== Tab1: 数据概览 ==============================
with tab1:
    # UP主信息卡片
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("UID", selected_uid)
    with col2:
        st.metric("粉丝数", f"{int(basic.get('粉丝数', 0)):,}")
    with col3:
        st.metric("获赞数", f"{int(basic.get('获赞数', 0)):,}" if basic.get('获赞数') else "无数据")
    with col4:
        st.metric("播放数", f"{int(basic.get('播放数', 0)):,}" if basic.get('播放数') else "无数据")
    with col5:
        st.metric("总视频数", len(df))

    st.divider()

    # 统计摘要
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        st.metric("平均播放量", f"{df['播放量'].mean():,.0f}")
    with col_b:
        st.metric("播放量中位数", f"{df['播放量'].median():,.0f}")
    with col_c:
        st.metric("平均弹幕率", f"{df['弹幕率'].mean():.4%}")
    with col_d:
        st.metric("平均投币率", f"{df['投币率'].mean():.4%}")

    st.divider()

    # Top10 播放量
    st.plotly_chart(plot_top10_views(df), width='stretch')

# ============================== Tab2: 视频分析 ==============================
with tab2:
    # 月度趋势
    st.plotly_chart(plot_monthly_trend(df), width='stretch')

    col_left, col_right = st.columns(2)
    with col_left:
        st.plotly_chart(plot_views_distribution(df), width='stretch')
    with col_right:
        st.plotly_chart(plot_engagement_boxplot(df), width='stretch')

    col_left2, col_right2 = st.columns(2)
    with col_left2:
        st.plotly_chart(plot_hourly_distribution(df), width='stretch')
    with col_right2:
        st.plotly_chart(plot_views_vs_coinrate(df), width='stretch')

    st.divider()

    # 视频数据表格
    st.subheader("视频数据列表")
    display_cols = ['标题', '播放量', '弹幕数', '点赞量', '投币数', '收藏量', '转发量', '评论数', '发布(更改)时间']
    if '视频时长' in df.columns:
        display_cols.insert(1, '视频时长')
    existing_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(
        df[existing_cols].sort_values('播放量', ascending=False),
        width='stretch',
        height=500,
    )

# ============================== Tab3: 标签分析 ==============================
with tab3:
    if '标签' not in df.columns or df['标签'].isna().all() or (df['标签'] == '').all():
        st.info("当前数据没有标签信息，请使用最新版爬虫重新爬取以获取标签数据")
    else:
        # 标签词云
        st.subheader("标签词云")
        wc_fig = generate_wordcloud(df['标签'])
        if wc_fig:
            st.pyplot(wc_fig)
        else:
            st.info("无标签数据")

        col_wc1, col_wc2 = st.columns(2)
        with col_wc1:
            top_tags_fig = plot_top_tags(df, top_n=20)
            if top_tags_fig:
                st.plotly_chart(top_tags_fig, width='stretch')
        with col_wc2:
            impact_fig = plot_tag_impact(df, top_n=10)
            if impact_fig:
                st.plotly_chart(impact_fig, width='stretch')
