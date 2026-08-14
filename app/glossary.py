# -*- coding: utf-8 -*-
"""自定义词库：与云端翻译配合使用。

原理：先把词库命中的原文替换成随机占位符，再交给云端翻译；
翻译完成后把占位符替换成词库译文。这样词库词条既不会被云端乱翻，
又能保证最终译文与词库一致（词条译文可与原文相同，用于“保留原名”）。

词库来源：
1. 手动词条 词库/默认词库.csv（界面内可增删改）
2. 词库/ 目录下的文件，按格式分子目录（tsv / tbx / tmx / json / csv / txt），
   可勾选启用哪些文件；默认内置两个 GitHub 词库项目：
   - LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words (txt)
   - LDNOOBW/naughty-words-js (json)
"""

import csv
import json
import os
import random
import re
import xml.etree.ElementTree as ET

from . import config as cfg_mod

MATCH_MODES = ["substring", "word", "regex"]
MATCH_MODE_NAMES = {
    "substring": "子串匹配",
    "word": "整词匹配",
    "regex": "正则表达式",
}
MODE_BY_NAME = {v: k for k, v in MATCH_MODE_NAMES.items()}

HEADER = ["原文", "译文", "匹配方式", "启用"]
FORMAT_DIRS = ["tsv", "tbx", "tmx", "json", "csv", "txt"]
FORMAT_NAMES = {
    "tsv": "TSV",
    "tbx": "TBX-Basic",
    "tmx": "TMX",
    "json": "JSON",
    "csv": "CSV",
    "txt": "TXT",
}

# 知名词库（名称, 下载/官网地址, 简介, 本地相对路径或 None）
FAMOUS_GLOSSARIES = [
    (
        "LDNOOBW 多语言脏话词库",
        "https://github.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words",
        "覆盖 29 种语言的脏话/敏感词列表，适合做内容过滤与词库示例",
        "txt/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words",
    ),
    (
        "LDNOOBW naughty-words-js",
        "https://github.com/LDNOOBW/naughty-words-js",
        "脏话/敏感词词库的 JSON 版本，28 种语言",
        "json/naughty-words-js",
    ),
    (
        "微软官方术语库 Microsoft Terminology",
        "https://www.microsoft.com/en-us/language/downloads",
        "微软多语言产品术语集合，100+ 种语言，覆盖 IT、软件、云计算等科技领域",
        None,
    ),
    (
        "IATE 欧盟术语库",
        "https://iate.europa.eu",
        "欧盟 24 种官方语言术语库，覆盖法律、科技、生物、农业等领域",
        None,
    ),
    (
        "UNTERM 联合国术语库",
        "https://unterm.un.org",
        "联合国多语言术语，覆盖政治、法律、外交等领域",
        None,
    ),
    (
        "WIPO Pearl 知识产权术语库",
        "https://wipopearl.wipo.int",
        "世界知识产权组织多语言术语，覆盖专利、科技、生物医药等领域",
        None,
    ),
    (
        "Termium Plus 加拿大术语库",
        "https://www.btb.termiumplus.gc.ca",
        "加拿大政府术语库，英/法/西三语，覆盖政府与科技领域",
        None,
    ),
    (
        "BabelNet 多语言语义网络",
        "https://babelnet.org",
        "覆盖 284 种语言的多语言语义网络",
        None,
    ),
    (
        "Open Multilingual Wordnet",
        "https://omwn.org",
        "多语言词网（Open Multilingual Wordnet）",
        None,
    ),
    (
        "Kaikki 机器可读词典",
        "https://kaikki.org",
        "上百种语言的机器可读词典数据",
        None,
    ),
    (
        "WordNet 英语词网",
        "https://wordnet.princeton.edu",
        "英语词汇语义网络，适合英文词义处理",
        None,
    ),
    (
        "GCIDE 协作英语词典",
        "https://www.gnu.org/software/gcide/",
        "GNU 协作国际英语词典",
        None,
    ),
    (
        "WOLD 世界借词数据库",
        "https://wold.clld.org",
        "41 种语言的借词数据库",
        None,
    ),
    (
        "CC-CEDICT 汉英词典",
        "https://www.mdbg.net/chinese/dictionary?page=cc-cedict",
        "开源汉英词典，收录大量汉字与常用词汇",
        None,
    ),
    (
        "JMDict 日英词典",
        "https://www.edrdg.org/jmdict/j_jmdict.html",
        "开源日英词典，收录 20 万+ 日语词条",
        None,
    ),
    (
        "FreeDict 多语言词典",
        "https://freedict.org",
        "多语言开源双语词典，支持自由下载",
        None,
    ),
    (
        "OmegaWiki 多语言词典",
        "https://www.omegawiki.org",
        "跨语言维基词典，覆盖上百种语言",
        None,
    ),
]


