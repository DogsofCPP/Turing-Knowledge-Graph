"""
生成词级 BIO 训练语料（精确标记，无重叠）
核心：用句子字符索引精确定位实体，再映射到词索引
"""
import os, re

BASE = os.path.dirname(__file__)
EN_CORPUS = os.path.join(BASE, "corpus", "raw_turing_en.txt")
ZH_CORPUS = os.path.join(BASE, "corpus", "raw_turing_zh.txt")
EN_OUT = os.path.join(BASE, "corpus", "bio_turing_en.txt")
ZH_OUT = os.path.join(BASE, "corpus", "bio_turing_zh.txt")

# 实体集合（文本 -> 类型）
# 用于BIO标注的实体词典，覆盖图灵相关的人名、地点、事件、著作、奖项
ALL_ENTS = {
    # 英文
    "Alan Turing": "PER", "Turing": "PER", "Julius Turing": "PER",
    "Ethel Sara Turing": "PER", "Alonzo Church": "PER", "Church": "PER",
    "John von Neumann": "PER", "Claude Shannon": "PER", "Max Newman": "PER",
    "Newman": "PER", "Queen Elizabeth II": "PER",
    "London": "LOC", "Maida Vale": "LOC", "Cambridge": "LOC",
    "Princeton": "LOC", "Bletchley Park": "LOC", "Manchester": "LOC",
    "Wilmslow": "LOC", "Cheshire": "LOC", "India": "LOC", "England": "LOC",
    "Bletchley": "LOC", "Milton Keynes": "LOC", "New Jersey": "LOC",
    "United States": "LOC", "King's College": "LOC", "Trinity College": "LOC",
    "World War I": "EVT", "World War II": "EVT",
    "On Computable Numbers": "PUB", "Computing Machinery and Intelligence": "PUB",
    "The Chemical Basis of Morphogenesis": "PUB", "Mind": "PUB",
    "Automatic Computing Engine": "PUB", "ACE": "PUB", "Turing Award": "PUB",
    "Royal Society": "AWD", "Order of the British Empire": "AWD",
    "OBE": "AWD", "royal pardon": "AWD", "fifty-pound banknote": "AWD",
    "Alan Turing Act": "AWD",
    # 中文
    "艾伦·图灵": "PER", "图灵": "PER", "朱利叶斯·图灵": "PER",
    "埃塞尔·萨拉·图灵": "PER", "阿隆佐·邱奇": "PER", "邱奇": "PER",
    "约翰·冯·诺依曼": "PER", "克劳德·香农": "PER", "马克斯·纽曼": "PER",
    "伊丽莎白二世": "PER",
    "伦敦": "LOC", "梅达韦尔": "LOC", "剑桥": "LOC", "普林斯顿": "LOC",
    "布莱切利园": "LOC", "曼彻斯特": "LOC", "威尔姆斯洛": "LOC",
    "柴郡": "LOC", "印度": "LOC", "科钦": "LOC", "英格兰": "LOC",
    "二战": "EVT",
    "论可计算数": "PUB", "计算机器与智能": "PUB",
    "形态发生的化学基础": "PUB", "心智": "PUB",
    "自动计算引擎": "PUB", "图灵奖": "PUB",
    "英国皇家学会": "AWD", "大英帝国勋章": "AWD", "皇家赦免": "AWD",
    "五十英镑纸币": "AWD", "艾伦·图灵法案": "AWD",
}


def tokenize_en(sentence):
    """
    英文分词：正则匹配单词、数字、标点符号
    - 保留缩写形式如 don't, Turing's
    - 保留缩写词如 U.S.
    """
    return re.findall(r"[A-Za-z]+(?:'[a-z]+)?(?:\.[A-Za-z]+)*|\d+|[.,;:!?'\"()[\]–—, -]+", sentence)


def tokenize_zh(sentence):
    """中文分词：使用 jieba 精确模式，过滤空白"""
    import jieba
    return [w for w in jieba.cut(sentence, cut_all=False) if w.strip()]


