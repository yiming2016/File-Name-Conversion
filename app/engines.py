# -*- coding: utf-8 -*-
"""翻译引擎：谷歌(免费)、DeepL、OpenAI 兼容 AI 模型、自定义 HTTP 翻译源。"""

import hashlib
import hmac
import json
import socket
import time
import urllib.parse

import requests

from .config import AI_LANG_NAMES, DEEPL_SUPPORTED


class EngineError(Exception):
    """翻译失败时抛出，message 会直接展示给用户。"""


_PROXY_SCHEME_CACHE = {}


def _http_probe(host, port, timeout=3):
    """探测是否为 HTTP 代理。"""
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.sendall(b"CONNECT translate.googleapis.com:443 HTTP/1.1\r\nHost: translate.googleapis.com:443\r\n\r\n")
        data = s.recv(64)
        s.close()
        return data.startswith(b"HTTP/")
    except OSError:
        return False


def _socks_probe(host, port, timeout=3):
    """探测是否为 SOCKS5 代理。"""
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.sendall(b"\x05\x01\x00")
        if s.recv(2) != b"\x05\x00":
            s.close()
            return False
        s.close()
        return True
    except OSError:
        return False


def detect_proxy_scheme(proxy, proxy_type="auto"):
    """未写协议时自动识别 HTTP / SOCKS5，返回带协议前缀的代理地址。"""
    proxy = proxy.strip()
    if proxy.startswith(("http://", "https://", "socks5://", "socks5h://")):
        return proxy
    if proxy_type == "http":
        return f"http://{proxy}"
    if proxy_type in ("socks", "socks5", "socks5h"):
        return f"socks5h://{proxy}"
    if proxy in _PROXY_SCHEME_CACHE:
        return f"{_PROXY_SCHEME_CACHE[proxy]}://{proxy}"
    scheme = "http"
    try:
        host, port = proxy.rsplit(":", 1)
        port = int(port)
        # 优先 SOCKS5：双协议代理走 SOCKS 更稳定
        if _socks_probe(host, port):
            scheme = "socks5h"
        elif _http_probe(host, port):
            scheme = "http"
    except (ValueError, OSError):
        pass
    _PROXY_SCHEME_CACHE[proxy] = scheme
    return f"{scheme}://{proxy}"


def _proxies(proxy, proxy_type="auto"):
    if not proxy:
        return None
    proxy = detect_proxy_scheme(proxy, proxy_type)
    return {"http": proxy, "https": proxy}


def _proxies_for_cfg(cfg):
    return _proxies(cfg.get("proxy"), cfg.get("proxy_type", "auto"))


def test_proxy_connectivity(proxy, proxy_type="auto"):
    """测试代理连通性：识别协议 + 真实请求。"""
    if not proxy:
        return "未填写代理地址。"
    detected = detect_proxy_scheme(proxy, proxy_type)
    try:
        resp = requests.get(
            "https://api.mymemory.translated.net/get?q=test&langpair=en|zh-CN",
            proxies=_proxies(proxy, proxy_type),
            timeout=15,
        )
        return f"代理可用（识别为 {detected}，测试请求 HTTP {resp.status_code}）"
    except requests.RequestException as e:
        return f"代理识别为 {detected}，但测试请求失败：{e}"


def _timeout(cfg):
    try:
        return max(5, int(cfg.get("timeout", 20)))
    except (TypeError, ValueError):
        return 20


class BaseEngine:
    key = "base"
    display = "基础引擎"

    def __init__(self, cfg):
        self.cfg = cfg
        self.session = requests.Session()

    def abort(self):
        """中断正在进行的请求（“停止”按钮调用）。"""
        try:
            self.session.close()
        except Exception:
            pass

    def translate(self, text, source, target):
        raise NotImplementedError