def find_famous_local(entry):
    """返回知名词库在本地 词库/ 目录中对应的文件夹路径；未找到返回 None。"""
    rel = entry[3] if len(entry) > 3 else None
    if not rel:
        return None
    p = os.path.join(glossary_dir(), rel)
    if os.path.isdir(p):
        return p
    if os.path.isfile(p):
        return os.path.dirname(p)
    return None


def glossary_path():
    """手动词条 CSV 路径：词库目录下的 默认词库.csv。"""
    return os.path.join(glossary_dir(), "默认词库.csv")


def glossary_dir():
    """词库文件目录：与程序同目录的 词库/ 文件夹。"""
    return os.path.join(cfg_mod.get_app_dir(), "词库")


def ensure_glossary_structure():
    """确保词库目录与各格式子目录存在。"""
    base = glossary_dir()
    for sub in FORMAT_DIRS:
        os.makedirs(os.path.join(base, sub), exist_ok=True)
    return base


# ---------------------------------------------------------------- 手动词条 CSV
def load_entries(path=None):
    """读取词库 CSV，返回 [{source, target, mode, enabled}, ...]。"""
    path = path or glossary_path()
    entries = []
    if not os.path.exists(path):
        return entries
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not row or not row.get("原文"):
                    continue
                source = (row.get("原文") or "").strip()
                target = (row.get("译文") or "").strip()
                mode = (row.get("匹配方式") or "").strip()
                mode = MODE_BY_NAME.get(mode, mode)
                if mode not in MATCH_MODES:
                    mode = "substring"
                enabled_raw = (row.get("启用") or "1").strip().lower()
                enabled = enabled_raw in ("1", "true", "是", "启用", "yes", "y")
                entries.append(
                    {
                        "source": source,
                        "target": target,
                        "mode": mode,
                        "enabled": enabled,
                    }
                )
    except OSError:
        pass
    return entries


def save_entries(entries, path=None):
    """写回词库 CSV（UTF-8 带 BOM，Excel 可直接打开编辑）。"""
    path = path or glossary_path()
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        for e in entries:
            writer.writerow(
                [
                    e.get("source", ""),
                    e.get("target", ""),
                    e.get("mode", "substring"),
                    1 if e.get("enabled", True) else 0,
                ]
            )
    return path


def ensure_glossary_file(path=None):
    """不存在时创建带表头的词库文件，并写入两条“停用”示例方便参考。"""
    path = path or glossary_path()
    if not os.path.exists(path):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            samples = [
                {"source": "NavEditor", "target": "导航编辑器", "mode": "substring", "enabled": False},
                {"source": "Deep Purple", "target": "Deep Purple", "mode": "word", "enabled": False},
            ]
            save_entries(samples, path)
        except OSError:
            pass
    return path


# ---------------------------------------------------------------- 词库目录扫描
def scan_glossary_files():
    """扫描 词库/ 目录，返回 [{rel, path, folder, name}, ...]，按格式分文件夹。"""
    base = glossary_dir()
    results = []
    if not os.path.isdir(base):
        return results
    for folder in sorted(os.listdir(base)):
        fdir = os.path.join(base, folder)
        if not os.path.isdir(fdir):
            continue
        for dirpath, dirnames, filenames in os.walk(fdir):
            dirnames.sort()
            for fn in sorted(filenames):
                if fn == "默认词库.csv":
                    continue  # 手动词条文件不参与“词库文件”勾选
                if fn.upper().startswith(("LICENSE", "README")) or fn.lower().endswith((".md", ".txt.md")):
                    continue
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, base).replace("\\", "/")
                results.append(
                    {
                        "rel": rel,
                        "path": full,
                        "folder": folder,
                        "name": fn,
                    }
                )
    return results


# ---------------------------------------------------------------- 各格式解析
def _pin_entry(word):
    return {"source": word, "target": word, "mode": "substring", "enabled": True}


