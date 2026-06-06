import requests
import json
import time
import random
import hashlib
import urllib.parse
import os
import argparse
from datetime import datetime

# ============================== 参数解析 ==============================
parser = argparse.ArgumentParser()
parser.add_argument('--uid', type=str, default='527299525', help='B站UP主UID')
args = parser.parse_args()
UID = args.uid

# ============================== 路径配置 ==============================
data_dir_path = os.path.join('.', 'data', 'raw', f'UID_{UID}')
os.makedirs(data_dir_path, exist_ok=True)
cookies_path = os.path.join('.', 'data', 'cookies.json')

# ============================== 请求配置 ==============================
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    'Referer': 'https://www.bilibili.com',
}
session = requests.Session()
session.headers.update(HEADERS)

# ============================== WBI 签名 ==============================
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]


def get_mixin_key(orig: str) -> str:
    """按MIXIN_KEY_ENC_TAB索引表重排字符串，取前32位作为签名密钥"""
    return ''.join([orig[i] for i in MIXIN_KEY_ENC_TAB])[:32]


def enc_wbi(params: dict, img_key: str, sub_key: str) -> dict:
    """对请求参数进行WBI签名：排序→过滤特殊字符→拼接密钥→MD5哈希"""
    mixin_key = get_mixin_key(img_key + sub_key)
    params['wts'] = round(time.time())
    params = dict(sorted(params.items()))
    params = {
        k: ''.join(filter(lambda ch: ch not in "!'()*", str(v)))
        for k, v in params.items()
    }
    query = urllib.parse.urlencode(params)
    params['w_rid'] = hashlib.md5((query + mixin_key).encode()).hexdigest()
    return params


def get_wbi_keys():
    """从 nav API 获取 img_key 和 sub_key"""
    resp = session.get('https://api.bilibili.com/x/web-interface/nav').json()
    img_url = resp['data']['wbi_img']['img_url']
    sub_url = resp['data']['wbi_img']['sub_url']
    img_key = img_url.split('/')[-1].split('.')[0]
    sub_key = sub_url.split('/')[-1].split('.')[0]
    return img_key, sub_key


# ============================== 带重试的请求 ==============================
def api_get(url, params=None, max_retries=3):
    """GET 请求，遇到 -412 等风控自动等待重试"""
    for attempt in range(max_retries):
        resp = session.get(url, params=params).json()
        code = resp.get('code', -1)
        if code == 0:
            return resp
        if code in (-412, -352):
            wait = (attempt + 1) * 5 + random.uniform(1, 3)
            print(f"  触发风控 (code={code})，等待 {wait:.0f}s 后重试 ({attempt + 1}/{max_retries})...")
            time.sleep(wait)
            continue
        return resp  # 其他错误直接返回
    return resp  # 重试用完


# ============================== 工具函数 ==============================
def format_duration(seconds):
    """秒数转 MM:SS 或 HH:MM:SS"""
    if not seconds:
        return ''
    seconds = int(seconds)
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f'{h}:{m:02d}:{s:02d}'
    return f'{m}:{s:02d}'


def format_time(timestamp):
    """Unix 时间戳转可读时间"""
    if not timestamp:
        return ''
    return datetime.fromtimestamp(int(timestamp)).strftime('%Y-%m-%d %H:%M:%S')


# ============================== 登录 ==============================
start_time = time.time()
print('检查登录状态...')


def load_cookies():
    """加载 cookies 并验证"""
    if not os.path.exists(cookies_path):
        return False
    try:
        with open(cookies_path, 'r', encoding='utf-8') as f:
            cookies_list = json.load(f)
        if not cookies_list:
            return False
        for item in cookies_list:
            session.cookies.set(item['name'], item['value'],
                                domain=item.get('domain', '.bilibili.com'))
        # 验证登录
        resp = session.get('https://api.bilibili.com/x/web-interface/nav').json()
        if resp['code'] == 0 and resp['data'].get('isLogin'):
            print(f"登录有效，用户: {resp['data']['uname']}")
            return True
        return False
    except Exception:
        return False


