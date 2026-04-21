"""
事件时间线抽取

目标：从原始语料句子中识别事件描述，构建图灵生平事件时间线，
      按年份排序，输出为 RDF XML。

事件来源：
  1. 手工定义的里程碑事件（已存在于 turing-full-data.xml，不重复生成）
  2. 从语料句子中抽取的新事件（如"图灵在二战期间破译德军密码"）

事件类型：PersonalEvent / AcademicEvent / HistoricalEvent

输出：ner/output/events_timeline.xml
"""
import os
import re
from xml.etree import ElementTree as ET

BASE = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(BASE, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

RAW_EN = os.path.join(BASE, "corpus", "raw_turing_en.txt")
RAW_ZH = os.path.join(BASE, "corpus", "raw_turing_zh.txt")

# ============================================================
# 事件抽取规则
# ============================================================

# 里程碑事件（不重复，从 turing-full-data.xml 获取）
# 此处仅定义语料中可能提到的新事件

EVENT_RULES_EN = [
    # (年份, 英文关键词, 事件描述模板, 子类)
    (1936, "On Computable Numbers", "发表《论可计算数》", "AcademicEvent"),
    (1936, "Turing machine", "提出图灵机概念", "AcademicEvent"),
    (1950, "Computing Machinery and Intelligence", "发表《计算机器与智能》", "AcademicEvent"),
    (1950, "Turing Test", "提出图灵测试", "AcademicEvent"),
    (1952, "Chemical Basis of Morphogenesis", "发表《形态发生的化学基础》", "AcademicEvent"),
    (1945, "ACE design", "设计自动计算引擎", "AcademicEvent"),
    (1946, "OBE", "获得大英帝国勋章", "AcademicEvent"),
    (1951, "Royal Society", "当选英国皇家学会院士", "AcademicEvent"),
    (1912, "born", "图灵出生于伦敦", "PersonalEvent"),
    (1954, "died", "图灵逝世", "PersonalEvent"),
    (1952, "prosecuted", "因同性恋被审判", "PersonalEvent"),
    (1939, "Bletchley Park", "加入布莱切利园", "AcademicEvent"),
    (1940, "Bombe", "设计Bombe破译机", "AcademicEvent"),
    (1948, "Manchester", "在曼彻斯特大学工作", "AcademicEvent"),
    (2013, "royal pardon", "获得皇家赦免", "HistoricalEvent"),
    (2009, "apology", "英国政府道歉", "HistoricalEvent"),
    (2017, "Alan Turing Act", "艾伦·图灵法案", "HistoricalEvent"),
    (1966, "Turing Award", "图灵奖设立", "HistoricalEvent"),
]

EVENT_RULES_ZH = [
    (1912, "出生", "图灵出生于伦敦", "PersonalEvent"),
    (1936, "图灵机", "提出图灵机概念", "AcademicEvent"),
    (1936, "论可计算数", "发表《论可计算数》", "AcademicEvent"),
    (1950, "计算机器与智能", "发表《计算机器与智能》", "AcademicEvent"),
    (1950, "图灵测试", "提出图灵测试", "AcademicEvent"),
    (1952, "形态发生的化学基础", "发表《形态发生的化学基础》", "AcademicEvent"),
    (1945, "自动计算引擎", "设计自动计算引擎", "AcademicEvent"),
    (1946, "大英帝国勋章", "获得大英帝国勋章", "AcademicEvent"),
    (1951, "英国皇家学会", "当选英国皇家学会院士", "AcademicEvent"),
    (1954, "逝世", "图灵逝世于威尔姆斯洛", "PersonalEvent"),
    (1952, "审判", "因同性恋被审判", "PersonalEvent"),
    (1939, "布莱切利园", "加入布莱切利园破译密码", "AcademicEvent"),
    (1940, "Bombe", "设计Bombe破译机", "AcademicEvent"),
    (1948, "曼彻斯特大学", "在曼彻斯特大学工作", "AcademicEvent"),
    (2013, "皇家赦免", "获得皇家赦免", "HistoricalEvent"),
    (2009, "道歉", "英国政府正式道歉", "HistoricalEvent"),
    (2017, "艾伦·图灵法案", "艾伦·图灵法案通过", "HistoricalEvent"),
    (1966, "图灵奖", "图灵奖设立", "HistoricalEvent"),
]


# ============================================================
# 辅助函数
# ============================================================

def event_subclass(label):
    """根据事件名称推断细分类型"""
    personal_kw = ["出生", "逝世", "死亡", "审判", "prosecuted", "born", "died", "death", "trial"]
    academic_kw = ["论文", "入学", "博士", "获奖", "发表", "设计", "加入",
                   "paper", "PhD", "published", "elected", "received", "joined"]
    for kw in personal_kw:
        if kw in label:
            return "PersonalEvent"
    for kw in academic_kw:
        if kw in label:
            return "AcademicEvent"
    return "HistoricalEvent"


def uid_from_label(label, year):
    """从标签和年份生成稳定的 ID"""
    s = re.sub(r"[\s·]+", "_", label.strip())
    s = re.sub(r"[^A-Za-z0-9_\u4e00-\u9fff]", "", s).strip("_")
    s = re.sub(r"_+", "_", s)
    return f"NEREvent_{year}_{s}" if s else f"NEREvent_{year}"


def load_sentences(path):
    """加载原始语料句子"""
    sents = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "\t" in line:
                sents.append(line.split("\t", 1)[1])
    return sents


def extract_events_from_sent(sent_text, lang):
    """
    从句子中抽取事件
    返回: [(年份, 标签, 描述, 子类), ...]
    """
    results = []
    rules = EVENT_RULES_EN if lang == "en" else EVENT_RULES_ZH

    for year, keyword, desc_template, default_type in rules:
        if keyword in sent_text:
            exact_type = event_subclass(desc_template)
            results.append((year, desc_template, desc_template, exact_type))

    return results


def extract_all_events():
    """从所有语料中抽取事件"""
    all_events = []
    seen = set()

    for path, lang in [(RAW_EN, "en"), (RAW_ZH, "zh")]:
        if not os.path.exists(path):
            continue
        sents = load_sentences(path)
        for sent in sents:
            events = extract_events_from_sent(sent, lang)
            for year, label, desc, etype in events:
                key = (year, label)
                if key not in seen:
                    seen.add(key)
                    all_events.append({
                        "year": year,
                        "label": label,
                        "description": desc,
                        "type": etype,
                        "id": uid_from_label(label, year),
                    })

    # 按年份排序
    all_events.sort(key=lambda x: x["year"])
    return all_events


# ============================================================
# RDF 输出
# ============================================================

def build_xml(events):
    """将事件时间线构建为 RDF XML"""
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<!--')
    lines.append('    图灵知识图谱 · 事件时间线')
    lines.append('    由 07_event_extraction.py 自动生成')
    lines.append('    逻辑：从语料句子中识别事件，按年份排序')
    lines.append('    被 turing-full-data.xml 通过 owl:imports 引入')
    lines.append('-->')
    lines.append('<rdf:RDF')
    lines.append('    xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"')
    lines.append('    xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"')
    lines.append('    xmlns:owl="http://www.w3.org/2002/07/owl#"')
    lines.append('    xmlns:xsd="http://www.w3.org/2001/XMLSchema#"')
    lines.append('    xmlns:turing="http://www.example.org/turing#"')
    lines.append('    xml:base="http://www.example.org/turing">')
    lines.append('')
    lines.append('    <!-- ==================== 本体声明 ==================== -->')
    lines.append('    <owl:Ontology rdf:about="http://www.example.org/turing">')
    lines.append('        <rdfs:comment>事件时间线层 - 从语料自动抽取</rdfs:comment>')
    lines.append('    </owl:Ontology>')
    lines.append('')
    lines.append('    <!-- ==================== 事件时间线（按年份排序）==================== -->')
    lines.append('')

    for ev in events:
        lines.append(f'    <turing:{ev["type"]} rdf:ID="{ev["id"]}">')
        lines.append(f'        <rdfs:label>{ev["label"]}</rdfs:label>')
        lines.append(f'        <turing:eventDate rdf:datatype="http://www.w3.org/2001/XMLSchema#date">{ev["year"]}-01-01</turing:eventDate>')
        lines.append(f'        <turing:description>{ev["description"]}</turing:description>')
        lines.append(f'        <turing:source>event-extraction</turing:source>')
        lines.append(f'    </turing:{ev["type"]}>')
        lines.append('')

    lines.append(f'    <!-- 共 {len(events)} 个事件 -->')
    lines.append('')
    lines.append('</rdf:RDF>')
    return "\n".join(lines)


def main():
    print("=" * 60)
    print("事件时间线抽取")
    print("=" * 60)

    events = extract_all_events()
    print(f"\n共抽取 {len(events)} 个事件")

    # 按年份展示
    print("\n事件时间线（按年份）：")
    for ev in events:
        print(f"  {ev['year']}  [{ev['type']}]  {ev['label']}")

    # 统计
    type_counts = {}
    for ev in events:
        type_counts[ev["type"]] = type_counts.get(ev["type"], 0) + 1
    print(f"\n类型分布: {dict(sorted(type_counts.items()))}")

    # 输出
    out_path = os.path.join(OUTPUT_DIR, "events_timeline.xml")
    xml_content = build_xml(events)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(xml_content)
    print(f"\n已生成: {out_path}")


if __name__ == "__main__":
    main()
