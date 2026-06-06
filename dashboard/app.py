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
import math
import shutil
from collections import Counter
from itertools import combinations
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import numpy as np

# ============================== 页面配置 ==============================
st.set_page_config(
    page_title="B站数据分析看板",
    page_icon="📊",
    layout="wide",
)

TITLE_FONT = dict(size=20)

# ============================== 数据处理函数 ==============================
RAW_DIR = os.path.join('.', 'data', 'raw')


def convert_count(value):
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


def delete_uid(uid):
    target = os.path.join(RAW_DIR, f'UID_{uid}')
    if os.path.isdir(target):
        shutil.rmtree(target)
        return True
    return False


def load_basic_data(uid):
    path = os.path.join(RAW_DIR, f'UID_{uid}', 'basic_data.json')
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if not data:
        return None
    return data[0]


def parse_duration(dur_str):
    if not dur_str or pd.isna(dur_str):
        return 0
    parts = str(dur_str).split(':')
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return int(parts[0])
    except:
        return 0


def load_video_data(uid):
    path = os.path.join(RAW_DIR, f'UID_{uid}', 'video_data.json')
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if not data:
        return None
    df = pd.DataFrame(data)

    num_cols = ['播放量', '弹幕数', '点赞量', '投币数', '收藏量', '转发量']
    for col in num_cols:
        if col in df.columns:
            df[col] = df[col].apply(convert_count).astype(int)
        else:
            df[col] = 0

    if '评论数' in df.columns:
        df['评论数'] = df['评论数'].apply(convert_count).astype(int)
    else:
        df['评论数'] = 0

    if '发布(更改)时间' in df.columns:
        df['发布(更改)时间'] = pd.to_datetime(df['发布(更改)时间'])

    if '视频时长' in df.columns:
        df['时长秒'] = df['视频时长'].apply(parse_duration)
    else:
        df['时长秒'] = 0

    for col, rate_name in [('弹幕数', '弹幕率'), ('投币数', '投币率'),
                           ('收藏量', '收藏率'), ('转发量', '转发率'),
                           ('评论数', '评论率')]:
        df[rate_name] = (df[col] / df['播放量'].replace(0, 1)).round(5)

    df['点赞投币比'] = (df['投币数'] / df['点赞量'].replace(0, 1)).round(4)
    df['有简介'] = df['简介'].apply(lambda x: 1 if str(x).strip() else 0)

    return df


def clean_data(df):
    log = []
    n_original = len(df)

    zero_mask = df['播放量'] == 0
    n_zero = zero_mask.sum()
    if n_zero > 0:
        log.append(f"播放量=0: {n_zero} 条（已排除）")
        df = df[~zero_mask].copy()

    n_before_dedup = len(df)
    df = df.sort_values('播放量', ascending=False).drop_duplicates(subset='标题', keep='first')
    n_dup = n_before_dedup - len(df)
    if n_dup > 0:
        log.append(f"重复标题: {n_dup} 条（已去重）")

    n_no_tag = (df['标签'].isna() | (df['标签'] == '')).sum()
    if n_no_tag > 0:
        log.append(f"空标签: {n_no_tag} 条（标签分析自动跳过）")

    n_no_desc = (1 - df['有简介']).sum()
    if n_no_desc > 0:
        log.append(f"空简介: {n_no_desc} 条")

    n_cleaned = len(df)
    n_removed = n_original - n_cleaned
    if n_removed > 0:
        log.insert(0, f"原始 {n_original} 条 → 清洗后 {n_cleaned} 条（移除 {n_removed}）")
    else:
        log.insert(0, f"共 {n_cleaned} 条，无需清洗")

    return df, log


# ============================== 图表分析函数 ==============================
def analyze_top10_views(df):
    top10 = df.nlargest(10, '播放量')
    t1, t10 = top10.iloc[0], top10.iloc[-1]
    gap = t1['播放量'] / t10['播放量'] if t10['播放量'] > 0 else 0
    avg = df['播放量'].mean()
    above_avg = (df['播放量'] > avg).sum()
    return f"Top1 播放量是 Top10 的 {gap:.1f} 倍，共 {above_avg}/{len(df)} 个视频超过均值 ({avg:,.0f})"


def analyze_pareto(df):
    n_top = max(1, int(len(df) * 0.2))
    top_views = df.nlargest(n_top, '播放量')['播放量'].sum()
    total = df['播放量'].sum()
    pct = top_views / total * 100
    if pct > 80:
        return f"头部效应极强：{n_top} 个视频（{n_top/len(df)*100:.0f}%）占据了 {pct:.1f}% 的播放量"
    elif pct > 60:
        return f"头部集中度较高：Top {n_top} 视频贡献了 {pct:.1f}% 的播放量"
    else:
        return f"播放量分布较均匀：Top {n_top} 视频仅占 {pct:.1f}%，长尾内容也有不错表现"


def analyze_duration_scatter(df):
    df_dur = df[df['时长秒'] > 0].copy()
    if df_dur.empty:
        return ""
    df_dur['分钟'] = df_dur['时长秒'] / 60
    bins = [(0, 1), (1, 3), (3, 5), (5, 10), (10, 20), (20, 60), (60, 999)]
    best_avg, best_range = 0, ""
    for lo, hi in bins:
        mask = (df_dur['分钟'] >= lo) & (df_dur['分钟'] < hi)
        if mask.sum() >= 2:
            avg = df_dur[mask]['播放量'].mean()
            if avg > best_avg:
                best_avg = avg
                best_range = f"{lo}-{hi}分钟"
    return f"平均播放量最高的时长区间：{best_range}（均值 {best_avg:,.0f}）" if best_range else ""


def analyze_duration_boxplot(df):
    df_dur = df[df['时长秒'] > 0].copy()
    if df_dur.empty:
        return ""
    bins = [0, 60, 300, 900, 3600, float('inf')]
    labels = ['<1分钟', '1-5分钟', '5-15分钟', '15-60分钟', '>60分钟']
    df_dur['分段'] = pd.cut(df_dur['时长秒'], bins=bins, labels=labels, right=False)
    medians = df_dur.groupby('分段', observed=True)['播放量'].median()
    if medians.empty:
        return ""
    best = medians.idxmax()
    return f"中位数播放量最高：{best}（{medians[best]:,.0f}），可重点关注该时长区间"


def analyze_heatmap(df):
    df_h = df.copy()
    df_h['星期'] = df_h['发布(更改)时间'].dt.dayofweek
    df_h['小时'] = df_h['发布(更改)时间'].dt.hour
    weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    avg = df_h.groupby(['星期', '小时'])['播放量'].mean()
    if avg.empty:
        return ""
    best_idx = avg.idxmax()
    return f"最佳发布时间：{weekday_names[best_idx[0]]} {best_idx[1]}:00（平均播放量 {avg.max():,.0f}）"


