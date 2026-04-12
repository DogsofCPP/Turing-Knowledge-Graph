"""
使用 CRF 模型进行实体抽取并转换为 RDF
词级版本（与训练对齐）
"""
import os, re, pickle
from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS

BASE = os.path.dirname(__file__)
MODEL_PATH = os.path.join(BASE, "models", "turing_crf_model.pkl")
OUTPUT_DIR = os.path.join(BASE, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 图灵知识图谱命名空间
TURING = Namespace("http://www.example.org/turing#")

# 加载训练好的 CRF 模型
with open(MODEL_PATH, "rb") as f:
    crf = pickle.load(f)


def word2features(sent, i):
    """
    与训练时相同的特征提取函数
    必须保持完全一致以确保预测准确性
    """
    word = sent[i][0]
    features = {
        "bias": 1.0, "word": word, "word.lower()": word.lower(),
        "word.isupper()": word.isupper(), "word.istitle()": word.istitle(),
        "word.isdigit()": word.isdigit(),
        "word.hasdigit": bool(re.search(r"\d", word)),
        "word[:2]": word[:2] if len(word) > 1 else word,
        "word[-2:]": word[-2:] if len(word) > 1 else word,
        "word[:3]": word[:3] if len(word) > 2 else word,
        "word[-3:]": word[-3:] if len(word) > 2 else word,
    }
    if i > 1:
        w2 = sent[i - 2][0]
        features["word-2"] = w2
        features["word-2.istitle()"] = w2.istitle()
        features["word-2[-2:]"] = w2[-2:] if len(w2) > 1 else w2
    else: features["word-2"] = "BOS"
    if i > 0:
        w1 = sent[i - 1][0]
        features["word-1"] = w1
        features["word-1.istitle()"] = w1.istitle()
        features["word-1[-2:]"] = w1[-2:] if len(w1) > 1 else w1
    else: features["word-1"] = "BOS"
    if i < len(sent) - 1:
        w1 = sent[i + 1][0]
        features["word+1"] = w1
        features["word+1.istitle()"] = w1.istitle()
        features["word+1[-2:]"] = w1[-2:] if len(w1) > 1 else w1
    else: features["word+1"] = "EOS"
    if i < len(sent) - 2:
        w2 = sent[i + 2][0]
        features["word+2"] = w2
        features["word+2.istitle()"] = w2.istitle()
        features["word+2[-2:]"] = w2[-2:] if len(w2) > 1 else w2
    else: features["word+2"] = "EOS"
    if i > 0 and i < len(sent) - 1:
        features["word-1+word"] = sent[i - 1][0] + "_" + word
        features["word+word+1"] = word + "_" + sent[i + 1][0]
    if i > 1:
        features["word-2+word-1"] = sent[i - 2][0] + "_" + sent[i - 1][0]
    return features


def sent2features(sent):
    """将句子转换为特征列表"""
    return [word2features(sent, i) for i in range(len(sent))]


def tokenize_en(text):
    """英文分词（与训练时一致）"""
    return re.findall(r"[A-Za-z]+(?:'[a-z]+)?(?:\.[A-Za-z]+)*|\d+|[.,;:!?'\"()[\]–, -]+", text)


def tokenize_zh(text):
    """中文分词（与训练时一致）"""
    import jieba
    return [w for w in jieba.cut(text, cut_all=False) if w.strip()]


# 规则分类器：已知实体词典 + 后缀规则
# 用于修正 CRF 模型可能产生的错误分类
KNOWN_PERSONS = {
    "Alan Turing", "Turing", "Julius Turing", "Ethel Sara Turing",
    "Alonzo Church", "Church", "John von Neumann", "Claude Shannon",
    "Max Newman", "Newman", "Queen Elizabeth II",
}
KNOWN_LOCATIONS = {
    "London", "Maida Vale", "Cambridge", "Princeton", "Bletchley Park",
    "Manchester", "Wilmslow", "Cheshire", "India", "Bletchley", "England",
    "Milton Keynes", "New Jersey", "United States", "King's College",
    "Trinity College",
}
KNOWN_PUBS = {
    "On Computable Numbers", "Computing Machinery and Intelligence",
    "The Chemical Basis of Morphogenesis", "Mind",
    "Automatic Computing Engine", "ACE", "Turing Award",
}
KNOWN_AWARDS = {
    "Royal Society", "Order of the British Empire", "OBE",
    "royal pardon", "fifty-pound banknote", "Alan Turing Act",
}
# 常见姓氏后缀（辅助判断人名）
SURNAME_SUFFIXES = {"son", "ing", "man", "ard", "ell", "ney", "art"}


def classify(text):
    """
    规则分类器：基于词典和后缀规则判断实体类型
    优先级：已知词典 > 后缀规则 > 其他
    """
    if text in KNOWN_PERSONS: return "PER"
    if text in KNOWN_LOCATIONS: return "LOC"
    if text in KNOWN_PUBS: return "PUB"
    if text in KNOWN_AWARDS: return "AWD"
    if text in ("World War II", "World War I"): return "EVT"
    lower = text.lower()
    if any(lower.endswith(s) for s in SURNAME_SUFFIXES): return "PER"
    return None


def merge(tokens, pred):
    """
    合并连续同类型实体并进行规则修正
    1. 将 B-xxx / I-xxx 序列合并为完整实体
    2. 使用规则分类器修正错误类型
    3. 过滤过短实体（长度<2）
    """
    entities = []
    cur, cur_type = [], None
    for (tok, _), p in zip(tokens, pred):
        if p.startswith("B-"):
            if cur_type:
                entities.append((" ".join(cur), cur_type))
            cur, cur_type = [tok], p[2:]
        elif p.startswith("I-") and cur_type:
            cur.append(tok)
        else:
            if cur_type:
                entities.append((" ".join(cur), cur_type))
            cur, cur_type = [], None
    if cur_type:
        entities.append((" ".join(cur), cur_type))
    # 规则修正
    result = []
    for text, etype in entities:
        if len(text.strip()) < 2:
            continue
        rule = classify(text)
        result.append((text.strip(), rule or etype))
    return result


def extract(sentence, tokenize_fn):
    """
    对单个句子进行实体抽取
    1. 分词
    2. 提取特征
    3. CRF 预测
    4. 合并实体并修正
    """
    tokens = tokenize_fn(sentence)
    tokens = [(t, "O") for t in tokens if t.strip()]
    if len(tokens) < 2:
        return []
    features = sent2features(tokens)
    pred = crf.predict([features])[0]
    return merge(tokens, pred)


def build_rdf(entities_dict):
    """
    将抽取的实体构建为 RDF 图
    - 创建实体类型类（PER, LOC, EVT, PUB, AWD）
    - 为每个实体创建 URI 并添加类型和标签
    """
    g = Graph()
    g.bind("turing", TURING)
    g.bind("rdfs", RDFS)

    # 本体元数据
    g.add((TURING.ontology, RDF.type, URIRef("http://www.w3.org/2002/07/owl#Ontology")))
    g.add((TURING.ontology, RDFS.comment,
           Literal("图灵知识图谱 - CRF 实体抽取结果")))

    # 定义实体类型类
    for etype, label_zh in [
        ("PER", "人物"), ("LOC", "地点"), ("EVT", "事件"),
        ("PUB", "著作"), ("AWD", "奖项"),
    ]:
        g.add((TURING[etype], RDF.type, RDFS["Class"]))
        g.add((TURING[etype], RDFS.label, Literal(label_zh)))

    # 添加实体实例
    for text, info in entities_dict.items():
        # 生成合法的 URI（替换特殊字符）
        safe_id = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]", "_", text.strip())
        uri = TURING[safe_id]
        g.add((uri, RDF.type, TURING[info["type"]]))
        g.add((uri, RDFS.label, Literal(text)))
        # 添加描述信息（记录来源句子）
        g.add((uri, TURING.description,
               Literal(f"CRF抽取 (来源: {', '.join(info['sentences'][:3])} )")))

    return g