class GoogleEngine(BaseEngine):
    key = "google"
    display = "谷歌翻译(免费)"

    def __init__(self, cfg):
        super().__init__(cfg)
        self.last_detected = None

    def translate(self, text, source, target):
        self.last_detected = None
        if source != "auto" and source == target:
            return text
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": source if source != "auto" else "auto",
            "tl": target,
            "dt": "t",
            "q": text,
        }
        try:
            resp = self.session.get(
                url,
                params=params,
                timeout=_timeout(self.cfg),
                proxies=_proxies_for_cfg(self.cfg),
            )
            resp.raise_for_status()
            data = resp.json()
            parts = []
            for seg in data[0]:
                if seg and seg[0]:
                    parts.append(seg[0])
            result = "".join(parts).strip()
            if not result:
                raise EngineError("谷歌翻译返回了空结果")
            if len(data) > 2 and isinstance(data[2], str) and 0 < len(data[2]) <= 8:
                self.last_detected = data[2]
            return result
        except EngineError:
            raise
        except requests.RequestException as e:
            raise EngineError(f"谷歌翻译请求失败：{e}\n国内网络可能无法直连，请在设置中配置代理或改用其他翻译源。") from e
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise EngineError(f"谷歌翻译返回格式异常：{e}") from e


class DeepLEngine(BaseEngine):
    key = "deepl"
    display = "DeepL(官方API)"

    def _code(self, lang):
        code = "zh" if lang == "zh-CN" else lang.lower()
        code = "nb" if code == "no" else code
        if code not in DEEPL_SUPPORTED:
            raise EngineError(f"DeepL 不支持该语言：{lang}")
        return code.upper()

    def translate(self, text, source, target):
        deepl_cfg = self.cfg.get("deepl", {})
        api_key = (deepl_cfg.get("api_key") or "").strip()
        if not api_key:
            raise EngineError("未配置 DeepL API Key：请点击“管理翻译源”，在 DeepL 标签页填入。")
        if source != "auto" and source == target:
            return text
        endpoint = (
            "https://api-free.deepl.com/v2/translate"
            if deepl_cfg.get("api_type", "free") == "free"
            else "https://api.deepl.com/v2/translate"
        )
        payload = {"text": [text], "target_lang": self._code(target)}
        if source != "auto":
            payload["source_lang"] = self._code(source)
        headers = {
            "Authorization": f"DeepL-Auth-Key {api_key}",
            "Content-Type": "application/json",
        }
        try:
            resp = self.session.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=_timeout(self.cfg),
                proxies=_proxies_for_cfg(self.cfg),
            )
            data = resp.json()
            if resp.status_code != 200:
                msg = data.get("message") or data.get("error", {}).get("message") or resp.text
                raise EngineError(f"DeepL 返回错误({resp.status_code})：{msg}")
            return data["translations"][0]["text"]
        except EngineError:
            raise
        except requests.RequestException as e:
            raise EngineError(f"DeepL 请求失败：{e}") from e
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise EngineError(f"DeepL 返回格式异常：{e}") from e