def analyze_hourly(df):
    df_h = df.copy()
    df_h['小时'] = df_h['发布(更改)时间'].dt.hour
    counts = df_h['小时'].value_counts()
    peak = counts.idxmax()
    return f"发布最频繁的时段：{peak}:00（共 {counts[peak]} 个视频）"


def analyze_engagement_boxplot(df):
    rates = {'弹幕率': df['弹幕率'].mean(), '投币率': df['投币率'].mean(),
             '收藏率': df['收藏率'].mean(), '转发率': df['转发率'].mean()}
    best = max(rates, key=rates.get)
    worst = min(rates, key=rates.get)
    return f"平均互动率最高：{best}（{rates[best]:.4%}），最低：{worst}（{rates[worst]:.4%}）"


def analyze_views_vs_coinrate(df):
    corr = df['播放量'].corr(df['投币率'])
    if corr > 0.3:
        return f"播放量与投币率正相关（r={corr:.2f}），高播放视频投币率也较高"
    elif corr < -0.3:
        return f"播放量与投币率负相关（r={corr:.2f}），高播放视频投币率反而较低"
    return f"播放量与投币率相关性弱（r={corr:.2f}），投币率不随播放量变化"


def analyze_views_vs_commentrate(df):
    corr = df['播放量'].corr(df['评论率'])
    if corr > 0.3:
        return f"播放量与评论率正相关（r={corr:.2f}），高播放视频引发更多讨论"
    elif corr < -0.3:
        return f"播放量与评论率负相关（r={corr:.2f}），娱乐向内容播放高但评论少"
    return f"播放量与评论率相关性弱（r={corr:.2f}），评论率独立于播放量"


def analyze_coin_ratio(df):
    valid = df[(df['点赞量'] > 0) & (df['投币数'] > 0)].copy()
    if valid.empty:
        return ""
    top = valid.nlargest(1, '点赞投币比').iloc[0]
    avg = valid['点赞投币比'].mean()
    return f"平均投币/点赞比: {avg:.3f}，最高: {top['标题'][:20]}...（{top['点赞投币比']:.3f}），比值越高说明内容越有深度"


def analyze_favorite_rate(df):
    top = df.nlargest(1, '收藏率').iloc[0]
    avg = df['收藏率'].mean()
    return f"平均收藏率: {avg:.4%}，最高: {top['标题'][:20]}...（{top['收藏率']:.4%}），高收藏 = 干货/教程类内容"


def analyze_cumulative(df):
    df_sorted = df.sort_values('发布(更改)时间')
    total = df_sorted['播放量'].sum()
    mid = len(df_sorted) // 2
    first_half = df_sorted.iloc[:mid]['播放量'].sum()
    second_half = df_sorted.iloc[mid:]['播放量'].sum()
    if second_half > first_half * 1.5:
        return f"增长加速：后半段播放量是前半段的 {second_half/first_half:.1f} 倍，账号在上升期"
    elif first_half > second_half * 1.5:
        return f"增长放缓：前半段播放量是后半段的 {first_half/second_half:.1f} 倍，早期内容表现更好"
    return f"增长平稳：前后半段播放量接近，累计 {total:,.0f}"


def analyze_interval(df):
    df_sorted = df.sort_values('发布(更改)时间')
    dates = df_sorted['发布(更改)时间'].dt.date.unique()
    if len(dates) < 2:
        return ""
    intervals = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
    return f"平均发布间隔: {sum(intervals)/len(intervals):.1f} 天，最长间隔: {max(intervals)} 天"


def analyze_views_wave(df):
    views = df['播放量']
    mean, std = views.mean(), views.std()
    threshold = mean + 2 * std
    burst_count = (views > threshold).sum()
    if burst_count > 0:
        names = '、'.join([t[:15] + '...' for t in df[views > threshold]['标题'].tolist()[:3]])
        return f"发现 {burst_count} 个爆款（超过均值+2σ={threshold:,.0f}）：{names}"
    return f"无明显爆款，播放量波动在正常范围内（均值 {mean:,.0f} ± {std:,.0f}）"


def analyze_monthly_trend(df):
    df_m = df.copy()
    df_m['发布年月'] = df_m['发布(更改)时间'].dt.to_period('M')
    monthly = df_m.groupby('发布年月').agg(发布数=('标题', 'count'), 平均播放量=('播放量', 'mean'))
    if monthly.empty:
        return ""
    best_month = monthly['平均播放量'].idxmax()
    most_active = monthly['发布数'].idxmax()
    return f"最佳月份: {best_month}（平均播放量 {monthly.loc[best_month, '平均播放量']:,.0f}），最活跃: {most_active}（发布 {monthly.loc[most_active, '发布数']} 个）"


def analyze_views_dist(df):
    views = df['播放量']
    mean, median = views.mean(), views.median()
    skew = (mean - median) / median if median > 0 else 0
    if skew > 0.5:
        return f"右偏分布：均值（{mean:,.0f}）远大于中位数（{median:,.0f}），少数爆款拉高了整体"
    elif skew < -0.5:
        return f"左偏分布：中位数（{median:,.0f}）大于均值（{mean:,.0f}），大部分视频表现不错"
    return f"近似正态：均值（{mean:,.0f}）与中位数（{median:,.0f}）接近，表现稳定"


def analyze_top_tags(df, top_n=20):
    all_tags = []
    for tags_str in df['标签'].dropna():
        if tags_str:
            all_tags.extend([t.strip() for t in str(tags_str).split(',') if t.strip()])
    if not all_tags:
        return ""
    counts = Counter(all_tags)
    top = counts.most_common(1)[0]
    return f"共 {len(counts)} 种标签，最高频: \"{top[0]}\"（{top[1]} 次），平均每视频 {len(all_tags)/len(df):.1f} 个标签"


def analyze_tag_impact(df, top_n=10):
    all_tags = []
    for tags_str in df['标签'].dropna():
        if tags_str:
            all_tags.extend([t.strip() for t in str(tags_str).split(',') if t.strip()])
    if not all_tags:
        return ""
    top_tags = [t for t, _ in Counter(all_tags).most_common(top_n)]
    results = []
    for tag in top_tags:
        has_avg = df[df['标签'].str.contains(tag, na=False)]['播放量'].mean()
        no_avg = df[~df['标签'].str.contains(tag, na=False)]['播放量'].mean()
        boost = (has_avg / no_avg - 1) * 100 if no_avg > 0 else 0
        results.append((tag, boost))
    results.sort(key=lambda x: x[1], reverse=True)
    best = results[0]
    if best[1] > 0:
        return f"最提播放量的标签: \"{best[0]}\"（比无该标签视频高 {best[1]:.0f}%）"
    return f"标签对播放量影响不大，最高: \"{best[0]}\"（{best[1]:+.0f}%）"


