from aqt.qt import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QSpinBox,
    QLineEdit,
    QCheckBox,
    QPushButton,
    QListWidget,
    QLabel,
    QWidget,
    Qt,
)
from aqt.utils import tooltip
from aqt import mw

from .config import get_config, save_config

class SettingsDialog(QDialog):
    """
    Settings dialog for AnkiMorphs Sibling Manager.

    In Java Swing terms, this is a JDialog subclass.
    We inherit from QDialog and build the UI in __init__.

    All widget values are loaded from config.json when the dialog opens,
    and written back when the user clicks Save.
    """

    def __init__(self, parent: QWidget) -> None:
        # super().__init__(parent) calls QDialog's constructor.
        # 'parent' tells Qt which window owns this dialog — used for
        # centering and memory management.
        super().__init__(parent)

        self.setWindowTitle("nkiMorphs Sibling Manager — Settings")
        self.setMinimumWidth(400)

        #Build the UI first, then populate with current values
        self._setup_ui()
        self._load_values()

    # ── UI construction ───────────────────────────────────────────────────────
    def _setup_ui(self) -> None:
        """
        Builds the dialog layout and all widgets.
        Think of this like writing the HTML structure of a form.
        """
        # Root layout — everything stacks vertically
        root = QVBoxLayout()
        self.setLayout(root)

        # ── Enabled toggle ────────────────────────────────────────────────
        self._enabled_checkbox = QCheckBox("Addon enabled")
        root.addWidget(self._enabled_checkbox)

        # ── Form section (daily limit + tags) ────────────────────────────
        # QFormLayout gives us a clean label | input grid
        form = QFormLayout()
        root.addLayout(form)

        self._daily_limit_spin = QSpinBox()
        self._daily_limit_spin.setMinimum(1)
        self._daily_limit_spin.setMaximum(999)
        form.addRow("Daily Limit:", self._daily_limit_spin)

        self._auto_tag_input = QLineEdit()
        self._auto_tag_input.setFixedWidth(100)
        form.addRow("Auto Tag:", self._auto_tag_input)

        self._promote_tag_input = QLineEdit()
        self._promote_tag_input.setFixedWidth(100)
        form.addRow("Promote Tag:", self._promote_tag_input)

        self._never_promote_tag_input = QLineEdit()
        self._never_promote_tag_input.setFixedWidth(100)
        form.addRow("Never Promote Tag:", self._never_promote_tag_input)

        # ── Decks list ────────────────────────────────────────────────────
        root.addWidget(QLabel("Decks:"))

        self._deck_list = QListWidget()
        self._deck_list.setMaximumHeight(120)
        root.addWidget(self._deck_list)

        # Add / Remove buttons sit in a horizontal row below the list
        deck_buttons_row = QHBoxLayout()

        add_deck_btn = QPushButton("Add Deck")
        add_deck_btn.clicked.connect(self._add_deck)
        deck_buttons_row.addWidget(add_deck_btn)

        remove_deck_btn = QPushButton("Remove Selected")
        remove_deck_btn.clicked.connect(self._remove_deck)
        deck_buttons_row.addWidget(remove_deck_btn)

        root.addLayout(deck_buttons_row)

        # ── Save / Cancel buttons ─────────────────────────────────────────
        # addStretch() pushes the buttons to the bottom, like margin-top: auto
        root.addStretch()

        button_row = QHBoxLayout()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)  # reject() closes without saving
        button_row.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        save_btn.setDefault(True) # pressing Enter triggers this button
        button_row.addWidget(save_btn)

        root.addLayout(button_row)

    # ── Data loading ──────────────────────────────────────────────────────────

    def _load_values(self) -> None:
        """
        Reads config.json and populates all widgets with current values.
        Called once when the dialog opens.
        """
        config = get_config()
        tags = config.get("tags", {})

        self._enabled_checkbox.setChecked(config.get("enabled", True))
        self._daily_limit_spin.setValue(int(config.get("daily_limit", 10)))
        self._auto_tag_input.setText(tags.get("auto_tag", "AM-sm::reviewed-sibling"))
        self._promote_tag_input.setText(tags.get("promote_tag", "AM-sm::promote"))
        self._never_promote_tag_input.setText(tags.get("never_promote_tag", "AM-sm::never-promote"))

        self._deck_list.clear()
        for deck in config.get("decks", ["中文"]):
            self._deck_list.addItem(deck)

    # ── Deck list actions ─────────────────────────────────────────────────────
    def _add_deck(self) -> None:
        """
            Prompts for a deck name and adds it to the list.
            Uses a simple inline input dialog — no need for a separate window.
        """
        from aqt.qt import QInputDialog

        # Pull all deck names from the collection, sorted alphabetically
        deck_names = sorted(mw.col.decks.all_names())

        deck_name, confirmed = QInputDialog.getItem(
            self,
            "Add Deck",
            "Select a deck:",
            deck_names,
            0,  # index of pre-selected item
            False  # False = not editable, user must pick from list
        )

        if not confirmed or not deck_name:
            return

        # Don't add duplicates
        existing = [
            self._deck_list.item(i).text()
            for i in range(self._deck_list.count())
        ]
        if deck_name in existing:
            tooltip(f"'{deck_name}' is already in the list.")
            return

        self._deck_list.addItem(deck_name)

    def _remove_deck(self) -> None:
        """Removes the currently selected item from the deck list."""
        selected = self._deck_list.currentRow()

        # currentRow() returns -1 if nothing is selected
        if selected >= 0:
            self._deck_list.takeItem(selected)

    # ── Save ──────────────────────────────────────────────────────────────────

    def _save(self) -> None:
        """
        Reads all widget values, validates them, writes to config.json,
        then closes the dialog.
        """
        # Read the deck list — items are QListWidgetItem objects, not strings,
        # so we call .text() on each one
        decks = [
            self._deck_list.item(i).text()
            for i in range(self._deck_list.count())
        ]

        if not decks:
            tooltip("Add at least one deck before saving.")
            return

        auto_tag = self._auto_tag_input.text().strip()
        promote_tag = self._promote_tag_input.text().strip()
        never_promote_tag = self._never_promote_tag_input.text().strip()

        if not all([auto_tag, promote_tag, never_promote_tag]):
            tooltip("Tag fields cannot be empty.")
            return

        new_config = {
            "enabled": self._enabled_checkbox.isChecked(),
            "daily_limit": self._daily_limit_spin.value(),
            "decks": decks,
            "tags": {
                "auto_tag": auto_tag,
                "promote_tag": promote_tag,
                "never_promote_tag": never_promote_tag,
            }
        }

        save_config(new_config)
        tooltip("Settings saved.")

        # accept() closes the dialog and signals success (like clicking OK)
        self.accept()