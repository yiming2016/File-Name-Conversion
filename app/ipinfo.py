# -*- coding: utf-8 -*-
"""IP 信息与风控程度查询（免费接口 ip-api.com）。"""

import requests

from .engines import _proxies_for_cfg

DATACENTER_KEYWORDS = [
    "alibaba", "aliyun", "tencent", "amazon", "aws", "google", "microsoft",
    "azure", "digitalocean", "linode", "vultr", "hetzner", "ovh", "cloudflare",
    "huawei", "baidu", "oracle", "ibm", "cogent", "akamai", "telegram", "linode",
    "腾讯", "阿里", "华为", "百度", "甲骨文",
]


def flag_emoji(country_code):
    """国家代码 -> 国旗 emoji。"""
    if not country_code or len(country_code) != 2:
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in country_code.upper())


def risk_info(score):
    """按风控分数返回 (等级, 颜色)。"""
    if score <= 15:
        return "极度纯净IP", "#1a7f37"   # 深绿
    if score <= 25:
        return "纯净IP", "#34a853"       # 绿
    if score <= 40:
        return "中性IP", "#7cb342"       # 黄绿
    if score <= 50:
        return "轻微风险IP", "#fbc02d"   # 黄
    if score <= 70:
        return "稍高风险IP", "#f57c00"   # 橙
    return "极度风险IP", "#d93025"       # 红


def get_ip_info(cfg):
    """查询公网 IP 及位置/类型/风控（经代理查询时显示代理出口 IP）。"""
    proxies = _proxies_for_cfg(cfg)
    url = (
        "http://ip-api.com/json/?lang=zh-CN"
        "&fields=status,message,query,country,countryCode,regionName,city,isp,org,as,proxy,hosting"
    )
    resp = requests.get(url, proxies=proxies, timeout=15)
    data = resp.json()
    if data.get("status") != "success":
        raise RuntimeError(f"IP 查询失败：{data.get('message', data)}")

    org = " ".join(
        str(data.get(k) or "") for k in ("org", "isp", "as")
    ).lower()
    is_datacenter = bool(data.get("hosting")) or bool(data.get("proxy")) or any(
        k in org for k in DATACENTER_KEYWORDS
    )
    if data.get("proxy"):
        score = 75
    elif data.get("hosting") or is_datacenter:
        score = 60
    else:
        score = 12
    label, color = risk_info(score)
    location = " · ".join(
        x for x in (data.get("country"), data.get("regionName"), data.get("city")) if x
    )
    return {
        "ip": data.get("query", ""),
        "flag": flag_emoji(data.get("countryCode", "")),
        "location": location,
        "ip_type": "机房IP" if is_datacenter else "家庭带宽",
        "score": score,
        "risk_label": label,
        "risk_color": color,
    }