def _pair_entry(source, target, mode="substring"):
    return {"source": source, "target": target, "mode": mode, "enabled": True}


def parse_txt(path):
    entries = []
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            if "\t" in line:
                parts = line.split("\t", 1)
                entries.append(_pair_entry(parts[0].strip(), parts[1].strip()))
            else:
                entries.append(_pin_entry(line))
    return entries


def parse_csv(path, delimiter=","):
    entries = []
    with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
        rows = list(csv.reader(f, delimiter=delimiter))
    if not rows:
        return entries
    header = rows[0]
    col = {name.strip(): i for i, name in enumerate(header) if name.strip()}
    if any(k in col for k in ("原文", "译文", "匹配方式", "启用")):
        data = rows[1:]

        def get(row, name, default=""):
            i = col.get(name)
            return row[i].strip() if i is not None and i < len(row) else default

        for row in data:
            source = get(row, "原文")
            if not source:
                continue
            mode = get(row, "匹配方式", "substring")
            mode = MODE_BY_NAME.get(mode, mode)
            if mode not in MATCH_MODES:
                mode = "substring"
            enabled = get(row, "启用", "1").lower() in ("1", "true", "是", "启用", "yes", "y")
            entries.append(
                {
                    "source": source,
                    "target": get(row, "译文", source),
                    "mode": mode,
                    "enabled": enabled,
                }
            )
    else:
        # 无表头：1 列=词表(保留原文)，2 列=原文,译文，3 列=原文,译文,匹配方式
        for row in rows:
            if not row or not row[0].strip():
                continue
            source = row[0].strip()
            if len(row) >= 3 and row[2].strip():
                mode = row[2].strip()
                mode = MODE_BY_NAME.get(mode, mode)
                entries.append(_pair_entry(source, row[1].strip(), mode if mode in MATCH_MODES else "substring"))
            elif len(row) >= 2:
                entries.append(_pair_entry(source, row[1].strip()))
            else:
                entries.append(_pin_entry(source))
    return entries


def parse_json(path):
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        data = json.load(f)
    entries = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                entries.append(_pin_entry(item.strip()))
            elif isinstance(item, dict) and item.get("source"):
                entries.append(_pair_entry(str(item["source"]).strip(), str(item.get("target") or item["source"]).strip()))
    elif isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, list):
                # {语言: [词...]} 或 {"source": [...], "target": [...]} 均按词表处理
                for word in value:
                    if isinstance(word, str) and word.strip():
                        entries.append(_pin_entry(word.strip()))
            elif isinstance(value, str) and key != "source":
                # {原文: 译文}
                entries.append(_pair_entry(key.strip(), value.strip()))
            elif isinstance(value, dict) and value.get("source"):
                entries.append(_pair_entry(str(value["source"]).strip(), str(value.get("target") or value["source"]).strip()))
    return entries


def _xml_pair_entries(root, container_tag, seg_path):
    entries = []
    for container in root.iter(container_tag):
        pairs = []
        for seg in container.iter(seg_path):
            text = "".join(seg.itertext()).strip()
            if text:
                pairs.append(text)
        if len(pairs) >= 2 and pairs[0] and pairs[1]:
            entries.append(_pair_entry(pairs[0], pairs[1]))
    return entries


def parse_tmx(path):
    tree = ET.parse(path)
    return _xml_pair_entries(tree.getroot(), "tu", "seg")


def parse_tbx(path):
    tree = ET.parse(path)
    entries = []
    for term_entry in tree.getroot().iter("termEntry"):
        terms = []
        for lang_set in term_entry.iter("langSet"):
            term = lang_set.find(".//term")
            if term is not None:
                text = "".join(term.itertext()).strip()
                if text:
                    terms.append(text)
        if len(terms) >= 2 and terms[0] and terms[1]:
            entries.append(_pair_entry(terms[0], terms[1]))
    return entries


def parse_file(path):
    """按扩展名解析词库文件，返回 (entries, error)。"""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".txt":
            return parse_txt(path), None
        if ext == ".csv":
            return parse_csv(path, ","), None
        if ext == ".tsv":
            return parse_csv(path, "\t"), None
        if ext == ".json":
            return parse_json(path), None
        if ext == ".tmx":
            return parse_tmx(path), None
        if ext == ".tbx":
            return parse_tbx(path), None
        return [], f"不支持的格式: {ext or '无扩展名'}"
    except Exception as e:
        return [], f"解析失败: {e}"


