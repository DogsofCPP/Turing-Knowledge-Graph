# Turing Knowledge Graph Project

图灵知识图谱是一个基于语义网技术构建的专题知识库，旨在以结构化的方式表示和存储关于艾伦·图灵（Alan Turing）的各类知识。

## 项目结构

```
Turing-Knowledge-Graph/
├── ontology/                    # 本体层
│   ├── turing-rdfs.xml        # RDFS类层次和属性定义
│   └── turing-owl.xml         # OWL约束定义
├── data/                       # 实例数据
│   ├── events.xml             # 事件实例
│   ├── locations.xml          # 地点实例
│   ├── publications.xml       # 学术著作实例
│   └── awards.xml             # 荣誉奖项实例
├── turing-full-data.xml        # 完整RDF数据集
├── ontology.ttl               # Turtle格式本体
└── turing-knowledge-graph.ttl  # 完整Turtle数据集
```

## 技术栈

- **数据层**: XML格式存储
- **表示层**: RDF三元组（资源-属性-属性值）
- **建模层**: RDFS定义类层次
- **本体层**: OWL定义约束关系
- **格式**: RDF/XML, Turtle

## 核心类

| 类名 | 说明 | 子类 |
|------|------|------|
| Event | 事件 | AcademicEvent, PersonalEvent, HistoricalEvent |
| Location | 地点 | City, Country, InstitutionLocation |
| Publication | 学术著作 | Paper, Book, TechnicalReport |
| Award | 荣誉奖项 | AcademicAward, HonoraryTitle |

## 核心属性

### 对象属性
- `participatedIn`: 参与事件
- `locatedIn`: 位于某地
- `wrote`: 撰写著作
- `received`: 获得奖项
- `happenedAt`: 事件发生地点
- `nominatedFor`: 被提名奖项

### 数据类型属性
- `eventDate`: 事件发生日期 (xsd:date)
- `publicationYear`: 发表年份 (xsd:gYear)
- `awardYear`: 获奖年份 (xsd:gYear)
- `description`: 描述信息 (xsd:string)

## 使用方法

### 查看RDF数据
可以使用任何RDF查看工具打开 `turing-knowledge-graph.ttl` 文件查看完整的图灵知识图谱数据。

### 扩展数据
如需添加新的实例数据，可以编辑 `data/` 目录下的相应XML文件，或直接扩展 `turing-full-data.xml`。

## 知识范围

本图谱涵盖艾伦·图灵的：
- 重要生平事件（出生、入学、工作、审判、逝世等）
- 主要活动地点（伦敦、剑桥、普林斯顿、布莱切利、曼彻斯特等）
- 学术著作（《论可计算数》、《计算机与智能》等）
- 荣誉奖项（皇家学会院士、大英帝国勋章、图灵奖等）
