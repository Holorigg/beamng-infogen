"""
BeamNG Info Config Generator — PySide6 GUI.
"""
import json
import random
import sys
import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QObject, Signal, QTimer, QThread
from PySide6.QtGui import QColor, QFont, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QFrame,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QSizePolicy, QSplitter, QTableWidget, QTableWidgetItem, QTextEdit,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from analyzer import analyze
from generator import generate, fix, validate
import json_utils
from json_view import JsonView
from scanner import ConfigEntry, scan_mods_folder
from zip_handler import write_many_to_zip

SETTINGS_FILE = Path.home() / ".beamng_infogen.json"

STATUS_SYM   = {"ok": "[✓]", "bad": "[!]", "missing": "[✗]"}
STATUS_COLOR = {"ok": "#4CAF50", "bad": "#E67E22", "missing": "#E74C3C"}

_ARROW_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 6">'
    '<polygon points="0,0 10,0 5,6" fill="#aaaaaa"/>'
    '</svg>'
)


def _icons_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "icons"
    return Path(__file__).parent / "icons"


def make_dark_style() -> str:
    icons_dir = _icons_dir()
    icons_dir.mkdir(exist_ok=True)
    arrow_path = icons_dir / "combo_arrow.svg"
    if not arrow_path.exists():
        arrow_path.write_text(_ARROW_SVG, encoding="utf-8")
    url = arrow_path.as_posix()

    return f"""
QWidget {{
    background-color: #2b2b2b;
    color: #cccccc;
    font-family: "Segoe UI";
    font-size: 10pt;
}}
QPushButton {{
    background-color: #3d5a80;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 5px 12px;
    min-height: 24px;
}}
QPushButton:hover    {{ background-color: #4a6fa5; }}
QPushButton:pressed  {{ background-color: #2d4a6e; }}
QPushButton:disabled {{ background-color: #444444; color: #888888; }}
QLineEdit {{
    background-color: #3c3c3c;
    color: #cccccc;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 4px 8px;
}}
QLineEdit:focus {{ border: 1px solid #4a6fa5; }}
QComboBox {{
    background-color: #3c3c3c;
    color: #cccccc;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 4px 8px 4px 8px;
    min-height: 24px;
}}
QComboBox:focus {{ border: 1px solid #4a6fa5; }}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: right center;
    width: 20px;
    border-left: 1px solid #555555;
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
}}
QComboBox::down-arrow {{
    image: url("{url}");
    width: 10px;
    height: 6px;
}}
QComboBox QAbstractItemView {{
    background-color: #3c3c3c;
    color: #cccccc;
    selection-background-color: #3d5a80;
    border: 1px solid #555555;
}}
QTextEdit {{
    background-color: #3c3c3c;
    color: #cccccc;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 4px;
}}
QTextEdit:focus {{ border: 1px solid #4a6fa5; }}
QTreeWidget {{
    background-color: #1c1c1c;
    color: #cccccc;
    border: none;
    outline: none;
}}
QTreeWidget::item           {{ padding: 2px; }}
QTreeWidget::item:hover     {{ background-color: #2a2a2a; }}
QTreeWidget::item:selected  {{ background-color: #2d4a6e; color: #ffffff; }}
QTreeWidget::branch         {{ background-color: #1c1c1c; }}
QScrollBar:vertical {{
    background: #2a2a2a; width: 10px; border: none;
}}
QScrollBar::handle:vertical {{
    background: #484848; min-height: 20px; border-radius: 5px;
}}
QScrollBar::handle:vertical:hover   {{ background: #666666; }}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical       {{ height: 0px; }}
QScrollBar:horizontal {{
    background: #2a2a2a; height: 10px; border: none;
}}
QScrollBar::handle:horizontal {{
    background: #484848; min-width: 20px; border-radius: 5px;
}}
QScrollBar::handle:horizontal:hover {{ background: #666666; }}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal     {{ width: 0px; }}
QScrollArea         {{ border: none; }}
#topBar             {{ background-color: #333333; }}
#botBar             {{ background-color: #333333; }}
#editorContainer    {{ background-color: #2b2b2b; }}
QDialog             {{ background-color: #2b2b2b; }}
QProgressBar {{
    background-color: #3c3c3c;
    border: none;
    border-radius: 4px;
    text-align: center;
}}
QProgressBar::chunk {{ background-color: #3d5a80; border-radius: 4px; }}
QListWidget {{
    background-color: #1c1c1c;
    color: #cccccc;
    border: none;
}}
QListWidget::item:selected  {{ background-color: #2d4a6e; color: #ffffff; }}
QSplitter::handle           {{ background-color: #444444; }}
QLabel                      {{ background: transparent; }}
"""


def _load_settings() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text("utf-8"))
    except Exception:
        return {}


def _save_settings(data: dict):
    try:
        SETTINGS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
    except Exception:
        pass


class _WorkerSignals(QObject):
    step     = Signal()
    finished = Signal()


class _ScanSignals(QObject):
    done = Signal(object)