def load_selected_file_entries(cfg):
    """加载配置中勾选的词库文件，返回词条列表。"""
    selected = cfg.get("glossary", {}).get("files") or []
    if not selected:
        return [], []
    selected = set(selected)
    entries = []
    errors = []
    for info in scan_glossary_files():
        if info["rel"] in selected:
            ents, err = parse_file(info["path"])
            entries.extend(ents)
            if err:
                errors.append(f"{info['rel']}: {err}")
    return entries, errors


# ---------------------------------------------------------------- 词库对象
def _make_token(index):
    return f"KWS{index}{random.randint(100000, 999999)}KWS"


class Glossary:
    """词库对象：protect -> 云端翻译 -> restore。

    子串/整词条目使用“最长优先”的字典扫描，几十万词条也能快速匹配；
    正则条目单独顺序处理。
    """

    def __init__(self, entries, case_sensitive=False):
        self.case_sensitive = case_sensitive
        self.entries = [e for e in entries if e.get("enabled") and e.get("source")]
        self.restore_map = {}
        self._token_i = 0
        self.sub_map = {}
        self.word_map = {}
        self.regex_entries = []
        self.max_len = 0
        for e in self.entries:
            source = e["source"]
            target = e.get("target") or source
            if e.get("mode") == "regex":
                try:
                    re.compile(source, self._flags())
                except re.error:
                    continue
                self.regex_entries.append(e)
                continue
            key = source if self.case_sensitive else source.lower()
            bucket = self.word_map if e.get("mode") == "word" else self.sub_map
            bucket[key] = (target, source)
            self.max_len = max(self.max_len, len(source))
        self.max_len = min(max(1, self.max_len), 300)

    @property
    def active_count(self):
        # 只统计真正可用的词条：无效正则（编译失败被跳过）不计数
        return len(self.sub_map) + len(self.word_map) + len(self.regex_entries)

    def _flags(self):
        return 0 if self.case_sensitive else re.IGNORECASE

    def _next_token(self):
        token = _make_token(self._token_i)
        self._token_i += 1
        return token

    @staticmethod
    def _boundary_ok(text, start, end):
        if start > 0 and (text[start - 1].isalnum() or text[start - 1] == "_"):
            return False
        if end < len(text) and (text[end].isalnum() or text[end] == "_"):
            return False
        return True

    def _scan_replace(self, text, word_map, boundary):
        """用字典扫描替换命中的词条（同一位置取最长匹配）。"""
        if not word_map:
            return text
        n = len(text)
        low = text.lower() if not self.case_sensitive else text
        out = []
        i = 0
        while i < n:
            found = None
            for length in range(min(self.max_len, n - i), 0, -1):
                key = low[i : i + length] if not self.case_sensitive else text[i : i + length]
                item = word_map.get(key)
                if item is None:
                    continue
                if boundary and not self._boundary_ok(text, i, i + length):
                    continue
                found = (length, item)
                break
            if found:
                length, (target, source) = found
                token = self._next_token()
                self.restore_map[token] = target if target else source
                out.append(token)
                i += length
            else:
                out.append(text[i])
                i += 1
        return "".join(out)

    def protect(self, text):
        """把命中的词条原文替换成占位符，返回 (掩码文本, 占位符->译文 映射)。"""
        self.restore_map = {}
        self._token_i = 0
        masked = self._scan_replace(text, self.sub_map, boundary=False)
        masked = self._scan_replace(masked, self.word_map, boundary=True)
        for e in self.regex_entries:
            source, target = e["source"], e.get("target") or e["source"]
            pattern = re.compile(source, self._flags())

            def repl(m, target=target):
                token = self._next_token()
                self.restore_map[token] = m.expand(target) if target else m.group(0)
                return token

            masked = pattern.sub(repl, masked)
        return masked, dict(self.restore_map)

    def restore(self, masked):
        result = masked
        for token, target in self.restore_map.items():
            result = result.replace(token, target)
        # 清理云端可能留下的双空格
        return re.sub(r"\s{2,}", " ", result).strip()

    def apply(self, translate_func, text, source, target):
        """词库 + 云端翻译：原文->占位符->云端翻译->还原词库译文。"""
        if not self.entries:
            return translate_func(text, source, target)
        masked, _map = self.protect(text)
        translated = translate_func(masked, source, target)
        return self.restore(translated)
