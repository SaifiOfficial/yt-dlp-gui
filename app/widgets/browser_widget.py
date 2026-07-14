import os
import logging
from PySide6.QtCore import QTimer, QUrl, Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QProgressBar, QDialog
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage

log = logging.getLogger(__name__)

def get_app_dir() -> str:
    from PySide6.QtCore import QStandardPaths
    base_app_dir = QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)
    if not base_app_dir:
        base_app_dir = os.path.join(os.path.expanduser('~'), '.yt-dlp-gui')
    app_dir = os.path.join(base_app_dir, 'yt-dlp-gui')
    os.makedirs(app_dir, exist_ok=True)
    return app_dir


def create_built_in_adblocker() -> str:
    app_dir = get_app_dir()
    ext_dir = os.path.join(app_dir, 'extensions', 'adblock')
    os.makedirs(ext_dir, exist_ok=True)
    
    # Write manifest.json
    manifest_path = os.path.join(ext_dir, 'manifest.json')
    manifest_content = {
        "manifest_version": 3,
        "name": "yt-dlp GUI Built-in Ad Blocker",
        "version": "1.1",
        "description": "Blocks ads and trackers for yt-dlp GUI browser.",
        "permissions": [
            "declarativeNetRequest"
        ],
        "host_permissions": ["<all_urls>"],
        "declarative_net_request": {
            "rule_resources": [{
                "id": "ad_rules",
                "enabled": True,
                "path": "rules.json"
            }]
        },
        "content_scripts": [
            {
                "matches": ["*://*.youtube.com/*"],
                "js": ["youtube-adblock.js"],
                "run_at": "document_start"
            }
        ]
    }
    
    import json
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest_content, f, indent=2)
        
    blocked_domains = [
        'doubleclick.net', 'googlesyndication.com', 'moatads.com',
        'adnxs.com', 'pubmatic.com', 'rubiconproject.com', 'criteo.com',
        'adservice.google.com', 'google-analytics.com', 'adserver.com',
        'adroll.com',
    ]
    rules = [
        {
            'id': index,
            'priority': 1,
            'action': {'type': 'block'},
            'condition': {
                'urlFilter': f'||{domain}^',
                'resourceTypes': [
                    'main_frame', 'sub_frame', 'script', 'image',
                    'xmlhttprequest', 'media', 'other',
                ],
            },
        }
        for index, domain in enumerate(blocked_domains, start=1)
    ]
    rules_path = os.path.join(ext_dir, 'rules.json')
    with open(rules_path, 'w', encoding='utf-8') as f:
        json.dump(rules, f, indent=2)

    # Write youtube-adblock.js
    script_path = os.path.join(ext_dir, 'youtube-adblock.js')
    script_content = """
(function() {
  const skipAd = () => {
    // 1. Click skip buttons
    const skipButtons = [
      '.ytp-ad-skip-button',
      '.ytp-ad-skip-button-modern',
      '.ytp-ad-skip-button-slot',
      '.ytp-ad-skip-button-text'
    ];
    for (const selector of skipButtons) {
      const btn = document.querySelector(selector);
      if (btn) {
        btn.click();
        console.log("Skipped YouTube ad via button click.");
        return;
      }
    }

    // 2. Fast-forward the video element if it's an ad
    const video = document.querySelector('video');
    const adShowing = document.querySelector('.ad-showing, .ad-interrupting, .ytp-ad-player-overlay');
    
    if (video && adShowing) {
      if (isFinite(video.duration) && video.duration > 0) {
        video.currentTime = video.duration;
      }
      video.playbackRate = 16.0;
      video.muted = true;
      console.log("Fast-forwarded YouTube video ad.");
    }
  };

  // Run skipAd periodically
  setInterval(skipAd, 300);
})();
"""
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
        
    return ext_dir


class CustomWebEnginePage(QWebEnginePage):
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)

    def createWindow(self, type_):
        # Force all new window requests to load in the current page
        return self


class BrowserWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cookies = {}
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self.save_cookies)

        self._build_ui()
        self._init_browser()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Control Bar
        control_layout = QHBoxLayout()
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(6)

        self.btn_back = QPushButton("◀")
        self.btn_back.setToolTip("Back")
        self.btn_back.setFixedWidth(36)
        self.btn_back.setStyleSheet("QPushButton { padding: 4px; font-weight: bold; }")
        
        self.btn_forward = QPushButton("▶")
        self.btn_forward.setToolTip("Forward")
        self.btn_forward.setFixedWidth(36)
        self.btn_forward.setStyleSheet("QPushButton { padding: 4px; font-weight: bold; }")

        self.btn_reload = QPushButton("⟳")
        self.btn_reload.setToolTip("Reload")
        self.btn_reload.setFixedWidth(36)
        self.btn_reload.setStyleSheet("QPushButton { padding: 4px; font-weight: bold; }")

        self.address_bar = QLineEdit()
        self.address_bar.setPlaceholderText("Enter URL or search...")
        self.address_bar.setStyleSheet("QLineEdit { padding: 6px; border-radius: 4px; }")

        self.cookie_status = QLabel("🍪 Cookies: 0 credentials loaded")
        self.cookie_status.setStyleSheet("QLabel { color: #a78bfa; font-weight: 500; padding: 0 6px; }")

        control_layout.addWidget(self.btn_back)
        control_layout.addWidget(self.btn_forward)
        control_layout.addWidget(self.btn_reload)
        control_layout.addWidget(self.address_bar, 1)
        control_layout.addWidget(self.cookie_status)
        layout.addLayout(control_layout)

        # Loading Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(3)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: transparent;
            }
            QProgressBar::chunk {
                background-color: #8b5cf6;
            }
        """)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Web View
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view, 1)

        # Connect navigation buttons
        self.btn_back.clicked.connect(self.web_view.back)
        self.btn_forward.clicked.connect(self.web_view.forward)
        self.btn_reload.clicked.connect(self.web_view.reload)
        self.address_bar.returnPressed.connect(self._on_address_entered)

        # Connect load updates
        self.web_view.loadProgress.connect(self._on_load_progress)
        self.web_view.loadFinished.connect(self._on_load_finished)
        self.web_view.urlChanged.connect(self._on_url_changed)

    def _init_browser(self):
        log.info("Initializing QtWebEngine built-in browser profile")
        
        # Configure a persistent WebEngine Profile
        self.profile = QWebEngineProfile("yt-dlp-gui-profile", self)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)

        # Bind cookie store signals
        self.cookie_store = self.profile.cookieStore()
        self.cookie_store.cookieAdded.connect(self._on_cookie_added)
        self.cookie_store.cookieRemoved.connect(self._on_cookie_removed)

        # Apply extension management
        self.apply_extensions()

        # Create the custom WebEngine page
        self.page = CustomWebEnginePage(self.profile, self)
        self.web_view.setPage(self.page)

        # Default home page
        self.web_view.setUrl(QUrl("https://www.youtube.com"))

    def apply_extensions(self):
        ext_manager = self.profile.extensionManager()
        for ext in list(ext_manager.extensions()):
            if ext.id() not in ('mhjfbmdgcfjbbpaeojofohoefgiehjai', 'nkeimhogjdpnpccoofpliimaahmaaome'):
                log.info("Unloading existing extension: %s (%s)", ext.name(), ext.id())
                ext_manager.unloadExtension(ext)

        from app.widgets.settings_dialog import load_settings
        settings = load_settings()

        # 1. Built-in ad blocker
        if settings.get('browser_ad_block', True):
            adblock_dir = create_built_in_adblocker()
            ext_manager.loadExtension(adblock_dir)
            log.info("Built-in ad blocker extension loaded.")

        # 2. Custom Chrome extension folder
        if settings.get('browser_custom_extension', False):
            custom_path = settings.get('browser_extension_path', '').strip()
            if custom_path and os.path.isdir(custom_path):
                ext_manager.loadExtension(custom_path)
                log.info("Custom extension loaded from: %s", custom_path)

    def apply_settings(self):
        log.info("Applying browser settings")
        self.apply_extensions()
        # Reload the current page so the updated proxy is used for the next request
        current_url = self.web_view.url()
        if current_url.isValid() and current_url.scheme() in ('http', 'https'):
            self.web_view.reload()
            log.info("Browser page reloaded to apply updated settings/proxy.")

    def _on_address_entered(self):
        text = self.address_bar.text().strip()
        if not text:
            return

        # Already a full URL with scheme
        if text.startswith("http://") or text.startswith("https://") or text.startswith("ftp://"):
            self.web_view.setUrl(QUrl(text))
            return

        # Looks like a domain: has a dot, no spaces, and no special search characters
        # e.g. "youtube.com", "google.com/search?q=test"
        has_dot = '.' in text
        has_spaces = ' ' in text
        if has_dot and not has_spaces:
            self.web_view.setUrl(QUrl("https://" + text))
            return

        # Everything else is treated as a search query
        from urllib.parse import quote_plus
        query = quote_plus(text)
        self.web_view.setUrl(QUrl(f"https://www.google.com/search?q={query}"))

    def _on_load_progress(self, progress):
        self.progress_bar.show()
        self.progress_bar.setValue(progress)

    def _on_load_finished(self, success):
        self.progress_bar.hide()

    def _on_url_changed(self, url):
        self.address_bar.setText(url.toString())

    def _on_cookie_added(self, cookie):
        domain = cookie.domain()
        if "youtube.com" in domain or "google.com" in domain:
            key = (domain, cookie.path(), cookie.name().data())
            self.cookies[key] = cookie
            self._schedule_save()

    def _on_cookie_removed(self, cookie):
        domain = cookie.domain()
        key = (domain, cookie.path(), cookie.name().data())
        if key in self.cookies:
            del self.cookies[key]
            self._schedule_save()

    def _schedule_save(self):
        self._save_timer.stop()
        self._save_timer.start(1000)

    def save_cookies(self):
        try:
            cookies_file = os.path.join(get_app_dir(), 'cookies.txt')
            with open(cookies_file, 'w', encoding='utf-8') as f:
                f.write("# Netscape HTTP Cookie File\n")
                f.write("# This file was generated automatically by the built-in browser.\n")
                f.write("# Do not edit.\n\n")
                for cookie in self.cookies.values():
                    domain = cookie.domain()
                    flag = "TRUE" if domain.startswith('.') else "FALSE"
                    path = cookie.path()
                    secure = "TRUE" if cookie.isSecure() else "FALSE"
                    expiry = int(cookie.expirationDate().toSecsSinceEpoch()) if not cookie.expirationDate().isNull() else 0
                    name = cookie.name().data().decode('utf-8', errors='ignore')
                    value = cookie.value().data().decode('utf-8', errors='ignore')
                    f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n")
            
            # Update indicator text
            self.cookie_status.setText(f"🍪 Cookies: {len(self.cookies)} credentials synced")
            log.debug("Cookies written successfully to: %s", cookies_file)
        except Exception as e:
            log.error("Failed to write Netscape cookies file: %s", e)


class BrowserWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Built-in Browser")
        self.setMinimumSize(1024, 768)
        self.setWindowFlags(self.windowFlags() | Qt.Window)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.browser_widget = BrowserWidget(self)
        layout.addWidget(self.browser_widget)

    def apply_settings(self):
        self.browser_widget.apply_settings()
