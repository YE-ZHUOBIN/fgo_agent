import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from bs4 import BeautifulSoup
import json
import re
import time
import os

# ====================== 全局配置 ======================
BASE = "https://fgo.wiki"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
}
session = requests.Session()
session.headers.update(HEADERS)
retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET", "POST"])
adapter = HTTPAdapter(max_retries=retry)
session.mount("https://", adapter)
session.mount("http://", adapter)

# 数据目录（相对于仓库文件夹）
DATA_DIR = os.path.join(os.path.dirname(__file__), "rag_crawl_data")
os.makedirs(DATA_DIR, exist_ok=True)

# ====================== 公共工具函数 ======================
def clean(s):
    if not s:
        return ""
    s = re.sub(r"\s+", " ", s).strip()
    s = s.replace("​", "").replace("\u200b", "").replace("\xa0", " ")
    return s

def save_rag(arr, fn):
    with open(fn, "w", encoding="utf-8") as f:
        for x in arr:
            f.write(x.get("rag_text", "") + "\n\n")


def extract_table_values(soup, key_map):
    values = {}
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [clean(cell.get_text()) for cell in tr.find_all(["th", "td"])]
            if len(cells) < 2:
                continue
            pairs = []
            if len(cells) == 2:
                pairs.append((cells[0], cells[1]))
            else:
                for idx in range(0, len(cells) - 1, 2):
                    pairs.append((cells[idx], cells[idx + 1]))
            for label, value in pairs:
                for field, variants in key_map.items():
                    if any(keyword in label for keyword in variants):
                        if field not in values or not values[field]:
                            values[field] = value
    return values


