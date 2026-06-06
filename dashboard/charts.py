import math
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
from collections import Counter
from itertools import combinations
from wordcloud import WordCloud
import matplotlib.pyplot as plt

TITLE_FONT = dict(size=20)

pio.templates.default = 'plotly'
pio.templates['plotly'].layout.hoverlabel.font.size = 16


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