class AIEngine(BaseEngine):
    key = "ai"
    display = "AI 模型(OpenAI兼容)"

    def __init__(self, cfg, provider=None):
        super().__init__(cfg)
        self.provider = provider

    def _provider_cfg(self):
        """取当前预设渠道的配置（旧版顶层字段作为兜底）。"""
        ai_cfg = self.cfg.get("ai", {})
        prov = {}
        if self.provider:
            prov = (ai_cfg.get("providers") or {}).get(self.provider) or {}
        return {
            "base_url": (prov.get("base_url") or ai_cfg.get("base_url") or "").strip().rstrip("/"),
            "api_key": (prov.get("api_key") or ai_cfg.get("api_key") or "").strip(),
            "model": (prov.get("model") or ai_cfg.get("model") or "").strip(),
            "temperature": prov.get("temperature", ai_cfg.get("temperature", 0.3)),
            "system_prompt": prov.get("system_prompt")
            or ai_cfg.get("system_prompt")
            or "你是一名专业翻译，只输出翻译结果。",
        }

    def translate(self, text, source, target):
        ai_cfg = self._provider_cfg()
        base_url = ai_cfg["base_url"]
        model = ai_cfg["model"]
        if not base_url or not model:
            raise EngineError("未配置 AI 接口地址或模型名：请点击“管理翻译源”，在 AI 标签页填写。")
        if source != "auto" and source == target:
            return text
        api_key = ai_cfg["api_key"]
        url = f"{base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        system_prompt = ai_cfg["system_prompt"]
        target_name = AI_LANG_NAMES.get(target, target)
        if source == "auto":
            user_msg = f"请把下面的文本翻译成{target_name}。只输出翻译结果，不要解释、引号或多余内容：\n\n{text}"
        else:
            source_name = AI_LANG_NAMES.get(source, source)
            user_msg = f"请把下面的{source_name}文本翻译成{target_name}。只输出翻译结果，不要解释、引号或多余内容：\n\n{text}"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            "temperature": float(ai_cfg.get("temperature", 0.3)),
            "stream": False,
        }
        try:
            resp = self.session.post(
                url,
                headers=headers,
                json=payload,
                timeout=_timeout(self.cfg),
                proxies=_proxies_for_cfg(self.cfg),
            )
            data = resp.json()
            if resp.status_code != 200:
                err = data.get("error", {})
                if isinstance(err, dict):
                    msg = err.get("message", resp.text)
                else:
                    msg = str(err)
                raise EngineError(f"AI 接口返回错误({resp.status_code})：{msg}")
            content = data["choices"][0]["message"]["content"]
            content = (content or "").strip().strip('"\'“”‘’ ')
            content = content.replace("翻译结果：", "").replace("译文：", "").strip()
            if not content:
                raise EngineError("AI 返回了空结果")
            return content
        except EngineError:
            raise
        except requests.RequestException as e:
            raise EngineError(f"AI 接口请求失败：{e}") from e
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise EngineError(f"AI 接口返回格式异常：{e}") from e


class YandexEngine(BaseEngine):
    key = "yandex"
    display = "Yandex(官方API)"

    def _code(self, lang):
        return "zh" if lang == "zh-CN" else lang.lower()

    def translate(self, text, source, target):
        yandex_cfg = self.cfg.get("yandex", {})
        api_key = (yandex_cfg.get("api_key") or "").strip()
        if not api_key:
            raise EngineError("未配置 Yandex API Key：请点击“管理翻译源”，在 Yandex 标签页填入。")
        if source != "auto" and source == target:
            return text
        url = "https://translate.yandex.net/api/v1.5/tr.json/translate"
        params = {"key": api_key, "text": text, "lang": self._code(target)}
        if source != "auto":
            params["lang"] = f"{self._code(source)}-{self._code(target)}"
        try:
            resp = self.session.post(
                url,
                data=params,
                timeout=_timeout(self.cfg),
                proxies=_proxies_for_cfg(self.cfg),
            )
            data = resp.json()
            if data.get("code") != 200:
                raise EngineError(f"Yandex 返回错误({data.get('code')})：{data.get('message') or data}")
            return data["text"][0]
        except EngineError:
            raise
        except requests.RequestException as e:
            raise EngineError(f"Yandex 请求失败：{e}") from e
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise EngineError(f"Yandex 返回格式异常：{e}") from e


def _iso_code(lang):
    """通用 ISO 语言代码（中文 -> zh）。"""
    return "zh" if lang == "zh-CN" else lang.lower()


