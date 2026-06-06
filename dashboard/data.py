import os
import json
import re
import shutil
import pandas as pd

RAW_DIR = os.path.join('.', 'data', 'raw')
SAMPLE_DIR = os.path.join('.', 'data', 'sample')


def convert_count(value):
    """将B站数值字符串转为int，支持'1.2万'格式"""
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
    """扫描data/raw和data/sample目录，返回已爬取的(UID, 昵称)列表"""
    uids = []
    for base_dir in [RAW_DIR, SAMPLE_DIR]:
        if not os.path.isdir(base_dir):
            continue
        for d in os.listdir(base_dir):
            if d.startswith('UID_'):
                uid = d[4:]
                if any(u[0] == uid for u in uids):
                    continue
                basic_path = os.path.join(base_dir, d, 'basic_data.json')
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
    """删除指定UID的全部数据目录"""
    target = os.path.join(RAW_DIR, f'UID_{uid}')
    if os.path.isdir(target):
        shutil.rmtree(target)
        return True
    return False


def load_basic_data(uid):
    """加载指定UID的UP主基础信息（昵称、粉丝、获赞等），优先raw目录，fallback到sample"""
    for base_dir in [RAW_DIR, SAMPLE_DIR]:
        path = os.path.join(base_dir, f'UID_{uid}', 'basic_data.json')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data:
                return data[0]
    return None


def parse_duration(dur_str):
    """将'HH:MM:SS'或'MM:SS'格式时长转为总秒数"""
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
    """加载视频数据JSON，清洗类型，计算互动率等衍生指标，优先raw目录，fallback到sample"""
    data = None
    for base_dir in [RAW_DIR, SAMPLE_DIR]:
        path = os.path.join(base_dir, f'UID_{uid}', 'video_data.json')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data:
                break
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
    """清洗数据：排除播放量=0、去重、统计空标签/简介，返回(清洗后df, 日志列表)"""
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


def generate_excel(uid, basic, df_raw):
    """生成格式化Excel文件（表头样式、斑马纹、自动筛选），返回bytes"""
    from io import BytesIO

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        center_format = workbook.add_format({"align": "center", "valign": "vcenter"})
        left_format = workbook.add_format({"align": "left", "valign": "vcenter", "text_wrap": True})
        int_format = workbook.add_format({'num_format': '#,##0', 'align': 'center'})
        header_fmt = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'bold': True,
                                          'fg_color': '#7BC4E8', 'font_color': '#FFFFFF', 'border': 1})
        row_even_fmt = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'fg_color': '#E8F4FD', 'border': 1})
        row_odd_fmt = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'fg_color': '#F5FAFE', 'border': 1})

        df_raw.to_excel(writer, sheet_name='Video_Data', index=False)
        ws = writer.sheets['Video_Data']
        nrows, ncols = df_raw.shape
        ws.set_column(0, 0, 6, center_format)    # 序号
        ws.set_column(1, 1, 40, left_format)     # 标题
        ws.set_column(2, 2, 50, left_format)     # 简介
        ws.set_column(3, 3, 10, center_format)   # 视频时长
        ws.set_column(4, 4, 30, left_format)     # 标签
        for col_name in ['播放量', '弹幕数', '点赞量', '投币数', '收藏量', '转发量', '评论数']:
            if col_name in df_raw.columns:
                ci = df_raw.columns.get_loc(col_name)
                ws.set_column(ci, ci, 12, int_format)
        if '发布(更改)时间' in df_raw.columns:
            ci = df_raw.columns.get_loc('发布(更改)时间')
            ws.set_column(ci, ci, 20, center_format)
        if '视频链接' in df_raw.columns:
            ci = df_raw.columns.get_loc('视频链接')
            ws.set_column(ci, ci, 50, left_format)
        ws.set_row(0, None, header_fmt)
        for r in range(nrows):
            ws.set_row(r + 1, None, row_even_fmt if r % 2 == 0 else row_odd_fmt)
        ws.autofilter(0, 0, nrows, ncols - 1)
    return output.getvalue()


def generate_markdown(uid, basic, df):
    """生成Markdown格式的数据分析报告"""
    lines = [f'# UID:{uid} 数据分析报告\n', f'**总视频数**: {len(df)}\n', '## 基础数据\n']
    lines.append(f'- 昵称: {basic.get("昵称", "")}')
    lines.append(f'- 粉丝数: {int(basic.get("粉丝数", 0)):,}')
    if basic.get('获赞数'):
        lines.append(f'- 获赞数: {int(basic.get("获赞数", 0)):,}')
    if basic.get('播放数'):
        lines.append(f'- 播放数: {int(basic.get("播放数", 0)):,}')
    lines.extend(['\n## 播放量统计\n', '| 指标 | 数值 |', '|------|------|',
                  f'| 均值 | {df["播放量"].mean():.0f} |', f'| 中位数 | {df["播放量"].median():.0f} |',
                  f'| 最高 | {int(df["播放量"].max()):,} |', f'| 最低 | {int(df["播放量"].min()):,} |', '\n## 播放量 Top 5\n'])
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
