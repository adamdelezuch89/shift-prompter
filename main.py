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
    QApplication, QWidget, QVBoxLayout, QListWidget, QPushButton,
    QMessageBox, QLineEdit, QTextEdit, QDialog,
    QDialogButtonBox, QFormLayout, QListWidgetItem
)
from PyQt6.QtCore import Qt, QEvent, QObject, pyqtSignal, QPoint, QRect, QTimer
from PyQt6.QtGui import QCursor, QGuiApplication

# --- Application Configuration ---
CONFIG_DIR = Path.home() / ".config" / "Shift-Prompter"
PROMPTS_FILE = CONFIG_DIR / "prompts.json"
DOUBLE_TAP_THRESHOLD_S = 0.4

class PromptDialog(QDialog):
    """A dialog window for adding and editing prompts."""
    def __init__(self, parent=None, name="", content=""):
        super().__init__(parent)
        self.setWindowTitle("Manage Prompt")
        self.name_input = QLineEdit(name)
        self.content_input = QTextEdit(content)
        self.content_input.setAcceptRichText(False)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QFormLayout(self)
        layout.addRow("Name:", self.name_input)
        layout.addRow("Content:", self.content_input)
        layout.addWidget(buttons)

    def get_data(self):
        return self.name_input.text(), self.content_input.toPlainText()

