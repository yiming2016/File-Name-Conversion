# -*- coding: utf-8 -*-
"""离线自测：验证核心逻辑（不访问网络）。
用法: python main.py --selftest
"""

import os
import shutil
import tempfile


FAILURES = []


def check(name, cond, detail=""):
    if cond:
        print(f"PASS  {name}")
    else:
        print(f"FAIL  {name}  {detail}")
        FAILURES.append(name)


def run_selftest():
    from . import config as cfg_mod
    from .core import (
        apply_plan,
        build_plan,
        detect_script_language,
        discover_entries,
        discover_files,
        looks_like_target_language,
        parse_extensions,
        sanitize_filename,
        selected_plan_items,
        split_targets,
        undo_plan,
    )
    from .engines import CustomHttpEngine, engine_choices, get_engine
    from .engines import YandexEngine, BaiduEngine, VolcengineEngine, TencentEngine, detect_proxy_scheme, _format_balance
    from .glossary import (
        Glossary,
        ensure_glossary_structure,
        load_selected_file_entries,
        load_entries,
        parse_file,
        scan_glossary_files,
        save_entries,
    )
    from .ipinfo import risk_info
    from .engines import _proxies

    # ---- 配置与语言
    cfg = cfg_mod.default_config()
    check("默认配置完整", set(cfg.keys()) >= {"engine", "source_lang", "target_lang", "ai", "deepl", "custom_sources"})
    check("默认源语言为多选列表", cfg.get("source_langs") == ["auto"] and cfg.get("source_lang") == "auto")
    check("语言表包含中英", cfg_mod.LANG_NAMES.get("zh-CN") == "中文" and cfg_mod.LANG_NAMES.get("en") == "英文")
    check("AI 语言名映射", cfg_mod.AI_LANG_NAMES.get("en") == "English")
    check(
        "引擎下拉列表",
        any(k == "google" for k, _ in engine_choices(cfg))
        and any(k.startswith("ai:") for k, _ in engine_choices(cfg)),
    )
    check("默认含自定义源示例", any(s.get("name") == "MyMemory(免费示例)" for s in cfg["custom_sources"]))
    check("get_engine 默认谷歌", get_engine(cfg, "google").display == "谷歌翻译(免费)")
    check(
        "新增国内翻译源",
        {k for k, _ in engine_choices(cfg)} >= {"baidu", "volcengine", "niutrans", "tencent", "bing", "papago"},
    )
    cfg_mod.ensure_ai_providers(cfg)
    check("AI 预设分块", set(cfg["ai"]["providers"].keys()) == set(cfg_mod.AI_PRESETS.keys()))
    check("AI 分块引擎", get_engine(cfg, "ai:DeepSeek").provider == "DeepSeek")
    check("Bing 引擎", get_engine(cfg, "bing").display == "Bing 翻译(免费)")
    check("Papago 引擎", get_engine(cfg, "papago").display == "Papago(官方API)")
    check("百度语言代码映射", BaiduEngine(cfg)._code("ja") == "jp" and BaiduEngine(cfg)._code("zh-CN") == "zh")
    ve_headers = VolcengineEngine(cfg)._sign("ak", "sk", "cn-north-1", "translate", b"{}")
    check(
        "火山签名生成",
        ve_headers["Authorization"].startswith("HMAC-SHA256 Credential=ak/") and "Signature=" in ve_headers["Authorization"],
    )
    tc_headers = TencentEngine(cfg)._sign("sid", "sk", b"{}", 1700000000)
    check(
        "腾讯签名生成",
        tc_headers["Authorization"].startswith("TC3-HMAC-SHA256 Credential=sid/") and "Signature=" in tc_headers["Authorization"],
    )
    check("Yandex 语言代码映射", YandexEngine(cfg)._code("zh-CN") == "zh" and YandexEngine(cfg)._code("en") == "en")
    check("余额字段解析-DeepSeek", _format_balance({"balance_infos": [{"total_balance": "12.3", "currency": "CNY"}]}) == "12.3 CNY")
    check("余额字段解析-通用", _format_balance({"balance": 5.5, "currency": "USD"}) == "5.5 USD")
    check("余额字段解析-未知", _format_balance({"foo": 1}) is None)

    # ---- 词库
    g = Glossary(
        [
            {"source": "NavEditor", "target": "导航编辑器", "mode": "substring", "enabled": True},
            {"source": "S01E01", "target": "第一季第一集", "mode": "substring", "enabled": True},
            {"source": "Deep Purple", "target": "Deep Purple", "mode": "word", "enabled": True},
        ],
        case_sensitive=False,
    )
    masked, rmap = g.protect("NavEditor S01E01 1080p Deep Purple")
    check("词库命中替换为占位符", "NavEditor" not in masked and "S01E01" not in masked and "Deep Purple" not in masked, masked)
    check("占位符数量正确", len(rmap) == 3, str(rmap))

    def fake_translate(text, _src, _tgt):
        return text.replace("1080p", "高清")

    result = g.apply(fake_translate, "NavEditor S01E01 1080p Deep Purple", "auto", "zh-CN")
    check("词库+云翻译结果正确", result == "导航编辑器 第一季第一集 高清 Deep Purple", result)

    g2 = Glossary([{"source": "cat", "target": "猫", "mode": "word", "enabled": True}], case_sensitive=True)
    check("整词匹配不误伤子串", g2.apply(lambda t, _s, _tg: t, "concatenate cat", "en", "zh-CN") == "concatenate 猫")
    g3 = Glossary([{"source": "EP(\\d)", "target": "第\\1集", "mode": "regex", "enabled": True}])
    check("正则词条支持组引用", g3.apply(lambda t, _s, _tg: t, "Show EP5", "en", "zh-CN") == "Show 第5集")
    g4 = Glossary([{"source": "NavEditor", "target": "导航编辑器", "mode": "substring", "enabled": True}], case_sensitive=True)
    r4 = g4.apply(lambda t, _s, _tg: t, "naveditor", "en", "zh-CN")
    check("区分大小写生效(小写不命中)", r4 == "naveditor", r4)

    tmp_csv = os.path.join(tempfile.gettempdir(), "tr_glossary_test.csv")
    entries = [
        {"source": "A", "target": "甲", "mode": "substring", "enabled": True},
        {"source": "B", "target": "乙", "mode": "regex", "enabled": False},
    ]
    save_entries(entries, tmp_csv)
    loaded = load_entries(tmp_csv)
    check("词库 CSV 往返", len(loaded) == 2 and loaded[0]["source"] == "A" and loaded[1]["enabled"] is False)
    os.remove(tmp_csv)

    # ---- 词库文件格式解析
    fmt_dir = tempfile.mkdtemp(prefix="tr_glossfmt_")
    try:
        def wf(name, content):
            p = os.path.join(fmt_dir, name)
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
            return p

        p_txt = wf("words.txt", "apple\nbanana\n# comment\ncherry\t樱桃\n")
        ents, err = parse_file(p_txt)
        check("txt 词表解析", len(ents) == 3 and ents[0]["source"] == "apple" and ents[2]["target"] == "樱桃" and err is None)
        p_csv = wf("pairs.csv", "原文,译文\nNavEditor,导航编辑器\nCodex,Codex\n")
        ents, err = parse_file(p_csv)
        check("csv 双列解析", len(ents) == 2 and ents[0]["target"] == "导航编辑器")
        p_tsv = wf("pairs.tsv", "one\t一\ntwo\t二\n")
        ents, err = parse_file(p_tsv)
        check("tsv 解析", len(ents) == 2 and ents[1]["source"] == "two")
        p_json_list = wf("list.json", '["alpha", "beta"]\n')
        ents, err = parse_file(p_json_list)
        check("json 数组解析", len(ents) == 2 and ents[0]["target"] == "alpha")
        p_json_map = wf("map.json", '{"zh": ["甲", "乙"], "hello": "你好"}\n')
        ents, err = parse_file(p_json_map)
        check("json 对象解析", len(ents) == 3 and any(e["source"] == "hello" and e["target"] == "你好" for e in ents))
        p_tmx = wf(
            "mem.tmx",
            '<?xml version="1.0"?><tmx><body><tu><tuv xml:lang="en"><seg>Hello</seg></tuv>'
            '<tuv xml:lang="zh"><seg>你好</seg></tuv></tu></body></tmx>',
        )
        ents, err = parse_file(p_tmx)
        check("tmx 解析", len(ents) == 1 and ents[0]["target"] == "你好")
        p_tbx = wf(
            "term.tbx",
            '<?xml version="1.0"?><martif><text><body><termEntry><langSet xml:lang="en"><ntig><term>Cat</term></ntig>'
            '</langSet><langSet xml:lang="zh"><ntig><term>猫</term></ntig></langSet></termEntry></body></text></martif>',
        )
        ents, err = parse_file(p_tbx)
        check("tbx 解析", len(ents) == 1 and ents[0]["source"] == "Cat" and ents[0]["target"] == "猫")
    finally:
        shutil.rmtree(fmt_dir, ignore_errors=True)

    # ---- 词库目录扫描与按勾选加载
    try:
        ensure_glossary_structure()
        files = scan_glossary_files()
        check("词库目录按格式分文件夹", any(f["folder"] == "json" for f in files) and any(f["folder"] == "txt" for f in files))
        check(
            "默认包含两个 GitHub 词库",
            any("naughty-words-js" in f["rel"] for f in files)
            and any("List-of-Dirty" in f["rel"] for f in files),
        )
        check("扫描不含 LICENSE 文件", not any(f["name"].upper().startswith("LICENSE") for f in files))
        test_cfg = {
            "glossary": {
                "files": [f["rel"] for f in files if f["rel"].endswith("/en.json") or f["rel"].endswith("/en.txt")]
            }
        }
        ents, errs = load_selected_file_entries(test_cfg)
        check("按勾选加载词库文件", len(ents) > 500, f"共 {len(ents)} 条")
    except Exception as e:
        check("词库目录扫描", False, str(e))

    # ---- 代理补全
    p1 = _proxies("http://127.0.0.1:10808")
    check("代理协议透传", p1 == {"http": "http://127.0.0.1:10808", "https": "http://127.0.0.1:10808"}, str(p1))
    check("空代理返回 None", _proxies("") is None)
    check("代理手动选HTTP", detect_proxy_scheme("127.0.0.1:10808", "http") == "http://127.0.0.1:10808")
    check("代理手动选SOCKS5", detect_proxy_scheme("127.0.0.1:10808", "socks5h") == "socks5h://127.0.0.1:10808")
    check("风控分级-极度纯净", risk_info(10)[0] == "极度纯净IP" and risk_info(15)[0] == "极度纯净IP")
    check("风控分级-纯净", risk_info(20)[0] == "纯净IP")
    check("风控分级-中性", risk_info(30)[0] == "中性IP" and risk_info(40)[0] == "中性IP")
    check("风控分级-轻微风险", risk_info(45)[0] == "轻微风险IP")
    check("风控分级-稍高风险", risk_info(60)[0] == "稍高风险IP" and risk_info(70)[0] == "稍高风险IP")
    check("风控分级-极度风险", risk_info(80)[0] == "极度风险IP")
    try:
        import socks  # noqa: F401

        check("PySocks 已打包(SOCKS代理支持)", True)
    except ImportError:
        check("PySocks 已打包(SOCKS代理支持)", False)
    try:
        import PIL  # noqa: F401

        check("Pillow 已打包(图片预览)", True)
    except ImportError:
        check("Pillow 已打包(图片预览)", False)

    # ---- 大词库匹配性能
    import time

    big = [
        {"source": f"word{i}", "target": f"word{i}", "mode": "substring", "enabled": True}
        for i in range(20000)
    ]
    gbig = Glossary(big)
    t0 = time.time()
    rbig = gbig.apply(lambda t, _s, _tg: t, "word19999 hello", "en", "zh-CN")
    dt = time.time() - t0
    check("大词库匹配快速", dt < 1.0 and "word19999" in rbig, f"{dt:.3f}s")

    # ---- 自定义 HTTP 源工具方法
    eng = CustomHttpEngine(cfg, cfg["custom_sources"][0])
    url = eng._fill_url("https://x.com/?q={text}&p={source}|{target}", {"text": "a b", "source": "en", "target": "zh-CN"})
    check("URL 占位符编码", url == "https://x.com/?q=a%20b&p=en%7Czh-CN", url)
    body = eng._fill_json({"q": "翻译{text}吧", "n": 1}, {"text": "你好"})
    check("JSON 占位符替换", body == {"q": "翻译你好吧", "n": 1}, str(body))
    data = {"responseData": {"translatedText": "结果"}, "data": {"translations": [{"text": "结果2"}]}}
    check("响应路径点式", eng._extract_path(data, "responseData.translatedText") == "结果")
    check("响应路径索引式", eng._extract_path(data, "data.translations[0].text") == "结果2")

    # ---- 文件名处理
    check("非法字符清理", sanitize_filename('a<b>:"c|d?*e') == "a b c d e", sanitize_filename('a<b>:"c|d?*e'))
    check("首尾点空格清理", sanitize_filename("  hello.  ") == "hello")
    check("已中文跳过", looks_like_target_language("电影第一集", "zh-CN") is True)
    check("脚本语言检测", detect_script_language("电影") == "zh-CN" and detect_script_language("アニメ") == "ja")
    check("脚本语言检测英文为未知", detect_script_language("Movie 01") is None)
    check("英文不跳过中文目标", looks_like_target_language("Movie 01", "zh-CN") is False)
    check("英文目标跳过", looks_like_target_language("Movie 01", "en") is True)
    check("中文不跳过英文目标", looks_like_target_language("电影第一集", "en") is False)
    check("日文检测", looks_like_target_language("アニメ01", "ja") is True)
    check("韩文检测", looks_like_target_language("영화01", "ko") is True)
    check("扩展名解析", parse_extensions("mp4,.mkv, .AVI") == {".mp4", ".mkv", ".avi"})
    check("扩展名星号", parse_extensions("*") is None)
    check("路径拆分", split_targets("a; b；\"c\"") == ["a", "b", "c"], str(split_targets("a; b；\"c\"")))

    # ---- 文件夹/文件混合选择
    selftest_tmp = tempfile.mkdtemp(prefix="tr_selftest2_")
    try:
        with open(os.path.join(selftest_tmp, "single.mp4"), "w", encoding="utf-8") as f:
            f.write("x")
        with open(os.path.join(selftest_tmp, "keep.txt"), "w", encoding="utf-8") as f:
            f.write("x")
        single = os.path.join(selftest_tmp, "single.mp4")
        paths5, invalid = discover_entries(
            single + ";" + os.path.join(selftest_tmp, "keep.txt") + ";not_exist_path",
            False,
            "mp4",
        )
        names5 = [os.path.basename(p) for p in paths5]
        check("混合选择只取匹配文件", names5 == ["single.mp4"] and invalid == ["not_exist_path"], str((names5, invalid)))
        paths6, invalid6 = discover_entries(selftest_tmp, False, "*")
        check("文件夹选择仍正常", sorted(os.path.basename(p) for p in paths6) == ["keep.txt", "single.mp4"] and not invalid6)
    finally:
        shutil.rmtree(selftest_tmp, ignore_errors=True)

    # ---- 真实文件重命名流程
    temp_dir = tempfile.mkdtemp(prefix="tr_selftest_")
    try:
        for name in ["hello.mp4", "world.mp4", "keep.txt", "dup.mp4"]:
            with open(os.path.join(temp_dir, name), "w", encoding="utf-8") as f:
                f.write("x")
        paths = discover_files(temp_dir, False, ".mp4")
        check("发现 mp4 文件", len(paths) == 3, str(paths))

        def fake_translate(text):
            return "翻译_" + text.upper()

        plan = build_plan(paths, fake_translate, "zh-CN", skip_target=False)
        ok_items = selected_plan_items(plan)
        check("规划出 3 个待重命名", len(ok_items) == 3, str(len(ok_items)))
        # dup.mp4 和某个文件可能撞名? 原文件互不相同，翻译后也互不相同
        new_names = {os.path.basename(i["new_path"]) for i in ok_items}
        check("新文件名互不冲突", len(new_names) == 3, str(new_names))

        errors, applied = apply_plan(ok_items)
        check("重命名无错误", not errors, str(errors))
        check("重命名数量正确", len(applied) == 3, str(len(applied)))
        check("新文件存在", os.path.exists(os.path.join(temp_dir, "翻译_HELLO.mp4")))
        check("旧文件不存在", not os.path.exists(os.path.join(temp_dir, "hello.mp4")))
        check("未匹配文件未动", os.path.exists(os.path.join(temp_dir, "keep.txt")))

        errors2, reverted = undo_plan(applied)
        check("撤销无错误", not errors2, str(errors2))
        check("撤销恢复旧名", os.path.exists(os.path.join(temp_dir, "hello.mp4")) and os.path.exists(os.path.join(temp_dir, "world.mp4")))
        check("撤销后新名消失", not os.path.exists(os.path.join(temp_dir, "翻译_HELLO.mp4")))

        # 冲突处理：两个不同文件翻译成同名
        paths2 = discover_files(temp_dir, False, ".mp4")
        plan2 = build_plan(paths2, lambda t: "同名结果", "zh-CN", skip_target=False)
        names2 = sorted(os.path.basename(i["new_path"]) for i in selected_plan_items(plan2))
        check("撞名自动加后缀", names2[0] != names2[1], str(names2))

        # 跳过已为目标语言
        with open(os.path.join(temp_dir, "中文名.mp4"), "w", encoding="utf-8") as f:
            f.write("x")
        paths3 = discover_files(temp_dir, False, "mp4")
        plan3 = build_plan(paths3, fake_translate, "zh-CN", skip_target=True)
        skips = [i for i in plan3 if i["status"] == "skip"]
        check("跳过中文文件", any(i["old_name"] == "中文名.mp4" for i in skips), str([i["old_name"] for i in skips]))

        # 多选源语言过滤：不在所选语言范围内的文件跳过
        paths4 = discover_files(temp_dir, False, ".mp4")
        plan4 = build_plan(
            paths4,
            fake_translate,
            "zh-CN",
            skip_target=False,
            post_filter=lambda item, translated: item["stem"].lower() != "world",
        )
        skipped4 = [i for i in plan4 if i["status"] == "skip"]
        check("多选源语言过滤", any(i["old_name"] == "world.mp4" and i["note"].startswith("源语言") for i in skipped4))

        # 跳过语言：post_filter 返回字符串 -> 跳过并显示自定义原因
        plan5 = build_plan(
            paths4,
            fake_translate,
            "zh-CN",
            skip_target=False,
            post_filter=lambda item, translated: "源语言为跳过语言，跳过" if item["stem"].lower() == "world" else True,
        )
        skipped5 = [i for i in plan5 if i["status"] == "skip"]
        check("跳过语言过滤", any(i["old_name"] == "world.mp4" and "跳过语言" in i["note"] for i in skipped5))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    # ---- 总结
    print()
    if FAILURES:
        print(f"自测完成: {len(FAILURES)} 项失败 -> {FAILURES}")
        return 1
    print("自测完成: 全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_selftest())