def main():
    """
    主流程：
    1. 加载中英文语料
    2. 对每句话进行实体抽取
    3. 合并中英文抽取结果
    4. 构建 RDF 图并输出为 XML 和 Turtle 格式
    """
    print("=" * 60)
    print("CRF 词级实体抽取 + RDF 转换")
    print("=" * 60)

    EN = os.path.join(BASE, "corpus", "raw_turing_en.txt")
    ZH = os.path.join(BASE, "corpus", "raw_turing_zh.txt")

    all_entities = {}

    # 英文语料实体抽取
    with open(EN, encoding="utf-8") as f:
        sents = [l.strip().split("\t", 1)[1] for l in f if "\t" in l.strip()]
    for sid, s in enumerate(sents):
        for text, etype in extract(s, tokenize_en):
            if text not in all_entities:
                all_entities[text] = {"type": etype, "sentences": []}
            all_entities[text]["sentences"].append(f"EN{sid+1}")
    print(f"\n[EN] {len(all_entities)} 个实体")

    # 中文语料实体抽取
    with open(ZH, encoding="utf-8") as f:
        sents = [l.strip().split("\t", 1)[1] for l in f if "\t" in l.strip()]
    for sid, s in enumerate(sents):
        for text, etype in extract(s, tokenize_zh):
            if text not in all_entities:
                all_entities[text] = {"type": etype, "sentences": []}
            all_entities[text]["sentences"].append(f"ZH{sid+1}")
    print(f"[All] {len(all_entities)} 个实体（合并后）")

    # 打印抽取结果
    counts = {}
    for text, info in sorted(all_entities.items(), key=lambda x: x[1]["type"]):
        t = info["type"]
        counts[t] = counts.get(t, 0) + 1
        print(f"  [{t:>12}] {text}")
    print(f"\n统计: {dict(sorted(counts.items()))}")

    # 构建 RDF 图并输出
    g = build_rdf(all_entities)
    out_xml = os.path.join(OUTPUT_DIR, "crf_extracted_entities.xml")
    out_ttl = os.path.join(OUTPUT_DIR, "crf_extracted_entities.ttl")
    g.serialize(out_xml, format="xml")
    g.serialize(out_ttl, format="turtle")
    print(f"\nRDF/XML: {out_xml}")
    print(f"Turtle: {out_ttl}")
    print(f"三元组总数: {len(g)}")


if __name__ == "__main__":
    main()