def analyze_cooccurrence(df):
    video_tags = []
    for tags_str in df['标签'].dropna():
        if tags_str:
            tags = [t.strip() for t in str(tags_str).split(',') if t.strip()]
            if len(tags) >= 2:
                video_tags.append(tags)
    if not video_tags:
        return ""
    pair_count = Counter()
    for tags in video_tags:
        for a, b in combinations(sorted(set(tags)), 2):
            pair_count[(a, b)] += 1
    if not pair_count:
        return ""
    top_pair = pair_count.most_common(1)[0]
    return f"最强标签组合: \"{top_pair[0][0]}\" + \"{top_pair[0][1]}\"（共现 {top_pair[1]} 次）"


def analyze_tag_trend(df, top_n=5):
    all_tags = []
    for tags_str in df['标签'].dropna():
        if tags_str:
            all_tags.extend([t.strip() for t in str(tags_str).split(',') if t.strip()])
    if not all_tags:
        return ""
    top_tags = [t for t, _ in Counter(all_tags).most_common(top_n)]
    df_m = df.copy()
    df_m['发布年月'] = df_m['发布(更改)时间'].dt.to_period('M')
    trends = []
    for tag in top_tags:
        monthly = df_m[df_m['标签'].str.contains(tag, na=False)].groupby('发布年月')['播放量'].mean()
        if len(monthly) >= 2:
            first = monthly.iloc[:3].mean()
            last = monthly.iloc[-3:].mean()
            change = (last / first - 1) * 100 if first > 0 else 0
            trends.append((tag, change))
    if not trends:
        return ""
    trends.sort(key=lambda x: x[1], reverse=True)
    best = trends[0]
    if best[1] > 20:
        return f"上升趋势标签: \"{best[0]}\"（近期播放量增长 {best[1]:.0f}%）"
    elif best[1] < -20:
        return f"下降趋势标签: \"{best[0]}\"（近期播放量下降 {abs(best[1]):.0f}%）"
    return f"标签热度稳定，变化最大的: \"{best[0]}\"（{best[1]:+.0f}%）"


# ============================== 图表函数 ==============================
def plot_top10_views(df):
    top10 = df.nlargest(10, '播放量').iloc[::-1]
    fig = go.Figure(go.Bar(
        x=top10['播放量'],
        y=[t[:25] + '...' if len(str(t)) > 25 else t for t in top10['标题']],
        orientation='h', marker_color='#00a1d6',
        text=top10['播放量'], textposition='outside',
    ))
    fig.update_layout(title='播放量 Top 10', title_font=TITLE_FONT,
                      xaxis_title='播放量', yaxis_title='', height=500, margin=dict(l=200))
    return fig


def plot_pareto(df):
    n_top = max(1, int(len(df) * 0.2))
    top_views = df.nlargest(n_top, '播放量')['播放量'].sum()
    rest_views = df['播放量'].sum() - top_views
    fig = go.Figure(go.Pie(
        labels=[f'Top {n_top} 视频', '其余视频'],
        values=[top_views, rest_views],
        marker_colors=['#00a1d6', '#e0e0e0'],
        textinfo='label+percent', hole=0.4,
    ))
    fig.update_layout(title=f'二八定律：Top {n_top} 视频占总播放量 {top_views/df["播放量"].sum()*100:.1f}%',
                      title_font=TITLE_FONT, height=400)
    return fig


def plot_duration_vs_views(df):
    df_dur = df[df['时长秒'] > 0].copy()
    if df_dur.empty:
        return None
    df_dur['时长(分钟)'] = (df_dur['时长秒'] / 60).round(1)
    fig = px.scatter(df_dur, x='时长(分钟)', y='播放量', color='投币数',
                     color_continuous_scale='viridis', hover_data=['标题'],
                     title='视频时长 vs 播放量')
    fig.update_layout(title_font=TITLE_FONT, height=500)
    return fig


def plot_duration_boxplot(df):
    df_dur = df[df['时长秒'] > 0].copy()
    if df_dur.empty:
        return None
    bins = [0, 60, 300, 900, 3600, float('inf')]
    labels = ['<1分钟', '1-5分钟', '5-15分钟', '15-60分钟', '>60分钟']
    df_dur['时长分段'] = pd.cut(df_dur['时长秒'], bins=bins, labels=labels, right=False)
    fig = go.Figure()
    colors = ['#ff6b6b', '#ffa502', '#00a1d6', '#7bed9f', '#a29bfe']
    for label, color in zip(labels, colors):
        segment = df_dur[df_dur['时长分段'] == label]
        if not segment.empty:
            fig.add_trace(go.Box(y=segment['播放量'], name=label, marker_color=color))
    fig.update_layout(title='不同时长段的播放量分布', title_font=TITLE_FONT,
                      yaxis_title='播放量', height=450)
    return fig


def plot_hour_heatmap(df):
    df_h = df.copy()
    df_h['星期'] = df_h['发布(更改)时间'].dt.dayofweek
    df_h['小时'] = df_h['发布(更改)时间'].dt.hour
    weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    pivot = df_h.groupby(['星期', '小时'])['播放量'].mean().unstack(fill_value=0)
    for h in range(24):
        if h not in pivot.columns:
            pivot[h] = 0
    pivot = pivot[sorted(pivot.columns)]
    pivot.index = [weekday_names[i] for i in pivot.index]
    fig = go.Figure(go.Heatmap(
        z=pivot.values, x=[f'{h}:00' for h in pivot.columns], y=pivot.index,
        colorscale='YlOrRd', text=pivot.values.round(0).astype(int),
        texttemplate='%{text}', textfont={"size": 10},
    ))
    fig.update_layout(title='星期 × 小时 平均播放量热力图', title_font=TITLE_FONT,
                      xaxis_title='小时', yaxis_title='', height=400)
    return fig


def plot_hourly_distribution(df):
    df_h = df.copy()
    df_h['小时'] = df_h['发布(更改)时间'].dt.hour
    hour_dist = df_h['小时'].value_counts().sort_index()
    fig = go.Figure(go.Bar(x=hour_dist.index, y=hour_dist.values, marker_color='#fb7299'))
    fig.update_layout(title='发布时间分布（按小时）', title_font=TITLE_FONT,
                      xaxis=dict(title='小时', dtick=1), yaxis_title='视频数', height=400)
    return fig


