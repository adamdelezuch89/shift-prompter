#!/usr/bin/env python3
"""
Shift-Prompter - A tool for quickly pasting predefined text snippets.

This application listens for a global hotkey (double-press of Shift),
opens a window with a list of user-defined prompts, and upon selection,
pastes the content at the current cursor position.
Data is stored persistently in ~/.config/Shift-Prompter/
"""

import os
import sys
import time
import json
import signal
import subprocess
from pathlib import Path
from pynput import keyboard
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QMessageBox, QLineEdit, QDialog,
    QDialogButtonBox, QFormLayout, QTreeWidget, QTreeWidgetItem,
    QInputDialog, QComboBox, QHBoxLayout, QAbstractItemView,
    QLabel, QSizePolicy, QPlainTextEdit, QTreeWidgetItemIterator, QStackedLayout, QStyle
)
from PyQt6.QtCore import Qt, QEvent, QObject, pyqtSignal, QPoint, QRect
from PyQt6.QtGui import QCursor, QGuiApplication, QIcon

# --- Application Configuration ---
CONFIG_DIR = Path.home() / ".config" / "Shift-Prompter"
PROMPTS_FILE = CONFIG_DIR / "prompts.json"
DOUBLE_TAP_THRESHOLD_S = 0.4
DATA_VERSION = 2

class PromptDialog(QDialog):
    """A dialog window for adding and editing prompts with category support."""
    def __init__(self, parent=None, name="", content="", categories=None, current_category=""):
        super().__init__(parent)
        self.setWindowTitle("Manage Prompt")
        self.resize(600, 500)

        self.name_input = QLineEdit(name)
        
        self.content_input = QPlainTextEdit(content)
        self.content_input.setMinimumHeight(300)
        self.content_input.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        
        self.select_widget = QWidget()
        select_layout = QHBoxLayout(self.select_widget)
        select_layout.setContentsMargins(0, 0, 0, 0)
        self.category_combo = QComboBox()
        if categories: self.category_combo.addItems(categories)
        if current_category and current_category in categories: self.category_combo.setCurrentText(current_category)
        
        add_category_button = QPushButton(QIcon.fromTheme("list-add"), "")
        add_category_button.setFixedSize(28, 28); add_category_button.setToolTip("Add a new category")
        add_category_button.clicked.connect(self.show_add_category_ui)
        
        select_layout.addWidget(self.category_combo)
        select_layout.addWidget(add_category_button)

        self.create_widget = QWidget()
        create_layout = QHBoxLayout(self.create_widget)
        create_layout.setContentsMargins(0, 0, 0, 0)
        self.new_category_input = QLineEdit()
        self.new_category_input.setPlaceholderText("Enter new category name...")
        
        save_button = QPushButton(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton), "")
        save_button.setFixedSize(28, 28); save_button.setToolTip("Save")
        save_button.clicked.connect(self.save_new_category)
        
        cancel_button = QPushButton(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton), "")
        cancel_button.setFixedSize(28, 28); cancel_button.setToolTip("Cancel")
        cancel_button.clicked.connect(self.show_select_category_ui)
        
        create_layout.addWidget(self.new_category_input)
        create_layout.addWidget(save_button)
        create_layout.addWidget(cancel_button)

        self.stacked_layout = QStackedLayout()
        self.stacked_layout.addWidget(self.select_widget)
        self.stacked_layout.addWidget(self.create_widget)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)

        layout = QFormLayout(self)
        layout.addRow("Name:", self.name_input)
        layout.addRow("Category:", self.stacked_layout)
        layout.addRow("Content:", self.content_input)
        layout.addWidget(buttons)

    def show_add_category_ui(self):
        self.stacked_layout.setCurrentIndex(1); self.new_category_input.setFocus()

    def show_select_category_ui(self):
        self.new_category_input.clear(); self.stacked_layout.setCurrentIndex(0)

    def save_new_category(self):
        text = self.new_category_input.text().strip()
        if text:
            if self.category_combo.findText(text) == -1: self.category_combo.addItem(text)
            self.category_combo.setCurrentText(text)
        self.show_select_category_ui()

    def get_data(self):
        return self.name_input.text(), self.content_input.toPlainText(), self.category_combo.currentText()

