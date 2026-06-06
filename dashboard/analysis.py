import pandas as pd
from collections import Counter
from itertools import combinations


def analyze_top10_views(df):
    """分析Top10播放量视频的头部效应"""
    top10 = df.nlargest(10, '播放量')
    t1, t10 = top10.iloc[0], top10.iloc[-1]
    gap = t1['播放量'] / t10['播放量'] if t10['播放量'] > 0 else 0
    avg = df['播放量'].mean()
    above_avg = (df['播放量'] > avg).sum()
    return f"Top1 播放量是 Top10 的 {gap:.1f} 倍，共 {above_avg}/{len(df)} 个视频超过均值 ({avg:,.0f})"


def analyze_pareto(df):
    """分析二八定律：Top20%视频占总播放量的比例"""
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
    """分析不同时长区间的平均播放量，找出最佳时长"""
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
    """分析不同时长段的中位数播放量"""
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
    """分析星期×小时维度的最佳发布时间"""
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
    """分析发布最频繁的时段"""
    df_h = df.copy()
    df_h['小时'] = df_h['发布(更改)时间'].dt.hour
    counts = df_h['小时'].value_counts()
    peak = counts.idxmax()
    return f"发布最频繁的时段：{peak}:00（共 {counts[peak]} 个视频）"


def analyze_engagement_boxplot(df):
    """分析各类互动率的高低对比"""
    rates = {'弹幕率': df['弹幕率'].mean(), '投币率': df['投币率'].mean(),
             '收藏率': df['收藏率'].mean(), '转发率': df['转发率'].mean()}
    best = max(rates, key=rates.get)
    worst = min(rates, key=rates.get)
    return f"平均互动率最高：{best}（{rates[best]:.4%}），最低：{worst}（{rates[worst]:.4%}）"


def analyze_views_vs_coinrate(df):
    """分析播放量与投币率的相关性"""
    corr = df['播放量'].corr(df['投币率'])
    if corr > 0.3:
        return f"播放量与投币率正相关（r={corr:.2f}），高播放视频投币率也较高"
    elif corr < -0.3:
        return f"播放量与投币率负相关（r={corr:.2f}），高播放视频投币率反而较低"
    return f"播放量与投币率相关性弱（r={corr:.2f}），投币率不随播放量变化"


def analyze_views_vs_commentrate(df):
    """分析播放量与评论率的相关性"""
    corr = df['播放量'].corr(df['评论率'])
    if corr > 0.3:
        return f"播放量与评论率正相关（r={corr:.2f}），高播放视频引发更多讨论"
    elif corr < -0.3:
        return f"播放量与评论率负相关（r={corr:.2f}），娱乐向内容播放高但评论少"
    return f"播放量与评论率相关性弱（r={corr:.2f}），评论率独立于播放量"


def analyze_coin_ratio(df):
    """分析点赞投币比，比值越高说明内容越有深度"""
    valid = df[(df['点赞量'] > 0) & (df['投币数'] > 0)].copy()
    if valid.empty:
        return ""
    top = valid.nlargest(1, '点赞投币比').iloc[0]
    avg = valid['点赞投币比'].mean()
    return f"平均投币/点赞比: {avg:.3f}，最高: {top['标题'][:20]}...（{top['点赞投币比']:.3f}），比值越高说明内容越有深度"


def analyze_favorite_rate(df):
    """分析收藏率，高收藏率代表干货/教程类内容"""
    top = df.nlargest(1, '收藏率').iloc[0]
    avg = df['收藏率'].mean()
    return f"平均收藏率: {avg:.4%}，最高: {top['标题'][:20]}...（{top['收藏率']:.4%}），高收藏 = 干货/教程类内容"


def analyze_cumulative(df):
    """分析累计播放量增长趋势（加速/放缓/平稳）"""
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
    """分析视频发布间隔的平均值和最大值"""
    df_sorted = df.sort_values('发布(更改)时间')
    dates = df_sorted['发布(更改)时间'].dt.date.unique()
    if len(dates) < 2:
        return ""
    intervals = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
    return f"平均发布间隔: {sum(intervals)/len(intervals):.1f} 天，最长间隔: {max(intervals)} 天"


def analyze_views_wave(df):
    """识别爆款视频（超过均值+2σ）"""
    views = df['播放量']
    mean, std = views.mean(), views.std()
    threshold = mean + 2 * std
    burst_count = (views > threshold).sum()
    if burst_count > 0:
        names = '、'.join([t[:15] + '...' for t in df[views > threshold]['标题'].tolist()[:3]])
        return f"发现 {burst_count} 个爆款（超过均值+2σ={threshold:,.0f}）：{names}"
    return f"无明显爆款，播放量波动在正常范围内（均值 {mean:,.0f} ± {std:,.0f}）"


def analyze_monthly_trend(df):
    """分析月度发布数和平均播放量趋势"""
    df_m = df.copy()
    df_m['发布年月'] = df_m['发布(更改)时间'].dt.to_period('M')
    monthly = df_m.groupby('发布年月').agg(发布数=('标题', 'count'), 平均播放量=('播放量', 'mean'))
    if monthly.empty:
        return ""
    best_month = monthly['平均播放量'].idxmax()
    most_active = monthly['发布数'].idxmax()
    return f"最佳月份: {best_month}（平均播放量 {monthly.loc[best_month, '平均播放量']:,.0f}），最活跃: {most_active}（发布 {monthly.loc[most_active, '发布数']} 个）"


def analyze_views_dist(df):
    """分析播放量分布的偏态（右偏/左偏/正态）"""
    views = df['播放量']
    mean, median = views.mean(), views.median()
    skew = (mean - median) / median if median > 0 else 0
    if skew > 0.5:
        return f"右偏分布：均值（{mean:,.0f}）远大于中位数（{median:,.0f}），少数爆款拉高了整体"
    elif skew < -0.5:
        return f"左偏分布：中位数（{median:,.0f}）大于均值（{mean:,.0f}），大部分视频表现不错"
    return f"近似正态：均值（{mean:,.0f}）与中位数（{median:,.0f}）接近，表现稳定"


def analyze_top_tags(df, top_n=20):
    """统计高频标签和平均每视频标签数"""
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
    """分析Top标签对播放量的提升效果"""
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
    """分析标签共现关系，找出最强标签组合"""
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
    """分析Top标签的播放量月度趋势变化"""
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