def plot_engagement_boxplot(df):
    rate_cols = ['弹幕率', '投币率', '收藏率', '转发率']
    fig = go.Figure()
    colors = ['#00a1d6', '#fb7299', '#ffb81c', '#6dc781']
    for col, color in zip(rate_cols, colors):
        fig.add_trace(go.Box(y=df[col], name=col, marker_color=color))
    fig.update_layout(title='互动率分布', title_font=TITLE_FONT, yaxis_title='比率', height=400)
    return fig


def plot_views_vs_coinrate(df):
    color_col = '评论数' if '评论数' in df.columns and df['评论数'].sum() > 0 else '弹幕数'
    fig = px.scatter(df, x='播放量', y='投币率', color=color_col,
                     color_continuous_scale='purpor', hover_data=['标题'],
                     title='播放量 vs 投币率')
    fig.update_layout(title_font=TITLE_FONT, height=500)
    return fig


def plot_views_vs_commentrate(df):
    fig = px.scatter(df, x='播放量', y='评论率', color='弹幕数',
                     color_continuous_scale='tealgrn', hover_data=['标题'],
                     title='播放量 vs 评论率')
    fig.update_layout(title_font=TITLE_FONT, height=500)
    return fig


def plot_top10_coin_ratio(df):
    valid = df[(df['点赞量'] > 0) & (df['投币数'] > 0)].copy()
    if valid.empty:
        return None
    top10 = valid.nlargest(10, '点赞投币比').iloc[::-1]
    fig = go.Figure(go.Bar(
        x=top10['点赞投币比'],
        y=[t[:25] + '...' if len(str(t)) > 25 else t for t in top10['标题']],
        orientation='h', marker_color='#fb7299',
        text=top10['点赞投币比'].round(3), textposition='outside',
    ))
    fig.update_layout(title='点赞投币比 Top 10（比值越高 = 内容越"深度"）', title_font=TITLE_FONT,
                      xaxis_title='投币/点赞', height=500, margin=dict(l=200))
    return fig


def plot_top10_favorite_rate(df):
    top10 = df.nlargest(10, '收藏率').iloc[::-1]
    fig = go.Figure(go.Bar(
        x=top10['收藏率'],
        y=[t[:25] + '...' if len(str(t)) > 25 else t for t in top10['标题']],
        orientation='h', marker_color='#ffb81c',
        text=(top10['收藏率'] * 100).round(2).astype(str) + '%', textposition='outside',
    ))
    fig.update_layout(title='收藏率 Top 10（最"干货"内容）', title_font=TITLE_FONT,
                      xaxis_title='收藏率', height=500, margin=dict(l=200))
    return fig


def plot_cumulative_views(df):
    df_sorted = df.sort_values('发布(更改)时间').copy()
    df_sorted['累计播放量'] = df_sorted['播放量'].cumsum()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_sorted['发布(更改)时间'], y=df_sorted['累计播放量'],
        mode='lines', fill='tozeroy', line=dict(color='#00a1d6', width=2),
    ))
    fig.update_layout(title='累计播放量增长曲线', title_font=TITLE_FONT,
                      xaxis_title='发布时间', yaxis_title='累计播放量', height=450)
    return fig


def plot_publish_interval(df):
    df_sorted = df.sort_values('发布(更改)时间').copy()
    dates = df_sorted['发布(更改)时间'].dt.date.unique()
    if len(dates) < 2:
        return None
    intervals = [{'日期': dates[i], '间隔天数': (dates[i] - dates[i - 1]).days} for i in range(1, len(dates))]
    df_int = pd.DataFrame(intervals)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_int['日期'], y=df_int['间隔天数'], mode='lines+markers',
        line=dict(color='#fb7299', width=1.5), marker=dict(size=5),
    ))
    fig.update_layout(title='视频发布间隔（天）', title_font=TITLE_FONT,
                      xaxis_title='日期', yaxis_title='间隔天数', height=400)
    return fig


def plot_views_wave(df):
    df_sorted = df.sort_values('发布(更改)时间').copy()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(range(1, len(df_sorted) + 1)), y=df_sorted['播放量'],
        mode='lines+markers', line=dict(color='#00a1d6', width=1.5), marker=dict(size=4),
        text=df_sorted['标题'], hovertemplate='%{text}<br>播放量: %{y}',
    ))
    mean, std = df_sorted['播放量'].mean(), df_sorted['播放量'].std()
    threshold = mean + 2 * std
    burst = df_sorted[df_sorted['播放量'] > threshold]
    if not burst.empty:
        fig.add_trace(go.Scatter(
            x=[list(df_sorted.index).index(i) + 1 for i in burst.index], y=burst['播放量'],
            mode='markers', marker=dict(size=12, color='red', symbol='star'),
            name='爆款', text=burst['标题'], hovertemplate='%{text}<br>播放量: %{y}',
        ))
    fig.update_layout(title='单视频播放量（红色=爆款，均值+2σ）', title_font=TITLE_FONT,
                      xaxis_title='视频序号（按发布时间）', yaxis_title='播放量', height=450)
    return fig


def plot_monthly_trend(df):
    df_m = df.copy()
    df_m['发布年月'] = df_m['发布(更改)时间'].dt.to_period('M')
    monthly = df_m.groupby('发布年月').agg(发布数=('标题', 'count'), 平均播放量=('播放量', 'mean')).reset_index()
    monthly['发布年月'] = monthly['发布年月'].astype(str)
    monthly['平均播放量'] = monthly['平均播放量'].round(0).astype(int)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=monthly['发布年月'], y=monthly['发布数'],
                         name='发布数', marker_color='#fb7299', opacity=0.7), secondary_y=False)
    fig.add_trace(go.Scatter(x=monthly['发布年月'], y=monthly['平均播放量'],
                             name='平均播放量', mode='lines+markers',
                             line=dict(color='#00a1d6', width=2.5)), secondary_y=True)
    fig.update_layout(title='月度趋势', title_font=TITLE_FONT, height=450)
    fig.update_xaxes(title_text='月份')
    fig.update_yaxes(title_text='发布数', secondary_y=False)
    fig.update_yaxes(title_text='平均播放量', secondary_y=True)
    return fig


