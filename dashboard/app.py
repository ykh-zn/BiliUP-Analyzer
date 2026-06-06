import streamlit as st
import os
import re
import sys
import time
import subprocess

from data import (
    get_available_uids, delete_uid, load_basic_data, load_video_data,
    clean_data, generate_excel, generate_markdown, RAW_DIR,
)
from analysis import (
    analyze_top10_views, analyze_pareto, analyze_duration_scatter,
    analyze_duration_boxplot, analyze_heatmap, analyze_hourly,
    analyze_engagement_boxplot, analyze_views_vs_coinrate,
    analyze_views_vs_commentrate, analyze_coin_ratio, analyze_favorite_rate,
    analyze_cumulative, analyze_interval, analyze_views_wave,
    analyze_monthly_trend, analyze_views_dist, analyze_top_tags,
    analyze_tag_impact, analyze_cooccurrence, analyze_tag_trend,
)
from charts import (
    plot_top10_views, plot_pareto, plot_duration_vs_views,
    plot_duration_boxplot, plot_hour_heatmap, plot_hourly_distribution,
    plot_engagement_boxplot, plot_views_vs_coinrate, plot_views_vs_commentrate,
    plot_top10_coin_ratio, plot_top10_favorite_rate, plot_cumulative_views,
    plot_publish_interval, plot_views_wave, plot_monthly_trend,
    plot_views_distribution, generate_wordcloud, plot_top_tags,
    plot_tag_impact, plot_tag_cooccurrence, plot_tag_trend,
)

# ============================== 页面配置 ==============================
st.set_page_config(
    page_title="B站数据分析看板",
    page_icon="📊",
    layout="wide",
)

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
        md_content = generate_markdown(selected_uid, basic, df)
        st.sidebar.download_button(label="下载 Markdown 报告", data=md_content,
                                   file_name=f"UID_{selected_uid}_report.md", mime="text/markdown")
        excel_bytes = generate_excel(selected_uid, basic, df_raw)
        st.sidebar.download_button(label="下载 Excel", data=excel_bytes,
                                   file_name=f"UID_{selected_uid}_video_data.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        vdata_path = os.path.join(RAW_DIR, f'UID_{selected_uid}', 'video_data.json')
        if os.path.exists(vdata_path):
            with open(vdata_path, 'r', encoding='utf-8') as f:
                vdata_bytes = f.read().encode('utf-8')
            st.sidebar.download_button(label="下载原始 JSON", data=vdata_bytes,
                                       file_name=f"UID_{selected_uid}_video_data.json", mime="application/json")

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
