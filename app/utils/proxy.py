import logging
import os
from urllib.parse import urlparse
from PySide6.QtNetwork import QNetworkProxy, QNetworkProxyFactory

log = logging.getLogger('app.utils.proxy')

_ENV_KEYS = ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY',
             'all_proxy', 'ALL_PROXY']


def _clear_proxy_env():
    """Remove all proxy-related environment variables."""
    for key in _ENV_KEYS:
        os.environ.pop(key, None)


def _set_proxy_env(url: str):
    """Set proxy environment variables that Chromium/WebEngine will inherit."""
    for key in _ENV_KEYS:
        os.environ[key] = url


def set_proxy_ip(proxy_str: str):
    """
    Sets the global/application-wide proxy for PySide6/Qt network requests
    AND updates os.environ so the Chromium subprocess inside QtWebEngine also
    uses the proxy for new connections.

    Accepts full proxy URLs (e.g. socks5://127.0.0.1:1080, http://127.0.0.1:8080)
    or host/IP formats (e.g. 127.0.0.1, 127.0.0.1:8080).
    """
    qproxy = QNetworkProxy()
    proxy_str = proxy_str.strip()
    if not proxy_str:
        qproxy.setType(QNetworkProxy.NoProxy)
        log.info("Resetting application proxy to Direct Connection")
        _clear_proxy_env()
        QNetworkProxyFactory.setUseSystemConfiguration(False)
        QNetworkProxy.setApplicationProxy(qproxy)
        return

    # Normalize input: if there is no scheme, add http:// by default
    url_to_parse = proxy_str
    if not (proxy_str.startswith("http://") or proxy_str.startswith("https://")
            or proxy_str.startswith("socks5://") or proxy_str.startswith("socks4://")):
        url_to_parse = "http://" + proxy_str

    try:
        parsed = urlparse(url_to_parse)
        scheme = parsed.scheme.lower()

        if 'socks' in scheme:
            qproxy.setType(QNetworkProxy.Socks5Proxy)
        else:
            qproxy.setType(QNetworkProxy.HttpProxy)

        if parsed.hostname:
            qproxy.setHostName(parsed.hostname)

        # Resolve port
        port = parsed.port
        if not port and ':' in parsed.netloc:
            try:
                port = int(parsed.netloc.split(':')[-1])
            except ValueError:
                pass

        if port:
            qproxy.setPort(port)
        else:
            # Default ports
            if qproxy.type() == QNetworkProxy.Socks5Proxy:
                qproxy.setPort(1080)
            else:
                qproxy.setPort(8080)

        if parsed.username:
            qproxy.setUser(parsed.username)
        if parsed.password:
            qproxy.setPassword(parsed.password)

        log.info("Set application proxy: type=%s, host=%s, port=%d, authenticated=%s",
                 qproxy.type(), qproxy.hostName(), qproxy.port(), bool(qproxy.user()))

        # Also update environment variables so Chromium picks up the proxy
        _set_proxy_env(url_to_parse)
        log.info("Set proxy environment for %s://%s:%d", scheme, qproxy.hostName(), qproxy.port())

    except Exception as e:
        log.error("Failed to parse proxy settings: %s", e)
        qproxy.setType(QNetworkProxy.NoProxy)
        _clear_proxy_env()

    QNetworkProxyFactory.setUseSystemConfiguration(False)
    QNetworkProxy.setApplicationProxy(qproxy)
