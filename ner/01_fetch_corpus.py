"""
图灵 Wikipedia 语料爬取
从英文维基百科获取 Alan Turing 词条正文段落
"""
import requests
import re
import json
import os

def fetch_wikipedia_page(title: str) -> str:
    """
    调用 Wikipedia REST API 获取指定词条的纯文本内容
    - explaintext=True: 返回纯文本而非HTML
    - exsectionformat="plain": 使用纯文本格式保留段落结构
    """
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
    """获取中文维基百科（同英文版，但接口为 zh.wikipedia.org）"""
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
    """
    按句子分割文本，保留基本换行结构
    - 合并多余空白字符
    - 按 . ! ? 等句子结束标点分割
    - 过滤长度小于10字符的短句
    """
    # 去除多余空白
    text = re.sub(r'\s+', ' ', text)
    # 按句子结束标点分割（使用零宽断言保留标点）
    sentences = re.split(r'(?<=[.!?])\s+', text)
    # 过滤空句和过短句
    return [s.strip() for s in sentences if len(s.strip()) > 10]


def main():
    """
    主流程：
    1. 获取 Alan Turing 主词条及相关词条
    2. 分割为句子并保存为语料文件
    3. 尝试获取中文语料（失败不影响主流程）
    """
    print("正在从 Wikipedia 爬取 Alan Turing 相关语料...")

    # 主词条
    en_text = fetch_wikipedia_page("Alan Turing")
    en_sentences = split_into_sentences(en_text)

    # 相关补充词条（扩展语料覆盖范围）
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

    # 保存英文语料（格式：序号\t句子）
    combined = "\n".join(f"{i+1}\t{s}" for i, s in enumerate(en_sentences))

    output_en = os.path.join(os.path.dirname(__file__), "corpus", "raw_turing_en.txt")
    with open(output_en, "w", encoding="utf-8") as f:
        f.write(combined)
    print(f"英文语料已保存: {output_en} ({len(en_sentences)} 句)")

    # 中文语料
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
