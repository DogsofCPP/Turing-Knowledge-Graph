"""
实体消歧与去重

目标：将 NER 抽取的实体与手工编写的结构化数据进行对齐，
      解决"图灵奖"等实体在两边数据中重复出现的问题。

逻辑：
  1. 加载 turing-full-data.xml 中的手工数据 rdf:ID 列表（manual_set）
  2. 加载 crf_extracted_entities.xml 中的 NER 结果 rdf:ID 列表（ner_set）
  3. 对每个 NER 实体：
     - 若其 ID 在 manual_set 中已存在 → 跳过（以手工数据为准）
     - 若不在 → 保留并标记为 NER 来源
  4. 输出 entities_deduplicated.xml

被 turing-full-data.xml 通过 owl:imports 引入。
"""
import os
import re
from xml.etree import ElementTree as ET

BASE = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(BASE, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

MANUAL_XML = os.path.join(BASE, "..", "turing-full-data.xml")
NER_XML = os.path.join(OUTPUT_DIR, "crf_extracted_entities.xml")

NS = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "turing": "http://www.example.org/turing#",
}


def extract_manual_ids(xml_path):
    """从手工数据中提取所有 rdf:ID（不含 #AlanTuring# 本身）"""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # 找 owl:Ontology（其中不含 rdf:ID 的实例节点）
    manual_ids = set()

    for elem in root.iter():
        rdf_id = elem.get(f'{{{NS["rdf"]}}}ID')
        if rdf_id and rdf_id != "AlanTuring":
            manual_ids.add(rdf_id)

    return manual_ids


def load_ner_entities(xml_path):
    """加载 NER 结果中的实体，返回 [(element, rdf_id, tag_name, label), ...]"""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    entities = []

    for elem in root:
        rdf_id = elem.get(f'{{{NS["rdf"]}}}ID')
        if not rdf_id:
            continue
        tag = elem.tag.replace(f'{{{NS["turing"]}}}', "")
        label_el = elem.find(f'{{{NS["rdfs"]}}}label')
        label = label_el.text if label_el is not None else rdf_id
        entities.append({
            "id": rdf_id,
            "type": tag,
            "label": label,
            "element": elem,
        })
    return entities


def disambiguate(ner_entities, manual_ids):
    """
    对 NER 实体做消歧：
    - 在 manual_ids 中的 → 跳过（以手工数据为准）
    - 不在其中的 → 保留，附加 source 标注
    返回保留的实体列表
    """
    kept = []
    skipped = []

    for ent in ner_entities:
        if ent["id"] in manual_ids:
            skipped.append(ent)
        else:
            kept.append(ent)

    return kept, skipped


def build_xml(kept_entities):
    """将消歧后的实体构建为 RDF XML"""
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<!--')
    lines.append('    图灵知识图谱 · 实体消歧结果')
    lines.append('    由 05_entity_disambiguation.py 自动生成')
    lines.append('    逻辑：手工数据优先，NER 数据中去重冲突后保留')
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
    lines.append('        <rdfs:comment>实体消歧层 - 手工数据优先，NER 去重</rdfs:comment>')
    lines.append('    </owl:Ontology>')
    lines.append('')
    lines.append('    <!-- ==================== 消歧后保留的 NER 实体（不在手工数据中） ==================== -->')
    lines.append('')

    type_counter = {}
    for ent in kept_entities:
        t = ent["type"]
        type_counter[t] = type_counter.get(t, 0) + 1

        lines.append(f'    <turing:{t} rdf:ID="{ent["id"]}">')
        lines.append(f'        <rdfs:label>{ent["label"]}</rdfs:label>')
        lines.append(f'        <turing:source>NER</turing:source>')

        # 附加年份等属性（从原始 element 中提取）
        elem = ent["element"]
        for child in elem:
            tag = child.tag
            if tag == f'{{{NS["rdfs"]}}}label':
                continue
            if tag == f'{{{NS["turing"]}}}source':
                continue
            attr_name = tag.replace(f'{{{NS["turing"]}}}', '')
            attr_val = child.text or ""
            dt = child.get(f'{{{NS["rdf"]}}}datatype', '')
            if dt:
                dt_short = dt.split("#")[-1]
                lines.append(f'        <turing:{attr_name} rdf:datatype="{dt}">{attr_val}</turing:{attr_name}>')
            else:
                res = child.get(f'{{{NS["rdf"]}}}resource', '')
                if res:
                    res_short = res.replace("#", "")
                    lines.append(f'        <turing:{attr_name} rdf:resource="#{res_short}"/>')
                else:
                    lines.append(f'        <turing:{attr_name}>{attr_val}</turing:{attr_name}>')

        lines.append(f'    </turing:{t}>')
        lines.append('')

    lines.append('    <!-- 实体统计 -->')
    for etype, cnt in sorted(type_counter.items()):
        lines.append(f'    <!-- {etype}: {cnt} 个 -->')
    lines.append('')
    lines.append('</rdf:RDF>')
    return "\n".join(lines)


def main():
    print("=" * 60)
    print("实体消歧与去重")
    print("=" * 60)

    # 加载手工数据 ID
    manual_ids = extract_manual_ids(MANUAL_XML)
    print(f"\n手工数据实体数: {len(manual_ids)}")
    print(f"  示例: {sorted(list(manual_ids))[:10]}")

    # 加载 NER 实体
    ner_entities = load_ner_entities(NER_XML)
    print(f"\nNER 实体总数: {len(ner_entities)}")

    # 消歧
    kept, skipped = disambiguate(ner_entities, manual_ids)
    print(f"\n消歧结果:")
    print(f"  保留（不在手工数据中）: {len(kept)}")
    print(f"  跳过（以手工数据为准）: {len(skipped)}")

    if skipped:
        print(f"\n  跳过的冲突实体: {[e['id'] for e in skipped]}")

    # 统计
    counts = {}
    for e in kept:
        t = e["type"]
        counts[t] = counts.get(t, 0) + 1
    print(f"\n  保留实体类型: {dict(sorted(counts.items()))}")

    # 输出
    out_path = os.path.join(OUTPUT_DIR, "entities_deduplicated.xml")
    xml_content = build_xml(kept)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(xml_content)
    print(f"\n已生成: {out_path}")


if __name__ == "__main__":
    main()