def plot_views_distribution(df):
    views = df[df['播放量'] > 0]['播放量']
    if views.empty:
        return go.Figure()
    log_min = np.log10(views.min())
    log_max = np.log10(views.max())
    counts, edges = np.histogram(views, bins=np.logspace(log_min, log_max, 25))
    bin_left, bin_right = edges[:-1], edges[1:]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=bin_left, y=counts, width=bin_right - bin_left,
                         marker_color='#00a1d6', opacity=0.7, name='视频数'))
    fig.add_vline(x=views.mean(), line_dash='dash', line_color='red',
                  annotation_text=f'均值: {views.mean():,.0f}')
    fig.add_vline(x=views.median(), line_dash='dash', line_color='orange',
                  annotation_text=f'中位数: {views.median():,.0f}')
    fig.update_layout(title='播放量分布（对数等距分桶）', title_font=TITLE_FONT,
                      xaxis=dict(title='播放量', type='log'), yaxis_title='视频数', height=400)
    return fig


def generate_wordcloud(tags_series):
    all_tags = []
    for tags_str in tags_series.dropna():
        if tags_str:
            all_tags.extend([t.strip() for t in str(tags_str).split(',') if t.strip()])
    if not all_tags:
        return None
    wc = WordCloud(font_path='C:/Windows/Fonts/msyh.ttc', width=800, height=400,
                   background_color='white', max_words=100, colormap='viridis').generate(' '.join(all_tags))
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.imshow(wc, interpolation='bilinear')
    ax.axis('off')
    return fig


def plot_top_tags(df, top_n=20):
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
    fig = go.Figure(go.Bar(x=list(counts)[::-1], y=list(tags)[::-1],
                           orientation='h', marker_color='#00a1d6'))
    fig.update_layout(title=f'高频标签 Top {top_n}', title_font=TITLE_FONT,
                      xaxis_title='出现次数', height=430, margin=dict(l=150))
    return fig


def plot_tag_impact(df, top_n=10):
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
    fig.update_layout(title=f'Top {top_n} 标签对播放量的影响', title_font=TITLE_FONT,
                      barmode='group', yaxis_title='平均播放量', height=430)
    return fig


def plot_tag_cooccurrence(df, top_n=15):
    if '标签' not in df.columns:
        return None
    video_tags = []
    for tags_str in df['标签'].dropna():
        if tags_str:
            tags = [t.strip() for t in str(tags_str).split(',') if t.strip()]
            if len(tags) >= 2:
                video_tags.append(tags)
    if not video_tags:
        return None
    all_tags = [t for tags in video_tags for t in tags]
    top_tags_set = {t for t, _ in Counter(all_tags).most_common(top_n)}
    pair_count = Counter()
    for tags in video_tags:
        filtered = [t for t in tags if t in top_tags_set]
        for a, b in combinations(sorted(set(filtered)), 2):
            pair_count[(a, b)] += 1
    filtered_weights = [w for w in pair_count.values() if w >= 2]
    if not filtered_weights:
        return None
    tag_counts = Counter(all_tags)
    max_count = max(tag_counts.values()) if tag_counts else 1
    max_weight = max(filtered_weights)
    min_weight = min(filtered_weights)
    node_tags = list(top_tags_set)
    n = len(node_tags)
    angles = [2 * math.pi * i / n for i in range(n)]
    pos = {tag: (math.cos(a), math.sin(a)) for tag, a in zip(node_tags, angles)}
    fig = go.Figure()
    for (a, b), weight in pair_count.items():
        if weight < 2:
            continue
        x0, y0 = pos[a]
        x1, y1 = pos[b]
        norm = (weight - min_weight) / (max_weight - min_weight) if max_weight > min_weight else 0.5
        line_w = 1.5 + norm * 8.5
        fig.add_trace(go.Scatter(
            x=[x0, x1, None], y=[y0, y1, None], mode='lines',
            line=dict(width=line_w, color='rgba(160,160,160,0.6)'),
            hoverinfo='skip', showlegend=False,
        ))
    node_x = [pos[t][0] for t in node_tags]
    node_y = [pos[t][1] for t in node_tags]
    node_size = [max(18, tag_counts[t] / max_count * 70) for t in node_tags]
    fig.add_trace(go.Scatter(
        x=node_x, y=node_y, mode='markers+text',
        marker=dict(size=node_size, color='#00a1d6',
                    line=dict(width=1.5, color='white')),
        text=[t[:5] for t in node_tags], textposition='top center',
        textfont=dict(size=11, color='#333'),
        hovertext=[f'{t}（{tag_counts[t]}次）' for t in node_tags], hoverinfo='text', showlegend=False,
    ))
    fig.update_layout(title=f'Top {top_n} 标签共现网络', title_font=TITLE_FONT,
                      xaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                                 range=[-2.0, 2.0]),
                      yaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                                 range=[-1.3, 1.3]),
                      hoverlabel=dict(font_size=14),
                      height=600, plot_bgcolor='white')
    return fig


def plot_tag_trend(df, top_n=5):
    if '标签' not in df.columns:
        return None
    all_tags = []
    for tags_str in df['标签'].dropna():
        if tags_str:
            all_tags.extend([t.strip() for t in str(tags_str).split(',') if t.strip()])
    if not all_tags:
        return None
    top_tags = [t for t, _ in Counter(all_tags).most_common(top_n)]
    df_m = df.copy()
    df_m['发布年月'] = df_m['发布(更改)时间'].dt.to_period('M')
    fig = go.Figure()
    colors = ['#00a1d6', '#fb7299', '#ffb81c', '#6dc781', '#a29bfe']
    for tag, color in zip(top_tags, colors):
        monthly = df_m[df_m['标签'].str.contains(tag, na=False)].groupby('发布年月')['播放量'].mean()
        if monthly.empty:
            continue
        monthly.index = monthly.index.astype(str)
        fig.add_trace(go.Scatter(x=monthly.index, y=monthly.values, name=tag,
                                 mode='lines+markers', line=dict(color=color, width=2)))
    fig.update_layout(title=f'Top {top_n} 标签的平均播放量月度趋势', title_font=TITLE_FONT,
                      xaxis_title='月份', yaxis_title='平均播放量', height=450)
    return fig


