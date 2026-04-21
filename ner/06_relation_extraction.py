"""
关系抽取（Relation Extraction）

目标：从 BIO 语料句子中，利用正则模式抽取实体间的语义关系，
      转换为 RDF 三元组，纳入知识图谱。

关系类型：
  - supervisedBy : 导师关系（指导 / supervised / advisor）
  - colleagueOf   : 同事关系（和 / with / and）
  - workedAt      : 工作地点（工作 / worked / at）
  - graduatedFrom : 毕业院校（学习 / studied / at）
  - received      : 获奖（获得 / received / awarded）
  - wrote         : 著作（发表 / wrote / published）

输出：ner/output/relations_extracted.xml（RDF/XML 格式）
"""
import os
import re
from xml.etree import ElementTree as ET

BASE = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(BASE, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# BIO 语料
BIO_EN = os.path.join(BASE, "corpus", "bio_turing_en.txt")
BIO_ZH = os.path.join(BASE, "corpus", "bio_turing_zh.txt")

# 中英文实体 ID 合并映射（与 04_extract_and_convert.py 保持一致）
MERGE_MAP = {
    # 英文 key → (canonical_id, label)
    "London": ("Location_London", "伦敦"),
    "Cambridge": ("Location_Cambridge", "剑桥"),
    "Princeton": ("Location_Princeton", "普林斯顿"),
    "Manchester": ("Location_Manchester", "曼彻斯特"),
    "Wilmslow": ("Location_Wilmslow", "威尔姆斯洛"),
    "BletchleyPark": ("Location_Bletchley", "布莱切利"),
    "Bletchley": ("Location_Bletchley", "布莱切利"),
    "England": ("Location_England", "英格兰"),
    "India": ("Location_India", "印度"),
    "NewJersey": ("Location_NewJersey", "新泽西"),
    "New Jersey": ("Location_NewJersey", "新泽西"),
    "UnitedStates": ("Location_UnitedStates", "美国"),
    "United States": ("Location_UnitedStates", "美国"),
    "MiltonKeynes": ("Location_MiltonKeynes", "米尔顿凯恩斯"),
    "Milton Keynes": ("Location_MiltonKeynes", "米尔顿凯恩斯"),
    "Cheshire": ("Location_Cheshire", "柴郡"),
    "King'sCollege": ("Location_KingsCollege", "剑桥大学国王学院"),
    "TrinityCollege": ("Location_TrinityCollege", "剑桥大学三一学院"),
    "WorldWarII": ("Event_WorldWarII", "二战"),
    "World War II": ("Event_WorldWarII", "二战"),
    "WorldWarI": ("Event_WorldWarI", "一战"),
    "World War I": ("Event_WorldWarI", "一战"),
    "ACE": ("Publication_ACE", "自动计算引擎"),
    "ComputingMachineryandIntelligence": ("Publication_ComputingMachineryandIntelligence", "计算机器与智能"),
    "Mind": ("Publication_ComputingMachineryandIntelligence", "计算机器与智能"),
    "TheChemicalBasisofMorphogenesis": ("Publication_ChemicalBasisofMorphogenesis", "形态发生的化学基础"),
    "TuringAward": ("Publication_TuringAward", "图灵奖"),
    "OBE": ("Award_OBE", "大英帝国勋章"),
    "RoyalSociety": ("Award_RoyalSociety", "英国皇家学会"),
    "royalpardon": ("Award_RoyalPardon", "皇家赦免"),
    "fifty-poundbanknote": ("Award_FiftyPoundBanknote", "五十英镑纸币"),
    "AlanTuringAct": ("Award_TuringAct", "艾伦·图灵法案"),
    # 中文
    "伦敦": ("Location_London", "伦敦"),
    "剑桥": ("Location_Cambridge", "剑桥"),
    "普林斯顿": ("Location_Princeton", "普林斯顿"),
    "曼彻斯特": ("Location_Manchester", "曼彻斯特"),
    "威尔姆斯洛": ("Location_Wilmslow", "威尔姆斯洛"),
    "布莱切利园": ("Location_Bletchley", "布莱切利"),
    "布莱切利": ("Location_Bletchley", "布莱切利"),
    "英格兰": ("Location_England", "英格兰"),
    "印度": ("Location_India", "印度"),
    "二战": ("Event_WorldWarII", "二战"),
    "一战": ("Event_WorldWarI", "一战"),
    "自动计算引擎": ("Publication_ACE", "自动计算引擎"),
    "计算机器与智能": ("Publication_ComputingMachineryandIntelligence", "计算机器与智能"),
    "心智": ("Publication_ComputingMachineryandIntelligence", "计算机器与智能"),
    "形态发生的化学基础": ("Publication_ChemicalBasisofMorphogenesis", "形态发生的化学基础"),
    "图灵奖": ("Publication_TuringAward", "图灵奖"),
    "大英帝国勋章": ("Award_OBE", "大英帝国勋章"),
    "皇家赦免": ("Award_RoyalPardon", "皇家赦免"),
    "五十英镑纸币": ("Award_FiftyPoundBanknote", "五十英镑纸币"),
    "艾伦·图灵法案": ("Award_TuringAct", "艾伦·图灵法案"),
}


# ============================================================
# 关系模式定义
# ============================================================

class RelationPattern:
    """关系抽取模式"""
    def __init__(self, pred, keywords_en, keywords_zh, subj_type, obj_type, bidirect=False):
        self.pred = pred
        self.keywords_en = keywords_en  # 英文关键词
        self.keywords_zh = keywords_zh  # 中文关键词
        self.subj_type = subj_type     # 主语类型（PER 等）
        self.obj_type = obj_type       # 宾语类型
        self.bidirect = bidirect       # 是否双向（如同事关系）

    def match_en(self, sent_lower):
        return any(k in sent_lower for k in self.keywords_en)

    def match_zh(self, sent):
        return any(k in sent for k in self.keywords_zh)


PATTERNS = [
    # supervisedBy：指导关系
    RelationPattern(
        "supervisedBy",
        ["supervised", "advisor", "guided"],
        ["指导", "导师"],
        "PER", "PER",
    ),
    # colleagueOf：同事关系
    RelationPattern(
        "colleagueOf",
        [" and ", " with ", ", ", "collaborated", "worked together"],
        ["和", "与", "及", "共同"],
        "PER", "PER",
        bidirect=True,
    ),
    # workedAt：工作地点
    RelationPattern(
        "workedAt",
        ["worked at", "worked in", "worked for", "employment", "position at"],
        ["工作", "任职", "任职于"],
        "PER", "LOC",
    ),
    # graduatedFrom：毕业院校
    RelationPattern(
        "graduatedFrom",
        ["studied at", "studied mathematics at", "enrolled at", "earned his phd at",
         "earned his", "matriculated at"],
        ["学习", "就读", "毕业于", "入学"],
        "PER", "LOC",
    ),
    # happenedAt：事件发生地点
    RelationPattern(
        "happenedAt",
        ["at ", "in ", "located in"],
        ["在", "位于"],
        "EVT", "LOC",
    ),
]


# ============================================================
# BIO 语料解析
# ============================================================

def parse_bio(fp):
    """解析 BIO 文件，返回句子列表及实体字典"""
    sents = []
    with open(fp, encoding="utf-8") as f:
        block_tokens, block_labs = [], []
        for line in f:
            line = line.rstrip("\n")
            if not line:
                if block_tokens:
                    entities = {}
                    cur, ct = [], None
                    for tok, lab in zip(block_tokens, block_labs):
                        if lab.startswith("B-"):
                            if ct:
                                entities["".join(cur)] = ct
                            cur, ct = [tok], lab[2:]
                        elif lab.startswith("I-") and ct:
                            cur.append(tok)
                        else:
                            if ct:
                                entities["".join(cur)] = ct
                            cur, ct = [], None
                    if ct:
                        entities["".join(cur)] = ct
                    full_sent = "".join(block_tokens)
                    sents.append((full_sent, entities))
                    block_tokens, block_labs = [], []
            else:
                parts = line.split("\t")
                tok = parts[0].strip() if parts else ""
                lab = parts[1].strip() if len(parts) == 2 else "O"
                if tok:
                    block_tokens.append(tok)
                    block_labs.append(lab)
    return sents


# ============================================================
# 关系抽取核心
# ============================================================

def canonicalize(key):
    """将原始实体 key 映射为 canonical_id"""
    if key in MERGE_MAP:
        return MERGE_MAP[key][0]
    # 默认：转下划线
    s = re.sub(r"[\s·]+", "_", key.strip())
    s = re.sub(r"[^A-Za-z0-9_\u4e00-\u9fff]", "", s).strip("_")
    return s or key


def extract_relations_from_sent(sent_text, entities):
    """
    从单句中抽取关系三元组
    返回: [(subj_id, pred, obj_id), ...]
    """
    triples = []
    if not entities:
        return triples

    ent_list = list(entities.items())  # [(text, type), ...]

    for pat in PATTERNS:
        subj_candidates = []
        obj_candidates = []

        for ent_text, ent_type in ent_list:
            if ent_type == pat.subj_type:
                subj_candidates.append(ent_text)
            if ent_type == pat.obj_type:
                obj_candidates.append(ent_text)

        if not subj_candidates or not obj_candidates:
            continue

        # 检查关键词是否在句子中
        matched = False
        if pat.match_en(sent_text.lower()):
            matched = True
        if not matched and pat.match_zh(sent_text):
            matched = True
        if not matched:
            continue

        # 对每对主语-宾语候选生成三元组
        for subj in subj_candidates:
            for obj in obj_candidates:
                subj_id = canonicalize(subj)
                obj_id = canonicalize(obj)
                if subj_id == obj_id:
                    continue  # 避免自环
                triples.append((subj_id, pat.pred, obj_id))
                if pat.bidirect:
                    triples.append((obj_id, pat.pred, subj_id))

    return triples


def extract_all_relations(bio_path, lang):
    """从 BIO 语料抽取所有关系"""
    sents = parse_bio(bio_path)
    all_triples = []
    seen = set()

    for sent_text, entities in sents:
        triples = extract_relations_from_sent(sent_text, entities)
        for t in triples:
            if t not in seen:
                seen.add(t)
                all_triples.append(t)

    return all_triples


# ============================================================
# RDF 输出
# ============================================================

def build_xml(triples):
    """将三元组构建为 RDF XML"""
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<!--')
    lines.append('    图灵知识图谱 · 关系抽取结果')
    lines.append('    由 06_relation_extraction.py 自动生成')
    lines.append('    逻辑：正则关键词模式匹配，从 BIO 语料句子中抽取三元组')
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
    lines.append('        <rdfs:comment>关系抽取层 - 正则模式匹配 BIO 语料</rdfs:comment>')
    lines.append('    </owl:Ontology>')
    lines.append('')
    lines.append('    <!-- ==================== RDF Reification：关系三元组 ==================== -->')
    lines.append('')

    # 按关系类型分组
    rel_groups = {}
    for subj, pred, obj in triples:
        rel_groups.setdefault(pred, []).append((subj, obj))

    for pred, pairs in rel_groups.items():
        for subj, obj in pairs:
            lines.append(f'    <!-- {pred}: {subj} → {obj} -->')
            lines.append(f'    <rdf:Description rdf:about="#{subj}">')
            lines.append(f'        <turing:{pred} rdf:resource="#{obj}"/>')
            lines.append(f'        <turing:source>relation-extraction</turing:source>')
            lines.append(f'    </rdf:Description>')
            lines.append('')

    lines.append(f'    <!-- 共 {len(triples)} 条关系断言 -->')
    lines.append('')
    lines.append('</rdf:RDF>')
    return "\n".join(lines)


def main():
    print("=" * 60)
    print("关系抽取（正则模式匹配）")
    print("=" * 60)

    all_triples = []

    if os.path.exists(BIO_EN):
        triples_en = extract_all_relations(BIO_EN, "en")
        all_triples.extend(triples_en)
        print(f"\n英文语料抽取: {len(triples_en)} 条三元组")

    if os.path.exists(BIO_ZH):
        triples_zh = extract_all_relations(BIO_ZH, "zh")
        all_triples.extend(triples_zh)
        print(f"中文语料抽取: {len(triples_zh)} 条三元组（去重前）")

    # 去重（按(pred, subj, obj)）
    seen = set()
    unique = []
    for t in all_triples:
        key = (t[1], t[0], t[2])
        if key not in seen:
            seen.add(key)
            unique.append(t)
    all_triples = unique

    print(f"去重后: {len(all_triples)} 条三元组")

    # 按关系类型统计
    rel_counts = {}
    for subj, pred, obj in all_triples:
        rel_counts[pred] = rel_counts.get(pred, 0) + 1
    print(f"\n关系类型分布: {dict(sorted(rel_counts.items()))}")

    # 打印所有三元组
    print("\n三元组列表：")
    for subj, pred, obj in all_triples:
        print(f"  ({subj}, {pred}, {obj})")

    # 输出
    out_path = os.path.join(OUTPUT_DIR, "relations_extracted.xml")
    xml_content = build_xml(all_triples)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(xml_content)
    print(f"\n已生成: {out_path}")


if __name__ == "__main__":
    main()
