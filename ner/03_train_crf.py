"""
CRF 特征工程与模型训练
为每个词构造特征向量，用于序列标注
"""
import os, re, pickle
import sklearn_crfsuite
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

BASE = os.path.dirname(__file__)
BIO_EN = os.path.join(BASE, "corpus", "bio_turing_en.txt")
BIO_ZH = os.path.join(BASE, "corpus", "bio_turing_zh.txt")
MODEL_PATH = os.path.join(BASE, "models", "turing_crf_model.pkl")


def word2features(sent, i):
    """
    为句子中的第 i 个词构造特征向量
    特征包括：
    - 词形特征：大写、标题式、数字等
    - 词缀特征：前后缀（捕捉命名实体模式）
    - 上下文特征：前后各2个词的词形和词缀
    - 组合特征：bigram 组合（捕捉实体边界）
    """
    word = sent[i][0]
    features = {
        "bias": 1.0,
        "word": word,
        "word.lower()": word.lower(),
        "word.isupper()": word.isupper(),
        "word.istitle()": word.istitle(),
        "word.isdigit()": word.isdigit(),
        "word.hasdigit": bool(re.search(r"\d", word)),
        "word[:2]": word[:2] if len(word) > 1 else word,
        "word[-2:]": word[-2:] if len(word) > 1 else word,
        "word[:3]": word[:3] if len(word) > 2 else word,
        "word[-3:]": word[-3:] if len(word) > 2 else word,
    }
    # 前一个词（word-1）
    if i > 1:
        w2 = sent[i - 2][0]
        features["word-2"] = w2
        features["word-2.istitle()"] = w2.istitle()
        features["word-2.isupper()"] = w2.isupper()
        features["word-2[-2:]"] = w2[-2:] if len(w2) > 1 else w2
    else:
        features["word-2"] = "BOS"  # 句首标记
    if i > 0:
        w1 = sent[i - 1][0]
        features["word-1"] = w1
        features["word-1.istitle()"] = w1.istitle()
        features["word-1.isupper()"] = w1.isupper()
        features["word-1[-2:]"] = w1[-2:] if len(w1) > 1 else w1
    else:
        features["word-1"] = "BOS"
    # 后一个词（word+1）
    if i < len(sent) - 1:
        w1 = sent[i + 1][0]
        features["word+1"] = w1
        features["word+1.istitle()"] = w1.istitle()
        features["word+1.isupper()"] = w1.isupper()
        features["word+1[-2:]"] = w1[-2:] if len(w1) > 1 else w1
    else:
        features["word+1"] = "EOS"  # 句尾标记
    if i < len(sent) - 2:
        w2 = sent[i + 2][0]
        features["word+2"] = w2
        features["word+2.istitle()"] = w2.istitle()
        features["word+2.isupper()"] = w2.isupper()
        features["word+2[-2:]"] = w2[-2:] if len(w2) > 1 else w2
    else:
        features["word+2"] = "EOS"
    # 组合特征（捕捉词组模式）
    if i > 0 and i < len(sent) - 1:
        features["word-1+word"] = sent[i - 1][0] + "_" + word
        features["word+word+1"] = word + "_" + sent[i + 1][0]
    if i > 1:
        features["word-2+word-1"] = sent[i - 2][0] + "_" + sent[i - 1][0]
    return features


def sent2features(sent):
    """将整个句子转换为特征列表"""
    return [word2features(sent, i) for i in range(len(sent))]


def sent2labels(sent):
    """提取句子中每个词的标签"""
    return [tag for _, tag in sent]


def load_bio(path):
    """
    加载 BIO 格式语料
    每行: 词\t标签
    句子之间以空行分隔
    返回: [(word, tag), ...] 的列表
    """
    sentences = []
    current = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                if current:
                    sentences.append(current)
                    current = []
            else:
                parts = line.split("\t")
                if len(parts) >= 2:
                    current.append((parts[0], parts[1]))
    if current:
        sentences.append(current)
    return sentences


def main():
    """主流程：加载语料 -> 构造特征 -> 训练 -> 评估 -> 保存模型"""
    print("=" * 60)
    print("CRF 词级特征工程与模型训练")
    print("=" * 60)

    print("\n[1] 加载语料...")
    en_sents = load_bio(BIO_EN)
    zh_sents = load_bio(BIO_ZH)
    all_sents = en_sents + zh_sents
    print(f"  EN: {len(en_sents)}, ZH: {len(zh_sents)}, Total: {len(all_sents)}")

    print("\n[2] 构造特征...")
    X_all = [sent2features(s) for s in all_sents]
    y_all = [sent2labels(s) for s in all_sents]

    # 划分训练集和测试集（8:2）
    X_train, X_test, y_train, y_test = train_test_split(
        X_all, y_all, test_size=0.2, random_state=42
    )
    print(f"  训练: {len(X_train)}, 测试: {len(X_test)}")

    print("\n[3] 训练 CRF...")
    crf = sklearn_crfsuite.CRF(
        algorithm="lbfgs",  # L-BFGS 优化算法
        c1=0.1,             # L1 正则化系数
        c2=0.1,             # L2 正则化系数
        max_iterations=200, # 最大迭代次数
        all_possible_transitions=True,  # 允许所有可能的标签转移
    )
    crf.fit(X_train, y_train)

    # 预测并评估
    y_pred = crf.predict(X_test)
    labels = [l for l in crf.classes_ if l != "O"]
    y_test_flat = [t for seq in y_test for t in seq]
    y_pred_flat = [p for seq in y_pred for p in seq]

    print("\n[4] 测试集分类报告:")
    print(classification_report(y_test_flat, y_pred_flat,
                                labels=labels, digits=4, zero_division=0))

    # 保存模型
    os.makedirs(os.path.join(BASE, "models"), exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(crf, f)
    print(f"模型已保存: {MODEL_PATH}")


if __name__ == "__main__":
    main()