# ============================== 导出功能 ==============================
def generate_excel(uid, basic, df):
    from io import BytesIO
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        center_format = workbook.add_format({"align": "center", "valign": "vcenter"})
        percent_format = workbook.add_format({'num_format': '0.000%', 'align': 'center'})
        int_format = workbook.add_format({'num_format': '#,##0', 'align': 'center'})
        header_fmt = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'bold': True,
                                          'fg_color': '#7BC4E8', 'font_color': '#FFFFFF', 'border': 1})
        row_even_fmt = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'fg_color': '#E8F4FD', 'border': 1})
        row_odd_fmt = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'fg_color': '#F5FAFE', 'border': 1})
        section_fmt = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'bold': True,
                                           'fg_color': '#5BA3D9', 'font_color': '#FFFFFF', 'border': 1})
        percent_fmt_even = workbook.add_format({'num_format': '0.000%', 'align': 'center', 'fg_color': '#E8F4FD', 'border': 1})
        percent_fmt_odd = workbook.add_format({'num_format': '0.000%', 'align': 'center', 'fg_color': '#F5FAFE', 'border': 1})
        int_fmt_even = workbook.add_format({'num_format': '#,##0', 'align': 'center', 'fg_color': '#E8F4FD', 'border': 1})
        int_fmt_odd = workbook.add_format({'num_format': '#,##0', 'align': 'center', 'fg_color': '#F5FAFE', 'border': 1})

        stats1 = df[['播放量', '弹幕数', '投币数', '收藏量', '转发量']].describe()
        stats1.to_excel(writer, sheet_name='Data_Describe', index=True, index_label='Metrics', float_format='%.0f')
        ws1 = writer.sheets['Data_Describe']
        nrows1, ncols1 = stats1.shape
        ws1.set_column(0, ncols1, 12, center_format)
        ws1.set_row(0, None, header_fmt)
        for r in range(nrows1):
            ws1.set_row(r + 1, None, row_even_fmt if r % 2 == 0 else row_odd_fmt)

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

        df_m = df.copy()
        df_m['发布年月'] = df_m['发布(更改)时间'].dt.to_period('M')
        monthly_stats = df_m.groupby('发布年月').agg(发布视频数=('标题', 'count'), 平均播放量=('播放量', 'mean'), 播放量中位数=('播放量', 'median')).reset_index()
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

        top_view = df.nlargest(5, '播放量')[['标题', '播放量']]
        top_dm = df.nlargest(5, '弹幕率')[['标题', '弹幕率', '弹幕数']]
        top_coin = df.nlargest(5, '投币率')[['标题', '投币率', '投币数']]
        top_fav = df.nlargest(5, '收藏率')[['标题', '收藏率', '收藏量']]
        top5_data = [('播放量 Top 5', top_view, False), ('弹幕率 Top 5', top_dm, True),
                     ('投币率 Top 5', top_coin, True), ('收藏率 Top 5', top_fav, True)]
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
    lines = [f'# UID:{uid} 数据分析报告\n', f'**总视频数**: {len(df)}\n', '## 基础数据\n']
    lines.append(f'- 昵称: {basic.get("昵称", "")}')
    lines.append(f'- 粉丝数: {int(basic.get("粉丝数", 0)):,}')
    if basic.get('获赞数'):
        lines.append(f'- 获赞数: {int(basic.get("获赞数", 0)):,}')
    if basic.get('播放数'):
        lines.append(f'- 播放数: {int(basic.get("播放数", 0)):,}')
    lines.extend(['\n## 播放量统计\n', '| 指标 | 数值 |', '|------|------|',
                  f'| 均值 | {df["播放量"].mean():.0f} |', f'| 中位数 | {df["播放量"].median():.0f} |',
                  f'| 最高 | {df["播放量"].max()} |', f'| 最低 | {df["播放量"].min()} |', '\n## 播放量 Top 5\n'])
    for i, (_, row) in enumerate(df.nlargest(5, '播放量').iterrows(), 1):
        lines.append(f'{i}. **{row["标题"]}** — {row["播放量"]:,} 播放')
    lines.append('\n## 月度趋势\n')
    df_m = df.copy()
    df_m['发布年月'] = df_m['发布(更改)时间'].dt.to_period('M')
    monthly = df_m.groupby('发布年月').agg(发布数=('标题', 'count'), 平均播放量=('播放量', 'mean')).reset_index()
    monthly['发布年月'] = monthly['发布年月'].astype(str)
    monthly['平均播放量'] = monthly['平均播放量'].round(0).astype(int)
    lines.extend(['| 月份 | 发布数 | 平均播放量 |', '|------|--------|------------|'])
    for _, row in monthly.iterrows():
        lines.append(f'| {row["发布年月"]} | {row["发布数"]} | {row["平均播放量"]:,} |')
    return '\n'.join(lines)


# ============================== 侧边栏 ==============================
st.sidebar.title("B站数据分析看板")
uid_list = get_available_uids()
uid_options = [f"{nickname} ({uid})" for uid, nickname in uid_list]
selected_uid = None
if uid_options:
    col_sel, col_del = st.sidebar.columns([4, 1])
    with col_sel:
        selected = st.selectbox("选择已有 UP 主", uid_options, label_visibility="collapsed")
    selected_uid = selected.split('(')[-1].rstrip(')')

    if 'confirm_delete' not in st.session_state:
        st.session_state['confirm_delete'] = None
    with col_del:
        if st.button("删除", key="delete_uid_btn"):
            st.session_state['confirm_delete'] = selected_uid
            st.rerun()

    if st.session_state.get('confirm_delete') == selected_uid:
        st.sidebar.warning(f"确认删除 UID {selected_uid} 的所有数据？")
        col_yes, col_no = st.sidebar.columns(2)
        with col_yes:
            if st.button("确认", key="confirm_yes", type="primary", use_container_width=True):
                delete_uid(selected_uid)
                st.session_state['confirm_delete'] = None
                st.rerun()
        with col_no:
            if st.button("取消", key="confirm_no", use_container_width=True):
                st.session_state['confirm_delete'] = None
                st.rerun()

st.sidebar.divider()
st.sidebar.subheader("爬取新 UP 主")
new_uid = st.sidebar.text_input("输入 B站 UID")
is_crawling = 'crawl_proc' in st.session_state
btn_col1, btn_col2 = st.sidebar.columns(2)
with btn_col1:
    crawl_btn = st.button("开始爬取", disabled=(not new_uid or is_crawling), use_container_width=True)
with btn_col2:
    stop_btn = st.button("停止爬取", disabled=not is_crawling, use_container_width=True, key="stop_crawl")

st.markdown("""<style>
div[data-testid="stSidebar"] button[data-testid="stBaseButton-stop_crawl"] { background-color: #ff4b4b !important; color: white !important; border: none !important; }
div[data-testid="stSidebar"] button[data-testid="stBaseButton-stop_crawl"]:disabled { background-color: #cccccc !important; color: #999999 !important; }
</style>""", unsafe_allow_html=True)

