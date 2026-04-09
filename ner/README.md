# 图灵知识图谱 - CRF 实体抽取模块

本模块实现了基于**条件随机场（CRF）**的传统机器学习方法进行命名实体识别（NER），
将抽取结果转换为 RDF 三元组，构成知识图谱的实体层。

---

## 目录结构

```
ner/
├── 01_fetch_corpus.py        # 语料爬取（Wikipedia API）
├── 02_prepare_bio.py         # BIO 标注语料生成
├── 03_train_crf.py           # CRF 特征工程与模型训练
├── 04_extract_and_convert.py # 实体抽取 + RDF 转换
├── requirements.txt           # 依赖
├── corpus/                   # 语料目录
│   ├── raw_turing_en.txt     # 原始英文语料
│   ├── raw_turing_zh.txt     # 原始中文语料
│   ├── bio_turing_en.txt     # 英文 BIO 训练语料
│   └── bio_turing_zh.txt     # 中文 BIO 训练语料
├── models/                  # 模型目录
│   └── turing_crf_model.pkl # 训练好的 CRF 模型
└── output/                   # 输出目录
    ├── crf_extracted_entities.xml  # RDF/XML 格式抽取结果
    └── crf_extracted_entities.ttl  # Turtle 格式抽取结果
```

---

## 流水线

### Step 1：语料获取

```bash
python 01_fetch_corpus.py
```

从 Wikipedia API 获取 Alan Turing 相关英文词条及关联词条（Enigma, Bletchley Park 等）。
若网络不可用，已预置 `corpus/raw_turing_*.txt` 语料。

### Step 2：BIO 标注语料生成

```bash
python 02_prepare_bio.py
```

将原始句子转换为 CRF 训练所需的 BIO 格式：
- **英文**：空格 + 标点分词（词级）
- **中文**：jieba 分词（词级）
- 实体按类型独立标注，长实体优先匹配避免覆盖

输出 `bio_turing_*.txt`，每行格式：`词[TAB]标签`

### Step 3：CRF 特征工程与训练

```bash
python 03_train_crf.py
```

为每个词构造特征向量：

| 特征类型 | 说明 |
|---------|------|
| 词形特征 | `isupper`, `istitle`, `isdigit`, `hasdigit` |
| 前后缀 | `word[:2]`, `word[-2:]`, `word[:3]`, `word[-3:]` |
| 上下文窗口 | ±2 词的词本身及后缀 |
| 组合特征 | `word-1+word`, `word+word+1`, `word-2+word-1` |

训练使用 **L-BFGS** 优化，输出 `models/turing_crf_model.pkl`。

### Step 4：实体抽取 + RDF 转换

```bash
python 04_extract_and_convert.py
```

对语料中的句子进行 CRF 预测，后处理包含：
- 合并相邻同名标��为实体
- 规则修正（已知实体表 + 后缀规则）
- 结果转换为 RDF 三元组（XML / Turtle）

---

## 实体类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `PER` | 人名 | Alan Turing, John von Neumann, 艾伦·图灵 |
| `LOC` | 地名 | London, Cambridge, 曼彻斯特, 布莱切利园 |
| `EVT` | 事件 | World War II, 二战 |
| `PUB` | 著作 | Turing Award, Computing Machinery and Intelligence |
| `AWD` | 奖项 | OBE, Royal Society, 皇家赦免, 艾伦·图灵法案 |

---

## 方法说明

### 为什么用 CRF？

CRF 是经典的序列标注模型，考虑标签之间的转移依赖关系（如 B-PER 后面通常是 I-PER），
比朴素贝叶斯等独立分类更适合 NER 任务。

### BIO 标注体系

```
Alan    B-PER   ← 实体的开头（Beginning）
Turing  I-PER   ← 实体的延续（Inside）
was     O       ← 非实体（Outside）
born    O
London  B-LOC   ← 地名实体的开头
```

### 特征设计要点

1. **词形特征**：大写字母 → 可能是专有名词，但不足以区分 PER/LOC
2. **后缀特征**：`‑son/‑ing/‑man` → 人名姓氏特征；`‑ton/‑ford/‑park` → 地名特征
3. **上下文窗口**：捕捉实体周围的介词（in/at → LOC）和动词（supervised/father → PER）
4. **组合特征**：如 `von Neumann` 中的 `von` 是强人名指示

### 后处理规则

训练语料规模有限（各 30-40 句），CRF 可能将某些实体误分类为其他类型。
后处理规则根据实体文本的**词典匹配 + 后缀模式**对 CRF 输出进行修正，
优先使用规则类型，保证准确率。

---

## 依赖

```bash
pip install -r requirements.txt
```

核心依赖：
- `sklearn-crfsuite` — CRF 实现（基于 python-crfsuite）
- `jieba` — 中文分词
- `rdflib` — RDF 转换
- `requests` — 语料爬取

---

## 局限与改进方向

1. **语料规模小**（70 句），模型泛化能力有限
2. **训练数据无噪声**：所有实体均由已知词典生成，缺少真实噪声语料
3. **可改进方向**：
   - 扩大语料规模（真实 Wikipedia 文章）
   - 使用 BERT-CRF / BILSTM-CRF 替代传统 CRF
   - 引入 POS 标签特征（需安装 spaCy / NLTK）
   - 关系抽取：从实体共现场景中抽取三元组关系