def build_word_positions(sentence, tokens):
    """
    构建每个 token 在句子中的字符位置映射
    返回: [(start, end), ...] 与 tokens 一一对应
    用于将字符级实体位置映射到词级位置
    """
    positions = []
    pos = 0
    for tok in tokens:
        start = sentence.find(tok, pos)
        if start < 0:
            start = pos
        end = start + len(tok)
        positions.append((start, end))
        pos = end
    return positions


def tag_sentence(sentence, tokens, lang):
    """
    对句子进行 BIO 标注
    - 初始化所有词为 O（非实体）
    - 按实体长度降序匹配（避免短实体覆盖长实体）
    - 跳过已被标记的字符区间（避免重叠）
    """
    word_tags = ["O"] * len(tokens)
    positions = build_word_positions(sentence, tokens)

    # 按实体长度降序（先匹配长实体）
    sorted_ents = sorted(ALL_ENTS.items(), key=lambda x: -len(x[0]))

    for entity_text, etype in sorted_ents:
        # 在句子中找实体
        start = 0
        while True:
            idx = sentence.find(entity_text, start)
            if idx < 0:
                break
            end = idx + len(entity_text)
            # 检查该区间是否被其他实体标记（避免重叠）
            covered = False
            for (ws, we) in positions:
                if ws >= idx and we <= end:
                    if word_tags[positions.index((ws, we))] != "O":
                        covered = True
                        break
            if covered:
                start = idx + 1
                continue
            # 找到该实体覆盖了哪些词
            covered_words = []
            for wi, (ws, we) in enumerate(positions):
                if ws >= idx and we <= end:
                    covered_words.append(wi)
            if covered_words:
                word_tags[covered_words[0]] = f"B-{etype}"  # 实体的第一个词
                for wi in covered_words[1:]:
                    word_tags[wi] = f"I-{etype}"           # 实体的后续词
            start = idx + 1

    return list(zip(tokens, word_tags))


def load_sentences(path):
    """加载语料文件，每行格式为 序号\t句子，返回句子列表"""
    with open(path, encoding="utf-8") as f:
        return [l.strip().split("\t", 1)[1] for l in f if "\t" in l.strip()]


def write_bio(output_path, sentences, tokenize_fn, lang):
    """
    将句子列表转换为 BIO 格式并写入文件
    每行: 词\t标签
    句子之间用空行分隔
    返回: 标注的实体片段数量
    """
    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for sent in sentences:
            tokens = tokenize_fn(sent)
            tagged = tag_sentence(sent, tokens, lang)
            for word, tag in tagged:
                f.write(f"{word}\t{tag}\n")
                if tag.startswith("B-"):
                    count += 1
            f.write("\n")  # 句子结束分隔
    return count


def main():
    """主流程：加载语料 -> 生成BIO标注 -> 保存 -> 验证"""
    print("=" * 60)
    print("词级 CRF 训练语料（精确无重叠 BIO 标注）")
    print("=" * 60)

    en_sents = load_sentences(EN_CORPUS)
    en_count = write_bio(EN_OUT, en_sents, tokenize_en, "en")
    print(f"\nEN: {len(en_sents)} sents, {en_count} entity fragments")

    zh_sents = load_sentences(ZH_CORPUS)
    zh_count = write_bio(ZH_OUT, zh_sents, tokenize_zh, "zh")
    print(f"ZH: {len(zh_sents)} sents, {zh_count} entity fragments")

    # 验证：打印前几句包含实体的句子
    print("\n验证（前几句含实体标注）:")
    with open(EN_OUT, encoding="utf-8") as f:
        buf = []
        for line in f:
            line = line.rstrip("\n")
            if not line:
                if buf:
                    shown = []
                    for l in buf:
                        parts = l.split("\t")
                        if len(parts) == 2:
                            shown.append((parts[0], parts[1]))
                    if any(t != "O" for _, t in shown):
                        print("  " + " ".join(f"{w}[{t}]" for w, t in shown[:12]))
                    buf = []
            else:
                buf.append(line)


if __name__ == "__main__":
    main()