if crawl_btn and new_uid:
    import threading
    from queue import Queue
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script_path = os.path.join(project_root, 'crawler', 'bilibili_selenium.py')
    log_queue = Queue()
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    proc = subprocess.Popen([sys.executable, '-u', script_path, '--uid', new_uid],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1,
                            text=True, encoding='utf-8', errors='replace', cwd=project_root, env=env)

    def read_output(proc, queue):
        for line in proc.stdout:
            queue.put(line.strip())
        proc.wait()
        queue.put(None)

    threading.Thread(target=read_output, args=(proc, log_queue), daemon=True).start()
    st.session_state['crawl_proc'] = proc
    st.session_state['crawl_uid'] = new_uid
    st.session_state['crawl_logs'] = []
    st.session_state['crawl_queue'] = log_queue
    st.rerun()

if 'crawl_proc' in st.session_state:
    proc = st.session_state['crawl_proc']
    log_lines = st.session_state['crawl_logs']
    queue = st.session_state['crawl_queue']
    while not queue.empty():
        line = queue.get_nowait()
        if line is None:
            break
        log_lines.append(line)
    if stop_btn:
        proc.terminate()
        for key in ['crawl_proc', 'crawl_logs', 'crawl_queue', 'crawl_progress']:
            if key in st.session_state:
                del st.session_state[key]
        st.sidebar.warning("已停止爬取")
        st.rerun()
    progress, progress_text = 0.0, ""
    for line in reversed(log_lines):
        match = re.search(r'爬取第\s*(\d+)/(\d+)\s*个视频', line)
        if match:
            current, total = int(match.group(1)), int(match.group(2))
            progress = current / total
            progress_text = f"{current}/{total}"
            break
    if progress > 0:
        st.sidebar.progress(progress, text=f"进度: {progress_text}")
    if proc.poll() is not None:
        if proc.returncode == 0:
            elapsed = ''
            for line in log_lines:
                m = re.search(r'总用时:\s*([\d.]+)s', line)
                if m:
                    elapsed = m.group(1)
                    break
            st.sidebar.success(f"爬取完成！耗时 {elapsed}s" if elapsed else "爬取完成！")
            selected_uid = st.session_state['crawl_uid']
            uid_list = get_available_uids()
        else:
            st.sidebar.error(f"爬取失败，返回码: {proc.returncode}")
        for key in ['crawl_proc', 'crawl_logs', 'crawl_queue']:
            if key in st.session_state:
                del st.session_state[key]
    else:
        st.sidebar.info(f"正在爬取 UID: {st.session_state['crawl_uid']}")
        st.sidebar.text_area("爬取日志", '\n'.join(reversed(log_lines[-15:])), height=250)
        time.sleep(0.5)
        st.rerun()