class PromptTreeWidget(QTreeWidget):
    """Custom QTreeWidget to handle drag-and-drop and display custom item widgets."""
    def __init__(self, prompt_window):
        super().__init__()
        self.prompt_window = prompt_window
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setHeaderHidden(True)
        self.setColumnCount(1)
        self.setIndentation(15)

    def dropEvent(self, event):
        target_item = self.itemAt(event.position().toPoint())
        dragged_item = self.selectedItems()[0]
        if not dragged_item or not target_item:
            event.ignore(); return
            
        dragged_data = dragged_item.data(0, Qt.ItemDataRole.UserRole)
        target_data = target_item.data(0, Qt.ItemDataRole.UserRole)
        
        # Scenario 1: Reordering categories.
        if dragged_data["is_category"] and target_data["is_category"] and dragged_data["name"] != target_data["name"]:
            self.prompt_window.handle_category_reorder(dragged_data["name"], target_data["name"])
            event.accept()
            return
        
        # Scenario 2: A prompt is being dragged.
        if not dragged_data["is_category"]:
            target_is_prompt = not target_data["is_category"]
            target_category_item = target_item.parent() if target_is_prompt else target_item
            
            # Sub-scenario 2a: Reordering prompts within the same category.
            if dragged_item.parent() == target_category_item:
                if target_is_prompt and dragged_data["name"] != target_data["name"]:
                    self.prompt_window.handle_prompt_reorder(
                        category_name=target_category_item.data(0, Qt.ItemDataRole.UserRole)["name"],
                        dragged_prompt_name=dragged_data["name"],
                        target_prompt_name=target_data["name"]
                    )
                    event.accept()
                    return
            # Sub-scenario 2b: Moving a prompt to a different category.
            else:
                self.prompt_window.handle_prompt_move(
                    prompt_name=dragged_data["name"],
                    old_c_name=dragged_item.parent().data(0, Qt.ItemDataRole.UserRole)["name"],
                    new_c_name=target_category_item.data(0, Qt.ItemDataRole.UserRole)["name"]
                )
                event.accept()
                return

        event.ignore()

