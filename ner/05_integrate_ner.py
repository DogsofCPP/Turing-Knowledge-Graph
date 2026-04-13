"""
将 CRF 实体抽取结果映射并整合进知识图谱
- 读取 ner/output/crf_extracted_entities.xml
- CRF 类型 (PER/LOC/EVT/PUB/AWD) → Ontology 类型 (Person/Location/Event/Publication/Award)
- 过滤噪音片段（如过短词、标点片段、错误标签）
- 输出为 ner/output/ner_integrated_instances.xml
- turing-full-data.xml 通过 owl:imports 引入此文件
"""
import os
import re
import xml.etree.ElementTree as ET
from collections import defaultdict

BASE = os.path.dirname(__file__)
SRC = os.path.join(BASE, "output", "crf_extracted_entities.xml")
OUT = os.path.join(BASE, "output", "ner_integrated_instances.xml")

# ----------------------- 类型映射表 -----------------------
# CRF NER 标签 → Ontology 类
CRF_TYPE_MAP = {
    "PER": "Person",
    "LOC": "Location",     # Location 的子类（城市级）用 City
    "EVT": "HistoricalEvent",
    "PUB": "Publication",  # 论文用 Paper
    "AWD": "Award",        # 荣誉称号用 HonoraryTitle
}

# 模糊判断 Location 实例应该用 City 还是 Location
CITY_KEYWORDS = {
    "London", "Cambridge", "Princeton", "Manchester", "Bletchley",
    "Wilmslow", "England", "India", "Cheshire", "New Jersey",
    "Milton Keynes", "United States",
}
CITY_KEYWORDS_ZH = {
    "伦敦", "剑桥", "普林斯顿", "曼彻斯特", "布莱切利", "威尔姆斯洛",
    "英格兰", "印度", "柴郡", "美国", "英格兰",
}

# 噪音过滤词（过短、标点、语义不明）
STOP_WORDS = {
    # 过短/无意义片段
    "皇家", "国王", "学院", "大学", "政府", "机构", "协会", "公司",
    "BOS", "EOS", "O",
    # 标点符号类
    "-", "–", "—", "~", ".", ",", ";", ":", "!", "?", "'", "\"",
    # NER 标签本身被误抽
    "PER", "LOC", "EVT", "PUB", "AWD",
    # 过短词
    "a", "an", "the", "of", "in", "on", "at", "to", "for",
}
STOP_LABELS = {
    "Royal", "King", "College", "University", "Institute",
    "Association", "the", "of", "and",
}


def is_noise_entity(label: str, crf_type: str) -> bool:
    """判断抽取实体是否为噪音，需要过滤"""
    label = label.strip()
    if not label:
        return True
    # 长度过短
    if len(label) <= 1:
        return True
    # 纯标点
    if re.fullmatch(r"[\W_]+", label):
        return True
    # 在停用词表中
    if label in STOP_WORDS:
        return True
    # 在停用标签表中
    if label in STOP_LABELS:
        return True
    # 纯数字
    if re.fullmatch(r"\d+", label):
        return True
    # 包含 @ 或 URL 残留
    if "@" in label or label.startswith("http"):
        return True
    # 片段分割噪音（分词错误导致的单字重复）
    # 例如 "布 莱切 利园" → 过滤 "布", "莱切", "利园"
    if len(label) <= 3 and " " in label:
        return True
    # 全角空格残留
    if re.search(r"[\u3000　]", label):
        return True
    return False


def normalize_label(label: str) -> str:
    """规范化标签：去除分词空格、残余符号"""
    # 去除词之间的空格（分词残留）
    label = re.sub(r" {1,3}", "", label)
    # 去除残余下划线
    label = label.replace("___", "·").replace("__", "·").replace("_", "·")
    # 统一全角/半角空格
    label = re.sub(r"[\u3000　]+", " ", label).strip()
    # 去除首尾标点
    label = label.strip("·-—–~.,;:!?\"'()[]{}")
    return label


def choose_subclass(label: str, base_type: str) -> str:
    """
    根据实体名称选择更精确的子类
    - Location → City（城市类）
    - Publication → Paper（论文类）
    - Award → HonoraryTitle（荣誉称号类）
    """
    if base_type == "Location":
        return "City"
    if base_type == "Publication":
        return "Paper"
    if base_type == "Award":
        return "HonoraryTitle"
    return base_type


def make_uri_id(label: str) -> str:
    """生成合法的 RDF URI local name"""
    # 转义空格和特殊字符
    s = label.strip()
    s = re.sub(r"[\s·]+", "_", s)
    s = re.sub(r"[^A-Za-z0-9_\u4e00-\u9fff]", "", s)
    s = re.sub(r"_+", "_", s)
    # 去除首尾下划线
    s = s.strip("_")
    # 加上前缀避免纯数字开头
    if s and s[0].isdigit():
        s = "N" + s
    return s


