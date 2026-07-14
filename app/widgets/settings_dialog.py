from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSpinBox, QTabWidget, QVBoxLayout,
    QWidget, QFileDialog, QMessageBox
)

from app.signals.signal_bus import signal_bus

_SETTINGS_FILE = 'settings.json'

_BROWSER_PROCESSES = {
    'chrome': 'chrome.exe',
    'edge': 'msedge.exe',
    'brave': 'brave.exe',
    'chromium': 'chromium.exe',
    'vivaldi': 'vivaldi.exe',
    'opera': 'opera.exe',
}


def _find_browser_executable(browser: str) -> str:
    process_name = _BROWSER_PROCESSES.get(browser, f'{browser}.exe')
    found = shutil.which(process_name)
    if found:
        return found

    if sys.platform == 'win32':
        try:
            import winreg
            key_path = rf'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{process_name}'
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(hive, key_path) as key:
                        value, _ = winreg.QueryValueEx(key, None)
                        if value and os.path.isfile(value):
                            return value
                except OSError:
                    continue
        except ImportError:
            pass

    roots = [
        os.environ.get('PROGRAMFILES', ''),
        os.environ.get('PROGRAMFILES(X86)', ''),
        os.environ.get('LOCALAPPDATA', ''),
    ]
    relative_candidates = {
        'chrome': [r'Google\Chrome\Application\chrome.exe'],
        'edge': [r'Microsoft\Edge\Application\msedge.exe'],
        'brave': [r'BraveSoftware\Brave-Browser\Application\brave.exe'],
        'vivaldi': [r'Vivaldi\Application\vivaldi.exe'],
        'opera': [r'Programs\Opera\launcher.exe'],
        'chromium': [r'Chromium\Application\chrome.exe'],
    }
    for root in roots:
        for relative in relative_candidates.get(browser, []):
            candidate = os.path.join(root, relative)
            if root and os.path.isfile(candidate):
                return candidate
    return ''


def _settings_path() -> str:
    from PySide6.QtCore import QStandardPaths
    import shutil

    base_app_dir = QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)
    if not base_app_dir:
        base_app_dir = os.path.join(os.path.expanduser('~'), '.yt-dlp-gui')
    app_dir = os.path.join(base_app_dir, 'yt-dlp-gui')
    os.makedirs(app_dir, exist_ok=True)
    new_path = os.path.join(app_dir, _SETTINGS_FILE)

    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
        base = os.path.join(base, '..', '..')
    old_path = os.path.join(base, _SETTINGS_FILE)

    local_appdata_old = os.path.join(
        os.environ.get('LOCALAPPDATA', ''), 'yt-dlp-gui', 'yt-dlp GUI', _SETTINGS_FILE
    )

    if not os.path.isfile(new_path):
        if os.path.isfile(local_appdata_old):
            try:
                shutil.copy2(local_appdata_old, new_path)
            except Exception:
                pass
        elif os.path.isfile(old_path):
            try:
                shutil.copy2(old_path, new_path)
            except Exception:
                pass

    return new_path


DEFAULT_SETTINGS = {
    'output_dir': '',
    'max_parallel': 3,
    'dark_theme': True,
    'proxy': '',
    'cookies_file': '',
    'cookies_from_browser': '',
    'impersonate': True,
    'embed_thumbnail': False,
    'embed_metadata': False,
    'write_subs': False,
    'convert_mp3': False,
    'custom_args': '',
    'browser_ad_block': True,
    'browser_custom_extension': False,
    'browser_extension_path': '',
}