class BaiduEngine(BaseEngine):
    key = "baidu"
    display = "百度翻译(官方API)"

    BAIDU_CODES = {
        "zh-CN": "zh", "en": "en", "ja": "jp", "ko": "kor", "fr": "fra", "es": "spa",
        "ru": "ru", "de": "de", "it": "it", "pt": "pt", "th": "th", "vi": "vie",
        "ar": "ara", "nl": "nl", "pl": "pl", "bg": "bul", "et": "est", "da": "dan",
        "fi": "fin", "cs": "cs", "ro": "rom", "sl": "slo", "sv": "swe", "hu": "hu",
        "el": "el",
    }

    def _code(self, lang):
        return self.BAIDU_CODES.get(lang, "en" if lang == "en" else lang.lower())

    def translate(self, text, source, target):
        cfg = self.cfg.get("baidu", {})
        appid = (cfg.get("appid") or "").strip()
        secret = (cfg.get("secret") or "").strip()
        if not appid or not secret:
            raise EngineError("未配置百度翻译 APP ID / 密钥：请点击“管理翻译源”，在百度翻译页签填写。")
        if source != "auto" and source == target:
            return text
        salt = str(int(time.time() * 1000))
        sign = hashlib.md5((appid + text + salt + secret).encode("utf-8")).hexdigest()
        params = {
            "q": text,
            "from": "auto" if source == "auto" else self._code(source),
            "to": self._code(target),
            "appid": appid,
            "salt": salt,
            "sign": sign,
        }
        try:
            resp = self.session.post(
                "https://fanyi-api.baidu.com/api/trans/vip/translate",
                data=params,
                timeout=_timeout(self.cfg),
                proxies=_proxies_for_cfg(self.cfg),
            )
            data = resp.json()
            if data.get("error_code") and data["error_code"] != "52000":
                raise EngineError(f"百度翻译错误({data.get('error_code')})：{data.get('error_msg')}")
            return data["trans_result"][0]["dst"]
        except EngineError:
            raise
        except requests.RequestException as e:
            raise EngineError(f"百度翻译请求失败：{e}") from e
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise EngineError(f"百度翻译返回格式异常：{e}") from e


class NiuTransEngine(BaseEngine):
    key = "niutrans"
    display = "小牛翻译(官方API)"

    def translate(self, text, source, target):
        cfg = self.cfg.get("niutrans", {})
        api_key = (cfg.get("api_key") or "").strip()
        if not api_key:
            raise EngineError("未配置小牛翻译 API Key：请点击“管理翻译源”，在小牛翻译页签填写。")
        if source != "auto" and source == target:
            return text
        payload = {
            "from": "auto" if source == "auto" else _iso_code(source),
            "to": _iso_code(target),
            "src_text": text,
        }
        headers = {"apikey": api_key, "Content-Type": "application/json"}
        try:
            resp = self.session.post(
                "https://api.niutrans.com/NiuTransServer/translation",
                json=payload,
                headers=headers,
                timeout=_timeout(self.cfg),
                proxies=_proxies_for_cfg(self.cfg),
            )
            data = resp.json()
            if "tgt_text" in data:
                return data["tgt_text"]
            raise EngineError(f"小牛翻译错误：{data}")
        except EngineError:
            raise
        except requests.RequestException as e:
            raise EngineError(f"小牛翻译请求失败：{e}") from e
        except (ValueError, TypeError) as e:
            raise EngineError(f"小牛翻译返回格式异常：{e}") from e