def load_crf_entities(path: str) -> dict:
    """解析 CRF 抽取结果 XML"""
    tree = ET.parse(path)
    root = tree.getroot()
    ns = {
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "turing": "http://www.example.org/turing#",
    }
    entities = defaultdict(lambda: {"type": None, "labels": set(), "sources": []})

    for desc in root.findall("rdf:Description", ns):
        about = desc.get(f"{{{ns['rdf']}}}about", "")
        if not about:
            continue
        # 提取 local name
        local = about.split("#")[-1] if "#" in about else about
        if not local:
            continue

        # 类型（rdf:type）
        rdf_type_el = desc.find("rdf:type", ns)
        if rdf_type_el is None:
            continue
        crf_type_uri = rdf_type_el.get(f"{{{ns['rdf']}}}resource", "")
        crf_type = crf_type_uri.split("#")[-1] if "#" in crf_type_uri else crf_type_uri

        # 标签
        label_el = desc.find("rdfs:label", ns)
        label = label_el.text if label_el is not None and label_el.text else local

        # 来源
        desc_el = desc.find("turing:description", ns)
        source = ""
        if desc_el is not None and desc_el.text:
            m = re.search(r"来源:\s*(.+?)(?:\s*来源:|$)", desc_el.text)
            if m:
                source = m.group(1).strip()

        entities[local] = {
            "crf_type": crf_type,
            "label": label,
            "source": source,
        }

    return entities


def build_integrated_xml(entities: dict) -> str:
    """构建整合后的 RDF XML 片段"""
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<rdf:RDF')
    lines.append('    xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"')
    lines.append('    xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"')
    lines.append('    xmlns:owl="http://www.w3.org/2002/07/owl#"')
    lines.append('    xmlns:turing="http://www.example.org/turing#">')
    lines.append("")
    lines.append("    <!--")
    lines.append("        NER 实体抽取实例（第 3 层）")
    lines.append("        由 05_integrate_ner.py 自动生成")
    lines.append("        来源：ner/output/crf_extracted_entities.xml")
    lines.append("        映射：CRF类型 → Ontology类")
    lines.append("    -->")
    lines.append("")

    counter = defaultdict(int)  # 统计各类型实体数量
    processed = set()

    for local, info in sorted(entities.items()):
        crf_type = info["crf_type"]
        label_raw = info["label"]
        source = info["source"]

        # 跳过不在映射表中的类型
        if crf_type not in CRF_TYPE_MAP:
            continue

        # 规范化标签
        label = normalize_label(label_raw)
        if is_noise_entity(label, crf_type):
            continue

        # 跳过已处理的同标签实体（避免重复）
        if label in processed:
            continue
        processed.add(label)

        # 映射到 Ontology 类型
        base_type = CRF_TYPE_MAP[crf_type]
        exact_type = choose_subclass(label, base_type)

        # 生成 URI
        uri_id = make_uri_id(label)
        if not uri_id:
            continue

        counter[exact_type] += 1

        lines.append(f"    <!-- 来源: {source} -->")
        lines.append(f"    <turing:{exact_type} rdf:ID=\"NER_{uri_id}\">")
        lines.append(f"        <rdfs:label>{label}</rdfs:label>")
        lines.append(f"        <turing:description>CRF抽取实体（NER方法：条件随机场）</turing:description>")
        lines.append(f"    </turing:{exact_type}>")
        lines.append("")

    # 统计信息
    lines.append("    <!-- NER 实体统计 -->")
    for etype, count in sorted(counter.items()):
        lines.append(f"    <!-- {etype}: {count} 个实体 -->")

    lines.append("")
    lines.append("</rdf:RDF>")
    return "\n".join(lines)


def main():
    print("=" * 60)
    print("CRF 实体抽取 → Ontology 整合")
    print("=" * 60)

    print(f"\n[1] 读取 CRF 抽取结果: {SRC}")
    entities = load_crf_entities(SRC)
    print(f"    共解析 {len(entities)} 个实体描述")

    print(f"\n[2] 类型映射与噪音过滤...")
    before = len(entities)
    valid = {k: v for k, v in entities.items()
             if v["crf_type"] in CRF_TYPE_MAP}
    after = len(valid)
    print(f"    过滤前: {before}, 过滤后: {after}（非 CRF 类型）")

    # 统计各类型数量
    type_counts = defaultdict(int)
    for v in valid.values():
        t = CRF_TYPE_MAP.get(v["crf_type"], "?")
        type_counts[t] += 1
    print(f"    各类型分布: {dict(sorted(type_counts.items()))}")

    print(f"\n[3] 生成整合 XML: {OUT}")
    xml_content = build_integrated_xml(valid)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(xml_content)
    print(f"    已写入 {OUT}")
    print(f"    有效实体数: {len(valid)}")


if __name__ == "__main__":
    main()
