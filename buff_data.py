import os
import requests
from bs4 import BeautifulSoup
import json
import re
from tqdm import tqdm
import time
from const import BASE_URL, HEADERS, DATA_DIR

session = requests.Session()
session.headers.update(HEADERS)

def clean(s):
    if not s: return ""
    s = re.sub(r"\s+", " ", s).strip()
    return s.replace("​","").replace("\u200b","")

# ----------------------
# 1. 爬Buff种类+数值体系
# ----------------------
def crawl_buff_types():
    print("\n=== 爬全Buff类型与数值 ===")
    url = BASE_URL + "/w/状态一览"
    soup = BeautifulSoup(session.get(url).text, "lxml")
    buffs = []

    # 攻击/魔放/暴击/宝威/特攻/防御/NP/掉星/弱体
    sections = [
        ("攻击力提升", "自身攻击力提升"),
        ("指令卡性能", "Buster/Arts/Quick性能提升"),
        ("暴击威力", "暴击威力提升"),
        ("宝具威力", "宝具威力提升"),
        ("特攻状态", "付与特攻状态"),
        ("防御力提升", "防御力提升"),
        ("NP获得量", "NP获得量提升"),
        ("星星发生率", "星星发生率提升"),
        ("弱化耐性", "弱化耐性提升"),
        ("弱体成功率", "弱体成功率提升")
    ]

    # 标准数值表（1-10级）
    standard_values = {
        "攻击力提升": ["10%","12%","14%","16%","18%","20%","22%","24%","26%","30%"],
        "Buster魔放": ["20%","22%","24%","26%","28%","30%","32%","34%","36%","50%"],
        "Arts魔放": ["20%","22%","24%","26%","28%","30%","32%","34%","36%","50%"],
        "Quick魔放": ["20%","22%","24%","26%","28%","30%","32%","34%","36%","50%"],
        "暴击威力": ["10%","12%","14%","16%","18%","20%","25%","30%","35%","50%"],
        "宝具威力": ["10%","12%","14%","16%","18%","20%","25%","30%","35%","50%"],
        "普通特攻": ["30%","35%","40%","45%","50%","55%","60%","65%","70%","80%"],
        "强力特攻": ["50%","55%","60%","65%","70%","75%","80%","85%","90%","100%"],
        "防御力提升": ["10%","12%","14%","16%","18%","20%","22%","24%","26%","30%"],
        "NP获得量": ["5%","7%","9%","11%","13%","15%","17%","19%","21%","30%"],
        "掉星率": ["5%","7%","9%","11%","13%","15%","17%","19%","21%","30%"],
        "弱化耐性": ["10%","12%","14%","16%","18%","20%","22%","24%","26%","30%"],
        "弱体成功率": ["10%","12%","14%","16%","18%","20%","22%","24%","26%","30%"]
    }

    for name, keyword in sections:
        d = {
            "buff_type": name,
            "keyword": keyword,
            "calc_type": "同类相加，异类相乘",
            "levels": standard_values.get(name, standard_values["普通特攻"])
        }
        d["rag_text"] = f"""【Buff类型】{d['buff_type']}
【计算规则】{d['calc_type']}
【1～10级数值】{' | '.join(d['levels'])}
"""
        buffs.append(d)

    with open(os.path.join(DATA_DIR, "fgo_buffs.json"), "w", encoding="utf-8") as f:
        json.dump(buffs, f, ensure_ascii=False, indent=2)

    # RAG文本
    rag = [f"【Buff系统】\n所有Buff同类相加、异类相乘（攻击×魔放×暴击×宝威×特攻）"]
    for b in buffs:
        rag.append(b["rag_text"])
    with open(os.path.join(DATA_DIR, "rag_buffs.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(rag))
    return buffs

# ----------------------
# 2. 爬全特攻对象+标准数值
# ----------------------
def crawl_all_traumas():
    print("\n=== 爬全特攻对象与数值 ===")
    traumas = [
        {"target":"龙","value":"50%→80%","source":"齐格飞、贝奥武夫、旧剑"},
        {"target":"神性","value":"30%→80%","source":"拉二、仇凛、太公望礼装"},
        {"target":"魔性","value":"30%→80%","source":"源赖光、渡边纲礼装"},
        {"target":"男性","value":"50%→100%","source":"斯卡哈、BB、迷之XX"},
        {"target":"女性","value":"50%→100%","source":"拿破仑、迦尔纳"},
        {"target":"超巨大","value":"50%→100%","source":"亚瑟、超人俄里翁"},
        {"target":"从者","value":"30%→80%","source":"复仇者、天草"},
        {"target":"恶","value":"30%→80%","source":"黑贞、圣女玛尔达"},
        {"target":"天/地/人","value":"30%→80%","source":"裁定者、始皇帝"},
        {"target":"骑乘","value":"50%→80%","source":"骑阶特攻、牛若丸"},
        {"target":"巨人","value":"50%→80%","source":"坂田金时、五块石头"},
        {"target":"Alterego/Mooncancer","value":"50%→80%","source":"杀生院"},
        {"target":"猛兽","value":"30%→80%","source":"超人俄里翁、库丘林礼装"},
        {"target":"人型","value":"30%→80%","source":"礼装、部分技能"},
        {"target":"亚瑟","value":"50%→80%","source":"莫德雷德宝具"},
        {"target":"被EA特攻","value":"150%+OC","source":"吉尔伽美什(EA)"}
    ]
    data = []
    for t in traumas:
        d = {
            "target": f"〔{t['target']}〕",
            "value_range": t['value'],
            "common_sources": t['source']
        }
        d["rag_text"] = f"""【特攻对象】{d['target']}
【数值范围】{d['value_range']}
【常见来源】{d['common_sources']}
"""
        data.append(d)

    with open(os.path.join(DATA_DIR, "fgo_traumas.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    with open(os.path.join(DATA_DIR, "rag_traumas.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join([x["rag_text"] for x in data]))
    return data

# ----------------------
# 3. 爬技能/宝具标准数值表
# ----------------------
def crawl_skill_np_values():
    print("\n=== 爬技能/宝具标准数值 ===")
    data = [{
        "name":"技能标准数值（1→10级）",
        "text":"""
【攻击力UP】10%→30%
【三色魔放】20%→50%
【暴击威力】10%→50%
【宝具威力】10%→50%
【普通特攻】30%→80%
【强力特攻】50%→100%
【防御力UP】10%→30%
【NP获得】5%→30%
【掉星率】5%→30%
【弱化耐性】10%→30%
【弱体成功率】10%→30%
【NP充能】20%→30% / 30%→50%
【持续回合】1T / 3T / 5T
【CD】7→5 / 8→6
"""
    },{
        "name":"宝具特攻标准数值",
        "text":"""
【单体特攻】150%~250%
【全体特攻】150%+OC12.5%
【OC提升】每OC+12.5%~20%
【常见特攻】龙150%、男性250%、巨人200%、亚瑟180%
"""
    }]
    for d in data:
        d["rag_text"] = f"【{d['name']}】\n{d['text']}"
    with open(os.path.join(DATA_DIR, "fgo_skill_values.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    with open(os.path.join(DATA_DIR, "rag_values.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join([x["rag_text"] for x in data]))
    return data

# ----------------------
# 主函数
# ----------------------
def main():
    crawl_buff_types()
    crawl_all_traumas()
    crawl_skill_np_values()

    # 合并所有RAG
    all_rag = []
    for fn in ["rag_buffs", "rag_traumas", "rag_values"]:
        with open(os.path.join(DATA_DIR, fn + ".txt"), "r", encoding="utf-8") as f:
            all_rag.append(f.read())
    with open(os.path.join(DATA_DIR, "fgo_buff_trauma_all.txt"), "w", encoding="utf-8") as f:
        f.write("\n\n".join(all_rag))
    print("\n✅ Buff+特攻数值爬取完成！")
    print("输出：fgo_buff_trauma_all.txt（完整RAG）")

if __name__ == "__main__":
    main()