class _CardPreview(QFrame):
    _IMG_W = 180
    _IMG_H = 112

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cardPreview")
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            QFrame#cardPreview {
                background-color: #1a1a2e;
                border: 1px solid #3d5a80;
                border-radius: 6px;
            }
        """)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 10, 12, 10)
        outer.setSpacing(12)

        self._lbl_img = QLabel()
        self._lbl_img.setFixedSize(self._IMG_W, self._IMG_H)
        self._lbl_img.setAlignment(Qt.AlignCenter)
        self._lbl_img.setStyleSheet(
            "background-color: #111122; border-radius: 4px; border: 1px solid #2a2a4a;"
        )
        outer.addWidget(self._lbl_img)

        info = QVBoxLayout()
        info.setSpacing(3)

        title_row = QHBoxLayout()
        self._lbl_name = QLabel("")
        self._lbl_name.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self._lbl_name.setStyleSheet("color: #ffffff; background: transparent;")
        title_row.addWidget(self._lbl_name, 1)
        self._lbl_type = QLabel("")
        self._lbl_type.setStyleSheet(
            "color: #9cdcfe; background: #2d4a6e; border-radius: 3px; "
            "padding: 1px 6px; font-size: 9pt;"
        )
        title_row.addWidget(self._lbl_type)
        info.addLayout(title_row)

        sep = QLabel("━" * 32)
        sep.setStyleSheet("color: #3d5a80; background: transparent;")
        info.addWidget(sep)

        self._lbl_row1 = QLabel("")
        self._lbl_row1.setStyleSheet("color: #cccccc; background: transparent;")
        info.addWidget(self._lbl_row1)

        self._lbl_row2 = QLabel("")
        self._lbl_row2.setStyleSheet("color: #cccccc; background: transparent;")
        info.addWidget(self._lbl_row2)

        self._lbl_stats = QLabel("")
        self._lbl_stats.setStyleSheet("color: #b5cea8; background: transparent;")
        info.addWidget(self._lbl_stats)

        self._lbl_desc = QLabel("")
        self._lbl_desc.setStyleSheet("color: #888888; font-style: italic; background: transparent;")
        self._lbl_desc.setWordWrap(True)
        self._lbl_desc.setMaximumHeight(34)
        info.addWidget(self._lbl_desc)

        info.addStretch()
        outer.addLayout(info, 1)

    def set_thumbnail(self, data: bytes):
        if not data:
            self._lbl_img.clear()
            return
        px = QPixmap()
        px.loadFromData(data)
        if px.isNull():
            self._lbl_img.clear()
        else:
            self._lbl_img.setPixmap(
                px.scaled(self._IMG_W, self._IMG_H,
                           Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

    def update(self, data: dict):
        name = data.get("Configuration") or "—"
        self._lbl_name.setText(name)
        self._lbl_type.setText(data.get("Config Type") or "")

        value = data.get("Value", "")
        try:
            value_str = f"{int(float(value)):,}".replace(",", " ")
        except (TypeError, ValueError):
            value_str = str(value) if value else "—"

        self._lbl_row1.setText(
            f"  {value_str}     "
            f"  {data.get('Drivetrain', '—')}   "
            f"  {data.get('Fuel Type', '—')}"
        )
        self._lbl_row2.setText(
            f"  {data.get('Transmission', '—')}   "
            f"  {data.get('Induction Type', '—')}   "
            f"  {data.get('Body Style', '—')}"
        )

        parts = []
        if data.get("Power"):   parts.append(f"  {data['Power']} HP")
        if data.get("Torque"):  parts.append(f"  {data['Torque']} Nm")
        if data.get("Weight"):  parts.append(f"  {data['Weight']} kg")
        self._lbl_stats.setText("   ".join(parts) if parts else "")

        desc = data.get("Description", "")
        if len(desc) > 90:
            desc = desc[:87] + "..."
        self._lbl_desc.setText(desc)

    def clear(self):
        self._lbl_img.clear()
        for lbl in (self._lbl_name, self._lbl_type, self._lbl_row1,
                    self._lbl_row2, self._lbl_stats, self._lbl_desc):
            lbl.setText("")


class App(QMainWindow):
    def __init__(self, mods_path: str = None):
        super().__init__()
        self.setWindowTitle("BeamNG Info Config Generator")
        self.resize(1100, 700)
        self.setMinimumSize(900, 560)

        self.mods_data: dict[str, list[ConfigEntry]] = {}
        self.selected_entry: Optional[ConfigEntry]   = None
        self._selection: set[int]                    = set()
        self._status_filter: set[str]                = {"ok", "bad", "missing"}
        # mods with all-ok entries are collapsed by default
        self._collapsed: dict[str, bool]             = {}

        self._build_ui()

        if mods_path:
            self.folder_edit.setText(mods_path)
            self._scan()
        else:
            self._load_last_path()

        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self._save_current)
        QShortcut(QKeySequence("F5"),     self).activated.connect(self._rescan)

    def _load_last_path(self):
        path = _load_settings().get("last_mods_path", "")
        if path and Path(path).exists():
            self.folder_edit.setText(path)

    def _save_last_path(self, path: str):
        s = _load_settings()
        s["last_mods_path"] = path
        _save_settings(s)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        top = QWidget()
        top.setObjectName("topBar")
        top.setFixedHeight(48)
        top_lay = QHBoxLayout(top)
        top_lay.setContentsMargins(12, 6, 12, 6)
        top_lay.setSpacing(6)

        top_lay.addWidget(QLabel("Mods folder:"))
        self.folder_edit = QLineEdit()
        top_lay.addWidget(self.folder_edit, 1)

        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self._browse)
        top_lay.addWidget(self.browse_btn)

        self.scan_btn = QPushButton("Scan")
        self.scan_btn.clicked.connect(self._scan)
        top_lay.addWidget(self.scan_btn)

        self.rescan_btn = QPushButton("Rescan")
        self.rescan_btn.setEnabled(False)
        self.rescan_btn.clicked.connect(self._rescan)
        top_lay.addWidget(self.rescan_btn)

        root.addWidget(top)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4)
        root.addWidget(splitter, 1)

        left = QWidget()
        left.setMinimumWidth(280)
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(4, 8, 4, 4)
        left_lay.setSpacing(4)

        hdr_lay = QHBoxLayout()
        hdr_lay.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("CONFIGS")
        lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        hdr_lay.addWidget(lbl)
        hdr_lay.addStretch()

        self._filter_btns: dict[str, QPushButton] = {}
        for status, sym, color in [("missing", "[✗]", STATUS_COLOR["missing"]),
                                    ("bad",     "[!]", STATUS_COLOR["bad"]),
                                    ("ok",      "[✓]", STATUS_COLOR["ok"])]:
            btn = QPushButton(sym)
            btn.setFixedSize(36, 24)
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {color}; color: white; "
                f"border-radius: 3px; font-size: 10pt; padding: 0; }}"
            )
            btn.clicked.connect(lambda _=False, s=status: self._toggle_filter(s))
            hdr_lay.addWidget(btn)
            self._filter_btns[status] = btn

        self._table_mode = False
        self._view_btn = QPushButton("⊞")
        self._view_btn.setFixedSize(28, 24)
        self._view_btn.setStyleSheet(
            "QPushButton { background-color: #444444; color: #cccccc; "
            "border-radius: 3px; font-size: 12pt; padding: 0; }"
            "QPushButton:hover { background-color: #555555; }"
        )
        self._view_btn.setToolTip("Switch to table view")
        self._view_btn.clicked.connect(self._toggle_view)
        hdr_lay.addWidget(self._view_btn)
        left_lay.addLayout(hdr_lay)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.tree.setIndentation(12)
        self.tree.setUniformRowHeights(True)
        self.tree.setRootIsDecorated(False)   # hide Qt's native expand arrows
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        left_lay.addWidget(self.tree)

        _TABLE_HEADERS = ["", "Mod", "Config", "Drive", "Fuel", "Trans.", "Type", "Value"]
        self.table = QTableWidget(0, len(_TABLE_HEADERS))
        self.table.setHorizontalHeaderLabels(_TABLE_HEADERS)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setStyleSheet("""
            QTableWidget { background-color: #1c1c1c; color: #cccccc; border: none; gridline-color: #333333; }
            QTableWidget::item:selected { background-color: #2d4a6e; color: #ffffff; }
            QHeaderView::section { background-color: #2b2b2b; color: #888888; border: none; padding: 4px; }
        """)
        self.table.setSortingEnabled(True)
        self.table.cellClicked.connect(self._on_table_cell_clicked)
        self.table.hide()
        left_lay.addWidget(self.table)

        splitter.addWidget(left)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        editor_container = QWidget()
        editor_container.setObjectName("editorContainer")
        self._editor_lay = QVBoxLayout(editor_container)
        self._editor_lay.setContentsMargins(12, 8, 12, 8)
        self._editor_lay.setSpacing(4)
        self._build_editor(self._editor_lay)

        scroll.setWidget(editor_container)
        splitter.addWidget(scroll)
        splitter.setSizes([380, 720])

        bot = QWidget()
        bot.setObjectName("botBar")
        bot.setFixedHeight(52)
        bot_lay = QHBoxLayout(bot)
        bot_lay.setContentsMargins(12, 8, 16, 8)
        bot_lay.setSpacing(8)

        gen_all_btn = QPushButton("Generate all [✗]")
        gen_all_btn.clicked.connect(self._generate_all_missing)
        bot_lay.addWidget(gen_all_btn)

        fix_all_btn = QPushButton("Fix all [!]")
        fix_all_btn.clicked.connect(self._fix_all_bad)
        bot_lay.addWidget(fix_all_btn)

        analyze_btn = QPushButton("Analyze")
        analyze_btn.clicked.connect(self._show_analyze_dialog)
        bot_lay.addWidget(analyze_btn)

        self.gen_sel_btn = QPushButton("Generate selected (0)")
        self.gen_sel_btn.setEnabled(False)
        self.gen_sel_btn.clicked.connect(self._generate_selected)
        bot_lay.addWidget(self.gen_sel_btn)

        bot_lay.addStretch()

        self.status_lbl = QLabel("No mods loaded.  |  Ctrl+S = Save   F5 = Rescan")
        self.status_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        bot_lay.addWidget(self.status_lbl)

        root.addWidget(bot)

    def _build_editor(self, layout: QVBoxLayout):
        LBL_W = 140

        def row(text: str) -> QHBoxLayout:
            h = QHBoxLayout()
            h.setSpacing(8)
            lbl = QLabel(text)
            lbl.setFixedWidth(LBL_W)
            h.addWidget(lbl)
            return h

        for label, values, attr in [
            ("Config Type:",  ["Factory", "Custom", "Race"],                         "w_config_type"),
            ("Drivetrain:",   ["RWD", "AWD", "FWD"],                                 "w_drivetrain"),
            ("Transmission:", ["Automatic", "Manual", "DCT", "CVT"],                 "w_transmission"),
            ("Fuel Type:",    ["Gasoline", "Diesel", "Electric", "Hybrid"],           "w_fuel"),
            ("Body Style:",   ["Sedan", "Coupe", "SUV", "Hatchback",
                               "Wagon", "Truck", "Van", "Convertible"],               "w_body"),
            ("Induction:",    ["Turbo", "Twin Turbo", "Supercharger", "Natural"],    "w_induction"),
        ]:
            r = row(label)
            w = QComboBox()
            w.addItems(values)
            w.setFixedWidth(220)
            r.addWidget(w)
            r.addStretch()
            layout.addLayout(r)
            setattr(self, attr, w)

        for label, attr in [
            ("Power (HP):",  "w_power"),
            ("Torque (Nm):", "w_torque"),
            ("Weight (kg):", "w_weight"),
            ("Price min:",   "w_price_min"),
            ("Price max:",   "w_price_max"),
        ]:
            r = row(label)
            w = QLineEdit()
            w.setFixedWidth(220)
            r.addWidget(w)
            r.addStretch()
            layout.addLayout(r)
            setattr(self, attr, w)

        r = row("Description:")
        self.w_description = QTextEdit()
        self.w_description.setFixedHeight(72)
        self.w_description.setAcceptRichText(False)
        r.addWidget(self.w_description)
        layout.addLayout(r)

        sep = QLabel("─── Raw JSON (editable) ───")
        sep.setAlignment(Qt.AlignCenter)
        sep.setStyleSheet("color: #888888; padding: 8px 0 4px 0;")
        layout.addWidget(sep)

        self.json_view = JsonView()
        self.json_view.setMinimumHeight(280)
        layout.addWidget(self.json_view)

        self.lbl_missing = QLabel("")
        self.lbl_missing.setStyleSheet("color: #E74C3C;")
        self.lbl_missing.setWordWrap(True)
        layout.addWidget(self.lbl_missing)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        for text, slot in [
            ("Save",        self._save_current),
            ("Regenerate",  self._regen_current),
            ("Save JSON",   self._save_json_current),
            ("Copy from...",self._copy_from_dialog),
        ]:
            b = QPushButton(text)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._card = _CardPreview()
        layout.addWidget(self._card)
        layout.addStretch()

        for w in (self.w_config_type, self.w_drivetrain, self.w_transmission,
                  self.w_fuel, self.w_body, self.w_induction):
            w.currentTextChanged.connect(self._refresh_card)
        for w in (self.w_power, self.w_torque, self.w_weight,
                  self.w_price_min, self.w_price_max):
            w.textChanged.connect(self._refresh_card)
        self.w_description.textChanged.connect(self._refresh_card)

    def _toggle_filter(self, status: str):
        if status in self._status_filter:
            if len(self._status_filter) <= 1:
                return
            self._status_filter.discard(status)
        else:
            self._status_filter.add(status)
        self._update_filter_buttons()
        if self._table_mode:
            self._rebuild_table()
        else:
            self._rebuild_tree()

    def _update_filter_buttons(self):
        for status, btn in self._filter_btns.items():
            if status in self._status_filter:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: {STATUS_COLOR[status]}; "
                    f"color: white; border-radius: 3px; font-size: 10pt; padding: 0; }}"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton { background-color: #555555; color: #888888; "
                    "border-radius: 3px; font-size: 10pt; padding: 0; }"
                )

    def _rebuild_tree(self):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            mod_name = item.data(0, Qt.UserRole + 1)
            if mod_name:
                self._collapsed[mod_name] = not item.isExpanded()

        self.tree.blockSignals(True)
        self.tree.clear()

        first_load = not self._collapsed  # no state yet → expand everything

        for mod_name, entries in self.mods_data.items():
            visible = [e for e in entries if e.status in self._status_filter]

            counts = {s: sum(1 for e in entries if e.status == s)
                      for s in ("ok", "bad", "missing")}
            badges = []
            if counts["ok"]:      badges.append(f"✓{counts['ok']}")
            if counts["bad"]:     badges.append(f"!{counts['bad']}")
            if counts["missing"]: badges.append(f"✗{counts['missing']}")
            badge_str = "  " + " ".join(badges) if badges else ""

            if first_load:
                all_ok = all(e.status == "ok" for e in entries)
                expand = not all_ok
            else:
                expand = not self._collapsed.get(mod_name, False)
            if not visible:
                expand = False

            sym = "▼" if expand else "▶"
            mod_item = QTreeWidgetItem([f" {sym} {mod_name}{badge_str}"])
            mod_item.setData(0, Qt.UserRole,     None)
            mod_item.setData(0, Qt.UserRole + 1, mod_name)
            mod_item.setForeground(0, QColor("#aaaaaa"))
            mod_item.setFont(0, QFont("Segoe UI", 10, QFont.Bold))

            for entry in visible:
                child = QTreeWidgetItem([f"  {STATUS_SYM[entry.status]}  {entry.config_name}"])
                child.setData(0, Qt.UserRole, entry)
                child.setForeground(0, QColor(STATUS_COLOR[entry.status]))
                mod_item.addChild(child)

            self.tree.addTopLevelItem(mod_item)
            mod_item.setExpanded(expand)

        self.tree.blockSignals(False)
        self._update_sel_button()

    def _rebuild_view(self):
        self._rebuild_tree()
        if self._table_mode:
            self._rebuild_table()

    def _toggle_view(self):
        self._table_mode = not self._table_mode
        if self._table_mode:
            self.tree.hide()
            self.table.show()
            self._view_btn.setText("≡")
            self._view_btn.setToolTip("Switch to tree view")
            self._rebuild_table()
        else:
            self.table.hide()
            self.tree.show()
            self._view_btn.setText("⊞")
            self._view_btn.setToolTip("Switch to table view")

    def _rebuild_table(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        for mod_name, entries in self.mods_data.items():
            for entry in entries:
                if entry.status not in self._status_filter:
                    continue
                data = entry.info_content or {}
                row = self.table.rowCount()
                self.table.insertRow(row)

                status_item = QTableWidgetItem(STATUS_SYM[entry.status])
                status_item.setForeground(QColor(STATUS_COLOR[entry.status]))
                status_item.setTextAlignment(Qt.AlignCenter)
                status_item.setData(Qt.UserRole, entry)
                self.table.setItem(row, 0, status_item)
                self.table.setItem(row, 1, QTableWidgetItem(mod_name))
                self.table.setItem(row, 2, QTableWidgetItem(entry.config_name))
                self.table.setItem(row, 3, QTableWidgetItem(data.get("Drivetrain", "")))
                self.table.setItem(row, 4, QTableWidgetItem(data.get("Fuel Type", "")))
                self.table.setItem(row, 5, QTableWidgetItem(data.get("Transmission", "")))
                self.table.setItem(row, 6, QTableWidgetItem(data.get("Config Type", "")))
                val = data.get("Value", "")
                try:
                    val_str = str(int(float(val)))
                except (TypeError, ValueError):
                    val_str = str(val) if val else ""
                val_item = QTableWidgetItem(val_str)
                val_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row, 7, val_item)

        self.table.setSortingEnabled(True)

    def _on_table_cell_clicked(self, row: int, _col: int):
        item = self.table.item(row, 0)
        if item is None:
            return
        entry = item.data(Qt.UserRole)
        if entry is None:
            return
        self.selected_entry = entry
        self._selection = {id(entry)}
        self._update_sel_button()
        self._load_to_editor(entry)

    def _maybe_auto_collapse(self, mod_name: str):
        entries = self.mods_data.get(mod_name, [])
        if entries and all(e.status == "ok" for e in entries):
            self._collapsed[mod_name] = True

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int):
        entry = item.data(0, Qt.UserRole)
        if entry is None:
            expand = not item.isExpanded()
            item.setExpanded(expand)
            text = item.text(0)
            if text.startswith(" ▼") or text.startswith(" ▶"):
                item.setText(0, (" ▼" if expand else " ▶") + text[2:])
            return
        self.selected_entry = entry
        self._load_to_editor(entry)

    def _on_selection_changed(self):
        eids = set()
        for item in self.tree.selectedItems():
            entry = item.data(0, Qt.UserRole)
            if entry is not None:
                eids.add(id(entry))
        self._selection = eids
        self._update_sel_button()

    def _update_sel_button(self):
        n = len(self._selection)
        self.gen_sel_btn.setText(f"Generate selected ({n})")
        self.gen_sel_btn.setEnabled(n > 0)

    def _refresh_entry_item(self, entry: ConfigEntry):
        for i in range(self.tree.topLevelItemCount()):
            mod_item = self.tree.topLevelItem(i)
            for j in range(mod_item.childCount()):
                child = mod_item.child(j)
                if child.data(0, Qt.UserRole) is entry:
                    child.setText(0, f"  {STATUS_SYM[entry.status]}  {entry.config_name}")
                    child.setForeground(0, QColor(STATUS_COLOR[entry.status]))
                    return

    def _load_to_editor(self, entry: ConfigEntry):
        data = entry.info_content or {}
        auto = entry.auto_detected

        def _set(w: QComboBox, val: str):
            idx = w.findText(val)
            w.setCurrentIndex(idx if idx >= 0 else 0)

        _set(self.w_config_type,  data.get("Config Type",   "Factory"))
        _set(self.w_drivetrain,   data.get("Drivetrain",    auto.get("Drivetrain",   "RWD")))
        _set(self.w_transmission, data.get("Transmission",  auto.get("Transmission", "Automatic")))
        _set(self.w_fuel,         data.get("Fuel Type",     auto.get("Fuel Type",    "Gasoline")))
        _set(self.w_body,         data.get("Body Style",    "Sedan"))
        _set(self.w_induction,    data.get("Induction Type","Turbo"))

        for widget, key in [(self.w_power, "Power"), (self.w_torque, "Torque"),
                             (self.w_weight, "Weight")]:
            val = data.get(key)
            widget.setText(str(val) if val is not None and val != "" else "")

        val = data.get("Value", "")
        price_str = str(int(val)) if isinstance(val, (int, float)) and val else str(val)
        self.w_price_min.setText(price_str)
        self.w_price_max.setText(price_str)

        self.w_description.setPlainText(data.get("Description", ""))
        self._populate_json_view(entry)
        self._card.set_thumbnail(entry.thumbnail or b"")
        self._refresh_card()

        self.lbl_missing.setText(
            f"Missing / invalid: {', '.join(entry.missing_fields)}"
            if entry.missing_fields else ""
        )

    def _populate_json_view(self, entry: ConfigEntry):
        if entry.info_raw is not None:
            self.json_view.set_raw(entry.info_raw, set(entry.missing_fields))
        else:
            auto = entry.auto_detected
            data = {
                "Configuration": entry.config_name,
                "Config Type":   "Factory",
                "Drivetrain":    auto.get("Drivetrain",   "RWD"),
                "Transmission":  auto.get("Transmission", "Automatic"),
                "Fuel Type":     auto.get("Fuel Type",    "Gasoline"),
                "Value":         0,
            }
            self.json_view.set_content(data, set(validate(data)))

    def _refresh_card(self):
        if not self.selected_entry:
            return
        try:
            price = int(self.w_price_min.text())
        except (ValueError, TypeError):
            price = 0
        data = {
            "Configuration":  self.selected_entry.config_name,
            "Config Type":    self.w_config_type.currentText(),
            "Drivetrain":     self.w_drivetrain.currentText(),
            "Transmission":   self.w_transmission.currentText(),
            "Fuel Type":      self.w_fuel.currentText(),
            "Induction Type": self.w_induction.currentText(),
            "Body Style":     self.w_body.currentText(),
            "Value":          price,
            "Description":    self.w_description.toPlainText(),
        }
        for key, w in [("Power", self.w_power), ("Torque", self.w_torque),
                       ("Weight", self.w_weight)]:
            try:
                data[key] = int(w.text())
            except (ValueError, TypeError):
                pass
        self._card.update(data)

    def _editor_defaults(self) -> dict:
        return {
            "config_type": self.w_config_type.currentText(),
            "induction":   self.w_induction.currentText(),
            "body_style":  self.w_body.currentText(),
            "power":       self.w_power.text(),
            "torque":      self.w_torque.text(),
            "weight":      self.w_weight.text(),
            "price_min":   self.w_price_min.text() or "10000",
            "price_max":   self.w_price_max.text() or "50000",
            "description": self.w_description.toPlainText(),
        }

    def _build_data_from_editor(self, entry: ConfigEntry) -> dict:
        d = self._editor_defaults()
        data: dict = {
            "Configuration":  entry.config_name,
            "Config Type":    self.w_config_type.currentText(),
            "Drivetrain":     self.w_drivetrain.currentText(),
            "Transmission":   self.w_transmission.currentText(),
            "Fuel Type":      self.w_fuel.currentText(),
            "Propulsion":     "Electric" if self.w_fuel.currentText() == "Electric" else "ICE",
            "Induction Type": d["induction"],
            "Body Style":     d["body_style"],
            "Description":    d["description"],
            "Population":     (entry.info_content or {}).get("Population", 5000),
            "Off-Road Score": (entry.info_content or {}).get("Off-Road Score", 20),
        }
        try:
            lo = int(d["price_min"])
            hi = int(d["price_max"])
            if lo > hi:
                lo, hi = hi, lo
            data["Value"] = lo if lo == hi else round(random.randint(lo, hi) / 500) * 500
        except (ValueError, TypeError):
            data["Value"] = 10000

        for key, dkey in [("Power", "power"), ("Torque", "torque"), ("Weight", "weight")]:
            try:
                data[key] = int(d[dkey])
            except (ValueError, TypeError):
                pass
        return data

    def _info_filename_for_entry(self, entry: ConfigEntry) -> str:
        if entry.info_path:
            return Path(entry.info_path).name

        stem = entry.config_name
        if stem.lower().startswith("config_"):
            stem = stem[len("config_"):]
        return f"info_{stem}.json"

    def _target_path_for_entry(self, entry: ConfigEntry) -> str:
        info_filename = self._info_filename_for_entry(entry)
        if entry.source == "zip":
            target = (Path(entry.pc_path).parent / info_filename).as_posix()
            if target.startswith("./"):
                target = target[2:]
            return target
        return str(Path(entry.pc_path).parent / info_filename)

    def _mark_entry_written(self, entry: ConfigEntry, data: dict, json_str: str, info_path: str):
        entry.info_path      = info_path
        entry.info_content   = data
        entry.info_raw       = json_str
        entry.missing_fields = validate(data)
        entry.status         = "ok" if not entry.missing_fields else "bad"

    def _write_entry(self, entry: ConfigEntry, data: dict, refresh: bool = True):
        self._write_entry_pairs([(entry, data)])
        if refresh:
            self._refresh_entry_item(entry)

    def _write_entry_pairs(self, pairs: list[tuple[ConfigEntry, dict]]):
        zip_updates: dict[str, dict[str, str]] = {}
        zip_written: list[tuple[ConfigEntry, dict, str, str]] = []

        for entry, data in pairs:
            json_str = json.dumps(data, indent=2, ensure_ascii=False)
            target = self._target_path_for_entry(entry)

            if entry.source == "zip":
                zip_updates.setdefault(entry.source_path, {})[target] = json_str
                zip_written.append((entry, data, json_str, target))
            else:
                Path(target).write_text(json_str, encoding="utf-8")
                self._mark_entry_written(entry, data, json_str, target)

        for zip_path, updates in zip_updates.items():
            write_many_to_zip(zip_path, updates)

        for entry, data, json_str, target in zip_written:
            self._mark_entry_written(entry, data, json_str, target)

    def _write_groups_for_pairs(self, pairs: list[tuple[ConfigEntry, dict]]) -> list[list[tuple[ConfigEntry, dict]]]:
        groups: list[list[tuple[ConfigEntry, dict]]] = []
        zip_groups: dict[str, list[tuple[ConfigEntry, dict]]] = {}

        for entry, data in pairs:
            if entry.source == "zip":
                zip_groups.setdefault(entry.source_path, []).append((entry, data))
            else:
                groups.append([(entry, data)])

        groups.extend(zip_groups.values())
        return groups

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Select mods folder")
        if path:
            self.folder_edit.setText(path)

    def _scan(self):
        path = self.folder_edit.text().strip()
        if not path or not Path(path).exists():
            QMessageBox.critical(self, "Error", "Invalid or missing folder path.")
            return
        self._save_last_path(path)
        self.mods_data = {}
        self.selected_entry = None
        self._selection.clear()
        self._collapsed.clear()
        self.tree.clear()
        self._update_sel_button()

        self.scan_btn.setEnabled(False)
        self.scan_btn.setText("Scanning...")
        self.rescan_btn.setEnabled(False)
        self.status_lbl.setText("Scanning mods folder...")

        sig = _ScanSignals()
        sig.done.connect(self._scan_done)
        self._scan_sig = sig  # keep alive

        def _worker():
            try:
                data = scan_mods_folder(path)
                sig.done.emit(data)
            except Exception as exc:
                sig.done.emit(None)
                QTimer.singleShot(0, lambda: QMessageBox.critical(
                    self, "Scan error", str(exc)))

        threading.Thread(target=_worker, daemon=True).start()

    def _rescan(self):
        path = self.folder_edit.text().strip()
        if path and Path(path).exists():
            self._scan()

    def _scan_done(self, data):
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("Scan")
        self.rescan_btn.setEnabled(True)
        if data is None:
            self.status_lbl.setText("Scan failed.")
            return
        self.mods_data = data
        self._rebuild_view()
        self._update_status()

    def _save_current(self):
        if not self.selected_entry:
            return
        entry = self.selected_entry
        data  = self._build_data_from_editor(entry)

        def work(_):
            self._write_entry(entry, data, refresh=False)

        def done(_):
            self._refresh_entry_item(entry)
            self._load_to_editor(entry)
            self._update_status()

        self._run_batch("Saving...", [entry], work, done,
                        subtitle="Writing config to disk...")

    def _regen_current(self):
        if not self.selected_entry:
            return
        entry = self.selected_entry
        regen = generate(entry.config_name, {
            "Drivetrain":   self.w_drivetrain.currentText(),
            "Transmission": self.w_transmission.currentText(),
            "Fuel Type":    self.w_fuel.currentText(),
        }, self._editor_defaults())

        def work(_):
            self._write_entry(entry, regen, refresh=False)

        def done(_):
            self._refresh_entry_item(entry)
            self._load_to_editor(entry)
            self._update_status()

        self._run_batch("Regenerating...", [entry], work, done,
                        subtitle="Regenerating config with new values...")

    def _save_json_current(self):
        if not self.selected_entry:
            return
        raw = self.json_view.get_raw_text().strip()
        try:
            data = json_utils.loads(raw)
        except Exception as exc:
            QMessageBox.critical(self, "JSON Error", f"Invalid JSON:\n{exc}")
            return
        entry = self.selected_entry

        def work(_):
            self._write_entry(entry, data, refresh=False)

        def done(_):
            self._refresh_entry_item(entry)
            self._load_to_editor(entry)
            self._update_status()

        self._run_batch("Saving...", [entry], work, done,
                        subtitle="Writing JSON to disk...")

    def _generate_all_missing(self):
        defaults = self._editor_defaults()
        pairs = [
            (e, generate(e.config_name, e.auto_detected, defaults))
            for es in self.mods_data.values()
            for e in es if e.status == "missing"
        ]
        groups = self._write_groups_for_pairs(pairs)
        created = len(pairs)

        def work(group):
            self._write_entry_pairs(group)

        def done(_):
            for mod_name in self.mods_data:
                self._maybe_auto_collapse(mod_name)
            self._rebuild_view()
            self._update_status(created=created)

        self._run_batch("Generating...", groups, work, done,
                        subtitle="Generating missing info configs...")

    def _generate_selected(self):
        if not self._selection:
            return
        defaults = self._editor_defaults()
        auto_override = {
            "Drivetrain":   self.w_drivetrain.currentText(),
            "Transmission": self.w_transmission.currentText(),
            "Fuel Type":    self.w_fuel.currentText(),
        }
        all_entries = {id(e): e for es in self.mods_data.values() for e in es}
        entries = [all_entries[eid] for eid in self._selection if eid in all_entries]
        pairs = [
            (e, generate(e.config_name, auto_override, defaults))
            for e in entries
        ]
        groups = self._write_groups_for_pairs(pairs)
        created = len(pairs)

        def work(group):
            self._write_entry_pairs(group)

        def done(_):
            for mod_name in self.mods_data:
                self._maybe_auto_collapse(mod_name)
            self._rebuild_view()
            self._update_status(created=created)
            if self.selected_entry and id(self.selected_entry) in self._selection:
                self._load_to_editor(self.selected_entry)

        self._run_batch("Generating...", groups, work, done,
                        subtitle="Generating selected configs...")

    def _fix_all_bad(self):
        defaults = self._editor_defaults()
        pairs = [
            (e, fix(e.info_content or {}, e.config_name, e.auto_detected, defaults))
            for es in self.mods_data.values()
            for e in es if e.status == "bad"
        ]
        groups = self._write_groups_for_pairs(pairs)
        updated = len(pairs)

        def work(group):
            self._write_entry_pairs(group)

        def done(_):
            for mod_name in self.mods_data:
                self._maybe_auto_collapse(mod_name)
            self._rebuild_view()
            self._update_status(updated=updated)

        self._run_batch("Fixing...", groups, work, done,
                        subtitle="Filling missing fields in existing configs...")

    def _show_analyze_dialog(self):
        report = analyze(self.mods_data)

        dialog = QDialog(self)
        dialog.setWindowTitle("Analyze — Config Issues")
        dialog.resize(560, 480)
        lay = QVBoxLayout(dialog)

        if not report:
            lay.addWidget(QLabel("All configs look good  [✓]"))
        else:
            tree = QTreeWidget()
            tree.setHeaderHidden(True)
            tree.setRootIsDecorated(True)
            tree.setIndentation(16)
            lay.addWidget(tree, 1)

            for mod_name, configs in report.items():
                mod_item = QTreeWidgetItem([mod_name])
                mod_item.setFont(0, QFont("Segoe UI", 10, QFont.Bold))
                mod_item.setForeground(0, QColor("#aaaaaa"))
                tree.addTopLevelItem(mod_item)

                for cfg in configs:
                    cfg_item = QTreeWidgetItem([cfg["config_name"]])
                    cfg_item.setForeground(0, QColor("#cccccc"))
                    mod_item.addChild(cfg_item)

                    for msg in cfg["critical"]:
                        ch = QTreeWidgetItem([f"  [✗]  {msg}"])
                        ch.setForeground(0, QColor("#E74C3C"))
                        cfg_item.addChild(ch)
                    for msg in cfg["warnings"]:
                        ch = QTreeWidgetItem([f"  [!]  {msg}"])
                        ch.setForeground(0, QColor("#E67E22"))
                        cfg_item.addChild(ch)

                mod_item.setExpanded(True)
                for i in range(mod_item.childCount()):
                    mod_item.child(i).setExpanded(True)

        btn_row = QHBoxLayout()
        if report:
            copy_btn = QPushButton("Copy report")
            def _copy():
                lines = []
                for mod_name, configs in report.items():
                    lines.append(mod_name)
                    for cfg in configs:
                        lines.append(f"  {cfg['config_name']}")
                        for m in cfg["critical"]:
                            lines.append(f"    [CRITICAL] {m}")
                        for m in cfg["warnings"]:
                            lines.append(f"    [WARNING]  {m}")
                QApplication.clipboard().setText("\n".join(lines))
            copy_btn.clicked.connect(_copy)
            btn_row.addWidget(copy_btn)
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        dialog.exec()

    def _copy_from_dialog(self):
        if not self.selected_entry or not self.mods_data:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Copy fields from...")
        dialog.resize(420, 480)
        lay = QVBoxLayout(dialog)

        lay.addWidget(QLabel("Select a config to copy fields from:"))

        listbox = QListWidget()
        lay.addWidget(listbox, 1)

        source_entries: list[ConfigEntry] = []
        for mod_name, entries in self.mods_data.items():
            for e in entries:
                if e.info_content and e is not self.selected_entry:
                    listbox.addItem(f"  {mod_name} / {e.config_name}")
                    source_entries.append(e)

        if not source_entries:
            lay.addWidget(QLabel("No configs with data to copy from."))

        def _do_copy():
            row = listbox.currentRow()
            if row < 0:
                return
            dialog.accept()
            self._apply_copy(source_entries[row])

        copy_btn = QPushButton("Copy")
        copy_btn.clicked.connect(_do_copy)
        lay.addWidget(copy_btn)
        dialog.exec()

    def _apply_copy(self, source: ConfigEntry):
        data = source.info_content or {}

        def _set(w: QComboBox, key: str):
            val = data.get(key)
            if val:
                idx = w.findText(val)
                if idx >= 0:
                    w.setCurrentIndex(idx)

        _set(self.w_config_type,  "Config Type")
        _set(self.w_drivetrain,   "Drivetrain")
        _set(self.w_transmission, "Transmission")
        _set(self.w_fuel,         "Fuel Type")
        _set(self.w_body,         "Body Style")
        _set(self.w_induction,    "Induction Type")

        for widget, key in [(self.w_power, "Power"), (self.w_torque, "Torque"),
                             (self.w_weight, "Weight")]:
            val = data.get(key)
            if val is not None and val != "":
                widget.setText(str(val))

        val = data.get("Value", "")
        if val:
            price_str = str(int(val)) if isinstance(val, float) else str(val)
            self.w_price_min.setText(price_str)
            self.w_price_max.setText(price_str)

        desc = data.get("Description", "")
        if desc:
            self.w_description.setPlainText(desc)

    def _run_batch(self, title: str, items: list, work_fn, done_fn,
                   subtitle: str = ""):
        if not items:
            done_fn(0)
            return

        total = len(items)

        SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        spin_idx = [0]

        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setFixedSize(360, 170)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowCloseButtonHint)
        lay = QVBoxLayout(dialog)
        lay.setSpacing(8)
        lay.setContentsMargins(20, 16, 20, 16)

        top_row = QWidget()
        top_row_lay = QHBoxLayout(top_row)
        top_row_lay.setContentsMargins(0, 0, 0, 0)
        top_row_lay.setSpacing(8)
        top_row_lay.addStretch()
        spin_lbl = QLabel(SPINNER[0])
        spin_lbl.setFont(QFont("Segoe UI", 18))
        top_row_lay.addWidget(spin_lbl)
        count_lbl = QLabel(f"0 / {total}")
        count_lbl.setFont(QFont("Segoe UI", 13))
        top_row_lay.addWidget(count_lbl)
        top_row_lay.addStretch()
        lay.addWidget(top_row)

        bar = QProgressBar()
        bar.setRange(0, total)
        bar.setValue(0)
        bar.setTextVisible(False)
        bar.setFixedHeight(10)
        lay.addWidget(bar)

        sub = QLabel(subtitle)
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("color: #888888;")
        lay.addWidget(sub)

        spin_timer = QTimer(dialog)
        spin_timer.setInterval(80)
        spin_timer.timeout.connect(
            lambda: (
                spin_idx.__setitem__(0, (spin_idx[0] + 1) % len(SPINNER)),
                spin_lbl.setText(SPINNER[spin_idx[0]])
            )
        )
        spin_timer.start()

        count = [0]
        sig = _WorkerSignals()

        def _on_step():
            count[0] += 1
            count_lbl.setText(f"{count[0]} / {total}")
            bar.setValue(count[0])

        def _on_finish():
            spin_timer.stop()
            dialog.accept()
            done_fn(total)

        sig.step.connect(_on_step)
        sig.finished.connect(_on_finish)

        def _worker():
            for item in items:
                work_fn(item)
                sig.step.emit()
            sig.finished.emit()

        threading.Thread(target=_worker, daemon=True).start()
        dialog.exec()

    def _update_status(self, created: int = 0, updated: int = 0):
        ok      = sum(1 for es in self.mods_data.values() for e in es if e.status == "ok")
        bad     = sum(1 for es in self.mods_data.values() for e in es if e.status == "bad")
        missing = sum(1 for es in self.mods_data.values() for e in es if e.status == "missing")
        parts = [f"[✓]: {ok}", f"[!]: {bad}", f"[✗]: {missing}"]
        if created:
            parts.append(f"Created: {created}")
        if updated:
            parts.append(f"Updated: {updated}")
        self.status_lbl.setText("   ".join(parts))