class VolcengineEngine(BaseEngine):
    """火山翻译（字节跳动）：使用火山引擎 HMAC-SHA256 签名。"""

    key = "volcengine"
    display = "火山翻译(官方API)"

    @staticmethod
    def _hmac(key, msg):
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    def _sign(self, access_key, secret_key, region, service, body):
        xdate = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        short_date = xdate[:8]
        host = "translate.volcengineapi.com"
        payload_hash = hashlib.sha256(body).hexdigest()
        canonical_headers = f"content-type:application/json; charset=utf-8\nhost:{host}\nx-content-sha256:{payload_hash}\nx-date:{xdate}\n"
        signed_headers = "content-type;host;x-content-sha256;x-date"
        canonical_request = (
            f"POST\n/\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
        )
        scope = f"{short_date}/{region}/{service}/request"
        string_to_sign = (
            f"HMAC-SHA256\n{xdate}\n{scope}\n"
            + hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
        )
        k_date = self._hmac(secret_key.encode("utf-8"), short_date)
        k_region = self._hmac(k_date, region)
        k_service = self._hmac(k_region, service)
        k_signing = self._hmac(k_service, "request")
        signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        authorization = (
            f"HMAC-SHA256 Credential={access_key}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        return {
            "Host": host,
            "X-Date": xdate,
            "X-Content-Sha256": payload_hash,
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": authorization,
        }

    def translate(self, text, source, target):
        cfg = self.cfg.get("volcengine", {})
        access_key = (cfg.get("access_key") or "").strip()
        secret_key = (cfg.get("secret_key") or "").strip()
        if not access_key or not secret_key:
            raise EngineError("未配置火山翻译 Access Key / Secret Key：请点击“管理翻译源”，在火山翻译页签填写。")
        if source != "auto" and source == target:
            return text
        payload = {
            "TargetLanguage": _iso_code(target),
            "TextList": [text],
        }
        if source != "auto":
            payload["SourceLanguage"] = _iso_code(source)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = self._sign(access_key, secret_key, "cn-north-1", "translate", body)
        url = "https://translate.volcengineapi.com/?Action=TranslateText&Version=2020-06-01"
        try:
            resp = self.session.post(
                url,
                data=body,
                headers=headers,
                timeout=_timeout(self.cfg),
                proxies=_proxies_for_cfg(self.cfg),
            )
            data = resp.json()
            if resp.status_code != 200:
                raise EngineError(f"火山翻译错误({resp.status_code})：{data}")
            return data["TranslationList"][0]["Translation"]
        except EngineError:
            raise
        except requests.RequestException as e:
            raise EngineError(f"火山翻译请求失败：{e}") from e
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise EngineError(f"火山翻译返回格式异常：{e}") from e


