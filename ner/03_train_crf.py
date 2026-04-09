"""
CRF 特征工程 - 词级版本
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
    if i > 1:
        w2 = sent[i - 2][0]
        features["word-2"] = w2
        features["word-2.istitle()"] = w2.istitle()
        features["word-2.isupper()"] = w2.isupper()
        features["word-2[-2:]"] = w2[-2:] if len(w2) > 1 else w2
    else:
        features["word-2"] = "BOS"
    if i > 0:
        w1 = sent[i - 1][0]
        features["word-1"] = w1
        features["word-1.istitle()"] = w1.istitle()
        features["word-1.isupper()"] = w1.isupper()
        features["word-1[-2:]"] = w1[-2:] if len(w1) > 1 else w1
    else:
        features["word-1"] = "BOS"
    if i < len(sent) - 1:
        w1 = sent[i + 1][0]
        features["word+1"] = w1
        features["word+1.istitle()"] = w1.istitle()
        features["word+1.isupper()"] = w1.isupper()
        features["word+1[-2:]"] = w1[-2:] if len(w1) > 1 else w1
    else:
        features["word+1"] = "EOS"
    if i < len(sent) - 2:
        w2 = sent[i + 2][0]
        features["word+2"] = w2
        features["word+2.istitle()"] = w2.istitle()
        features["word+2.isupper()"] = w2.isupper()
        features["word+2[-2:]"] = w2[-2:] if len(w2) > 1 else w2
    else:
        features["word+2"] = "EOS"
    if i > 0 and i < len(sent) - 1:
        features["word-1+word"] = sent[i - 1][0] + "_" + word
        features["word+word+1"] = word + "_" + sent[i + 1][0]
    if i > 1:
        features["word-2+word-1"] = sent[i - 2][0] + "_" + sent[i - 1][0]
    return features


def sent2features(sent):
    return [word2features(sent, i) for i in range(len(sent))]


def sent2labels(sent):
    return [tag for _, tag in sent]


def load_bio(path):
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

    X_train, X_test, y_train, y_test = train_test_split(
        X_all, y_all, test_size=0.2, random_state=42
    )
    print(f"  训练: {len(X_train)}, 测试: {len(X_test)}")

    print("\n[3] 训练 CRF...")
    crf = sklearn_crfsuite.CRF(
        algorithm="lbfgs", c1=0.1, c2=0.1,
        max_iterations=200, all_possible_transitions=True,
    )
    crf.fit(X_train, y_train)

    y_pred = crf.predict(X_test)
    labels = [l for l in crf.classes_ if l != "O"]
    y_test_flat = [t for seq in y_test for t in seq]
    y_pred_flat = [p for seq in y_pred for p in seq]

    print("\n[4] 测试集分类报告:")
    print(classification_report(y_test_flat, y_pred_flat,
                                labels=labels, digits=4, zero_division=0))

    os.makedirs(os.path.join(BASE, "models"), exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(crf, f)
    print(f"模型已保存: {MODEL_PATH}")


if __name__ == "__main__":
    main()
