# -*- coding: utf-8 -*-
"""配置管理与语言定义。"""

import json
import os
import sys


APP_DIR_CACHE = None


def get_app_dir():
    """程序所在目录（exe 运行时为 exe 所在目录，脚本运行时为项目目录）。"""
    global APP_DIR_CACHE
    if APP_DIR_CACHE is None:
        if getattr(sys, "frozen", False):
            APP_DIR_CACHE = os.path.dirname(os.path.abspath(sys.executable))
        else:
            APP_DIR_CACHE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return APP_DIR_CACHE


def config_path():
    """配置文件路径：优先与程序同目录，写不进去时退回用户目录。"""
    path = os.path.join(get_app_dir(), "config.json")
    try:
        with open(path, "a", encoding="utf-8"):
            pass
        return path
    except OSError:
        return os.path.join(os.path.expanduser("~"), ".文件名翻译器_config.json")


# ---------------------------------------------------------------- 语言列表
# (语言代码, 中文显示名)。AI 接口使用中文名拼接提示词，Google/DeepL 使用代码。
LANGUAGES = [
    ("auto", "自动检测"),
    ("zh-CN", "中文"),
    ("en", "英文"),
    ("ja", "日文"),
    ("ko", "韩文"),
    ("ru", "俄文"),
    ("fr", "法文"),
    ("de", "德文"),
    ("es", "西班牙文"),
    ("it", "意大利文"),
    ("pt", "葡萄牙文"),
    ("th", "泰文"),
    ("vi", "越南文"),
    ("ar", "阿拉伯文"),
    ("hi", "印地文"),
    ("tr", "土耳其文"),
    ("id", "印尼文"),
    ("ms", "马来文"),
    ("nl", "荷兰文"),
    ("pl", "波兰文"),
    ("uk", "乌克兰文"),
    ("he", "希伯来文"),
    ("el", "希腊文"),
    ("sv", "瑞典文"),
    ("cs", "捷克文"),
    ("fi", "芬兰文"),
    ("hu", "匈牙利文"),
    ("ro", "罗马尼亚文"),
    ("da", "丹麦文"),
    ("no", "挪威文"),
    ("bg", "保加利亚文"),
    ("sk", "斯洛伐克文"),
    ("sl", "斯洛文尼亚文"),
    ("lt", "立陶宛文"),
    ("lv", "拉脱维亚文"),
    ("et", "爱沙尼亚文"),
    ("hr", "克罗地亚文"),
    ("sr", "塞尔维亚文"),
    ("fa", "波斯文"),
    ("ur", "乌尔都文"),
    ("bn", "孟加拉文"),
    ("tl", "菲律宾文"),
    ("mn", "蒙古文"),
    ("kk", "哈萨克文"),
    ("uz", "乌兹别克文"),
    ("my", "缅甸文"),
    ("km", "高棉文"),
    ("ne", "尼泊尔文"),
    ("sw", "斯瓦希里文"),
]

LANG_NAMES = {code: name for code, name in LANGUAGES}

# AI 提示词使用的英文语言名（对主流模型更稳定）。
AI_LANG_NAMES = {
    "auto": "原语言",
    "zh-CN": "Simplified Chinese",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "ru": "Russian",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "th": "Thai",
    "vi": "Vietnamese",
    "ar": "Arabic",
    "hi": "Hindi",
    "tr": "Turkish",
    "id": "Indonesian",
    "ms": "Malay",
    "nl": "Dutch",
    "pl": "Polish",
    "uk": "Ukrainian",
    "he": "Hebrew",
    "el": "Greek",
    "sv": "Swedish",
    "cs": "Czech",
    "fi": "Finnish",
    "hu": "Hungarian",
    "ro": "Romanian",
    "da": "Danish",
    "no": "Norwegian",
    "bg": "Bulgarian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "et": "Estonian",
    "hr": "Croatian",
    "sr": "Serbian",
    "fa": "Persian",
    "ur": "Urdu",
    "bn": "Bengali",
    "tl": "Filipino",
    "mn": "Mongolian",
    "kk": "Kazakh",
    "uz": "Uzbek",
    "my": "Burmese",
    "km": "Khmer",
    "ne": "Nepali",
    "sw": "Swahili",
}

# DeepL API 支持的语言（代码大写，中文为 ZH）。
DEEPL_SUPPORTED = {
    "bg", "cs", "da", "de", "el", "en", "es", "et", "fi", "fr", "hu", "id",
    "it", "ja", "ko", "lt", "lv", "nb", "nl", "pl", "pt", "ro", "ru", "sk",
    "sl", "sv", "tr", "uk", "zh",
}


# ---------------------------------------------------------------- AI 接口预设
AI_PRESETS = {
    "DeepSeek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "api_key_hint": "在 https://platform.deepseek.com 获取 API Key",
        "api_key_url": "https://platform.deepseek.com",
    },
    "OpenAI": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "api_key_hint": "在 https://platform.openai.com 获取 API Key",
        "api_key_url": "https://platform.openai.com",
    },
    "通义千问(阿里)": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "api_key_hint": "在 https://dashscope.console.aliyun.com 获取 API Key",
        "api_key_url": "https://dashscope.console.aliyun.com",
    },
    "智谱GLM": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
        "api_key_hint": "在 https://open.bigmodel.cn 获取 API Key",
        "api_key_url": "https://open.bigmodel.cn",
    },
    "Moonshot(Kimi)": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "api_key_hint": "在 https://platform.moonshot.cn 获取 API Key",
        "api_key_url": "https://platform.moonshot.cn",
    },
    "本地 Ollama": {
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "qwen2.5:7b",
        "api_key_hint": "本地服务无需 API Key，可留空",
        "api_key_url": "https://ollama.com/download",
    },
    "自定义": {
        "base_url": "https://",
        "model": "",
        "api_key_hint": "填入任意 OpenAI 兼容接口的地址、Key 和模型名",
        "api_key_url": "",
    },
}