def load_settings() -> dict:
    path = _settings_path()
    if os.path.isfile(path):
        try:
            with open(path, 'r') as f:
                return {**DEFAULT_SETTINGS, **json.load(f)}
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict):
    path = _settings_path()
    try:
        with open(path, 'w') as f:
            json.dump(settings, f, indent=2)
        signal_bus.settings_changed.emit()
    except Exception as e:
        QMessageBox.warning(None, 'Settings Error', f'Could not save settings: {e}')


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = load_settings()
        self.setWindowTitle('Settings')
        self.setMinimumWidth(500)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        tabs.addTab(self._general_tab(), 'General')
        tabs.addTab(self._download_tab(), 'Download')
        tabs.addTab(self._network_tab(), 'Network')
        tabs.addTab(self._advanced_tab(), 'Advanced')
        tabs.addTab(self._browser_tab(), 'Browser')

        layout.addWidget(tabs)

        btn_row = QHBoxLayout()
        save_btn = QPushButton('Save')
        save_btn.clicked.connect(self._on_save)
        cancel_btn = QPushButton('Cancel')
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _general_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        dir_label = QLabel(
            'All downloads (MP3, MP4, etc.) will be saved to this folder.'
        )
        dir_label.setStyleSheet('font-size: 11px; color: #999; padding-bottom: 6px;')
        form.addRow(dir_label)

        self.output_dir_edit = QLineEdit(self.settings['output_dir'])
        self.output_dir_edit.setPlaceholderText('Default: Downloads folder')
        browse_btn = QPushButton('Browse...')
        browse_btn.clicked.connect(self._browse_output)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self.output_dir_edit, 1)
        dir_row.addWidget(browse_btn)
        form.addRow('Download Location:', dir_row)

        form.addRow('', QLabel(''))

        self.dark_theme_cb = QCheckBox('Enable dark theme')
        self.dark_theme_cb.setChecked(self.settings['dark_theme'])
        form.addRow(self.dark_theme_cb)
        return w

    def _download_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self.parallel_spin = QSpinBox()
        self.parallel_spin.setRange(1, 10)
        self.parallel_spin.setValue(self.settings['max_parallel'])
        form.addRow('Max parallel downloads:', self.parallel_spin)

        self.embed_thumb_cb = QCheckBox('Embed thumbnail')
        self.embed_thumb_cb.setChecked(self.settings['embed_thumbnail'])
        form.addRow(self.embed_thumb_cb)

        self.embed_meta_cb = QCheckBox('Embed metadata')
        self.embed_meta_cb.setChecked(self.settings['embed_metadata'])
        form.addRow(self.embed_meta_cb)

        self.write_subs_cb = QCheckBox('Write subtitles')
        self.write_subs_cb.setChecked(self.settings['write_subs'])
        form.addRow(self.write_subs_cb)

        self.convert_mp3_cb = QCheckBox('Convert audio to MP3')
        self.convert_mp3_cb.setChecked(self.settings['convert_mp3'])
        form.addRow(self.convert_mp3_cb)
        return w

    def _network_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        
        # Proxy presets
        self.proxy_preset_combo = QComboBox()
        self.proxy_presets = {
            'None (No Proxy)': '',
            'Default Proxy (http://127.0.0.1:8888)': 'http://127.0.0.1:8888',
            'Local SOCKS5 (socks5://127.0.0.1:1080)': 'socks5://127.0.0.1:1080',
            'Local HTTP (http://127.0.0.1:8080)': 'http://127.0.0.1:8080',
            'Clash Preset (http://127.0.0.1:7890)': 'http://127.0.0.1:7890',
            'Custom Proxy...': 'custom'
        }
        self.proxy_preset_combo.addItems(list(self.proxy_presets.keys()))
        
        self.proxy_edit = QLineEdit()
        self.proxy_edit.setPlaceholderText('http://user:pass@host:port')

        # Determine initial selection
        current_proxy = self.settings.get('proxy', '').strip()
        matched = False
        for label, val in self.proxy_presets.items():
            if val and val == current_proxy:
                self.proxy_preset_combo.setCurrentText(label)
                self.proxy_edit.setText(current_proxy)
                self.proxy_edit.setEnabled(False)
                matched = True
                break
        
        if not matched:
            if not current_proxy:
                self.proxy_preset_combo.setCurrentText('None (No Proxy)')
                self.proxy_edit.setText('')
                self.proxy_edit.setEnabled(False)
            else:
                self.proxy_preset_combo.setCurrentText('Custom Proxy...')
                self.proxy_edit.setText(current_proxy)
                self.proxy_edit.setEnabled(True)

        self.proxy_preset_combo.currentTextChanged.connect(self._on_proxy_preset_changed)

        form.addRow('Proxy Preset:', self.proxy_preset_combo)
        form.addRow('Proxy URL:', self.proxy_edit)

        self.cookies_edit = QLineEdit(self.settings['cookies_file'])
        cookies_btn = QPushButton('Browse...')
        cookies_btn.clicked.connect(self._browse_cookies)
        cookies_row = QHBoxLayout()
        cookies_row.addWidget(self.cookies_edit, 1)
        cookies_row.addWidget(cookies_btn)
        form.addRow('Cookies file:', cookies_row)

        browsers = ['', 'chrome', 'firefox', 'edge', 'brave', 'opera', 'chromium', 'vivaldi']
        self.cookies_browser_combo = QComboBox()
        self.cookies_browser_combo.addItems(browsers)
        current = self.settings.get('cookies_from_browser', '')
        idx = browsers.index(current) if current in browsers else 0
        self.cookies_browser_combo.setCurrentIndex(idx)
        self.cookies_browser_combo.setToolTip('Extract cookies from browser (requires browser to have been used with yt-dlp)')

        export_row = QHBoxLayout()
        export_row.addWidget(self.cookies_browser_combo, 1)
        export_btn = QPushButton('Export Cookies')
        export_btn.clicked.connect(self._export_cookies)
        export_row.addWidget(export_btn)
        form.addRow('Cookies from browser:', export_row)

        self.impersonate_cb = QCheckBox('Impersonate browser (curl_cffi), helps avoid bot detection')
        self.impersonate_cb.setChecked(self.settings.get('impersonate', True))
        form.addRow(self.impersonate_cb)
        return w

    def _on_proxy_preset_changed(self, text: str):
        val = self.proxy_presets.get(text, '')
        if val == 'custom':
            self.proxy_edit.setEnabled(True)
            self.proxy_edit.setFocus()
        else:
            self.proxy_edit.setEnabled(False)
            self.proxy_edit.setText(val)

    def _advanced_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self.custom_args_edit = QLineEdit(self.settings['custom_args'])
        self.custom_args_edit.setPlaceholderText('--no-mtime --limit-rate 5M')
        form.addRow('Extra yt-dlp args:', self.custom_args_edit)
        return w

    def _browser_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        
        self.ad_block_cb = QCheckBox('Enable built-in ad blocker')
        self.ad_block_cb.setChecked(self.settings.get('browser_ad_block', True))
        form.addRow(self.ad_block_cb)
        
        self.custom_ext_cb = QCheckBox('Use custom Chrome extension')
        self.custom_ext_cb.setChecked(self.settings.get('browser_custom_extension', False))
        form.addRow(self.custom_ext_cb)
        
        self.ext_path_edit = QLineEdit(self.settings.get('browser_extension_path', ''))
        self.ext_path_edit.setPlaceholderText('Path to unpacked extension directory')
        ext_browse_btn = QPushButton('Browse...')
        ext_browse_btn.clicked.connect(self._browse_extension_path)
        
        ext_row = QHBoxLayout()
        ext_row.addWidget(self.ext_path_edit, 1)
        ext_row.addWidget(ext_browse_btn)
        form.addRow('Extension Folder:', ext_row)
        
        self.ext_path_edit.setEnabled(self.custom_ext_cb.isChecked())
        ext_browse_btn.setEnabled(self.custom_ext_cb.isChecked())
        self.custom_ext_cb.toggled.connect(self.ext_path_edit.setEnabled)
        self.custom_ext_cb.toggled.connect(ext_browse_btn.setEnabled)
        
        return w

    def _browse_extension_path(self):
        path = QFileDialog.getExistingDirectory(self, 'Select Unpacked Extension Folder')
        if path:
            self.ext_path_edit.setText(path)

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, 'Select Output Directory')
        if path:
            self.output_dir_edit.setText(path)

    def _browse_cookies(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Select Cookies File', '', '*.txt;;*.*')
        if path:
            self.cookies_edit.setText(path)

    def _export_cookies(self):
        browser = self.cookies_browser_combo.currentText().strip()
        if not browser:
            QMessageBox.warning(self, 'Export Cookies', 'Select a browser from the dropdown first.')
            return

        chromium_browsers = set(_BROWSER_PROCESSES)
        browser_running = False
        process_name = _BROWSER_PROCESSES.get(browser, f'{browser}.exe')
        browser_executable = _find_browser_executable(browser)
        if browser in chromium_browsers:
            try:
                result = subprocess.run(
                    ['tasklist', '/FI', f'IMAGENAME eq {process_name}'],
                    capture_output=True, text=True, timeout=10
                )
                browser_running = process_name.lower() in result.stdout.lower()
            except Exception:
                pass

        if browser_running:
            reply = QMessageBox.question(
                self, 'Browser Running',
                f'{browser.title()} is running in the background.\n\n'
                'Click Yes to temporarily close it (tabs will be restored on next launch), '
                'export cookies, then reopen it.\n'
                'Click No to cancel.',
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
            subprocess.run(['taskkill', '/F', '/IM', process_name],
                           capture_output=True, timeout=10)

        app_dir = os.path.dirname(_settings_path())
        cookies_path = os.path.join(app_dir, f'cookies_{browser}.txt')

        try:
            from yt_dlp.cookies import extract_cookies_from_browser
            cookie_jar = extract_cookies_from_browser(browser)
            cookie_jar.save(cookies_path, ignore_discard=True, ignore_expires=True)

            if os.path.isfile(cookies_path) and os.path.getsize(cookies_path) > 0:
                self.cookies_edit.setText(cookies_path)
                self.cookies_browser_combo.setCurrentIndex(0)
                QMessageBox.information(
                    self, 'Export Cookies',
                    f'Exported {os.path.getsize(cookies_path)} bytes of cookies from {browser}.\n'
                    f'Cookies file set. Cookie-from-browser disabled (now using file). Click Save.'
                )
            else:
                QMessageBox.warning(
                    self, 'Export Failed',
                    f'Could not export cookies from {browser}. No cookies were found.'
                )
        except Exception as e:
            QMessageBox.warning(self, 'Export Failed', f'Error: {e}')
        finally:
            if browser_running:
                try:
                    if browser_executable:
                        subprocess.Popen([browser_executable])
                    elif browser == 'edge' and hasattr(os, 'startfile'):
                        os.startfile('microsoft-edge:')
                    else:
                        raise FileNotFoundError(f'Could not locate {browser}')
                except Exception as e:
                    QMessageBox.warning(
                        self, 'Browser Restart',
                        f'Cookies were exported, but {browser.title()} could not be restarted: {e}'
                    )

    def _on_save(self):
        self.settings['output_dir'] = self.output_dir_edit.text().strip()
        self.settings['dark_theme'] = self.dark_theme_cb.isChecked()
        self.settings['max_parallel'] = self.parallel_spin.value()
        self.settings['embed_thumbnail'] = self.embed_thumb_cb.isChecked()
        self.settings['embed_metadata'] = self.embed_meta_cb.isChecked()
        self.settings['write_subs'] = self.write_subs_cb.isChecked()
        self.settings['convert_mp3'] = self.convert_mp3_cb.isChecked()
        preset = self.proxy_preset_combo.currentText()
        preset_val = self.proxy_presets.get(preset, '')
        if preset_val == 'custom':
            self.settings['proxy'] = self.proxy_edit.text().strip()
        else:
            self.settings['proxy'] = preset_val
        self.settings['cookies_file'] = self.cookies_edit.text().strip()
        self.settings['cookies_from_browser'] = self.cookies_browser_combo.currentText().strip()
        self.settings['impersonate'] = self.impersonate_cb.isChecked()
        self.settings['custom_args'] = self.custom_args_edit.text().strip()
        
        self.settings['browser_ad_block'] = self.ad_block_cb.isChecked()
        self.settings['browser_custom_extension'] = self.custom_ext_cb.isChecked()
        self.settings['browser_extension_path'] = self.ext_path_edit.text().strip()
        
        save_settings(self.settings)
        self.accept()