class PromptWindow(QWidget):
    """The main application window that displays the list of prompts."""
    def __init__(self, app_controller):
        super().__init__()
        self.app = app_controller
        self.prompts = []
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.init_ui()
        self.load_prompts()

    def init_ui(self):
        self.setWindowTitle("Shift-Prompter")
        # --- ZMIANY ZNAJDUJĄ SIĘ TUTAJ ---
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        
        # 1. Usunięcie atrybutu przezroczystości
        # self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) 
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        # 2. Dodanie stylu tła i wyglądu za pomocą arkusza stylów
        # Ustawiamy nazwę obiektu, aby styl dotyczył tylko tego konkretnego okna, a nie jego dzieci (np. przycisków)
        self.setObjectName("promptWindow")
        self.setStyleSheet("""
            #promptWindow {
                background-color: #495e80; /* Kolor "AliceBlue", bardzo jasny niebieski */
                border: 1px solid #000000;   /* Jasna stalowa ramka */
                border-radius: 8px;          /* Zaokrąglone rogi */
            }
        """)
        # --- KONIEC ZMIAN ---

        layout = QVBoxLayout()
        # Dodajemy marginesy, aby zawartość nie przylegała do krawędzi okna
        layout.setContentsMargins(10, 10, 10, 10) 
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.item_selected)

        add_button = QPushButton("Add")
        edit_button = QPushButton("Edit")
        delete_button = QPushButton("Delete")

        add_button.clicked.connect(self.add_prompt)
        edit_button.clicked.connect(self.edit_prompt)
        delete_button.clicked.connect(self.delete_prompt)

        layout.addWidget(self.list_widget)
        layout.addWidget(add_button)
        layout.addWidget(edit_button)
        layout.addWidget(delete_button)
        self.setLayout(layout)

    def event(self, event):
        if event.type() == QEvent.Type.WindowDeactivate:
            self.hide()
        return super().event(event)

    def load_prompts(self):
        try:
            if PROMPTS_FILE.exists():
                with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
                    self.prompts = json.load(f)
            else:
                self.prompts = [
                    {"name": "Polite Email Closing", "content": "Kind regards,\n\n"},
                    {"name": "Quick Question", "content": "Hi, I have a quick question: "}
                ]
                self.save_prompts()
            self.refresh_list()
        except (IOError, json.JSONDecodeError) as e:
            QMessageBox.warning(self, "Error", f"Could not load prompts: {e}")

    def save_prompts(self):
        try:
            with open(PROMPTS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.prompts, f, indent=4, ensure_ascii=False)
        except IOError as e:
            QMessageBox.warning(self, "Error", f"Could not save prompts: {e}")

    def refresh_list(self):
        self.list_widget.clear()
        for prompt in self.prompts:
            self.list_widget.addItem(QListWidgetItem(prompt["name"]))

    def add_prompt(self):
        dialog = PromptDialog(self)
        if dialog.exec():
            name, content = dialog.get_data()
            if name and content:
                self.prompts.append({"name": name, "content": content})
                self.save_prompts()
                self.refresh_list()
            else:
                QMessageBox.warning(self, "Input Error", "Name and content cannot be empty.")

    def edit_prompt(self):
        selected_item = self.list_widget.currentItem()
        if not selected_item:
            return
        
        index = self.list_widget.row(selected_item)
        prompt = self.prompts[index]

        dialog = PromptDialog(self, name=prompt["name"], content=prompt["content"])
        if dialog.exec():
            name, content = dialog.get_data()
            if name and content:
                self.prompts[index] = {"name": name, "content": content}
                self.save_prompts()
                self.refresh_list()
            else:
                QMessageBox.warning(self, "Input Error", "Name and content cannot be empty.")

    def delete_prompt(self):
        selected_item = self.list_widget.currentItem()
        if not selected_item:
            return

        reply = QMessageBox.question(self, "Confirm Deletion", "Are you sure you want to delete this prompt?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            index = self.list_widget.row(selected_item)
            del self.prompts[index]
            self.save_prompts()
            self.refresh_list()

    def item_selected(self, item):
        index = self.list_widget.row(item)
        content = self.prompts[index]["content"]
        self.hide()
        self.app.inject_text(content)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.list_widget.currentItem():
                self.item_selected(self.list_widget.currentItem())

# --- Application Core ---
class ShiftPrompterApp(QObject):
    """The main application class, managing logic and keyboard listening."""
    toggle_window_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.last_shift_press_time = 0
        self.prompt_window = PromptWindow(self)
        self.toggle_window_signal.connect(self.toggle_window)
        signal.signal(signal.SIGINT, self.handle_exit)
        signal.signal(signal.SIGTERM, self.handle_exit)

    def handle_exit(self, *args):
        print("\nClosing Shift-Prompter...")
        QApplication.instance().quit()

    def on_shift_press(self, key):
        if key in {keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r}:
            current_time = time.monotonic()
            time_diff = current_time - self.last_shift_press_time
            self.last_shift_press_time = current_time

            if time_diff < DOUBLE_TAP_THRESHOLD_S:
                self.toggle_window_signal.emit()

    def toggle_window(self):
        if self.prompt_window.isVisible():
            self.prompt_window.hide()
        else:
            self.prompt_window.refresh_list()
            self.position_window_near_cursor()
            self.prompt_window.show()
            self.prompt_window.activateWindow()
            self.prompt_window.raise_()
            self.prompt_window.list_widget.setFocus()

    def position_window_near_cursor(self):
        screen = QGuiApplication.screenAt(QCursor.pos())
        if not screen:
            return

        screen_rect: QRect = screen.availableGeometry()
        cursor_pos: QPoint = QCursor.pos()

        self.prompt_window.adjustSize()
        win_size = self.prompt_window.size()

        margin = 10
        x = min(cursor_pos.x(), screen_rect.right() - win_size.width() - margin)
        y = min(cursor_pos.y(), screen_rect.bottom() - win_size.height() - margin)

        x = max(x, screen_rect.left() + margin)
        y = max(y, screen_rect.top() + margin)

        self.prompt_window.move(x, y)

    def inject_text(self, text: str):
        try:
            session_type = os.getenv('XDG_SESSION_TYPE', '').lower()
            if session_type == 'wayland':
                subprocess.run(['wl-copy'], text=True, check=True, input=text)
                subprocess.run(['wtype', '-M', 'shift', '-P', 'insert', '-m', 'shift'], check=True)
            else:
                subprocess.run(['xclip', '-selection', 'clipboard'], text=True, check=True, input=text)
                subprocess.run(['xdotool', 'key', '--clearmodifiers', 'ctrl+v'], check=True)
            print(f"✅ Pasted text: '{text[:30]}...'")
        except FileNotFoundError as e:
            error_msg = f"Missing tool: {e.filename}. Please check if it's installed."
            QMessageBox.critical(None, "Critical Error", error_msg)
            print(f"❌ {error_msg}")
        except Exception as e:
            error_msg = f"Error while pasting text: {e}"
            QMessageBox.critical(None, "Critical Error", error_msg)
            print(f"❌ {error_msg}")

    def run(self):
        print("🚀 Shift-Prompter is active.")
        print("👂 Double-press Shift to open the window.")
        print("ℹ️ Press Ctrl+C in the terminal to exit.")

        listener = keyboard.Listener(on_press=self.on_shift_press)
        listener.start()

        app = QApplication(sys.argv)
        app.aboutToQuit.connect(lambda: listener.stop())
        self.prompt_window.hide()
        sys.exit(app.exec())
if __name__ == "__main__":
    q_app = QApplication(sys.argv)
    # The application logic is now in a QObject
    app = ShiftPrompterApp()
    app.run()