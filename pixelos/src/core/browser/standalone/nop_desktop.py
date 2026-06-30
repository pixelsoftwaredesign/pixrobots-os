#!/usr/bin/env python3
"""NOP Browser Desktop — Standalone PyQt6 QWebEngine browser with Web3 resolution."""

import sys
import os
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Qt6 imports ──────────────────────────────────────────
try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLineEdit, QPushButton, QTabWidget, QSplitter, QTreeWidget,
        QTreeWidgetItem, QLabel, QMenu, QMenuBar, QStatusBar,
        QDialog, QDialogButtonBox, QFormLayout, QCheckBox,
        QSpinBox, QMessageBox, QToolBar, QToolButton, QCompleter,
    )
    from PyQt6.QtCore import (
        Qt, QUrl, QTimer, QSize, QPropertyAnimation, pyqtSignal, QThread,
    )
    from PyQt6.QtGui import (
        QAction, QIcon, QKeySequence, QFont, QPalette, QColor,
        QPixmap, QPainter, QPen, QBrush,
    )
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import (
        QWebEnginePage, QWebEngineProfile, QWebEngineUrlRequestInterceptor,
    )
except ImportError:
    print("NOP Desktop requires PyQt6. Install with: pip install PyQt6 PyQt6-WebEngine")
    sys.exit(1)

# ── PixelOS path ─────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from core.browser.nop_resolver import NOPResolver
from core.browser.nop_privacy import NOPPrivacy
from core.browser.nop_wallet_bridge import NOPWalletBridge

# ── Config dirs per platform ─────────────────────────────
if sys.platform == "win32":
    CONFIG_DIR = Path(os.environ.get("APPDATA", ".")) / "NOPBrowser"
elif sys.platform == "darwin":
    CONFIG_DIR = Path.home() / "Library" / "Application Support" / "NOPBrowser"
else:
    CONFIG_DIR = Path.home() / ".config" / "nop-browser"

HISTORY_FILE = CONFIG_DIR / "history.json"
BOOKMARKS_FILE = CONFIG_DIR / "bookmarks.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
CACHE_DIR = CONFIG_DIR / "cache"

DEFAULT_SETTINGS = {
    "homepage": "https://duckduckgo.com",
    "search_engine": "https://duckduckgo.com/?q=",
    "block_ads": True,
    "block_trackers": True,
    "disable_scripts": False,
    "web3_resolver": True,
    "wallet_integration": True,
    "privacy_mode": False,
    "max_tabs": 10,
    "user_agent": "Mozilla/5.0 ({} {}) PixelOS-NOP/1.0",
}


def _ensure_dir(d):
    d.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════
#  URL Request Interceptor — ad/tracker blocking
# ═══════════════════════════════════════════════════════════

class NOPRequestInterceptor(QWebEngineUrlRequestInterceptor):
    def __init__(self, privacy: NOPPrivacy):
        super().__init__()
        self.privacy = privacy
        self.blocked_count = 0

    def interceptRequest(self, info):
        url = info.requestUrl().toString()
        blocked, rule = self.privacy.is_blocked(url)
        if blocked:
            self.blocked_count += 1
            info.block(True)


# ═══════════════════════════════════════════════════════════
#  WebEnginePage with custom navigation & Web3 resolution
# ═══════════════════════════════════════════════════════════

class NOPWebPage(QWebEnginePage):
    def __init__(self, profile, browser_core):
        super().__init__(profile)
        self.browser_core = browser_core


# ═══════════════════════════════════════════════════════════
#  Tab widget — each tab has its own QWebEngineView
# ═══════════════════════════════════════════════════════════

