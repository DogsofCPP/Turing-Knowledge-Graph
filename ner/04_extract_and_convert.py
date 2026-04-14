"""
bio_turing_*.txt 标注语料 → RDF XML
格式与 turing-full-data.xml 一致
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
    elif etype == "City":
        for n, c in COUNTRY_MAP.items():
            if n in label or label in n: attrs["country"] = c; break
    return attrs


def person_rels(label, all_sents):
    rels, seen = [], set()
    for _, ents in all_sents:
        # 匹配句中含"图灵"的人（中文全名/简称）或英文"Turing"
        match = label in ents
        if not match:
            if "图灵" in label:
                match = any("图灵" in k for k in ents if ents.get(k) == "PER")
            elif label == "AlanTuring":
                match = "Turing" in ents
        if not match: continue
        pred_map = {"EVT": "participatedIn", "PUB": "wrote", "AWD": "received"}
        for en, ct in ents.items():
            if ct not in pred_map: continue
            key = (pred_map[ct], uid(en))
            if key not in seen and key[1]:
                seen.add(key); rels.append(key)
    return rels


def build_person_rels_merged(all_sents):
    """合并中文+英文，收集所有图灵相关的关系"""
    rels, seen = [], set()
    for _, ents in all_sents:
        has_turing = any(
            ("图灵" in k or k == "Turing")
            for k in ents if ents.get(k) == "PER"
        )
        if not has_turing: continue
        pred_map = {"EVT": "participatedIn", "PUB": "wrote", "AWD": "received"}
        for en, ct in ents.items():
            if ct not in pred_map: continue
            key = (pred_map[ct], uid(en))
            if key not in seen and key[1]:
                seen.add(key); rels.append(key)
    return rels


def build_xml(entities, all_sents):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<rdf:RDF',
             '    xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"',
             '    xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"',
             '    xmlns:owl="http://www.w3.org/2002/07/owl#"',
             '    xmlns:xsd="http://www.w3.org/2001/XMLSchema#"',
             '    xmlns:turing="http://www.example.org/turing#"',
             '    xml:base="http://www.example.org/turing">',
             '',
             '    <owl:Ontology rdf:about="http://www.example.org/turing"/>',
             '']

    type_order = list(CRF_TYPE_MAP.keys())
    sorted_ents = sorted(entities.items(),
                        key=lambda x: type_order.index(x[1]["type"]) if x[1]["type"] in type_order else 99)

    for label, info in sorted_ents:
        crf_type = info["type"]
        if crf_type not in CRF_TYPE_MAP: continue
        label = label.strip()
        if not label or len(label) <= 1: continue
        # 只保留艾伦·图灵 一个人物（AlanTuring 不单独输出）
        if crf_type == "PER" and label not in ("艾伦·图灵",): continue

        base = CRF_TYPE_MAP[crf_type]
        etype = subclass(label, base)
        u = uid(label)
        if not u: continue

        sent = info.get("sentence", "")
        attrs = infer(label, etype, sent)
        # 人物节点只输出"艾伦·图灵"一个，中英文关系合并
        rels = build_person_rels_merged(all_sents) if etype == "Person" else []

        lines.append(f'    <turing:{etype} rdf:ID="NER_{u}">')
        lines.append(f'        <rdfs:label>{label}</rdfs:label>')
        if "publicationYear" in attrs:
            lines.append(f'        <turing:publicationYear rdf:datatype="http://www.w3.org/2001/XMLSchema#gYear">{attrs["publicationYear"]}</turing:publicationYear>')
        if "awardYear" in attrs:
            lines.append(f'        <turing:awardYear rdf:datatype="http://www.w3.org/2001/XMLSchema#gYear">{attrs["awardYear"]}</turing:awardYear>')
        if "country" in attrs:
            lines.append(f'        <turing:country>{attrs["country"]}</turing:country>')
        for p, t in rels:
            lines.append(f'        <turing:{p} rdf:resource="#NER_{t}"/>')
        lines.append(f'    </turing:{etype}>')
        lines.append('')

    lines.append('</rdf:RDF>')
    return "\n".join(lines)


def main():
    print("CRF 标注语料 → RDF XML（与 turing-full-data.xml 格式一致）")

    entities, all_sents, file_sents = {}, [], {}
    for fname in ["bio_turing_zh.txt", "bio_turing_en.txt"]:
        fp = os.path.join(BASE, "corpus", fname)
        if not os.path.exists(fp): continue
        sents = parse_bio(fp)
        file_sents[fname] = len(sents)
        for st, ents in sents:
            all_sents.append((st, ents))
            for t, ct in ents.items():
                if t not in entities:
                    entities[t] = {"type": ct, "sentence": ""}
                if not entities[t]["sentence"]:
                    entities[t]["sentence"] = st

    for fname, n in file_sents.items():
        print(f"[{fname}] {n} 句子")

    counts = {}
    for info in entities.values():
        t = info["type"]
        if t == "PER" and info.get("sentence", ""):
            if not any(k in entities for k in ("艾伦·图灵", "AlanTuring")): continue
        counts[t] = counts.get(t, 0) + 1
    print(f"共 {len(entities)} 个实体: {dict(sorted(counts.items()))}")

    out = os.path.join(OUTPUT_DIR, "crf_extracted_entities.xml")
    with open(out, "w", encoding="utf-8") as f:
        f.write(build_xml(entities, all_sents))
    print(f"已生成: {out}")


if __name__ == "__main__":
    main()
