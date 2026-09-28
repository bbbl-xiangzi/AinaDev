"""出站请求安全：阻止 SSRF（私网/回环/链路本地/云元数据地址）。

应用于：知识库 URL 导入、资讯源抓取、原文/图片下载等所有服务端发起的 HTTP 请求。
生产环境默认开启（settings.block_private_urls=True）；客户若需抓取内网 RSS/资讯源，
可在 .env 中设置 BLOCK_PRIVATE_URLS=false 放开（需自行评估风险）。
"""
import ipaddress
import logging
import socket
from urllib.parse import urlparse

from app.config import settings

logger = logging.getLogger(__name__)

# 云厂商元数据等敏感地址（大小写不敏感）
BLOCKED_HOSTS = {
    "169.254.169.254", "169.254.170.2", "169.254.170.23",
    "metadata.google.internal", "metadata.google", "metadata",
}


def _host_to_ip(host: str) -> str | None:
    """解析主机名到 IP（首个 A 记录）；失败返回 None。"""
    try:
        infos = socket.getaddrinfo(host, None)
        for info in infos:
            ip = info[4][0]
            # 跳过 IPv6 映射形式，取标准 IPv4
            if ":" not in ip:
                return ip
        return infos[0][4][0]
    except Exception:
        return None


def is_safe_url(url: str) -> tuple[bool, str]:
    """返回 (是否允许访问, 拒绝原因)。settings.block_private_urls=False 时全部放行。"""
    if not settings.block_private_urls:
        return True, ""
    if not url or not url.startswith(("http://", "https://")):
        return False, "仅允许 http/https 地址"
    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"URL 解析失败: {e}"
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        return False, "URL 缺少主机名"
    if host in BLOCKED_HOSTS:
        return False, f"禁止访问保留地址 {host}"
    ip = _host_to_ip(host)
    if ip:
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return False, f"无法解析主机地址 {host}"
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_multicast
            or addr.is_reserved
            or addr.is_unspecified
        ):
            return False, f"禁止访问内网/保留地址 {host} ({ip})"
    else:
        # 无法解析 DNS：放行但记录（避免功能因临时 DNS 故障全挂；真实请求时由下游超时兜底）
        logger.warning("SSRF 检查：无法解析主机 %s，放行（请确认 DNS）", host)
    return True, ""


def assert_safe_url(url: str, what: str = "目标地址") -> None:
    """校验并抛 ValueError（用于创建/配置时快速失败）。"""
    ok, reason = is_safe_url(url)
    if not ok:
        raise ValueError(f"{what}不合法：{reason}")