# ============================== 主页面 ==============================
if selected_uid:
    basic = load_basic_data(selected_uid)
    df_raw = load_video_data(selected_uid)
    if basic is not None and df_raw is not None:
        df, clean_log = clean_data(df_raw)
        df_tag = df[df['标签'].notna() & (df['标签'] != '')].copy()

        st.sidebar.divider()
        st.sidebar.subheader("数据清洗")
        for msg in clean_log:
            st.sidebar.caption(f"· {msg}")

        st.sidebar.divider()
        st.sidebar.subheader("数据导出")
        excel_bytes = generate_excel(selected_uid, basic, df)
        st.sidebar.download_button(label="下载 Excel 报告", data=excel_bytes,
                                   file_name=f"UID_{selected_uid}_report.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        md_content = generate_markdown(selected_uid, basic, df)
        st.sidebar.download_button(label="下载 Markdown 报告", data=md_content,
                                   file_name=f"UID_{selected_uid}_report.md", mime="text/markdown")

if not selected_uid:
    st.info("请在左侧选择一个 UP 主，或输入新的 UID 进行爬取")
    st.stop()

if basic is None or df_raw is None:
    st.error(f"UID {selected_uid} 的数据加载失败")
    st.stop()

st.title(f"📊 {basic.get('昵称', selected_uid)} 的 B站数据分析")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 数据概览", "🎯 内容策略", "💬 互动分析", "📈 生命周期", "🏷️ 标签分析"])

# ============================== Tab1: 数据概览 ==============================
with tab1:
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1: st.metric("UID", selected_uid)
    with col2: st.metric("粉丝数", f"{int(basic.get('粉丝数', 0)):,}")
    with col3: st.metric("获赞数", f"{int(basic.get('获赞数', 0)):,}" if basic.get('获赞数') else "无数据")
    with col4: st.metric("播放数", f"{int(basic.get('播放数', 0)):,}" if basic.get('播放数') else "无数据")
    with col5: st.metric("总视频数", len(df))

    st.divider()

    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a: st.metric("平均播放量", f"{df['播放量'].mean():,.0f}")
    with col_b: st.metric("播放量中位数", f"{df['播放量'].median():,.0f}")
    with col_c: st.metric("平均弹幕率", f"{df['弹幕率'].mean():.4%}")
    with col_d: st.metric("平均投币率", f"{df['投币率'].mean():.4%}")

    st.divider()

    total_views = int(basic.get('播放数', 0)) if basic.get('播放数') else 0
    followers = int(basic.get('粉丝数', 0)) if basic.get('粉丝数') else 0
    fan_avg = total_views / followers if followers > 0 else 0
    total_engagement = df['点赞量'].sum() + df['投币数'].sum() + df['收藏量'].sum() + df['转发量'].sum() + df['评论数'].sum()
    total_video_views = df['播放量'].sum()
    overall_eng_rate = total_engagement / total_video_views if total_video_views > 0 else 0

    col_e, col_f, col_g = st.columns(3)
    with col_e: st.metric("粉均播放量", f"{fan_avg:,.1f}")
    with col_f: st.metric("综合互动率", f"{overall_eng_rate:.4%}")
    with col_g:
        n_top = max(1, int(len(df) * 0.2))
        st.metric(f"Top 20% 视频占比", f"{df.nlargest(n_top, '播放量')['播放量'].sum() / total_video_views * 100:.1f}%")

    st.divider()

    col_chart1, col_chart2 = st.columns(2)
    with col_chart1: st.plotly_chart(plot_top10_views(df), use_container_width=True)
    with col_chart2: st.plotly_chart(plot_pareto(df), use_container_width=True)
    a1, a2 = st.columns(2)
    with a1: st.markdown(f"<b>分析：</b>{analyze_top10_views(df)}", unsafe_allow_html=True)
    with a2: st.markdown(f"<b>分析：</b>{analyze_pareto(df)}", unsafe_allow_html=True)

# ============================== Tab2: 内容策略 ==============================
with tab2:
    st.subheader("时长分析")
    dur_fig1 = plot_duration_vs_views(df)
    dur_fig2 = plot_duration_boxplot(df)
    if dur_fig1 and dur_fig2:
        col_d1, col_d2 = st.columns(2)
        with col_d1: st.plotly_chart(dur_fig1, use_container_width=True)
        with col_d2: st.plotly_chart(dur_fig2, use_container_width=True)
        a1, a2 = st.columns(2)
        with a1: st.markdown(f"<b>分析：</b>{analyze_duration_scatter(df)}", unsafe_allow_html=True)
        with a2: st.markdown(f"<b>分析：</b>{analyze_duration_boxplot(df)}", unsafe_allow_html=True)
    else:
        st.info("当前数据缺少视频时长信息，请使用最新版爬虫重新爬取")

    st.divider()

    st.subheader("发布时间分析")
    col_h1, col_h2 = st.columns(2)
    with col_h1: st.plotly_chart(plot_hour_heatmap(df), use_container_width=True)
    with col_h2: st.plotly_chart(plot_hourly_distribution(df), use_container_width=True)
    a1, a2 = st.columns(2)
    with a1: st.markdown(f"<b>分析：</b>{analyze_heatmap(df)}", unsafe_allow_html=True)
    with a2: st.markdown(f"<b>分析：</b>{analyze_hourly(df)}", unsafe_allow_html=True)

# ============================== Tab3: 互动分析 ==============================
with tab3:
    st.subheader("互动率分布")
    col_i1, col_i2 = st.columns(2)
    with col_i1: st.plotly_chart(plot_engagement_boxplot(df), use_container_width=True)
    with col_i2: st.plotly_chart(plot_views_vs_coinrate(df), use_container_width=True)
    a1, a2 = st.columns(2)
    with a1: st.markdown(f"<b>分析：</b>{analyze_engagement_boxplot(df)}", unsafe_allow_html=True)
    with a2: st.markdown(f"<b>分析：</b>{analyze_views_vs_coinrate(df)}", unsafe_allow_html=True)

    st.divider()

    st.subheader("深度互动")
    col_i3, col_i4 = st.columns(2)
    with col_i3: st.plotly_chart(plot_views_vs_commentrate(df), use_container_width=True)
    with col_i4:
        fig_coin_ratio = plot_top10_coin_ratio(df)
        if fig_coin_ratio:
            st.plotly_chart(fig_coin_ratio, use_container_width=True)
        else:
            st.info("无法计算点赞投币比")
    a1, a2 = st.columns(2)
    with a1: st.markdown(f"<b>分析：</b>{analyze_views_vs_commentrate(df)}", unsafe_allow_html=True)
    with a2:
        if fig_coin_ratio:
            st.markdown(f"<b>分析：</b>{analyze_coin_ratio(df)}", unsafe_allow_html=True)

    st.divider()

    st.subheader("干货内容")
    fig_fav = plot_top10_favorite_rate(df)
    if fig_fav:
        st.plotly_chart(fig_fav, use_container_width=True)
        st.markdown(f"<b>分析：</b>{analyze_favorite_rate(df)}", unsafe_allow_html=True)

# ============================== Tab4: 生命周期 ==============================
with tab4:
    st.subheader("增长趋势")
    st.plotly_chart(plot_cumulative_views(df), use_container_width=True)
    st.markdown(f"<b>分析：</b>{analyze_cumulative(df)}", unsafe_allow_html=True)

    st.divider()

    st.subheader("更新节奏")
    col_l1, col_l2 = st.columns(2)
    with col_l1:
        fig_interval = plot_publish_interval(df)
        if fig_interval:
            st.plotly_chart(fig_interval, use_container_width=True)
        else:
            st.info("视频数量不足，无法计算发布间隔")
    with col_l2:
        st.plotly_chart(plot_views_wave(df), use_container_width=True)
    a1, a2 = st.columns(2)
    with a1:
        if fig_interval:
            st.markdown(f"<b>分析：</b>{analyze_interval(df)}", unsafe_allow_html=True)
    with a2:
        st.markdown(f"<b>分析：</b>{analyze_views_wave(df)}", unsafe_allow_html=True)

    st.divider()

    st.subheader("月度与分布")
    col_l3, col_l4 = st.columns(2)
    with col_l3: st.plotly_chart(plot_monthly_trend(df), use_container_width=True)
    with col_l4: st.plotly_chart(plot_views_distribution(df), use_container_width=True)
    a1, a2 = st.columns(2)
    with a1: st.markdown(f"<b>分析：</b>{analyze_monthly_trend(df)}", unsafe_allow_html=True)
    with a2: st.markdown(f"<b>分析：</b>{analyze_views_dist(df)}", unsafe_allow_html=True)

# ============================== Tab5: 标签分析 ==============================
with tab5:
    if df_tag.empty:
        st.info("当前数据没有标签信息，请使用最新版爬虫重新爬取以获取标签数据")
    else:
        st.caption(f"有标签视频: {len(df_tag)}/{len(df)} 条")

        st.subheader("标签概览")
        wc_fig = generate_wordcloud(df_tag['标签'])
        if wc_fig:
            _, col_wc, _ = st.columns([1, 6, 1])
            with col_wc:
                st.pyplot(wc_fig)
        else:
            st.info("无标签数据")

        col_wc1, col_wc2 = st.columns(2)
        with col_wc1:
            top_tags_fig = plot_top_tags(df_tag, top_n=20)
            if top_tags_fig:
                st.plotly_chart(top_tags_fig, use_container_width=True)
        with col_wc2:
            impact_fig = plot_tag_impact(df, top_n=10)
            if impact_fig:
                st.plotly_chart(impact_fig, use_container_width=True)
        a1, a2 = st.columns(2)
        with a1:
            if top_tags_fig:
                st.markdown(f"<b>分析：</b>{analyze_top_tags(df_tag, top_n=20)}", unsafe_allow_html=True)
        with a2:
            if impact_fig:
                st.markdown(f"<b>分析：</b>{analyze_tag_impact(df, top_n=10)}", unsafe_allow_html=True)

        st.divider()

        st.subheader("标签关系与趋势")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            cooc_fig = plot_tag_cooccurrence(df_tag, top_n=15)
            if cooc_fig:
                st.plotly_chart(cooc_fig, use_container_width=True)
            else:
                st.info("标签共现数据不足")
        with col_t2:
            trend_fig = plot_tag_trend(df, top_n=5)
            if trend_fig:
                st.plotly_chart(trend_fig, use_container_width=True)
            else:
                st.info("标签趋势数据不足")
        a1, a2 = st.columns(2)
        with a1:
            if cooc_fig:
                st.markdown(f"<b>分析：</b>{analyze_cooccurrence(df_tag)}", unsafe_allow_html=True)
        with a2:
            if trend_fig:
                st.markdown(f"<b>分析：</b>{analyze_tag_trend(df, top_n=5)}", unsafe_allow_html=True)