class PromptWindow(QWidget):
    """The main application window that displays the list of prompts."""
    UNCATEGORIZED_NAME = "Uncategorized"

    def __init__(self, app_controller):
        super().__init__()
        self.app = app_controller; self.prompts_data = {}
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.init_ui()
        self.load_prompts()

    def init_ui(self):
        self.setFixedWidth(320)
        self.setWindowTitle("Shift-Prompter")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setObjectName("promptWindow")
        self.setStyleSheet("""
            #promptWindow { background-color: #495e80; border: 1px solid #000000; border-radius: 8px; }
            QPushButton { padding: 5px; }
            QPushButton#ActionIcon { border: none; background: transparent; padding: 2px; }
        """)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10) 
        
        self.tree_widget = PromptTreeWidget(self)
        self.tree_widget.itemDoubleClicked.connect(self.item_selected)
        self.tree_widget.itemExpanded.connect(lambda item: self.on_item_expansion_changed(item, True))
        self.tree_widget.itemCollapsed.connect(lambda item: self.on_item_expansion_changed(item, False))

        add_prompt_button = QPushButton("Add Prompt")
        add_cat_button = QPushButton("Add Category")
        add_prompt_button.clicked.connect(self.add_prompt)
        add_cat_button.clicked.connect(self.add_category)

        self.button_layout = QHBoxLayout()
        self.button_layout.addWidget(add_prompt_button)
        self.button_layout.addWidget(add_cat_button)
        self.main_layout.addWidget(self.tree_widget)
        self.main_layout.addLayout(self.button_layout)

    def event(self, event):
        if event.type() == QEvent.Type.WindowDeactivate: self.hide()
        return super().event(event)

    def migrate_prompts_data(self, old_data):
        return {"version": DATA_VERSION, "categories": [], "uncategorized": old_data}

    def load_prompts(self):
        try:
            if PROMPTS_FILE.exists():
                with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.prompts_data = self.migrate_prompts_data(data) if isinstance(data, list) else data
            else:
                self.prompts_data = { "version": DATA_VERSION, "categories": [{"name": "Email", "prompts": [{"name": "Closing", "content": "Kind regards,\n\n"}], "expanded": True}], "uncategorized": [{"name": "Quick Question", "content": "Hi, I have a quick question: "}], "uncategorized_expanded": True }
            
            if "uncategorized" not in self.prompts_data: self.prompts_data["uncategorized"] = []
            if "uncategorized_expanded" not in self.prompts_data: self.prompts_data["uncategorized_expanded"] = True
            for category in self.prompts_data.get("categories", []):
                if "expanded" not in category: category["expanded"] = True
            self.save_prompts(); self.refresh_list()
        except (IOError, json.JSONDecodeError) as e: QMessageBox.warning(self, "Error", f"Could not load prompts: {e}")

    def save_prompts(self):
        try:
            with open(PROMPTS_FILE, "w", encoding="utf-8") as f: json.dump(self.prompts_data, f, indent=4, ensure_ascii=False)
        except IOError as e: QMessageBox.warning(self, "Error", f"Could not save prompts: {e}")
            
    def _create_item_widget(self, name, item_data):
        widget, layout = QWidget(), QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        label = QLabel(name)
        label.setToolTip(name)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(label)
        
        if not (item_data["is_category"] and name == self.UNCATEGORIZED_NAME):
            edit_button = QPushButton(QIcon.fromTheme("document-edit-symbolic", QIcon.fromTheme("document-edit")), "")
            edit_button.setObjectName("ActionIcon"); edit_button.setFixedSize(22, 22); edit_button.setToolTip("Edit")
            edit_button.clicked.connect(lambda: self.edit_item(item_data))
            layout.addWidget(edit_button)
            delete_button = QPushButton(QIcon.fromTheme("edit-delete-symbolic", QIcon.fromTheme("user-trash")), "")
            delete_button.setObjectName("ActionIcon"); delete_button.setFixedSize(22, 22); delete_button.setToolTip("Delete")
            delete_button.clicked.connect(lambda: self.delete_item(item_data))
            layout.addWidget(delete_button)
        widget.setLayout(layout)
        return widget

    def refresh_list(self):
        self.tree_widget.clear()
        for category in self.prompts_data.get("categories", []): self.create_category_item(category)
        
        if self.prompts_data.get("uncategorized"):
            unc_data = {"name": self.UNCATEGORIZED_NAME, "is_category": True}
            unc_item = QTreeWidgetItem(self.tree_widget)
            unc_item.setData(0, Qt.ItemDataRole.UserRole, unc_data)
            unc_item.setFlags(unc_item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled)
            self.tree_widget.setItemWidget(unc_item, 0, self._create_item_widget(self.UNCATEGORIZED_NAME, unc_data))
            unc_item.setExpanded(self.prompts_data.get("uncategorized_expanded", True))
            for prompt in self.prompts_data.get("uncategorized", []): self.create_prompt_item(prompt, self.UNCATEGORIZED_NAME, unc_item)

    def create_category_item(self, cat_dict):
        cat_data = {"name": cat_dict["name"], "is_category": True}
        cat_item = QTreeWidgetItem(self.tree_widget)
        cat_item.setData(0, Qt.ItemDataRole.UserRole, cat_data)
        cat_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDropEnabled | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsDragEnabled)
        self.tree_widget.setItemWidget(cat_item, 0, self._create_item_widget(cat_dict["name"], cat_data))
        cat_item.setExpanded(cat_dict.get("expanded", True))
        for prompt in cat_dict.get("prompts", []): self.create_prompt_item(prompt, cat_dict["name"], cat_item)

    def create_prompt_item(self, prompt_dict, cat_name, parent_item):
        prompt_data = {"name": prompt_dict["name"], "category": cat_name, "is_category": False}
        prompt_item = QTreeWidgetItem(parent_item)
        prompt_item.setData(0, Qt.ItemDataRole.UserRole, prompt_data)
        prompt_item.setFlags(prompt_item.flags() | Qt.ItemFlag.ItemIsDragEnabled)
        self.tree_widget.setItemWidget(prompt_item, 0, self._create_item_widget(prompt_dict["name"], prompt_data))

    def get_category_names(self):
        return [self.UNCATEGORIZED_NAME] + [c["name"] for c in self.prompts_data.get("categories", [])]

    def find_prompt_list(self, category_name):
        if category_name == self.UNCATEGORIZED_NAME: return self.prompts_data.get("uncategorized", [])
        return next((c.get("prompts", []) for c in self.prompts_data.get("categories", []) if c["name"] == category_name), None)

    def on_item_expansion_changed(self, item, expanded):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and data["is_category"]:
            if data["name"] == self.UNCATEGORIZED_NAME: self.prompts_data["uncategorized_expanded"] = expanded
            else:
                for category in self.prompts_data.get("categories", []):
                    if category["name"] == data["name"]: category["expanded"] = expanded; break
            self.save_prompts()

    def add_prompt(self):
        dialog = PromptDialog(self, categories=self.get_category_names())
        if dialog.exec():
            name, content, category_name = dialog.get_data()
            if not (name and content): return QMessageBox.warning(self, "Input Error", "Name and content cannot be empty.")
            new_prompt = {"name": name, "content": content}
            prompt_list = self.find_prompt_list(category_name)
            if prompt_list is not None: prompt_list.append(new_prompt)
            self.save_prompts(); self.refresh_list()

    def add_category(self):
        text, ok = QInputDialog.getText(self, "New Category", "Enter new category name:")
        if ok and text:
            if text in self.get_category_names(): return QMessageBox.warning(self, "Error", "A category with this name already exists.")
            self.prompts_data.setdefault("categories", []).append({"name": text, "prompts": [], "expanded": True})
            self.save_prompts(); self.refresh_list()

    def edit_item(self, item_data):
        if item_data["is_category"]:
            old_name, new_name, ok = item_data["name"], *QInputDialog.getText(self, "Edit Category", "Enter new name:", text=item_data["name"])
            if ok and new_name and new_name != old_name:
                if new_name in self.get_category_names(): return QMessageBox.warning(self, "Error", "Category name exists.")
                for cat in self.prompts_data["categories"]:
                    if cat["name"] == old_name: cat["name"] = new_name; break
                self.save_prompts(); self.refresh_list()
        else:
            p_name, c_name = item_data["name"], item_data["category"]
            p_list = self.find_prompt_list(c_name)
            prompt = next((p for p in p_list if p["name"] == p_name), None) if p_list is not None else None
            if not prompt: return
            dialog = PromptDialog(self, name=p_name, content=prompt["content"], categories=self.get_category_names(), current_category=c_name)
            if dialog.exec():
                new_n, new_c, new_cat_n = dialog.get_data()
                if not (new_n and new_c): return QMessageBox.warning(self, "Input Error", "Fields cannot be empty.")
                p_list.remove(prompt)
                upd_prompt = {"name": new_n, "content": new_c}
                new_p_list = self.find_prompt_list(new_cat_n)
                if new_p_list is not None: new_p_list.append(upd_prompt)
                self.save_prompts(); self.refresh_list()

    def delete_item(self, item_data):
        name = item_data["name"]
        if item_data["is_category"]:
            if name == self.UNCATEGORIZED_NAME: return
            if QMessageBox.question(self, "Confirm", f"Delete '{name}'?\nPrompts will move to Uncategorized.") == QMessageBox.StandardButton.Yes:
                cat = next((c for c in self.prompts_data["categories"] if c["name"] == name), None)
                if cat:
                    self.prompts_data.setdefault("uncategorized", []).extend(cat["prompts"])
                    self.prompts_data["categories"].remove(cat)
                    self.save_prompts(); self.refresh_list()
        else:
            if QMessageBox.question(self, "Confirm", f"Delete prompt '{name}'?") == QMessageBox.StandardButton.Yes:
                p_list = self.find_prompt_list(item_data["category"])
                prompt = next((p for p in p_list if p["name"] == name), None) if p_list is not None else None
                if prompt: p_list.remove(prompt); self.save_prompts(); self.refresh_list()
    
    def handle_prompt_move(self, prompt_name, old_c_name, new_c_name):
        old_p_list = self.find_prompt_list(old_c_name)
        prompt = next((p for p in old_p_list if p["name"] == prompt_name), None) if old_p_list is not None else None
        if prompt:
            old_p_list.remove(prompt)
            new_p_list = self.find_prompt_list(new_c_name)
            if new_p_list is not None: new_p_list.append(prompt)
            self.save_prompts(); self.refresh_list()
    
    def handle_prompt_reorder(self, category_name, dragged_prompt_name, target_prompt_name):
        prompt_list = self.find_prompt_list(category_name)
        if prompt_list is None: return
        dragged_idx = next((i for i, p in enumerate(prompt_list) if p["name"] == dragged_prompt_name), -1)
        target_idx = next((i for i, p in enumerate(prompt_list) if p["name"] == target_prompt_name), -1)
        if dragged_idx != -1 and target_idx != -1:
            moved_item = prompt_list.pop(dragged_idx)
            prompt_list.insert(target_idx, moved_item)
            self.save_prompts(); self.refresh_list()

    def handle_category_reorder(self, dragged_name, target_name):
        cats = self.prompts_data["categories"]
        drag_idx = next((i for i, c in enumerate(cats) if c["name"] == dragged_name), -1)
        target_idx = next((i for i, c in enumerate(cats) if c["name"] == target_name), -1)
        if drag_idx != -1 and target_idx != -1:
            cats.insert(target_idx, cats.pop(drag_idx))
            self.save_prompts(); self.refresh_list()

    def item_selected(self, item, col):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and not data["is_category"]:
            p_list = self.find_prompt_list(data["category"])
            p = next((p for p in p_list if p["name"] == data["name"]), None) if p_list is not None else None
            if p: self.hide(); self.app.inject_text(p["content"])
            
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape: self.hide()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.tree_widget.currentItem(): self.item_selected(self.tree_widget.currentItem(), 0)

