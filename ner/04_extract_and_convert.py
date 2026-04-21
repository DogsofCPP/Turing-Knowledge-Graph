"""
CRF 实体抽取 → RDF XML
格式与 turing-full-data.xml 一致：
- <turing:Type rdf:ID="..."> 直接元素形式
- 人物关联事件/著作/奖项（participatedIn / wrote / received）
- 中英文重复实体合并，标签优先中文
- 事件细分为 PersonalEvent / AcademicEvent / HistoricalEvent
"""
import os, re

BASE = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(BASE, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CRF_TYPE_MAP = {"PER": "Person", "LOC": "City", "EVT": "HistoricalEvent", "PUB": "Paper", "AWD": "Award"}

COUNTRY_MAP = {
    "England": "英国", "India": "印度", "New Jersey": "美国", "United States": "美国",
    "Milton Keynes": "英国", "Cheshire": "英国",
    "伦敦": "英国", "英格兰": "英国", "剑桥": "英国", "普林斯顿": "美国",
    "曼彻斯特": "英国", "布莱切利园": "英国", "威尔姆斯洛": "英国",
    "印度": "印度", "柴郡": "英国", "米尔顿凯恩斯": "英国", "布莱切利": "英国",
}

AWARD_KEYWORDS = ["奖", "奖章", "勋章", "赦免", "纸币", "Award", "medal", "pardon", "banknote", "Act", "Royal", "皇家"]
REPORT_KEYWORDS = ["设计", "design", "Design", "ACE", "报告"]

# 中英文实体合并映射：key → (canonical_id, label)
# 英文 key → 英文 ID + 中文 label（中文优先作为显示标签）
# 中文 key 也直接映射到同一 canonical_id
MERGE_MAP = {
    # 位置
    "London": ("Location_London", "伦敦"),
    "伦敦": ("Location_London", "伦敦"),
    "Cambridge": ("Location_Cambridge", "剑桥"),
    "剑桥": ("Location_Cambridge", "剑桥"),
    "Princeton": ("Location_Princeton", "普林斯顿"),
    "普林斯顿": ("Location_Princeton", "普林斯顿"),
    "Manchester": ("Location_Manchester", "曼彻斯特"),
    "曼彻斯特": ("Location_Manchester", "曼彻斯特"),
    "Wilmslow": ("Location_Wilmslow", "威尔姆斯洛"),
    "威尔姆斯洛": ("Location_Wilmslow", "威尔姆斯洛"),
    "BletchleyPark": ("Location_Bletchley", "布莱切利"),
    "布莱切利园": ("Location_Bletchley", "布莱切利"),
    "England": ("Location_England", "英格兰"),
    "英格兰": ("Location_England", "英格兰"),
    "India": ("Location_India", "印度"),
    "科钦": ("Location_Kochi", "科钦"),
    "NewJersey": ("Location_NewJersey", "新泽西"),
    "New Jersey": ("Location_NewJersey", "新泽西"),
    "UnitedStates": ("Location_UnitedStates", "美国"),
    "United States": ("Location_UnitedStates", "美国"),
    "MiltonKeynes": ("Location_MiltonKeynes", "米尔顿凯恩斯"),
    "Milton Keynes": ("Location_MiltonKeynes", "米尔顿凯恩斯"),
    "Cheshire": ("Location_Cheshire", "柴郡"),
    # 学院/大学
    "King'sCollege": ("Location_KingsCollege", "剑桥大学国王学院"),
    "TrinityCollege": ("Location_TrinityCollege", "剑桥大学三一学院"),
    # 事件
    "WorldWarII": ("Event_WorldWarII", "二战"),
    "二战": ("Event_WorldWarII", "二战"),
    "WorldWarI": ("Event_WorldWarI", "一战"),
    "一战": ("Event_WorldWarI", "一战"),
    # 论文/著作
    "ACE": ("Publication_ACE", "自动计算引擎"),
    "自动计算引擎": ("Publication_ACE", "自动计算引擎"),
    "ComputingMachineryandIntelligence": ("Publication_ComputingMachineryandIntelligence", "计算机器与智能"),
    "计算机器与智能": ("Publication_ComputingMachineryandIntelligence", "计算机器与智能"),
    "Mind": ("Publication_ComputingMachineryandIntelligence", "计算机器与智能"),
    "TheChemicalBasisofMorphogenesis": ("Publication_ChemicalBasisofMorphogenesis", "形态发生的化学基础"),
    "形态发生的化学基础": ("Publication_ChemicalBasisofMorphogenesis", "形态发生的化学基础"),
    "TuringAward": ("Publication_TuringAward", "图灵奖"),
    "图灵奖": ("Publication_TuringAward", "图灵奖"),
    # 奖项/荣誉
    "OBE": ("Award_OBE", "大英帝国勋章"),
    "大英帝国勋章": ("Award_OBE", "大英帝国勋章"),
    "RoyalSociety": ("Award_RoyalSociety", "英国皇家学会"),
    "英国皇家学会": ("Award_RoyalSociety", "英国皇家学会"),
    "royalpardon": ("Award_RoyalPardon", "皇家赦免"),
    "皇家": ("Award_RoyalPardon", "皇家赦免"),
    "fifty-poundbanknote": ("Award_FiftyPoundBanknote", "五十英镑纸币"),
    "五十英镑纸币": ("Award_FiftyPoundBanknote", "五十英镑纸币"),
    "AlanTuringAct": ("Award_TuringAct", "艾伦·图灵法案"),
    "艾伦·图灵法案": ("Award_TuringAct", "艾伦·图灵法案"),
}

# 中文 key → ID 前缀
ID_PREFIX = {
    "Person": "AlanTuring",
    "Location": "Location_",
    "Event": "Event_",
    "Publication": "Publication_",
    "Award": "Award_",
    "AcademicAward": "Award_",
    "HonoraryTitle": "Award_",
    "TechnicalReport": "Publication_",
    "Paper": "Publication_",
}


def parse_bio(fp):
    sents = []
    for block in open(fp, encoding="utf-8").read().split("\n\n"):
        tokens, labs = [], []
        for line in block.strip().split("\n"):
            p = line.split("\t")
            tok = (p[0].strip() if p else "")
            lab = p[1].strip() if len(p) == 2 else "O"
            if tok:
                tokens.append(tok); labs.append(lab)
        if not tokens: continue
        entities = {}
        cur, ct = [], None
        for tok, lab in zip(tokens, labs):
            if lab.startswith("B-"):
                if ct: entities["".join(cur)] = ct
                cur, ct = [tok], lab[2:]
            elif lab.startswith("I-") and ct:
                cur.append(tok)
            else:
                if ct: entities["".join(cur)] = ct
                cur, ct = [], None
        if ct: entities["".join(cur)] = ct
        sents.append(("".join(tokens), entities))
    return sents


def uid(label):
    s = re.sub(r"[\s·]+", "_", label.strip())
    s = re.sub(r"[^A-Za-z0-9_\u4e00-\u9fff]", "", s).strip("_")
    return ("N" + s) if s and s[0].isdigit() else s


def subclass(label, base):
    if base == "City": return "City"
    if base == "Paper": return "TechnicalReport" if any(k in label for k in REPORT_KEYWORDS) else "Paper"
    if base == "Award": return "HonoraryTitle" if any(k in label for k in AWARD_KEYWORDS) else "AcademicAward"
    return base


def infer(label, etype, sent):
    attrs = {}
    if etype in ("Paper", "TechnicalReport"):
        m = re.search(r"(\d{4})\s*年", sent) or re.search(r"in\s+(\d{4})", sent)
        if m: attrs["publicationYear"] = m.group(1)
    elif etype in ("AcademicAward", "HonoraryTitle"):
        m = re.search(r"(\d{4})\s*年", sent) or re.search(r"in\s+(\d{4})", sent)
        if m: attrs["awardYear"] = m.group(1)
    elif etype in ("PersonalEvent", "AcademicEvent", "HistoricalEvent"):
        m = re.search(r"(\d{4})\s*年", sent) or re.search(r"in\s+(\d{4})", sent)
        if m: attrs["eventDate"] = m.group(1) + "-01-01"
    elif etype == "City":
        for n, c in COUNTRY_MAP.items():
            if n in label or label in n: attrs["country"] = c; break
    return attrs


def event_subclass(label):
    """根据事件名称推断细分类型"""
    personal_kw = ["出生", "逝世", "死亡", "审判", "审判", "Trial", "Death", "Birth", "Trial", "prosecuted"]
    academic_kw = ["论文", "入学", "博士", "获奖", "发表", "报告", "设计", "Paper", "PhD", "Award", "published", "elected", "received"]
    for kw in personal_kw:
        if kw in label: return "PersonalEvent"
    for kw in academic_kw:
        if kw in label: return "AcademicEvent"
    return "HistoricalEvent"


def merge_entities(entities):
    """
    合并中英文重复实体，优先保留中文 label。
    返回：{canonical_id: {"type": ..., "sentence": ..., "label": ..., "id": ...}}
    """
    merged = {}

    for key, info in entities.items():
        if key in MERGE_MAP:
            canonical_id, canonical_label = MERGE_MAP[key]
        else:
            canonical_id = key
            canonical_label = key

        if canonical_id not in merged:
            merged[canonical_id] = {"type": info["type"], "sentence": info.get("sentence", ""), "label": canonical_label}
        else:
            # 优先保留中文 label
            existing_zh = any("\u4e00" <= c <= "\u9fff" for c in merged[canonical_id].get("label", ""))
            new_zh = any("\u4e00" <= c <= "\u9fff" for c in canonical_label)
            if new_zh and not existing_zh:
                merged[canonical_id]["label"] = canonical_label
            if not merged[canonical_id]["sentence"] and info.get("sentence"):
                merged[canonical_id]["sentence"] = info.get("sentence", "")

    return merged


def build_person_rels_merged(all_sents):
    """合并中英文，收集所有图灵相关的关系"""
    rels = {}  # pred -> list of (uri_id, label)
    seen = set()
    for _, ents in all_sents:
        has_turing = any(
            ("图灵" in k or k == "Turing")
            for k in ents if ents.get(k) == "PER"
        )
        if not has_turing: continue
        pred_map = {"EVT": "participatedIn", "PUB": "wrote", "AWD": "received"}
        for en, ct in ents.items():
            if ct not in pred_map: continue
            if en in MERGE_MAP:
                uri_id, label = MERGE_MAP[en]
            else:
                uri_id = en
                label = en
            key = (pred_map[ct], uri_id)
            if key not in seen and uri_id:
                seen.add(key)
                rels.setdefault(pred_map[ct], []).append((uri_id, label))
    return rels


def build_xml(entities_merged, all_sents):
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<!--')
    lines.append('    图灵知识图谱 · CRF 实体抽取实例（第 3 层）')
    lines.append('    由 04_extract_and_convert.py 自动生成')
    lines.append('    来源：bio_turing_zh.txt + bio_turing_en.txt 标注语料')
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
    lines.append('        <rdfs:comment>CRF 实体抽取实例层 - bio_turing 标注语料</rdfs:comment>')
    lines.append('    </owl:Ontology>')
    lines.append('')
    lines.append('    <!-- ==================== CRF 抽取实体实例（去重后）==================== -->')
    lines.append('')

    all_rels = build_person_rels_merged(all_sents)

    type_counter = {}
    type_order = ["PER", "EVT", "LOC", "PUB", "AWD"]

    # 已输出的 canonical_id（防止重复）
    seen_ids = set()

    for crf_type in type_order:
        for key, info in sorted(entities_merged.items(), key=lambda x: x[0]):
            if info["type"] != crf_type: continue
            label = info.get("label", key)
            label = label.strip()
            if not label or len(label) <= 1: continue

            # 只保留艾伦·图灵一个人物
            if crf_type == "PER" and label != "艾伦·图灵": continue

            base = CRF_TYPE_MAP[crf_type]
            exact_type = subclass(label, base)
            if exact_type == "HistoricalEvent":
                exact_type = event_subclass(label)

            sent = info.get("sentence", "")

            # 确定 ID
            if crf_type == "PER":
                u = "AlanTuring"
                out_label = "艾伦·图灵"
            else:
                u = key
                out_label = label

            if not u or u in seen_ids: continue
            seen_ids.add(u)

            type_counter[exact_type] = type_counter.get(exact_type, 0) + 1
            attrs = infer(label, exact_type, sent)

            lines.append(f'    <turing:{exact_type} rdf:ID="{u}">')
            lines.append(f'        <rdfs:label>{out_label}</rdfs:label>')

            if "eventDate" in attrs:
                lines.append(f'        <turing:eventDate rdf:datatype="http://www.w3.org/2001/XMLSchema#date">{attrs["eventDate"]}</turing:eventDate>')
            if "publicationYear" in attrs:
                lines.append(f'        <turing:publicationYear rdf:datatype="http://www.w3.org/2001/XMLSchema#gYear">{attrs["publicationYear"]}</turing:publicationYear>')
            if "awardYear" in attrs:
                lines.append(f'        <turing:awardYear rdf:datatype="http://www.w3.org/2001/XMLSchema#gYear">{attrs["awardYear"]}</turing:awardYear>')
            if "country" in attrs:
                lines.append(f'        <turing:country>{attrs["country"]}</turing:country>')

            # Person 节点输出关系
            if crf_type == "PER":
                for pred, targets in all_rels.items():
                    for target_uri, target_label in targets:
                        lines.append(f'        <turing:{pred} rdf:resource="#{target_uri}"/>')

            lines.append(f'    </turing:{exact_type}>')
            lines.append('')

    lines.append('    <!-- 实体统计 -->')
    for etype, cnt in sorted(type_counter.items()):
        lines.append(f'    <!-- {etype}: {cnt} 个 -->')
    lines.append('')
    lines.append('</rdf:RDF>')
    return "\n".join(lines)


def build_ttl(entities_merged, all_sents):
    """生成 Turtle 格式（与 XML 输出相同的去重实体）"""
    lines = [
        '@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .',
        '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .',
        '@prefix owl: <http://www.w3.org/2002/07/owl#> .',
        '@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .',
        '@prefix turing: <http://www.example.org/turing#> .',
        '',
        '# 图灵知识图谱 · CRF 实体抽取实例（第 3 层）',
        '# 被 turing-full-data.xml 通过 owl:imports 引入',
        '',
        'turing: crf_extracted_entities a owl:Ontology ;',
        '    rdfs:comment "CRF 实体抽取实例层 - bio_turing 标注语料" .',
        '',
    ]

    all_rels = build_person_rels_merged(all_sents)
    seen_ids = set()
    type_counter = {}

    type_order = ["PER", "EVT", "LOC", "PUB", "AWD"]

    for crf_type in type_order:
        for key, info in sorted(entities_merged.items(), key=lambda x: x[0]):
            if info["type"] != crf_type: continue
            label = info.get("label", key)
            label = label.strip()
            if not label or len(label) <= 1: continue

            if crf_type == "PER" and label != "艾伦·图灵": continue

            base = CRF_TYPE_MAP[crf_type]
            exact_type = subclass(label, base)
            if exact_type == "HistoricalEvent":
                exact_type = event_subclass(label)

            sent = info.get("sentence", "")

            if crf_type == "PER":
                u = "AlanTuring"
                out_label = "艾伦·图灵"
            else:
                u = key
                out_label = label

            if not u or u in seen_ids: continue
            seen_ids.add(u)
            type_counter[exact_type] = type_counter.get(exact_type, 0) + 1
            attrs = infer(label, exact_type, sent)

            # 构建三元组
            lines.append(f'turing:{u} a turing:{exact_type} ;')
            lines.append(f'    rdfs:label "{out_label}"^^rdf:XMLLiteral ;')

            if "eventDate" in attrs:
                lines.append(f'    turing:eventDate "{attrs["eventDate"]}"^^xsd:date ;')
            if "publicationYear" in attrs:
                lines.append(f'    turing:publicationYear "{attrs["publicationYear"]}"^^xsd:gYear ;')
            if "awardYear" in attrs:
                lines.append(f'    turing:awardYear "{attrs["awardYear"]}"^^xsd:gYear ;')
            if "country" in attrs:
                lines.append(f'    turing:country "{attrs["country"]}" ;')

            # Person 关系
            if crf_type == "PER":
                for pred, targets in all_rels.items():
                    for target_uri, target_label in targets:
                        lines.append(f'    turing:{pred} turing:{target_uri} ;')
                # 去掉末尾分号，改为句号
                if all_rels:
                    lines[-1] = lines[-1].rstrip(' ;') + ' .'
            else:
                lines.append('    .')

            lines.append('')

    # 统计注释
    lines.append('# 实体统计')
    for etype, cnt in sorted(type_counter.items()):
        lines.append(f'# {etype}: {cnt} 个')
    lines.append('')
    return "\n".join(lines)


def main():
    print("=" * 60)
    print("CRF 标注语料 → RDF XML（与 turing-full-data.xml 格式一致）")
    print("=" * 60)

    BIO_ZH = os.path.join(BASE, "corpus", "bio_turing_zh.txt")
    BIO_EN = os.path.join(BASE, "corpus", "bio_turing_en.txt")

    raw_entities = {}
    all_sents = []

    if os.path.exists(BIO_ZH):
        sents = parse_bio(BIO_ZH)
        for st, ents in sents:
            all_sents.append((st, ents))
            for t, ct in ents.items():
                if t not in raw_entities:
                    raw_entities[t] = {"type": ct, "sentence": ""}
                if not raw_entities[t]["sentence"]:
                    raw_entities[t]["sentence"] = st
        print(f"\n[bio_turing_zh.txt] 解析完成，句子数: {len(sents)}")

    if os.path.exists(BIO_EN):
        sents = parse_bio(BIO_EN)
        for st, ents in sents:
            all_sents.append((st, ents))
            for t, ct in ents.items():
                if t not in raw_entities:
                    raw_entities[t] = {"type": ct, "sentence": ""}
                if not raw_entities[t]["sentence"]:
                    raw_entities[t]["sentence"] = st
        print(f"[bio_turing_en.txt] 解析完成，句子数: {len(sents)}")

    # 中英文实体合并
    entities_merged = merge_entities(raw_entities)
    print(f"\n合并后实体数: {len(entities_merged)}")

    # 统计
    counts = {}
    for info in entities_merged.values():
        t = info["type"]
        label = info.get("label", "")
        if t == "PER" and label != "艾伦·图灵": continue
        exact = subclass(label, CRF_TYPE_MAP.get(t, t))
        if exact == "HistoricalEvent" and t == "EVT":
            exact = event_subclass(label)
        counts[exact] = counts.get(exact, 0) + 1
    print(f"各类型: {dict(sorted(counts.items()))}")

    # 打印实体列表
    print("\n实体列表：")
    for key, info in sorted(entities_merged.items(), key=lambda x: x[0]):
        label = info.get("label", "")
        t = info["type"]
        if t == "PER" and label != "艾伦·图灵": continue
        print(f"  [{t:>4}] {label}")

    # 生成 XML
    out_xml = os.path.join(OUTPUT_DIR, "crf_extracted_entities.xml")
    xml_content = build_xml(entities_merged, all_sents)
    with open(out_xml, "w", encoding="utf-8") as f:
        f.write(xml_content)
    print(f"\n已生成: {out_xml}")

    # 生成 Turtle 格式
    out_ttl = os.path.join(OUTPUT_DIR, "crf_extracted_entities.ttl")
    ttl_content = build_ttl(entities_merged, all_sents)
    with open(out_ttl, "w", encoding="utf-8") as f:
        f.write(ttl_content)
    print(f"已生成: {out_ttl}")

    print(f"\n输出格式与 turing-full-data.xml 一致")
    print("  - 人物关联事件（participatedIn）、著作（wrote）、奖项（received）")
    print("  - 中英文重复实体已合并")


if __name__ == "__main__":
    main()