def selenium_login():
    """Selenium 扫码登录获取 cookies"""
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    print('请在浏览器进行登录，如登录后无反应请手动刷新页面')

    options = webdriver.EdgeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-infobars")

    driver = webdriver.Edge(options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    driver.set_window_size(1000, 800)
    driver.set_window_position(0, 0)

    driver.get("https://www.bilibili.com")

    try:
        WebDriverWait(driver, 60).until(
            EC.invisibility_of_element_located(
                (By.XPATH, '//*[@id="app"]//div[@class="bili-header__bar"]//ul[@class="right-entry"]//div[@class="header-login-entry"]')
            )
        )
    except Exception:
        driver.close()
        raise TimeoutError('登录超时请稍后重试')

    # 提取 cookies
    selenium_cookies = driver.get_cookies()
    driver.close()

    # 保存到文件
    with open(cookies_path, 'w', encoding='utf-8') as f:
        json.dump(selenium_cookies, f, ensure_ascii=False, indent=4)
    print('登录成功，已保存 Cookies')

    # 加载到 session
    for item in selenium_cookies:
        session.cookies.set(item['name'], item['value'],
                            domain=item.get('domain', '.bilibili.com'))


if not load_cookies():
    selenium_login()

# ============================== 获取 WBI 密钥 ==============================
print('获取 WBI 密钥...')
img_key, sub_key = get_wbi_keys()

# ============================== 视频列表 ==============================
print('获取视频列表...')


def fetch_video_list(uid, img_key, sub_key):
    """分页获取所有视频 bvid 列表"""
    video_list = []
    pn = 1
    ps = 50

    while True:
        params = enc_wbi({
            'mid': uid,
            'ps': ps,
            'pn': pn,
            'order': 'pubdate',
            'tid': 0,
        }, img_key, sub_key)

        resp = session.get(
            'https://api.bilibili.com/x/space/wbi/arc/search',
            params=params
        ).json()

        if resp['code'] != 0:
            print(f"获取视频列表失败: {resp['message']} (code: {resp['code']})")
            break

        vlist = resp['data']['list']['vlist']
        total = resp['data']['page']['count']

        if not vlist:
            break

        for v in vlist:
            video_list.append({
                'bvid': v['bvid'],
                'title': v['title'],
            })

        print(f"  第 {pn} 页，已获取 {len(video_list)}/{total} 个视频")

        if len(video_list) >= total:
            break

        pn += 1
        time.sleep(random.uniform(0.05, 0.1))

    return video_list


video_list = fetch_video_list(UID, img_key, sub_key)
num_all_video = len(video_list)
print(f'共获取到 {num_all_video} 个视频，开始爬取详情...')

# ============================== 视频详情（新 API） ==============================
video_data_json = []
error_time = 0

for idx, video in enumerate(video_list, start=1):
    bvid = video['bvid']
    try:
        print(f'爬取第 {idx}/{num_all_video} 个视频: {bvid}...')

        # 使用 view/detail API（一个请求拿到所有数据）
        resp = api_get(
            f'https://api.bilibili.com/x/web-interface/view/detail?bvid={bvid}'
        )

        if resp['code'] != 0:
            print(f"  失败: {resp['message']}")
            error_time += 1
            continue

        detail = resp['data']
        view = detail['View']
        stat = view['stat']
        card = detail.get('Card', {})
        tags_list = detail.get('Tags', [])

        # 第一个视频时保存 UP 主基础数据
        if idx == 1:
            card_info = card.get('card', {})
            # 补充总播放数（Card 里没有）
            upstat_resp = session.get(f'https://api.bilibili.com/x/space/upstat?mid={UID}').json()
            total_views = upstat_resp['data'].get('archive', {}).get('view', 0) if upstat_resp['code'] == 0 else 0

            basic_data_json = [{
                'UID': UID,
                '昵称': card_info.get('name', ''),
                '签名': card_info.get('sign', ''),
                '等级': card_info.get('level_info', {}).get('current_level', 0),
                '粉丝数': str(card.get('follower', 0)),
                '关注数': str(card_info.get('attention', 0)),
                '获赞数': str(card.get('like_num', 0)),
                '播放数': str(total_views),
                '作品数': str(card.get('archive_count', 0)),
                '文章数': str(card.get('article_count', 0)),
            }]
            basic_data_path = os.path.join(data_dir_path, 'basic_data.json')
            with open(basic_data_path, 'w', encoding='utf-8') as f:
                json.dump(basic_data_json, f, ensure_ascii=False, indent=4)

            print('=' * 50)
            print(f"UID:{UID}")
            print(f"昵称:{basic_data_json[0]['昵称']}")
            print(f"粉丝数:{int(basic_data_json[0]['粉丝数']):,}")
            print(f"获赞数:{int(basic_data_json[0]['获赞数']):,}")
            print(f"播放数:{int(basic_data_json[0]['播放数']):,}")
            print(f"作品数:{basic_data_json[0]['作品数']}")
            print('=' * 50)
            print(f'基础数据保存成功: {basic_data_path}')

        # 标签
        tags = ','.join([t['tag_name'] for t in tags_list]) if tags_list else ''

        # 格式化时长和发布时间
        duration = format_duration(view.get('duration', 0))
        pubdate = format_time(view.get('pubdate', 0))

        # 保存到 video_data.json（与看板兼容的格式）
        video_info = {
            '序号': idx,
            '标题': view['title'],
            '简介': view.get('desc', ''),
            '视频时长': duration,
            '标签': tags,
            '播放量': str(stat['view']),
            '弹幕数': str(stat['danmaku']),
            '发布(更改)时间': pubdate,
            '点赞量': str(stat['like']),
            '投币数': str(stat['coin']),
            '收藏量': str(stat['favorite']),
            '转发量': str(stat['share']),
            '评论数': str(stat['reply']),
            '视频链接': f'https://www.bilibili.com/video/{bvid}',
        }
        video_data_json.append(video_info)

        time.sleep(random.uniform(0.05, 0.1))

    except Exception as e:
        print(f'第 {idx} 条视频爬取失败: {e}')
        error_time += 1
        continue

# ============================== 保存数据 ==============================
# 保存 video_data.json（看板读取）
video_data_path = os.path.join(data_dir_path, 'video_data.json')
if video_data_json:
    with open(video_data_path, 'w', encoding='utf-8') as f:
        json.dump(video_data_json, f, ensure_ascii=False, indent=4)
    print(f'视频数据保存成功: {video_data_path}')

# 统计
num_success = len(video_data_json)
print(f'成功爬取: {num_success}/{num_all_video}')
if error_time:
    print(f'失败: {error_time}')
    print(f'成功率: {num_success / num_all_video * 100:.2f}%')
else:
    print('成功率: 100.00%')

end_time = time.time()
print(f'总用时: {end_time - start_time:.1f}s')