# --- Application Core ---
class ShiftPrompterApp(QObject):
    toggle_window_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.last_shift_press_time = 0
        self.prompt_window = PromptWindow(self)
        self.toggle_window_signal.connect(self.toggle_window)
        signal.signal(signal.SIGINT, self.handle_exit); signal.signal(signal.SIGTERM, self.handle_exit)

    def handle_exit(self, *args):
        print("\nClosing Shift-Prompter..."); QApplication.instance().quit()

    def on_shift_press(self, key):
        if key in {keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r}:
            current_time = time.monotonic()
            if (current_time - self.last_shift_press_time) < DOUBLE_TAP_THRESHOLD_S: self.toggle_window_signal.emit()
            self.last_shift_press_time = current_time

    def toggle_window(self):
        if self.prompt_window.isVisible(): self.prompt_window.hide()
        else:
            self.prompt_window.refresh_list()
            iterator = QTreeWidgetItemIterator(self.prompt_window.tree_widget)
            visible_rows, row_height = 0, self.prompt_window.tree_widget.sizeHintForRow(0)
            if row_height <= 0: row_height = 28
            while iterator.value():
                if not iterator.value().isHidden(): visible_rows += 1
                iterator += 1
            
            margins = self.prompt_window.main_layout.contentsMargins()
            buttons_height = self.prompt_window.button_layout.sizeHint().height()
            spacing = self.prompt_window.main_layout.spacing()
            total_height = (row_height * visible_rows) + buttons_height + margins.top() + margins.bottom() + spacing + 5

            max_height = int(QGuiApplication.primaryScreen().availableGeometry().height() * 0.6)
            self.prompt_window.resize(self.prompt_window.width(), min(total_height, max_height))
            self.position_window_near_cursor()
            self.prompt_window.show()
            self.prompt_window.activateWindow(); self.prompt_window.raise_()
            self.prompt_window.tree_widget.setFocus()

    def position_window_near_cursor(self):
        screen_rect = (QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()).availableGeometry()
        cursor_pos, win_size, margin = QCursor.pos(), self.prompt_window.size(), 10
        x = max(screen_rect.left() + margin, min(cursor_pos.x(), screen_rect.right() - win_size.width() - margin))
        y = max(screen_rect.top() + margin, min(cursor_pos.y(), screen_rect.bottom() - win_size.height() - margin))
        self.prompt_window.move(x, y)

    def inject_text(self, text: str):
        try:
            if os.getenv('XDG_SESSION_TYPE', '').lower() == 'wayland':
                subprocess.run(['wl-copy'], text=True, check=True, input=text)
                subprocess.run(['wtype', '-M', 'shift', '-P', 'insert', '-m', 'shift'], check=True)
            else:
                subprocess.run(['xclip', '-selection', 'clipboard'], text=True, check=True, input=text)
                subprocess.run(['xdotool', 'key', '--clearmodifiers', 'ctrl+v'], check=True)
            print(f"✅ Pasted: '{text[:30].strip()}...'")
        except FileNotFoundError as e:
            msg = f"Missing tool: {e.filename}. Is it installed?"
            QMessageBox.critical(None, "Error", msg); print(f"❌ {msg}")
        except Exception as e:
            msg = f"Pasting error: {e}"
            QMessageBox.critical(None, "Error", msg); print(f"❌ {msg}")

    def run(self):
        print("🚀 Shift-Prompter is active. (Press Ctrl+C to exit)")
        listener = keyboard.Listener(on_press=self.on_shift_press); listener.start()
        app = QApplication.instance()
        app.aboutToQuit.connect(listener.stop)
        self.prompt_window.hide(); sys.exit(app.exec())

if __name__ == "__main__":
    q_app = QApplication.instance() or QApplication(sys.argv)
    app = ShiftPrompterApp()
    app.run()