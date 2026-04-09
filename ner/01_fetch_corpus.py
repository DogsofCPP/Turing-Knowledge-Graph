"""
图灵 Wikipedia 语料爬取
从英文维基百科获取 Alan Turing 词条正文段落
"""
import requests
import re
import json
import os

OUTPUT = os.path.join(os.path.dirname(__file__), "corpus", "raw_turing.txt")

def fetch_wikipedia_page(title: str) -> str:
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "titles": title,
        "prop": "extracts",
        "explaintext": True,
        "exsectionformat": "plain",
        "format": "json",
        "exlimit": "max",
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    pages = data["query"]["pages"]
    for page in pages.values():
        return page.get("extract", "")
    return ""


def fetch_wikipedia_page_zh(title: str) -> str:
    """获取中文维基百科"""
    url = "https://zh.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "titles": title,
        "prop": "extracts",
        "explaintext": True,
        "exsectionformat": "plain",
        "format": "json",
        "exlimit": "max",
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    pages = data["query"]["pages"]
    for page in pages.values():
        return page.get("extract", "")
    return ""


def split_into_sentences(text: str):
    """按句子分割，保留换行结构"""
    # 去除多余空白
    text = re.sub(r'\s+', ' ', text)
    # 按句子结束标点分割
    sentences = re.split(r'(?<=[.!?])\s+', text)
    # 过滤空句和过短句
    return [s.strip() for s in sentences if len(s.strip()) > 10]


def main():
    print("正在从 Wikipedia 爬取 Alan Turing 相关语料...")

    # 英文词条
    en_text = fetch_wikipedia_page("Alan Turing")
    en_sentences = split_into_sentences(en_text)

    # 补充相关词条
    related_pages = [
        "Turing_machine",
        "Enigma_machine",
        "Bletchley_Park",
        "Turing_Award",
        "Computer_Science",
        "Artificial_intelligence",
    ]
    for p in related_pages:
        text = fetch_wikipedia_page(p)
        en_sentences.extend(split_into_sentences(text))

    # 合并所有英文句子
    combined = "\n".join(f"{i+1}\t{s}" for i, s in enumerate(en_sentences))

    output_en = os.path.join(os.path.dirname(__file__), "corpus", "raw_turing_en.txt")
    with open(output_en, "w", encoding="utf-8") as f:
        f.write(combined)
    print(f"英文语料已保存: {output_en} ({len(en_sentences)} 句)")

    # 中文语料（辅助）
    try:
        zh_text = fetch_wikipedia_page_zh("艾伦·图灵")
        zh_sentences = split_into_sentences(zh_text)
        output_zh = os.path.join(os.path.dirname(__file__), "corpus", "raw_turing_zh.txt")
        with open(output_zh, "w", encoding="utf-8") as f:
            f.write("\n".join(f"{i+1}\t{s}" for i, s in enumerate(zh_sentences)))
        print(f"中文语料已保存: {output_zh} ({len(zh_sentences)} 句)")
    except Exception as e:
        print(f"中文语料获取失败（可忽略）: {e}")


if __name__ == "__main__":
    main()
