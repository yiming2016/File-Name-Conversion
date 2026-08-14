# -*- coding: utf-8 -*-
"""文件发现、重命名规划、冲突处理与撤销。"""

import os
import re
import time


# ---------------------------------------------------------------- 文件名处理
ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(name):
    """去掉 Windows 非法字符，压缩空白，去掉首尾的点与空格。"""
    name = ILLEGAL_CHARS.sub(" ", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    # 控制最大长度，避免超出路径限制
    if len(name) > 180:
        name = name[:180].rstrip(" .")
    return name


def unique_path(path, taken):
    """路径冲突时自动加 (2)、(3)...，返回可用路径并登记。"""
    folder, name = os.path.split(path)
    stem, ext = os.path.splitext(name)
    candidate = path
    n = 2
    while candidate in taken or os.path.exists(candidate):
        candidate = os.path.join(folder, f"{stem} ({n}){ext}")
        n += 1
        if n > 999:
            break
    taken.add(candidate)
    return candidate


# ---------------------------------------------------------------- 语言脚本检测
def _any_in_ranges(text, ranges):
    for ch in text:
        for lo, hi in ranges:
            if lo <= ord(ch) <= hi:
                return True
    return False


SCRIPT_RANGES = {
    "zh-CN": [(0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF)],
    "ja": [(0x3040, 0x30FF)],  # 假名
    "ko": [(0xAC00, 0xD7AF), (0x1100, 0x11FF)],
    "ru": [(0x0400, 0x04FF)],
    "th": [(0x0E00, 0x0E7F)],
    "ar": [(0x0600, 0x06FF)],
    "he": [(0x0590, 0x05FF)],
    "el": [(0x0370, 0x03FF)],
    "hi": [(0x0900, 0x097F)],
    "fa": [(0x0600, 0x06FF)],
}


def looks_like_target_language(stem, target):
    """粗略判断文件名是否已经属于目标语言（用于“跳过已翻译”）。"""
    if not stem:
        return True
    if target == "en":
        return all(ch.isascii() for ch in stem)
    ranges = SCRIPT_RANGES.get(target)
    if ranges:
        return _any_in_ranges(stem, ranges)
    return False


def detect_script_language(text):
    """按文字体系粗略检测语言（用于“源语言多选”过滤）；无法判断返回 None。"""
    for code, ranges in SCRIPT_RANGES.items():
        if _any_in_ranges(text, ranges):
            return code
    return None


# ---------------------------------------------------------------- 文件发现
def parse_extensions(text):
    """把用户输入的扩展名文本解析成小写集合；'*' 或空表示全部。"""
    text = (text or "").strip()
    if not text or text == "*":
        return None  # None 表示全部
    exts = set()
    for part in text.replace("，", ",").split(","):
        part = part.strip().lower()
        if not part:
            continue
        if part == "*":
            return None
        if not part.startswith("."):
            part = "." + part
        exts.add(part)
    return exts or None


def discover_files(folder, recursive, extensions_text):
    exts = parse_extensions(extensions_text)
    paths = []
    if recursive:
        for root, _dirs, files in os.walk(folder):
            for name in files:
                full = os.path.join(root, name)
                if exts is None or os.path.splitext(name)[1].lower() in exts:
                    paths.append(full)
    else:
        try:
            names = os.listdir(folder)
        except OSError as e:
            raise OSError(f"无法读取文件夹：{e}") from e
        for name in names:
            full = os.path.join(folder, name)
            if os.path.isfile(full):
                if exts is None or os.path.splitext(name)[1].lower() in exts:
                    paths.append(full)
    return sorted(paths)


def split_targets(text):
    """把输入拆成多个路径（支持 ; 或全角；分隔，支持带引号的路径）。"""
    parts = []
    for p in text.replace("；", ";").split(";"):
        p = p.strip().strip('"').strip()
        if p:
            parts.append(p)
    return parts


def discover_entries(text, recursive, extensions_text):
    """支持文件夹或文件（多个用 ; 分隔）：文件夹按规则扫描，文件直接加入。
    返回 (文件路径列表, 无效路径列表)。"""
    paths = []
    invalid = []
    for part in split_targets(text):
        if os.path.isdir(part):
            paths.extend(discover_files(part, recursive, extensions_text))
        elif os.path.isfile(part):
            exts = parse_extensions(extensions_text)
            if exts is None or os.path.splitext(part)[1].lower() in exts:
                paths.append(part)
        else:
            invalid.append(part)
    return sorted(set(paths)), invalid


# ---------------------------------------------------------------- 重命名规划
def build_plan(paths, translate_fn, target_lang, skip_target, progress_cb=None, stop_flag=None, post_filter=None, pause_event=None):
    """为每个文件计算新文件名。

    返回列表，每项：
        path / old_name / folder / stem / new_name / new_path / status
    status: "ok"(待重命名) / "skip"(跳过) / "error"(翻译失败，保留原名)
    """
    plan = []
    taken = set()
    total = len(paths)
    for i, full in enumerate(paths):
        if stop_flag is not None and stop_flag.is_set():
            break
        if pause_event is not None:
            # 暂停：等待恢复（期间仍响应停止）
            while pause_event.is_set():
                if stop_flag is not None and stop_flag.is_set():
                    break
                time.sleep(0.2)
        folder = os.path.dirname(full)
        old_name = os.path.basename(full)
        stem, ext = os.path.splitext(old_name)
        item = {
            "path": full,
            "folder": folder,
            "old_name": old_name,
            "stem": stem,
            "new_name": old_name,
            "new_path": full,
            "status": "skip",
            "note": "",
        }
        if not stem:
            item["note"] = "空文件名"
        elif skip_target and looks_like_target_language(stem, target_lang):
            item["note"] = "已为目标语言，跳过"
        else:
            try:
                translated = (translate_fn(stem) or "").strip()
                skip_note = None
                if not translated:
                    item["note"] = "翻译结果为空"
                elif post_filter is not None:
                    _keep = post_filter(item, translated)
                    if isinstance(_keep, str):
                        # 返回字符串表示“跳过”，字符串即为跳过原因
                        skip_note = _keep
                    elif not _keep:
                        skip_note = "源语言不在所选范围，跳过"
                if skip_note:
                    item["status"] = "skip"
                    item["note"] = skip_note
                elif translated:
                    new_stem = sanitize_filename(translated)
                    new_name = new_stem + ext
                    if new_name.lower() == old_name.lower() and new_name == old_name:
                        item["note"] = "翻译后无变化"
                    else:
                        item["status"] = "ok"
                        item["new_name"] = new_name
                        item["new_path"] = unique_path(os.path.join(folder, new_name), taken)
                        item["note"] = "待重命名"
            except Exception as e:  # 单个文件失败不中断整体
                item["status"] = "error"
                item["note"] = str(e)
        plan.append(item)
        if progress_cb:
            progress_cb(i + 1, total, old_name, item)
    return plan


def selected_plan_items(plan):
    return [item for item in plan if item["status"] == "ok"]


# ---------------------------------------------------------------- 执行与撤销
def apply_plan(items, log_cb=None):
    """两阶段重命名：先改成临时名，再改成最终名，避免互相冲突。返回错误列表。"""
    errors = []
    applied = []  # [(old_full, new_full)]
    temp_pairs = []
    try:
        for i, item in enumerate(items):
            temp = os.path.join(item["folder"], f".__tr_{time.time_ns()}_{i}__")
            os.rename(item["path"], temp)
            temp_pairs.append((temp, item))
        for temp, item in temp_pairs:
            try:
                os.rename(temp, item["new_path"])
                applied.append((item["path"], item["new_path"]))
                if log_cb:
                    log_cb(f"重命名: {item['old_name']} -> {os.path.basename(item['new_path'])}")
            except OSError as e:
                errors.append(f"{item['old_name']}: {e}")
                try:
                    os.rename(temp, item["path"])
                except OSError:
                    pass
    except OSError as e:
        errors.append(str(e))
        for temp, item in temp_pairs:
            try:
                os.rename(temp, item["path"])
            except OSError:
                pass
    return errors, applied


def undo_plan(applied, log_cb=None):
    """把 (old, new) 列表倒着改回去。"""
    errors = []
    reverted = 0
    for old_full, new_full in reversed(applied):
        if not os.path.exists(new_full):
            errors.append(f"找不到文件，无法撤销: {os.path.basename(new_full)}")
            continue
        folder = os.path.dirname(new_full)
        temp = os.path.join(folder, f".__undo_{time.time_ns()}__")
        try:
            os.rename(new_full, temp)
            os.rename(temp, old_full)
            reverted += 1
            if log_cb:
                log_cb(f"撤销: {os.path.basename(new_full)} -> {os.path.basename(old_full)}")
        except OSError as e:
            errors.append(f"{os.path.basename(new_full)}: {e}")
            try:
                os.rename(temp, new_full)
            except OSError:
                pass
    return errors, reverted


def append_rename_log(folder, entries):
    """把重命名记录写入文件夹下的 重命名记录.log。"""
    try:
        log_path = os.path.join(folder, "重命名记录.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}]\n")
            for old, new in entries:
                f.write(f"{old}\t->\t{new}\n")
        return log_path
    except OSError:
        return None