class NOPTabWidget(QTabWidget):
    url_changed = pyqtSignal(str)
    web3_info = pyqtSignal(dict)

    def __init__(self, browser_core, interceptor):
        super().__init__()
        self.browser_core = browser_core
        self.interceptor = interceptor
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self.close_tab)
        self.setDocumentMode(True)
        self.setElideMode(Qt.TextElideMode.ElideRight)

    def add_new_tab(self, url: str = "", background: bool = False):
        profile = QWebEngineProfile()
        profile.setHttpCacheType(
            QWebEngineProfile.HttpCacheType.DiskHttpCache
        )
        _ensure_dir(CACHE_DIR)
        profile.setCachePath(str(CACHE_DIR))
        profile.setRequestInterceptor(self.interceptor)
        profile.setHttpUserAgent(
            DEFAULT_SETTINGS["user_agent"].format(sys.platform, "Qt6")
        )

        page = NOPWebPage(profile, self.browser_core)
        view = QWebEngineView()
        view.setPage(page)

        idx = self.addTab(view, "Nouvel onglet")
        if not background:
            self.setCurrentIndex(idx)

        page.urlChanged.connect(lambda qurl: self._on_url_changed(idx, qurl))
        page.titleChanged.connect(lambda title: self.setTabText(idx, title[:30]))
        page.iconChanged.connect(lambda icon: self.setTabIcon(idx, icon))

        if url:
            resolved = self.browser_core.resolve_url(url)
            final_url = resolved.get("resolved", url)
            view.setUrl(QUrl(final_url))
            self.setTabText(idx, final_url[:30])
            self.web3_info.emit(resolved)

        return idx

    def _on_url_changed(self, idx, qurl):
        if idx == self.currentIndex():
            self.url_changed.emit(qurl.toString())

        resolved = self.browser_core.resolve_url(qurl.toString())
        if resolved.get("web3_type") != "standard":
            self.web3_info.emit(resolved)

        url_str = qurl.toString()
        self.browser_core.add_history(url_str, title=self.tabText(idx))

    def close_tab(self, idx):
        if self.count() > 1:
            w = self.widget(idx)
            self.removeTab(idx)
            w.deleteLater()

    def current_url(self) -> str:
        view = self.currentWidget()
        if view:
            return view.url().toString()
        return ""


# ═══════════════════════════════════════════════════════════
#  Main Window
# ═══════════════════════════════════════════════════════════

class NOPMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NOP Browser — PixelOS")
        self.resize(1280, 800)

        # ── Core modules ──────────────────────────────────
        self.resolver = NOPResolver()
        self.privacy = NOPPrivacy()
        self.wallet = NOPWalletBridge()
        self._settings = dict(DEFAULT_SETTINGS)
        self._load_settings()
        self._history = []
        self._load_history()
        self._bookmarks = []
        self._load_bookmarks()

        # ── Request interceptor ───────────────────────────
        self.interceptor = NOPRequestInterceptor(self.privacy)

        # ── Central widget ────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Toolbar ────────────────────────────────────────
        toolbar = QToolBar("Navigation")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(20, 20))
        self.addToolBar(toolbar)

        # Back / Forward / Refresh
        self.btn_back = QToolButton()
        self.btn_back.setText("◀")
        self.btn_back.clicked.connect(self._go_back)
        toolbar.addWidget(self.btn_back)

        self.btn_fwd = QToolButton()
        self.btn_fwd.setText("▶")
        self.btn_fwd.clicked.connect(self._go_forward)
        toolbar.addWidget(self.btn_fwd)

        self.btn_refresh = QToolButton()
        self.btn_refresh.setText("⟳")
        self.btn_refresh.clicked.connect(self._refresh)
        toolbar.addWidget(self.btn_refresh)

        # URL bar with Web3 badge
        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Entrez une URL ou chercher... (.eth .pixel .ipfs)")
        self.url_bar.returnPressed.connect(self._navigate)
        self.url_bar.setStyleSheet("""
            QLineEdit {
                border: 2px solid #333;
                border-radius: 16px;
                padding: 6px 14px;
                font-size: 13px;
                background: #1e1e2e;
                color: #cdd6f4;
                min-height: 20px;
            }
            QLineEdit:focus { border-color: #e94560; }
        """)
        toolbar.addWidget(self.url_bar)

        # Web3 badge
        self.web3_badge = QLabel("🌐")
        self.web3_badge.setStyleSheet("""
            QLabel {
                background: #0f3460;
                color: #e0e0e0;
                padding: 4px 10px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        toolbar.addWidget(self.web3_badge)

        # Wallet indicator
        self.wallet_indicator = QLabel("💳")
        self.wallet_indicator.setStyleSheet("""
            QLabel {
                background: #1e1e2e;
                color: #4ecca3;
                padding: 4px 10px;
                border-radius: 12px;
                font-size: 11px;
            }
        """)
        toolbar.addWidget(self.wallet_indicator)

        # Menu buttons
        self.btn_bookmarks = QToolButton()
        self.btn_bookmarks.setText("★")
        self.btn_bookmarks.setToolTip("Favoris")
        self.btn_bookmarks.clicked.connect(self._show_bookmarks)
        toolbar.addWidget(self.btn_bookmarks)

        self.btn_history = QToolButton()
        self.btn_history.setText("⌛")
        self.btn_history.setToolTip("Historique")
        self.btn_history.clicked.connect(self._show_history)
        toolbar.addWidget(self.btn_history)

        self.btn_settings = QToolButton()
        self.btn_settings.setText("⚙")
        self.btn_settings.setToolTip("Paramètres")
        self.btn_settings.clicked.connect(self._show_settings)
        toolbar.addWidget(self.btn_settings)

        # ── Tab widget ────────────────────────────────────
        self.tabs = NOPTabWidget(self, self.interceptor)
        self.tabs.url_changed.connect(self.url_bar.setText)
        self.tabs.web3_info.connect(self._on_web3_info)
        main_layout.addWidget(self.tabs)
        self.tabs.add_new_tab(self._settings["homepage"])

        # ── Status bar ────────────────────────────────────
        self.status = QStatusBar()
        self.status_label = QLabel("Prêt")
        self.status.addWidget(self.status_label)
        self.setStatusBar(self.status)

        # ── Dark theme ────────────────────────────────────
        self._apply_theme()

        # ── Wallet check ──────────────────────────────────
        if self.wallet.is_available():
            self.wallet_indicator.setText("💳 Wallet OK")

        # ── Key shortcuts ─────────────────────────────────
        QAction("Nouvel onglet", self, shortcut=QKeySequence("Ctrl+T"),
                triggered=lambda: self.tabs.add_new_tab()).setShortcutVisibleInContextMenu(True)
        QAction("Fermer onglet", self, shortcut=QKeySequence("Ctrl+W"),
                triggered=lambda: self.tabs.close_tab(self.tabs.currentIndex()))
        QAction("Recharger", self, shortcut=QKeySequence("F5"),
                triggered=self._refresh)
        QAction("Focus URL", self, shortcut=QKeySequence("Ctrl+L"),
                triggered=lambda: self.url_bar.selectAll())
        QAction("Plein écran", self, shortcut=QKeySequence("F11"),
                triggered=self.toggleFullScreen)

    # ── Theme ─────────────────────────────────────────────

    def _apply_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#1e1e2e"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#cdd6f4"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#181825"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#313244"))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#45475a"))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#cdd6f4"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#cdd6f4"))
        palette.setColor(QPalette.ColorRole.Button, QColor("#313244"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#cdd6f4"))
        palette.setColor(QPalette.ColorRole.BrightText, QColor("#e94560"))
        palette.setColor(QPalette.ColorRole.Link, QColor("#89b4fa"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#e94560"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#1e1e2e"))
        self.setPalette(palette)

        style = """
        QMainWindow { background: #1e1e2e; }
        QToolBar { background: #181825; border: none; padding: 4px; spacing: 6px; }
        QToolButton { background: #313244; color: #cdd6f4; border: none;
                      border-radius: 6px; padding: 6px 12px; font-size: 13px; }
        QToolButton:hover { background: #e94560; color: #fff; }
        QTabWidget::pane { background: #1e1e2e; border: none; }
        QTabBar::tab { background: #181825; color: #6c7086; padding: 8px 16px;
                       border: none; border-radius: 8px 8px 0 0; margin-right: 2px; }
        QTabBar::tab:selected { background: #313244; color: #cdd6f4; }
        QTabBar::tab:hover { background: #45475a; color: #cdd6f4; }
        QStatusBar { background: #181825; color: #6c7086; font-size: 12px; }
        QMenu { background: #1e1e2e; color: #cdd6f4; border: 1px solid #45475a; }
        QMenu::item:selected { background: #e94560; }
        QMenu::separator { height: 1px; background: #45475a; margin: 4px 8px; }
        """
        self.setStyleSheet(style)

    # ── Settings persistence ──────────────────────────────

    def _load_settings(self):
        _ensure_dir(CONFIG_DIR)
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE) as f:
                    self._settings = {**DEFAULT_SETTINGS, **json.load(f)}
            except Exception:
                pass

    def _save_settings(self):
        _ensure_dir(CONFIG_DIR)
        with open(SETTINGS_FILE, "w") as f:
            json.dump(self._settings, f, indent=2)

    def _load_history(self):
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE) as f:
                    self._history = json.load(f)
            except Exception:
                self._history = []

    def _save_history(self):
        _ensure_dir(CONFIG_DIR)
        with open(HISTORY_FILE, "w") as f:
            json.dump(self._history[-2000:], f, indent=2)

    def _load_bookmarks(self):
        if BOOKMARKS_FILE.exists():
            try:
                with open(BOOKMARKS_FILE) as f:
                    self._bookmarks = json.load(f)
            except Exception:
                self._bookmarks = []

    def _save_bookmarks(self):
        _ensure_dir(CONFIG_DIR)
        with open(BOOKMARKS_FILE, "w") as f:
            json.dump(self._bookmarks, f, indent=2)

    def add_history(self, url, title=""):
        entry = {"url": url, "title": title, "ts": datetime.now().isoformat()}
        self._history.append(entry)
        self._save_history()

    # ── Navigation ────────────────────────────────────────

    def _navigate(self):
        raw = self.url_bar.text().strip()
        if not raw:
            return

        resolved = self.resolve_url(raw)
        final_url = resolved.get("resolved", raw)
        self._on_web3_info(resolved)

        view = self.tabs.currentWidget()
        if view:
            view.setUrl(QUrl(final_url))
        self.add_history(final_url, title=raw)

    def _go_back(self):
        view = self.tabs.currentWidget()
        if view:
            view.back()

    def _go_forward(self):
        view = self.tabs.currentWidget()
        if view:
            view.forward()

    def _refresh(self):
        view = self.tabs.currentWidget()
        if view:
            view.reload()

    def toggleFullScreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # ── URL resolution (Web3) ─────────────────────────────

    def resolve_url(self, url):
        if not url.strip():
            return {"url": self._settings["homepage"], "type": "homepage"}
        url = url.strip()

        r = self.resolver.resolve(url)
        if r.get("web3_type") != "standard":
            return {
                "original": url,
                "resolved": r.get("resolved_url", url),
                "type": "web3",
                "web3_type": r.get("web3_type", "standard"),
                "resolver_info": r,
            }

        if not url.startswith("http://") and not url.startswith("https://"):
            if "." in url:
                url = "https://" + url
            else:
                url = self._settings["search_engine"] + urllib.parse.quote(url)

        return {"original": url, "resolved": url, "type": "web", "web3_type": "standard"}

    def _on_web3_info(self, info):
        wtype = info.get("web3_type", "standard")
        if wtype == "standard":
            self.web3_badge.setText("🌐")
            self.web3_badge.setStyleSheet("""
                QLabel { background: #0f3460; color: #e0e0e0;
                         padding: 4px 10px; border-radius: 12px; font-size: 11px; }
            """)
        else:
            labels = {
                "ens": "⬡ ENS", "pixel": "⬡ .pixel", "ipfs": "⬡ IPFS",
                "bit": "⬡ .bit", "pixelos": "⬡ PixelOS",
            }
            self.web3_badge.setText(labels.get(wtype, f"⬡ {wtype}"))
            self.web3_badge.setStyleSheet("""
                QLabel { background: #e94560; color: #fff;
                         padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: bold; }
            """)
        self.status_label.setText(
            f"Type: {info.get('type', 'web')} · "
            f"Résolu: {info.get('resolved', info.get('original', ''))[:60]}"
        )

    # ── Bookmarks ─────────────────────────────────────────

    def _show_bookmarks(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Favoris")
        dialog.resize(450, 350)

        layout = QVBoxLayout(dialog)
        tree = QTreeWidget()
        tree.setHeaderLabels(["URL", "Titre"])
        tree.setAlternatingRowColors(True)

        for bm in reversed(self._bookmarks):
            item = QTreeWidgetItem([bm["url"], bm.get("title", "")])
            tree.addTopLevelItem(item)

        btn_layout = QHBoxLayout()
        btn_add = QPushButton("Ajouter")
        btn_del = QPushButton("Supprimer")

        def add_current():
            url = self.tabs.current_url()
            if url:
                self._bookmarks.append({
                    "url": url,
                    "title": self.tabs.tabText(self.tabs.currentIndex()),
                    "ts": datetime.now().isoformat(),
                })
                self._save_bookmarks()
                QMessageBox.information(self, "Favori", "Page ajoutée aux favoris")

        def delete_selected():
            for item in tree.selectedItems():
                url = item.text(0)
                self._bookmarks = [b for b in self._bookmarks if b["url"] != url]
                self._save_bookmarks()
                tree.takeTopLevelItem(tree.indexOfTopLevelItem(item))

        btn_add.clicked.connect(add_current)
        btn_del.clicked.connect(delete_selected)

        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_del)
        layout.addWidget(tree)
        layout.addLayout(btn_layout)
        dialog.exec()

    # ── History ───────────────────────────────────────────

    def _show_history(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Historique")
        dialog.resize(500, 400)

        layout = QVBoxLayout(dialog)
        tree = QTreeWidget()
        tree.setHeaderLabels(["URL", "Titre", "Date"])
        tree.setAlternatingRowColors(True)

        for entry in reversed(self._history[-200:]):
            item = QTreeWidgetItem([
                entry["url"],
                entry.get("title", ""),
                entry.get("ts", "")[:19],
            ])
            tree.addTopLevelItem(item)

        def clear():
            self._history = []
            self._save_history()
            tree.clear()
            QMessageBox.information(self, "Historique", "Historique effacé")

        btn_clear = QPushButton("Effacer")
        btn_clear.clicked.connect(clear)

        layout.addWidget(tree)
        layout.addWidget(btn_clear)
        dialog.exec()

    # ── Settings ──────────────────────────────────────────

    def _show_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Paramètres NOP")
        dialog.resize(400, 350)

        layout = QFormLayout(dialog)

        chk_adblock = QCheckBox()
        chk_adblock.setChecked(self._settings.get("block_ads", True))
        layout.addRow("Bloquer pubs:", chk_adblock)

        chk_track = QCheckBox()
        chk_track.setChecked(self._settings.get("block_trackers", True))
        layout.addRow("Bloquer traceurs:", chk_track)

        chk_web3 = QCheckBox()
        chk_web3.setChecked(self._settings.get("web3_resolver", True))
        layout.addRow("Résolveur Web3:", chk_web3)

        chk_wallet = QCheckBox()
        chk_wallet.setChecked(self._settings.get("wallet_integration", True))
        layout.addRow("Pont Wallet:", chk_wallet)

        chk_noscript = QCheckBox()
        chk_noscript.setChecked(self._settings.get("disable_scripts", False))
        layout.addRow("Désactiver JS:", chk_noscript)

        home_edit = QLineEdit(self._settings.get("homepage", ""))
        layout.addRow("Page d'accueil:", home_edit)

        search_edit = QLineEdit(self._settings.get("search_engine", ""))
        layout.addRow("Moteur recherche:", search_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(lambda: self._save_settings_dialog(
            chk_adblock, chk_track, chk_web3, chk_wallet, chk_noscript,
            home_edit, search_edit, dialog
        ))
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        dialog.exec()

    def _save_settings_dialog(self, adblock, track, web3, wallet, noscript,
                              home, search, dialog):
        self._settings.update({
            "block_ads": adblock.isChecked(),
            "block_trackers": track.isChecked(),
            "web3_resolver": web3.isChecked(),
            "wallet_integration": wallet.isChecked(),
            "disable_scripts": noscript.isChecked(),
            "homepage": home.text(),
            "search_engine": search.text(),
        })
        self._save_settings()
        dialog.accept()
        self.status_label.setText("Paramètres sauvegardés")

    # ── About ─────────────────────────────────────────────

    def _show_about(self):
        QMessageBox.about(self, "NOP Browser",
            "<h2>NOP Browser</h2>"
            "<p>Navigateur Web3 PixelOS</p>"
            "<p>Résolution .eth · .pixel · .ipfs · .bit · .pxl</p>"
            "<p>Blocage pubs/traceurs · Pont Wallet</p>"
            "<hr><p>PixelOS — Agriculture Intelligente</p>")


# ═══════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("NOP Browser")
    app.setOrganizationName("PixelOS")
    app.setOrganizationDomain("pixelos.org")

    window = NOPMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
