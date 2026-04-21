# Turing Knowledge Graph Project

图灵知识图谱是一个基于语义网技术构建的专题知识库，以结构化方式表示艾伦·图灵（Alan Turing）的各类知识，并采用 **CRF（条件随机场）命名实体识别** 技术从 Wikipedia 语料中自动抽取实体，纳入知识图谱。

## 项目架构

```
ontology/
├── turing-rdfs.xml         ① RDFS 层：类层次 + 属性定义（domain/range）
└── turing-owl.xml          ② OWL 层：owl:imports turing-rdfs.xml
                              └── FunctionalProperty、minCardinality 等约束

turing-full-data.xml        ③ 实例数据层：owl:imports turing-owl.xml
                              └── 手工结构化实例
                              └── NER 抽取实例（由 04_extract_and_convert.py 生成）

index.html                  可视化界面：加载 turing-full-data.xml
```

**本体层级链：**

```
turing-rdfs.xml  ── owl:imports ──▶  turing-owl.xml  ── owl:imports ──▶  turing-full-data.xml
(类层次+属性)                        (OWL 约束)                            (实例数据)
                                                                                 │
                                                                         ── owl:imports ──▶  ner/output/crf_extracted_entities.xml
                                                                                            (CRF 抽取实体，类型映射后纳入)
```

## ner/ 模块（CRF 命名实体识别流水线）

```
01_fetch_corpus.py          爬取 Wikipedia → raw_turing_en.txt / raw_turing_zh.txt
        ↓
02_prepare_bio.py           词典 + BIO 标注 → bio_turing_en.txt / bio_turing_zh.txt
        ↓
03_train_crf.py             CRF 特征工程 + 训练 → turing_crf_model.pkl
        ↓
04_extract_and_convert.py   实体抽取 → crf_extracted_entities.xml/ttl
                                 PER → Person
                                 LOC → Location (实例用 City)
                                 EVT → HistoricalEvent
                                 PUB → Publication (实例用 Paper)
                                 AWD → Award (实例用 HonoraryTitle)
```

**NER 实体类型映射规则：**

| CRF 标签 | Ontology 类 | 说明 |
|---------|------------|------|
| PER | Person | 人物 |
| LOC | Location（实例 City） | 地点 |
| EVT | HistoricalEvent | 历史事件 |
| PUB | Publication（实例 Paper） | 学术著作 |
| AWD | Award（实例 HonoraryTitle） | 荣誉奖项 |

## 技术栈

- **数据格式**：RDF/XML、Turtle
- **本体层**：RDFS（类层次、属性定义）、OWL（函数性属性、基数约束）
- **实体识别**：CRF（条件随机场），scikit-learn-crfsuite
- **分词**：英文正则、中文 jieba
- **可视化**：原生 DOM 解析 + HTML 渲染

## 核心类

| 类名 | 说明 | 子类 |
|------|------|------|
| Person | 人物 | — |
| Event | 事件 | AcademicEvent、PersonalEvent、HistoricalEvent |
| Location | 地点 | City、Country、InstitutionLocation |
| Publication | 学术著作 | Paper、Book、TechnicalReport |
| Award | 荣誉奖项 | AcademicAward、HonoraryTitle |

## 核心属性

### 对象属性
- `participatedIn`：参与事件（Person → Event）
- `wrote`：撰写著作（Person → Publication）
- `received`：获得奖项（Person → Award）
- `happenedAt`：事件发生地点（Event → Location）
- `locatedIn`：位于某地（Location → Location）

### 数据类型属性
- `eventDate`：事件日期（xsd:date）
- `publicationYear`：发表年份（xsd:gYear）
- `awardYear`：获奖年份（xsd:gYear）
- `description`：描述信息（xsd:string）
- `country`：所属国家（xsd:string）

## 使用方法

### 1. 运行 NER 流水线

```bash
cd ner
pip install -r requirements.txt
python 01_fetch_corpus.py    # 爬取 Wikipedia 语料
python 02_prepare_bio.py     # 生成 BIO 标注
python 03_train_crf.py       # 训练 CRF 模型
python 04_extract_and_convert.py  # 实体抽取 → RDF XML + Turtle
```

### 2. 查看知识图谱

直接在浏览器中打开 `index.html`，页面会自动加载 `turing-full-data.xml`，包含：
- 手工编写的结构化实例
- CRF 抽取并映射后的 NER 实体

### 3. 扩展数据

- 添加手工实例：编辑 `turing-full-data.xml`
- 调整 NER 类型映射规则：修改 `ner/04_extract_and_convert.py` 中的 `CRF_TYPE_MAP`
- 调整中英文实体合并：修改 `ner/04_extract_and_convert.py` 中的 `MERGE_MAP`

## 知识范围

本图谱涵盖艾伦·图灵的：
- 重要生平事件（出生、入学、工作、审判、逝世等）
- 主要活动地点（伦敦、剑桥、普林斯顿、布莱切利、曼彻斯特等）
- 学术著作（《论可计算数》、《计算机与智能》等）
- 荣誉奖项（皇家学会院士、大英帝国勋章、图灵奖等）
- NER 自动抽取的相关人物、地点、著作、奖项（如克劳德·香农、约翰·冯·诺依曼、二战等）