def get_category_links(category_name):
    api_url = BASE + "/api.php"
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": f"Category:{category_name}",
        "cmtype": "page",
        "cmlimit": 500,
        "format": "json"
    }
    links = set()
    while True:
        resp = session.get(api_url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        for page in data.get("query", {}).get("categorymembers", []):
            title = page.get("title", "")
            if title and ":" not in title:
                links.add("/w/" + requests.utils.requote_uri(title).replace(" ", "_"))
        cont = data.get("continue")
        if not cont:
            break
        params.update(cont)
    print(f"通过分类 {category_name} 找到链接：{len(links)} 个")
    return sorted(links)


def _load_existing_json(fn):
    try:
        with open(fn, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def _existing_name_set(data_list, key_choices=('name', 'skill_name')):
    s = set()
    for item in data_list:
        for k in key_choices:
            if k in item and item[k]:
                s.add(clean(item[k]))
                break
    return s

# ====================== 1. 爬取从者（API稳定版） ======================
def get_servant_links_via_api():
    api_url = "https://fgo.wiki/api.php?action=query&list=categorymembers&cmtitle=Category:从者&cmtype=page&cmlimit=500&format=json"
    try:
        resp = session.get(api_url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        pages = data.get("query", {}).get("categorymembers", [])
        links = []
        for page in pages:
            title = page.get("title", "")
            if title and "从者" not in title and ":" not in title:
                links.append(f"{BASE}/w/{title}")
        links = sorted(list(set(links)))
        print(f"通过 API 找到从者：{len(links)} 个")
        return links
    except Exception as e:
        print(f"API 请求失败：{e}")
        return []

def crawl_servants():
    print("\n=== 开始爬从者 ===")
    links = get_servant_links_via_api()
    if not links:
        print("未获取到从者链接，跳过")
        return []
    # load existing
    exist_file = os.path.join(DATA_DIR, "fgo_servants.json")
    existing = _load_existing_json(exist_file)
    existing_names = _existing_name_set(existing, ('name',))

    data = []
    for url in links:
        try:
            # try to extract title from url to skip network if already exists
            title_seg = url.split('/w/')[-1]
            candidate = requests.utils.unquote(title_seg).replace('_', ' ')
            if clean(candidate) in existing_names:
                print("skip existing =>", candidate)
                continue
            print("get url =>", url)
            html = session.get(url, timeout=10).text
            s = BeautifulSoup(html, "lxml")
            d = {"url": url}

            d["name"] = clean(s.find("h1").text)
            ib = s.find("table", class_="infobox")
            for tr in ib.find_all("tr") if ib else []:
                th, td = tr.find("th"), tr.find("td")
                if th and td:
                    k, v = clean(th.text), clean(td.text)
                    if "职阶" in k:
                        d["cls"] = v
                    if "星级" in k:
                        d["star"] = v
                    if "配卡" in k:
                        d["deck"] = v

            d["skills"] = []
            for tab in s.select("table.skilltable")[:3]:
                d["skills"].append(clean(tab.text))

            np_sec = s.find("span", id=re.compile("宝具"))
            d["np"] = clean(np_sec.find_next("table").text) if np_sec else ""

            mat_sec = s.find("span", id=re.compile("素材|灵基|强化|技能强化"))
            d["mat"] = clean(mat_sec.find_next("table").text) if mat_sec else ""

            d["rag_text"] = f"""【从者】{d.get('name')}
【职阶】{d.get('cls','')} 【星级】{d.get('star','')} 【配卡】{d.get('deck','')}
【技能1】{d['skills'][0] if len(d['skills'])>0 else ''}
【技能2】{d['skills'][1] if len(d['skills'])>1 else ''}
【技能3】{d['skills'][2] if len(d['skills'])>2 else ''}
【宝具】{d.get('np','')}
【素材】{d.get('mat','')}
"""
            data.append(d)
            time.sleep(0.6)
        except Exception:
            continue
    # merge with existing and write
    merged = existing + [x for x in data if clean(x.get('name','')) not in existing_names]
    with open(os.path.join(DATA_DIR, "fgo_servants.json"), "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    save_rag(merged, os.path.join(DATA_DIR, "rag_servants.txt"))
    added = len(merged) - len(existing)
    print(f"✅ 从者完成：{len(merged)} 个（新增 {added} 个）")
    return merged

# ====================== 2. 爬取全量怪物 ======================
def crawl_enemy():
    print("\n=== 开始全量怪物数据爬取 ===")
    enemy_index_pages = [
        "/w/Enemy"
    ]
    enemy_detail_links = set()

    for idx_path in enemy_index_pages:
        url = BASE + idx_path
        try:
            res = session.get(url, timeout=12)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "lxml")
            for a in soup.select('table.wikitable a[href^="/w/"]'):
                link = a["href"]
                if "#" not in link:
                    enemy_detail_links.add(link)
            time.sleep(0.8)
        except Exception as e:
            print(f"分类页失败 {idx_path}: {e}")

    print(f"共计待爬怪物：{len(enemy_detail_links)} 只")
    # load existing
    exist_file = os.path.join(DATA_DIR, "fgo_enemy_full.json")
    existing = _load_existing_json(exist_file)
    existing_names = _existing_name_set(existing, ('name',))

    enemy_all = []

    for sub_url in enemy_detail_links:
        full = BASE + sub_url
        try:
            resp = session.get(full, timeout=12)
            resp.raise_for_status()
            sp = BeautifulSoup(resp.text, "lxml")
            name = clean(sp.find("h1").text)
            info = {
                "name": name,
                "wiki_path": sub_url,
                "class": "",
                "attribute": "",
                "trait": "",
                "skill": "",
                "np": "",
                "instant_death_rate": "",
                "rag_text": ""
            }
            base_table = sp.find("table", class_="closetable")
            if base_table:
                trs = base_table.find_all("tr")
                for tr in trs:
                    td = [clean(x.text) for x in tr.find_all("td")]
                    if len(td) < 2:
                        continue
                    k, v = td[0], td[1]
                    if "职阶" in k:
                        info["class"] = v
                    elif "属性" in k:
                        info["attribute"] = v
                    elif "特性" in k:
                        info["trait"] = v
                    elif "被即死率" in k:
                        info["instant_death_rate"] = v

            skill_block = sp.find("span", string=lambda x: x and "技能" in x)
            if skill_block:
                info["skill"] = clean(skill_block.find_next("table").text)
            np_block = sp.find("span", string=lambda x: x and "宝具" in x)
            if np_block:
                info["np"] = clean(np_block.find_next("table").text)

            info["rag_text"] = f"""【敌方怪物】{info['name']}
职阶：{info['class']}｜属性：{info['attribute']}｜特性：{info['trait']}
被即死率：{info['instant_death_rate']}
技能：{info['skill']}
宝具：{info['np']}
"""
            # skip if already exists
            if clean(info['name']) in existing_names:
                print('skip existing enemy', info['name'])
            else:
                enemy_all.append(info)
            time.sleep(0.7)
        except Exception as e:
            print(f"怪物页面异常 {sub_url}: {e}")

    merged = existing + [x for x in enemy_all if clean(x.get('name','')) not in existing_names]
    with open(os.path.join(DATA_DIR, "fgo_enemy_full.json"), "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    save_rag(merged, os.path.join(DATA_DIR, "rag_enemy.txt"))
    added = len(merged) - len(existing)
    print(f"✅ 全量怪物完成：{len(merged)} 只（新增 {added} 只）")
    return merged

# ====================== 3. 爬取概念礼装 ======================
def crawl_ce():
    print("\n=== 开始爬取全概念礼装 ===")
    ce_links = set(get_category_links("概念礼装"))
    print(f"待爬礼装总数：{len(ce_links)}")
    # load existing
    exist_file = os.path.join(DATA_DIR, "fgo_ce.json")
    existing = _load_existing_json(exist_file)
    existing_names = _existing_name_set(existing, ('name',))
    ce_data = []

    key_map = {
        "star": ["星级"],
        "atk": ["ATK", "攻击力"],
        "hp": ["HP", "生命值", "体力"],
        "effect": ["固有效果", "效果", "礼装效果"],
        "max_effect": ["满破效果", "满破后效果", "宝具升级效果"]
    }

    for path in ce_links:
        try:
            # try skip by path title
            title_seg = path.split('/w/')[-1]
            candidate = requests.utils.unquote(title_seg).replace('_', ' ')
            if clean(candidate) in existing_names:
                print('skip existing ce', candidate)
                continue
            sp = BeautifulSoup(session.get(BASE + path, timeout=12).text, "lxml")
            name = clean(sp.find("h1").text if sp.find("h1") else "")
            item = {
                "name": name,
                "wiki_path": path,
                "star": "",
                "atk": "",
                "hp": "",
                "effect": "",
                "max_effect": "",
                "rag_text": ""
            }
            values = extract_table_values(sp, key_map)
            item.update({k: values.get(k, "") for k in ["star", "atk", "hp", "effect", "max_effect"]})

            if not item["effect"]:
                fallback = sp.find(string=re.compile("固有效果|效果|礼装效果"))
                if fallback:
                    t = fallback.find_next("table")
                    if t:
                        item["effect"] = clean(t.text)

            item["rag_text"] = f"""【概念礼装】{name}
星级：{item['star']}｜ATK:{item['atk']} HP:{item['hp']}
基础效果：{item['effect']}
满破效果：{item['max_effect']}"""
            ce_data.append(item)
            time.sleep(0.5)
        except Exception as e:
            print("礼装异常", path, e)
    merged = existing + [x for x in ce_data if clean(x.get('name','')) not in existing_names]
    with open(os.path.join(DATA_DIR, "fgo_ce.json"), "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    save_rag(merged, os.path.join(DATA_DIR, "rag_ce.txt"))
    added = len(merged) - len(existing)
    print(f"✅ 礼装完成：{len(merged)} 件（新增 {added} 件）")
    return merged

# ====================== 4. 爬取指令纹章 ======================
def crawl_cm():
    print("\n=== 开始爬指令纹章 ===")
    cm_links = set(get_category_links("指令纹章"))
    # load existing
    exist_file = os.path.join(DATA_DIR, "fgo_cm.json")
    existing = _load_existing_json(exist_file)
    existing_names = _existing_name_set(existing, ('name',))
    if not cm_links:
        res = session.get(BASE + "/w/指令纹章", timeout=12)
        soup = BeautifulSoup(res.text, "lxml")
        for a in soup.select('table.wikitable a[href^="/w/"]'):
            h = a["href"]
            if "#" not in h:
                cm_links.add(h)
    print(f"待爬纹章 {len(cm_links)}")
    cm_data = []

    key_map = {
        "star": ["星级"],
        "effect": ["效果", "效果说明", "说明"]
    }

    for p in cm_links:
        try:
            title_seg = p.split('/w/')[-1]
            candidate = requests.utils.unquote(title_seg).replace('_', ' ')
            if clean(candidate) in existing_names:
                print('skip existing cm', candidate)
                continue
            sp = BeautifulSoup(session.get(BASE + p, timeout=12).text, "lxml")
            name = clean(sp.find("h1").text if sp.find("h1") else "")
            d = {"name": name, "path": p, "star": "", "effect": "", "rag_text": ""}
            values = extract_table_values(sp, key_map)
            d.update({k: values.get(k, "") for k in ["star", "effect"]})
            if not d["effect"]:
                fallback = sp.find(string=re.compile("效果|说明"))
                if fallback:
                    nxt = fallback.find_next("table")
                    if nxt:
                        d["effect"] = clean(nxt.text)
            d["rag_text"] = f"""【指令纹章】{name}｜星级:{d['star']}
效果：{d['effect']}"""
            cm_data.append(d)
            time.sleep(0.4)
        except Exception as e:
            print("纹章报错", p, e)

    merged = existing + [x for x in cm_data if clean(x.get('name','')) not in existing_names]
    with open(os.path.join(DATA_DIR, "fgo_cm.json"), "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    save_rag(merged, os.path.join(DATA_DIR, "rag_cm.txt"))
    added = len(merged) - len(existing)
    print(f"✅ 纹章完成：{len(merged)} 个（新增 {added} 个）")
    return merged

# ====================== 5. 爬取魔术礼装(御主礼装) ======================
def crawl_mc():
    print("\n=== 开始爬魔术礼装(御主) ===")
    mc_links = set()
    res = session.get(BASE + "/w/魔术礼装", timeout=12)
    soup = BeautifulSoup(res.text, "lxml")
    for a in soup.select('table.wikitable a[href^="/w/"]'):
        h = a["href"]
        if "#" not in h:
            mc_links.add(h)
    print(f"待爬魔术礼装 {len(mc_links)} 套")
    # load existing
    exist_file = os.path.join(DATA_DIR, "fgo_mc.json")
    existing = _load_existing_json(exist_file)
    existing_names = _existing_name_set(existing, ('name',))
    mc_data = []

    for p in mc_links:
        try:
            title_seg = p.split('/w/')[-1]
            candidate = requests.utils.unquote(title_seg).replace('_', ' ')
            if clean(candidate) in existing_names:
                print('skip existing mc', candidate)
                continue
            sp = BeautifulSoup(session.get(BASE + p, timeout=12).text, "lxml")
            name = clean(sp.find("h1").text)
            d = {"name": name, "path": p, "get_way": "", "skill_list": "", "rag_text": ""}
            tb = sp.find("table", class_="closetable")
            if tb:
                for tr in tb.find_all("tr"):
                    td = [clean(x.text) for x in tr.find_all("td")]
                    if len(td) < 2:
                        continue
                    if "获取" in td[0]:
                        d["get_way"] = td[1]

            skill_block = sp.find_all("span", class_="mw-headline")
            sk_text = ""
            for s in skill_block:
                sk_text += clean(s.text) + ":" + clean(s.find_next("table").text) + "\n"
            d["skill_list"] = sk_text

            d["rag_text"] = f"""【魔术礼装】{name}
获取方式：{d['get_way']}
技能详情：
{d['skill_list']}"""
            mc_data.append(d)
            time.sleep(0.5)
        except Exception as e:
            print("MC错误", p, e)

    merged = existing + [x for x in mc_data if clean(x.get('name','')) not in existing_names]
    with open(os.path.join(DATA_DIR, "fgo_mc.json"), "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    save_rag(merged, os.path.join(DATA_DIR, "rag_mc.txt"))
    added = len(merged) - len(existing)
    print(f"✅ 魔术礼装完成：{len(merged)} 套（新增 {added} 套）")
    return merged

# ====================== 6. 爬取通用技能一览 ======================
def crawl_skill():
    print("\n=== 全从者技能汇总爬虫 ===")
    sk_links = set()
    res = session.get(BASE + "/w/技能一览", timeout=12)
    soup = BeautifulSoup(res.text, "lxml")
    for a in soup.select('table.wikitable a[href^="/w/"]'):
        h = a["href"]
        if "#" not in h:
            sk_links.add(h)
    print(f"待爬技能 {len(sk_links)}")
    # load existing
    exist_file = os.path.join(DATA_DIR, "fgo_skill.json")
    existing = _load_existing_json(exist_file)
    existing_names = _existing_name_set(existing, ('skill_name','name'))
    sk_data = []

    for p in sk_links:
        try:
            title_seg = p.split('/w/')[-1]
            candidate = requests.utils.unquote(title_seg).replace('_', ' ')
            if clean(candidate) in existing_names:
                print('skip existing skill', candidate)
                continue
            sp = BeautifulSoup(session.get(BASE + p, timeout=12).text, "lxml")
            name = clean(sp.find("h1").text)
            d = {"skill_name": name, "path": p, "type": "", "effect": "", "up_effect": "", "rag_text": ""}
            tb = sp.find("table", class_="closetable")
            if tb:
                for tr in tb.find_all("tr"):
                    td = [clean(x.text) for x in tr.find_all("td")]
                    if len(td) < 2:
                        continue
                    if "分类" in td[0]:
                        d["type"] = td[1]
                    if "效果" in td[0]:
                        d["effect"] = td[1]
                    if "升级" in td[0]:
                        d["up_effect"] = td[1]

            d["rag_text"] = f"""【技能】{name}｜分类:{d['type']}
基础效果：{d['effect']}
升级效果：{d['up_effect']}"""
            sk_data.append(d)
            time.sleep(0.35)
        except Exception as e:
            print("技能爬取异常", p, e)

    merged = existing + [x for x in sk_data if clean(x.get('skill_name','')) not in existing_names]
    with open(os.path.join(DATA_DIR, "fgo_skill.json"), "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    save_rag(merged, os.path.join(DATA_DIR, "rag_skill.txt"))
    added = len(merged) - len(existing)
    print(f"✅ 全技能完成：{len(merged)} 个（新增 {added} 个）")
    return merged

# ====================== 7. 爬取全主线关卡 ======================
def crawl_stages():
    print("\n=== 开始爬关卡配置 ===")
    stage_pages = [
        # 第一部 特异点
        "/w/特异点F_燃烧污染都市_冬木/关卡配置",
        "/w/第一特异点_邪龙百年战争_奥尔良/关卡配置",
        "/w/第二特异点_永续疯狂帝国_七丘之城/关卡配置",
        "/w/第三特异点_封锁终局四海_俄刻阿诺斯/关卡配置",
        "/w/第四特异点_死界魔雾都市_伦敦/关卡配置",
        "/w/第五特异点_北美神话大战_合众为一/关卡配置",
        "/w/第六特异点_神圣圆桌领域_卡美洛/关卡配置",
        "/w/第七特异点_绝对魔兽战线_巴比伦尼亚/关卡配置",
        "/w/终局特异点_冠位时间神殿_所罗门/关卡配置",
        # 1.5部 亚种特异点
        "/w/亚种特异点I_恶性隔绝魔境_新宿/关卡配置",
        "/w/亚种特异点II_传承地底世界_雅戈泰/关卡配置",
        "/w/亚种特异点III_尸山血河舞台_下总国/关卡配置",
        "/w/亚种特异点IV_禁忌降临庭园_塞勒姆/关卡配置",
        # 第二部 异闻带
        "/w/Lostbelt_No.1_永久冻土帝国_阿纳斯塔西娅/关卡配置",
        "/w/Lostbelt_No.2_无间冰焰世纪_诸神黄昏/关卡配置",
        "/w/Lostbelt_No.3_人智统合真国_SIN/关卡配置",
        "/w/Lostbelt_No.4_创世灭亡轮回_由伽·刹多罗/关卡配置",
        "/w/Lostbelt_No.5_神代巨神海洋_亚特兰蒂斯/关卡配置",
        "/w/Lostbelt_No.5_星间都市山脉_奥林波斯/关卡配置",
        "/w/地狱界曼荼罗_平安京/关卡配置",
        "/w/Lostbelt_No.6_妖精圆桌领域_阿瓦隆·勒·菲(前篇)/关卡配置",
        "/w/Lostbelt_No.6_妖精圆桌领域_阿瓦隆·勒·菲(后篇)/关卡配置",
        "/w/Lostbelt_No.7_黄金树海纪行_纳维·米克特兰(前篇)/关卡配置",
        "/w/Lostbelt_No.7_黄金树海纪行_纳维·米克特兰(后篇)/关卡配置",
        # 奏章
        "/w/奏章Ⅰ_虚数罗针内界_平面之月/关卡配置",
        "/w/奏章Ⅱ_不可逆废弃孔_伊底/关卡配置"
    ]
    # load existing
    exist_file = os.path.join(DATA_DIR, "fgo_stages.json")
    existing = _load_existing_json(exist_file)
    existing_keys = set()
    for it in existing:
        k = clean(it.get('chapter','')) + '|' + clean(it.get('stage',''))
        existing_keys.add(k)

    data = []
    for path in stage_pages:
        full_url = BASE + path
        try:
            resp = session.get(full_url, timeout=15)
            resp.raise_for_status()
            s = BeautifulSoup(resp.text, "lxml")
            title = clean(s.find("h1").text)
            print(f"正在爬取：{title}")

            for span in s.find_all("span", class_="mw-headline"):
                stage_name = clean(span.text)
                tbl = span.find_next("table", class_="wikitable")
                if not tbl:
                    continue
                rows = []
                for tr in tbl.find_all("tr"):
                    cells = [clean(td.text) for td in tr.find_all("td")]
                    if any(cells):
                        rows.append(" | ".join(cells))
                content = "\n".join(rows)
                d = {
                    "chapter": title,
                    "stage": stage_name,
                    "content": content
                }
                key = clean(d['chapter']) + '|' + clean(d['stage'])
                if key in existing_keys:
                    print('skip existing stage', d['chapter'], '->', d['stage'])
                else:
                    d["rag_text"] = f"""【关卡】{d['chapter']}→{d['stage']}
【敌方配置】
{content}
"""
                    data.append(d)
            time.sleep(1)
        except Exception as e:
            print(f"页面异常 {path}：{e}")
            continue

    merged = existing + [x for x in data if (clean(x.get('chapter','')) + '|' + clean(x.get('stage',''))) not in existing_keys]
    with open(os.path.join(DATA_DIR, "fgo_stages.json"), "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    save_rag(merged, os.path.join(DATA_DIR, "rag_stages.txt"))
    print(f"✅ 关卡完成：{len(merged)} 个")
    return merged

# ====================== 合并所有RAG文本 ======================
def merge_all_rag():
    print("\n=== 合并全部RAG知识库 ===")
    file_list = [
        os.path.join(DATA_DIR, "rag_servants.txt"),
        os.path.join(DATA_DIR, "rag_enemy.txt"),
        os.path.join(DATA_DIR, "rag_ce.txt"),
        os.path.join(DATA_DIR, "rag_cm.txt"),
        os.path.join(DATA_DIR, "rag_mc.txt"),
        os.path.join(DATA_DIR, "rag_skill.txt"),
        os.path.join(DATA_DIR, "rag_stages.txt")
    ]
    all_content = []
    for fname in file_list:
        try:
            with open(fname, "r", encoding="utf-8") as f:
                all_content.append(f.read())
        except FileNotFoundError:
            print(f"跳过缺失文件：{fname}")

    with open(os.path.join(DATA_DIR, "fgo_rag_final.txt"), "w", encoding="utf-8") as f:
        f.write("\n\n".join(all_content))
    print("总知识库合并完成：/rag_crawl_data/fgo_rag_final.txt")

# ====================== 主入口 ======================
if __name__ == "__main__":
    crawl_servants()
    crawl_enemy()
    crawl_ce()
    crawl_cm()
    crawl_mc()
    crawl_skill()
    crawl_stages()
    merge_all_rag()
    print("\n全量数据爬取&合并全部完成！")