class TencentEngine(BaseEngine):
    """腾讯云机器翻译：TC3-HMAC-SHA256 签名。"""

    key = "tencent"
    display = "腾讯云(官方API)"

    @staticmethod
    def _hmac(key, msg):
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    def _sign(self, secret_id, secret_key, payload, timestamp):
        host = "tmt.tencentcloudapi.com"
        service = "tmt"
        short_date = time.strftime("%Y-%m-%d", time.gmtime(timestamp))
        content_type = "application/json; charset=utf-8"
        payload_hash = hashlib.sha256(payload).hexdigest()
        canonical_headers = f"content-type:{content_type}\nhost:{host}\n"
        signed_headers = "content-type;host"
        canonical_request = f"POST\n/\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
        scope = f"{short_date}/{service}/tc3_request"
        string_to_sign = (
            f"TC3-HMAC-SHA256\n{timestamp}\n{scope}\n"
            + hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
        )
        k_date = self._hmac(secret_key.encode("utf-8"), short_date)
        k_service = self._hmac(k_date, service)
        k_signing = self._hmac(k_service, "tc3_request")
        signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        authorization = (
            f"TC3-HMAC-SHA256 Credential={secret_id}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        return {
            "Host": host,
            "Content-Type": content_type,
            "X-TC-Action": "TextTranslate",
            "X-TC-Version": "2018-03-21",
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Region": "ap-guangzhou",
            "Authorization": authorization,
        }

    def translate(self, text, source, target):
        cfg = self.cfg.get("tencent", {})
        secret_id = (cfg.get("secret_id") or "").strip()
        secret_key = (cfg.get("secret_key") or "").strip()
        if not secret_id or not secret_key:
            raise EngineError("未配置腾讯云 SecretId / SecretKey：请点击“管理翻译源”，在腾讯云页签填写。")
        if source != "auto" and source == target:
            return text
        payload = {
            "SourceText": text,
            "Source": "auto" if source == "auto" else _iso_code(source),
            "Target": _iso_code(target),
            "ProjectId": 0,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        timestamp = int(time.time())
        headers = self._sign(secret_id, secret_key, body, timestamp)
        try:
            resp = self.session.post(
                "https://tmt.tencentcloudapi.com/",
                data=body,
                headers=headers,
                timeout=_timeout(self.cfg),
                proxies=_proxies_for_cfg(self.cfg),
            )
            data = resp.json()
            response = data.get("Response", data)
            if response.get("Error"):
                raise EngineError(f"腾讯云错误：{response['Error'].get('Message')}")
            return response["TargetText"]
        except EngineError:
            raise
        except requests.RequestException as e:
            raise EngineError(f"腾讯云请求失败：{e}") from e
        except (ValueError, KeyError, TypeError) as e:
            raise EngineError(f"腾讯云返回格式异常：{e}") from e


class BingEngine(BaseEngine):
    """Bing（微软 Edge）免费翻译接口，无需 API Key。"""

    key = "bing"
    display = "Bing 翻译(免费)"

    @staticmethod
    def _ms_code(lang):
        return "zh-Hans" if lang == "zh-CN" else ("zh-Hant" if lang == "zh-TW" else lang.lower())

    def _token(self):
        resp = self.session.get(
            "https://edge.microsoft.com/translate/auth",
            timeout=_timeout(self.cfg),
            proxies=_proxies_for_cfg(self.cfg),
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
        resp.raise_for_status()
        token = resp.text.strip()
        if not token:
            raise EngineError("Bing 翻译鉴权失败，请稍后重试或更换翻译源")
        return token

    def translate(self, text, source, target):
        if source != "auto" and source == target:
            return text
        try:
            token = self._token()
            params = {"api-version": "3.0", "to": self._ms_code(target)}
            if source != "auto":
                params["from"] = self._ms_code(source)
            resp = self.session.post(
                "https://api-edge.cognitive.microsofttranslator.com/translate",
                params=params,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                },
                json=[{"text": text}],
                timeout=_timeout(self.cfg),
                proxies=_proxies_for_cfg(self.cfg),
            )
            data = resp.json()
            if resp.status_code != 200:
                raise EngineError(f"Bing 翻译返回错误({resp.status_code})：{data}")
            return data[0]["translations"][0]["text"]
        except EngineError:
            raise
        except requests.RequestException as e:
            raise EngineError(f"Bing 翻译请求失败：{e}\n国内网络可能无法直连，请在设置中配置代理。") from e
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise EngineError(f"Bing 翻译返回格式异常：{e}") from e


class PapagoEngine(BaseEngine):
    """Naver Papago 官方 API（需要 Client ID / Client Secret）。"""

    key = "papago"
    display = "Papago(官方API)"

    @staticmethod
    def _code(lang):
        return "zh-CN" if lang == "zh-CN" else lang.lower()

    def translate(self, text, source, target):
        papago_cfg = self.cfg.get("papago", {})
        client_id = (papago_cfg.get("client_id") or "").strip()
        client_secret = (papago_cfg.get("client_secret") or "").strip()
        if not client_id or not client_secret:
            raise EngineError("未配置 Papago Client ID / Client Secret：请点击“管理翻译源”，在 Papago 页签填写。")
        if source != "auto" and source == target:
            return text
        payload = {
            "source": "auto" if source == "auto" else self._code(source),
            "target": self._code(target),
            "text": text,
        }
        headers = {
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        try:
            resp = self.session.post(
                "https://naveropenapi.apigw.ntruss.com/nmt/v1/translate",
                data=payload,
                headers=headers,
                timeout=_timeout(self.cfg),
                proxies=_proxies_for_cfg(self.cfg),
            )
            data = resp.json()
            if data.get("errorCode") or data.get("errorMessage"):
                raise EngineError(f"Papago 返回错误：{data.get('errorMessage') or data}")
            return data["message"]["result"]["translatedText"]
        except EngineError:
            raise
        except requests.RequestException as e:
            raise EngineError(f"Papago 请求失败：{e}") from e
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise EngineError(f"Papago 返回格式异常：{e}") from e


class CustomHttpEngine(BaseEngine):
    """自定义 HTTP 翻译源：可配置 URL 模板、请求头、请求体与响应取值路径。"""

    def __init__(self, cfg, spec):
        super().__init__(cfg)
        self.spec = spec or {}
        self.key = spec.get("name", "custom")
        self.display = f"自定义: {self.key}"

    # ---------------- 工具 ----------------
    @staticmethod
    def _fill_url(template, vals):
        out = template
        for key, value in vals.items():
            out = out.replace("{" + key + "}", urllib.parse.quote(str(value), safe=""))
        # 模板里残留的非法字符(如 |)也一并编码，同时保留 URL 结构字符
        return urllib.parse.quote(out, safe="/:?&=#%+@!$'()*,-._~[]")

    @staticmethod
    def _fill_json(obj, vals):
        if isinstance(obj, str):
            out = obj
            for key, value in vals.items():
                out = out.replace("{" + key + "}", str(value))
            return out
        if isinstance(obj, dict):
            return {k: CustomHttpEngine._fill_json(v, vals) for k, v in obj.items()}
        if isinstance(obj, list):
            return [CustomHttpEngine._fill_json(v, vals) for v in obj]
        return obj

    @staticmethod
    def _extract_path(data, path):
        if not path:
            return None
        cur = data
        for part in path.split("."):
            if not part:
                continue
            if "[" in part:
                key, rest = part.split("[", 1)
                if key:
                    cur = cur[key]
                for idx_text in rest.rstrip("]").split("]["):
                    if idx_text:
                        cur = cur[int(idx_text)]
            else:
                cur = cur[part]
        return cur

    # ---------------- 翻译 ----------------
    def translate(self, text, source, target):
        spec = self.spec
        url_tpl = (spec.get("url") or "").strip()
        method = (spec.get("method") or "GET").upper()
        response_path = (spec.get("response_path") or "").strip()
        if not url_tpl:
            raise EngineError(f"自定义翻译源“{self.key}”未配置请求 URL。")
        try:
            headers = json.loads(spec.get("headers") or "{}")
            if not isinstance(headers, dict):
                raise ValueError("headers 必须是 JSON 对象")
        except (ValueError, TypeError) as e:
            raise EngineError(f"自定义翻译源“{self.key}”的请求头不是合法 JSON：{e}") from e

        vals = {
            "text": text,
            "source": source if source != "auto" else "auto",
            "target": target,
        }
        url = self._fill_url(url_tpl, vals)
        try:
            if method in ("GET", "HEAD"):
                resp = self.session.request(
                    method,
                    url,
                    headers=headers,
                    timeout=_timeout(self.cfg),
                    proxies=_proxies_for_cfg(self.cfg),
                )
            else:
                body = spec.get("body") or ""
                if body.strip():
                    try:
                        json_body = self._fill_json(json.loads(body), vals)
                    except (ValueError, TypeError) as e:
                        raise EngineError(f"自定义翻译源“{self.key}”的请求体不是合法 JSON：{e}") from e
                else:
                    json_body = None
                resp = self.session.request(
                    method,
                    url,
                    headers=headers,
                    json=json_body,
                    timeout=_timeout(self.cfg),
                    proxies=_proxies_for_cfg(self.cfg),
                )
            resp.raise_for_status()
            data = resp.json()
            result = self._extract_path(data, response_path)
            if result is None:
                raise EngineError(f"自定义翻译源“{self.key}”按路径“{response_path}”未取到结果。")
            return str(result).strip()
        except EngineError:
            raise
        except requests.RequestException as e:
            raise EngineError(f"自定义翻译源“{self.key}”请求失败：{e}") from e
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise EngineError(f"自定义翻译源“{self.key}”返回格式异常：{e}") from e


BUILTIN_ENGINES = [
    GoogleEngine,
    DeepLEngine,
    YandexEngine,
    BaiduEngine,
    VolcengineEngine,
    NiuTransEngine,
    TencentEngine,
    BingEngine,
    PapagoEngine,
]


def _ai_fields(cfg, provider=None):
    """返回 (base_url, api_key) —— 兼容旧版顶层字段与新版分块结构。"""
    from . import config as cfg_mod

    cfg_mod.ensure_ai_providers(cfg)
    ai = cfg.get("ai", {})
    prov = (ai.get("providers") or {}).get(provider) or {} if provider else {}
    base = (prov.get("base_url") or ai.get("base_url") or "").strip().rstrip("/")
    key = (prov.get("api_key") or ai.get("api_key") or "").strip()
    return base, key


def list_ai_models(cfg, provider=None):
    """查询 OpenAI 兼容接口的可用模型列表。"""
    base, key = _ai_fields(cfg, provider)
    if not base:
        raise EngineError("请先填写 AI 接口地址。")
    headers = {}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        resp = requests.get(
            f"{base}/models",
            headers=headers,
            timeout=_timeout(cfg),
            proxies=_proxies_for_cfg(cfg),
        )
        data = resp.json()
        if resp.status_code != 200:
            err = data.get("error", data)
            raise EngineError(f"获取模型列表失败({resp.status_code})：{err}")
        models = [m.get("id") for m in data.get("data", []) if isinstance(m, dict) and m.get("id")]
        if not models:
            raise EngineError("接口返回的模型列表为空。")
        return models
    except EngineError:
        raise
    except requests.RequestException as e:
        raise EngineError(f"获取模型列表失败：{e}") from e
    except (ValueError, TypeError, KeyError) as e:
        raise EngineError(f"获取模型列表返回格式异常：{e}") from e


def _format_balance(data):
    if isinstance(data, dict):
        for key in ("total_balance", "available_balance", "balance", "amount", "granted_balance"):
            if key in data and data[key] not in (None, ""):
                currency = data.get("currency") or ""
                return f"{data[key]} {currency}".strip()
        infos = data.get("balance_infos")
        if isinstance(infos, list) and infos and isinstance(infos[0], dict):
            info = infos[0]
            value = info.get("total_balance") or info.get("balance") or info.get("granted_balance")
            if value is not None:
                return f"{value} {info.get('currency') or ''}".strip()
    return None


def query_ai_balance(cfg, provider=None):
    """根据接口地址尝试查询 API Key 余额（DeepSeek/通义千问等）。"""
    base, key = _ai_fields(cfg, provider)
    if not key:
        raise EngineError("请先填写 API Key 再查询余额。")
    if "dashscope" in base or "aliyuncs" in base:
        urls = ["https://dashscope.aliyuncs.com/api/v1/users/balance"]
    else:
        urls = [f"{base}/user/balance"]
    last_err = ""
    for url in urls:
        try:
            resp = requests.get(
                url,
                headers={"Authorization": f"Bearer {key}"},
                timeout=_timeout(cfg),
                proxies=_proxies_for_cfg(cfg),
            )
            data = resp.json()
            if resp.status_code == 200:
                text = _format_balance(data)
                if text:
                    return text
                return "查询成功，但未识别到余额字段"
            last_err = f"HTTP {resp.status_code}: {data}"
        except EngineError:
            raise
        except requests.RequestException as e:
            last_err = str(e)
        except (ValueError, TypeError) as e:
            last_err = str(e)
    raise EngineError(f"该接口暂不支持余额查询（{last_err}）")


def engine_choices(cfg):
    """返回 [(key, 显示名), ...]，供界面下拉框使用。"""
    from . import config as cfg_mod

    choices = [(cls.key, cls.display) for cls in BUILTIN_ENGINES]
    cfg_mod.ensure_ai_providers(cfg)
    for name in cfg_mod.AI_PRESETS:
        choices.append((f"ai:{name}", f"AI: {name}"))
    for spec in cfg.get("custom_sources", []):
        name = (spec.get("name") or "").strip()
        if name:
            choices.append((name, f"自定义: {name}"))
    return choices


def get_engine(cfg, key=None):
    key = key or cfg.get("engine", "google")
    for cls in BUILTIN_ENGINES:
        if cls.key == key:
            return cls(cfg)
    if key == "ai":
        from . import config as cfg_mod

        cfg_mod.ensure_ai_providers(cfg)
        provider = cfg.get("ai", {}).get("current") or "DeepSeek"
        return AIEngine(cfg, provider)
    if isinstance(key, str) and key.startswith("ai:"):
        return AIEngine(cfg, key[3:])
    for spec in cfg.get("custom_sources", []):
        if spec.get("name") == key:
            return CustomHttpEngine(cfg, spec)
    raise EngineError(f"未知翻译源：{key}")