DEFAULT_AI_PROMPT = (
    "你是一名专业翻译。请准确、通顺地翻译用户提供的文件名文本，"
    "保留数字、符号和常见缩写，只输出翻译结果，不要任何解释、引号或多余内容。"
)

# 本地 Ollama 适合翻译的推荐模型（用途, 模型名, 大小, 下载地址）
OLLAMA_RECOMMENDED = [
    ("中英", "qwen3:8b", "8G", "https://ollama.com/library/qwen3"),
    ("中日韩", "shisa-v2:8b", "8G", "https://ollama.com/library/shisa-v2"),
    ("多语种通用", "nllb:3b", "4G", "https://ollama.com/library/nllb"),
    ("轻量中英", "qwen2.5:7b", "7G", "https://ollama.com/library/qwen2.5"),
    ("极小多语种", "gemma3:4b", "4G", "https://ollama.com/library/gemma3"),
    ("欧洲小语种", "mistral:7b", "7G", "https://ollama.com/library/mistral"),
]


def ensure_ai_providers(cfg):
    """把 AI 配置升级为“每个预设渠道单独一块”的结构，兼容旧版顶层字段。"""
    ai = cfg.setdefault("ai", {})
    if ai.get("providers") and isinstance(ai["providers"], dict) and ai["providers"]:
        return ai
    prompt = ai.get("system_prompt") or DEFAULT_AI_PROMPT
    try:
        temp = float(ai.get("temperature", 0.3))
    except (TypeError, ValueError):
        temp = 0.3
    providers = {}
    for name, p in AI_PRESETS.items():
        providers[name] = {
            "base_url": p["base_url"],
            "model": p["model"],
            "api_key": "",
            "temperature": temp,
            "system_prompt": prompt,
        }
    old_url = (ai.get("base_url") or "").strip().rstrip("/")
    old_key = (ai.get("api_key") or "").strip()
    old_model = (ai.get("model") or "").strip()
    current = "DeepSeek"
    if old_key or old_url not in ("", "https:", "https:/", "https://"):
        target = "自定义"
        for name, p in AI_PRESETS.items():
            if old_url and p["base_url"].rstrip("/") == old_url:
                target = name
                break
        providers[target]["base_url"] = old_url
        providers[target]["api_key"] = old_key
        providers[target]["model"] = old_model
        providers[target]["temperature"] = temp
        providers[target]["system_prompt"] = prompt
        current = target
    ai["providers"] = providers
    ai["current"] = current
    # 清理旧顶层字段，避免与新结构并存混乱
    for key in ("base_url", "api_key", "model", "temperature", "system_prompt"):
        ai.pop(key, None)
    return ai


# ---------------------------------------------------------------- 默认配置
DEFAULT_CUSTOM_SOURCES = [
    {
        "name": "MyMemory(免费示例)",
        "url": "https://api.mymemory.translated.net/get?q={text}&langpair={source}|{target}",
        "method": "GET",
        "headers": "{}",
        "body": "",
        "response_path": "responseData.translatedText",
    }
]


def default_config():
    return {
        "engine": "google",
        "source_lang": "auto",
        "source_langs": ["auto"],
        "target_lang": "zh-CN",
        "skip_langs": [],
        "skip_target": True,
        "recursive": False,
        "extensions": "*",
        "last_folder": "",
        "proxy": "",
        "proxy_type": "auto",
        "timeout": 20,
        "google": {},
        "deepl": {"api_key": "", "api_type": "free"},
        "yandex": {"api_key": ""},
        "baidu": {"appid": "", "secret": ""},
        "volcengine": {"access_key": "", "secret_key": ""},
        "niutrans": {"api_key": ""},
        "tencent": {"secret_id": "", "secret_key": ""},
        "bing": {},
        "papago": {"client_id": "", "client_secret": ""},
        "ai": {
            "base_url": "https://api.deepseek.com/v1",
            "api_key": "",
            "model": "deepseek-chat",
            "temperature": 0.3,
            "system_prompt": DEFAULT_AI_PROMPT,
        },
        "custom_sources": list(DEFAULT_CUSTOM_SOURCES),
        "glossary": {
            "enabled": True,
            "case_sensitive": False,
            "files": None,  # None = 首次运行时自动全选词库目录下的文件；之后保存用户勾选
        },
    }


def load_config():
    cfg = default_config()
    try:
        with open(config_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            merged = default_config()
            merged.update(data)
            # 逐层合并子字典，避免旧配置缺字段
            for key in ("deepl", "yandex", "baidu", "volcengine", "niutrans", "tencent", "ai", "glossary"):
                if isinstance(data.get(key), dict):
                    merged[key].update(data[key])
            # 旧配置兼容：只有 source_lang 时转成多选列表
            if "source_langs" not in data and data.get("source_lang"):
                merged["source_langs"] = [data["source_lang"]]
            cfg = merged
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg):
    try:
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True, config_path()
    except OSError as e:
        return False, str(e)
