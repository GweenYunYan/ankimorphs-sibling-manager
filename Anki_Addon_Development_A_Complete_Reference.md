# Anki Addon Development: The Complete Reference

A practical, example-driven guide to building, debugging, and maintaining Anki addons — from your first "Hello World" to publishing on AnkiWeb. All examples are drawn from real addons and reflect modern Anki (2.1.60+ / Qt6).

---

## Table of Contents

1. [Overview & Prerequisites](#1-overview--prerequisites)
2. [Project Setup](#2-project-setup)
3. [Quick Start: Your First Addon](#3-quick-start-your-first-addon)
4. [How Anki Loads Addons](#4-how-anki-loads-addons)
5. [The Anki API: Collections, Cards & Notes](#5-the-anki-api-collections-cards--notes)
6. [Reacting to Anki: The Hooks System](#6-reacting-to-anki-the-hooks-system)
7. [Building User Interfaces with Qt](#7-building-user-interfaces-with-qt)
8. [Heavy Operations: Background Threads](#8-heavy-operations-background-threads)
9. [Saving Data: Config & State](#9-saving-data-config--state)
10. [Integrating with Other Addons](#10-integrating-with-other-addons)
11. [Debugging & Troubleshooting](#11-debugging--troubleshooting)
12. [Production Best Practices](#12-production-best-practices)
13. [Editing and Maintaining Others' Addons](#13-editing-and-maintaining-others-addons)
14. [Sharing & Distribution](#14-sharing--distribution)
15. [Quick Reference Cheat Sheet](#15-quick-reference-cheat-sheet)
16. [Python Patterns for Anki Developers](#16-python-patterns-for-anki-developers)
17. [Glossary](#17-glossary)

---

## 1. Overview & Prerequisites

### What This Guide Covers

| Topic | What You'll Learn |
|---|---|
| **Environment** | PyCharm, type stubs, live-reload via symlinks |
| **Architecture** | The boundary between `anki` (backend) and `aqt` (UI) |
| **Data API** | Searching, reading, and modifying cards, notes, and tags |
| **Events** | Hooks, signals, and when to use each |
| **UI** | Qt widgets, dialogs, menus, and input forms |
| **Threading** | Running heavy logic without freezing Anki |
| **Integration** | Talking to other addons, monkey-patching safely |
| **Persistence** | Config, state, and per-profile settings |
| **Debugging** | Console output, logging, IDE breakpoints |
| **Shipping** | GitHub Actions, `.ankiaddon` packaging, AnkiWeb |

### What You Should Already Know

- [ ] **Python 3.9+**: syntax, data structures, functions, and basic OOP
- [ ] **Git**: committing, branching, and tagging
- [ ] **Anki**: daily use of decks, cards, notes, the browser, and note types
- [ ] **Optional**: basic SQL (`SELECT`, `WHERE`, `JOIN`) for advanced queries

> **New to Python?** Skip to [Section 16: Python Patterns for Anki Developers](#16-python-patterns-for-anki-developers) for a condensed primer on the idioms used throughout this guide.

### The Two Anki Modules

Every addon imports from two namespaces. Understanding their separation prevents architecture mistakes.

| Module | Purpose | Lives In | Example Import |
|---|---|---|---|
| **`anki`** | Backend engine: database, schedulers, search logic | Headless (no screen) | `from anki.collection import Collection` |
| **`aqt`** | Qt UI layer: windows, dialogs, webviews | Requires running Anki | `from aqt import mw` |

**Rule of thumb**: If it touches the screen, it lives in `aqt`. If it touches the database, it lives in `anki`.

```python
# Backend: querying the collection
from anki.consts import CARD_TYPE_NEW
from anki.utils import ids2str

# UI: showing a dialog
from aqt import mw
from aqt.utils import showInfo
from aqt.qt import QPushButton
```

---

## 2. Project Setup

### IDE: PyCharm Community Edition

The Anki docs recommend PyCharm (free). Download at [jetbrains.com/pycharm](https://www.jetbrains.com/pycharm/).

After creating a project, install Anki's type stubs so PyCharm can autocomplete API calls and flag type errors before you run:

```bash
pip3 install --upgrade pip
pip3 install "aqt[qt6]"
```

> **You cannot run addon code directly from PyCharm.** Addons must execute inside a live Anki process. PyCharm is for editing, linting, and debugging only.

### Folder Structure

Anki loads addons from a special folder:

| OS | Path |
|---|---|
| macOS | `~/Library/Application Support/Anki2/addons21/` |
| Windows | `%APPDATA%\Anki2\addons21\` |
| Linux | `~/.local/share/Anki2/addons21/` |

Inside `addons21/`, each subfolder is one addon **package**:

```
addons21/
    your_addon_name/          <- must be a valid Python identifier (underscores only)
        __init__.py           <- entry point. Anki runs this on startup.
        other_module.py
        config.json           <- default user settings (shipped with addon)
        manifest.json         <- addon metadata (required for sharing)
        meta.json             <- Anki's internal metadata (do not commit)
        state.json            <- runtime state (gitignored)
```

> **Folder naming**: The folder name must be a valid Python identifier — underscores only, no hyphens, cannot start with a number. The repo root can use hyphens (`your-addon-repo`), but the Python package inside must use underscores (`your_addon_name`).

### Symlinks for Live Development

Instead of copying files after every change, create a **symbolic link** so Anki reads your live project files:

```bash
# macOS / Linux
ln -s /path/to/your/project/your_addon_name \
  ~/Library/Application\ Support/Anki2/addons21/your_addon_name

# Windows (PowerShell, as Admin)
New-Item -ItemType SymbolicLink `
  -Path "$env:APPDATA\Anki2\addons21\your_addon_name" `
  -Target "C:\path\to\your\project\your_addon_name"
```

Verify:
```bash
ls -la ~/Library/Application\ Support/Anki2/addons21/
# -> your_addon_name -> /path/to/your/project/your_addon_name
```

**Workflow**: save in PyCharm -> restart Anki -> changes are live. No copying.

### GitHub Repository Structure

```
your-addon-repo/                 <- GitHub repo root (hyphens OK)
    your_addon_name/             <- the Python package (underscores only)
        __init__.py
        config.json
        manifest.json
    .github/
        workflows/
            build.yml            <- auto-builds .ankiaddon on tag push
    .gitignore
    README.md
    CHANGELOG.md                 <- track version history
```

`.gitignore`:
```gitignore
__pycache__/
*.pyc
*.pyo
.DS_Store
*.ankiaddon
.idea/
meta.json          <- Anki generates this; don't commit
state.json         <- runtime state; don't commit
```

#### GitHub Actions: Auto-Build on Tag

When you push a version tag (e.g., `v1.0.0`), this workflow creates a `.ankiaddon` file and attaches it to a GitHub Release:

```yaml
# .github/workflows/build.yml
name: Build Addon

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build .ankiaddon file
        run: |
          cd your_addon_name
          find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
          zip -r ../your-addon-name.ankiaddon . -x "*.pyc"
      - name: Create Release
        uses: softprops/action-gh-release@v1
        with:
          files: your-addon-name.ankiaddon
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**Enable write permissions**: GitHub repo -> Settings -> Actions -> General -> Workflow permissions -> **Read and write**.

#### Tagging a Release

```bash
git add .
git commit -m "v1.0.0: description of release"
git tag -a v1.0.0 -m "Initial release"
git push origin main --tags
```

In PyCharm: Git -> Tag -> fill name and message -> Git -> Push -> check **Push Tags**.

---

## 3. Quick Start: Your First Addon

Before diving into theory, build something that works. This minimal addon adds a **Tools -> Hello Anki** menu item that counts and displays the number of new cards in your collection.

### Step 1: Create the File

Create `your_addon_name/__init__.py` inside your symlinked addon folder:

```python
# your_addon_name/__init__.py
from aqt import mw, gui_hooks
from aqt.qt import QAction, qconnect
from aqt.utils import showInfo, tooltip
from anki.consts import QUEUE_TYPE_NEW


def count_new_cards() -> int:
    """Count cards that are truly new (never studied)."""
    if not mw or not mw.col:
        return 0
    return mw.col.db.scalar(
        "SELECT count() FROM cards WHERE queue = ?", QUEUE_TYPE_NEW
    )


def on_hello() -> None:
    count = count_new_cards()
    showInfo(f"Hello from your addon!\nYou have {count} new cards waiting.")


def setup_menu() -> None:
    action = QAction("Hello Anki", mw)
    qconnect(action.triggered, on_hello)
    mw.form.menuTools.addAction(action)


# Register setup to run after Anki finishes loading the profile
gui_hooks.profile_did_open.append(setup_menu)
```

### Step 2: Restart Anki

Save the file, then fully quit and reopen Anki.

### Step 3: Test

Click **Tools -> Hello Anki**. A dialog appears showing your new card count.

### What You Just Learned

| Concept | Where It Appears |
|---|---|
| Startup hook | `gui_hooks.profile_did_open.append(setup_menu)` |
| Menu injection | `mw.form.menuTools.addAction(action)` |
| Modern signal connection | `qconnect(action.triggered, on_hello)` |
| Collection query | `mw.col.db.scalar(...)` |
| Safety check | `if not mw or not mw.col` |

> **Tip**: If the menu item doesn't appear, check Anki's stdout (terminal output) for Python errors. See [Section 11: Debugging](#11-debugging--troubleshooting).

---

## 4. How Anki Loads Addons

Understanding the loading sequence prevents timing bugs (e.g., trying to use `mw.col` before a profile is open).

### The Loading Sequence

```
1. Anki starts -> initializes mw (main window)
2. Anki adds addons21/ to Python's import path (sys.path)
3. For each subfolder in addons21/:
   a. Anki calls __import__(folder_name)
   b. Python runs that folder's __init__.py
   c. Your code registers hooks and exits
4. User opens a profile -> collection loads
5. Hooks fire -> your registered functions run
```

**Critical implication**: When `__init__.py` runs, `mw.col` is usually `None` because no profile is open yet. Always delay collection access until `profile_did_open` or another post-load hook fires.

### The Shared Namespace

All addons run in the same Python process and share one namespace.

| Risk | Example | Prevention |
|---|---|---|
| Module collision | Two addons both define `utils.py` | Keep all code inside your package folder |
| Global pollution | Setting `global x` in `__init__.py` | Namespace everything inside your package |
| Cross-addon imports | `from other_addon import x` | Use `sys.modules` scan for numeric IDs (see below) |

### Numeric Folder IDs

Addons installed from AnkiWeb are stored in numeric folders (`addons21/472573498/`). Python identifiers cannot start with a number, so you cannot do:

```python
import 472573498   # SyntaxError
```

To import from a numerically-named addon, scan `sys.modules`:

```python
import sys

for name, module in sys.modules.items():
    if "recalc_main" in name and hasattr(module, "_on_success"):
        recalc_main = module
        break
```

### manifest.json

Required for sharing. Contains:

```json
{
    "package": "your_addon_name",
    "name": "Your Addon Display Name",
    "conflicts": ["other_addon_package_name"]
}
```

- `package` — must match the folder name exactly
- `name` — shown in the addon list and AnkiWeb
- `conflicts` — list of other addon packages that conflict (Anki warns users before installing)

### meta.json

Created by Anki when installing from AnkiWeb. For local development, create it manually to set the display name in the addon list:

```json
{
    "name": "Your Addon Display Name",
    "mod": 0,
    "conflicts": [],
    "max_point_version": 0,
    "min_point_version": 0,
    "branch_index": 0,
    "update_enabled": true
}
```

Do not commit `meta.json` — Anki overwrites it on each update.

> **See Also**: [Section 9: Saving Data](#9-saving-data-config--state) for `config.json`, and [Section 14: Sharing](#14-sharing--distribution) for packaging.

---

## 5. The Anki API: Collections, Cards & Notes

### `mw` — The Main Window

`mw` is the central object. Import it from `aqt`:

```python
from aqt import mw
```

| Attribute | What it gives you | Safe before profile opens? |
|---|---|---|
| `mw.col` | The collection (cards, notes, tags, media) | No |
| `mw.pm` | The profile manager | Yes |
| `mw.pm.name` | Current profile name (e.g., `"MAIN"`) | Yes |
| `mw.pm.profileFolder()` | Path to current profile's folder | Yes |
| `mw.addonManager` | Addon manager (config, install) | Yes |
| `mw.form.menuTools` | The Tools menu | Yes |
| `mw.taskman` | Task manager for background operations | Yes |
| `mw.progress` | Progress bar manager | Yes |
| `mw.reset()` | Force UI refresh (study screen, browser, etc.) | No |
| `mw.checkpoint(label)` | Create an undo point | No |

### `mw.col` — The Collection

Everything about your cards and notes:

```python
# Find card IDs matching a browser search query
card_ids: list[int] = mw.col.find_cards("deck:中文 is:new")

# Find note IDs
note_ids: list[int] = mw.col.find_notes("tag:has-reviewed-sibling")

# Get a single card object
card = mw.col.get_card(card_id)

# Get a single note object
note = mw.col.get_note(note_id)

# Write a modified card back to the database
mw.col.update_card(card)

# Write a modified note back to the database
mw.col.update_note(note)

# Remove cards and orphaned notes (use with caution!)
mw.col.remove_cards_and_orphaned_notes(card_ids)
```

### Tag Operations

```python
# Add a tag to many notes at once (one SQL UPDATE)
mw.col.tags.bulk_add(note_ids, "your-tag")

# Remove a tag from many notes
mw.col.tags.bulk_remove(note_ids, "your-tag")

# Get all tags on a note
note = mw.col.get_note(note_id)
print(note.tags)   # list of strings

# Check if a tag exists globally
if "my-tag" in mw.col.tags.all_tags():
    ...
```

### Raw SQL Access

Anki's collection is a SQLite database. Access it directly for queries that don't have a dedicated API method:

```python
from anki.utils import ids2str

# .list() — returns a flat list (one value per row)
note_ids = mw.col.db.list(
    f"select distinct nid from cards where id in {ids2str(card_ids)}"
)

# .all() — returns list of rows, each row is a list
rows = mw.col.db.all("select id, nid, queue from cards where queue = 0")

# .scalar() — returns a single value
count = mw.col.db.scalar("select count() from cards where queue = -1")

# .execute() — for INSERT/UPDATE/DELETE with parameters
mw.col.db.execute("UPDATE cards SET due = ? WHERE id = ?", new_due, card_id)
```

> **Always use `ids2str()`** instead of string-joining IDs manually. It converts `[1,2,3]` -> `"(1,2,3)"` and prevents SQL injection/syntax errors.

### Card Fields & Lifecycle

A `Card` object (from `mw.col.get_card(card_id)`) has:

| Field | Type | Meaning |
|---|---|---|
| `card.id` | `int` | Unique card ID |
| `card.nid` | `int` | Parent note ID |
| `card.did` | `int` | Deck ID |
| `card.ord` | `int` | Card template index (0 = card 1, 1 = card 2...) |
| `card.type` | `int` | What kind of card it is (new/learning/review) |
| `card.queue` | `int` | Where it currently sits |
| `card.due` | `int` | Due date (days for review, position for new) |
| `card.ivl` | `int` | Current interval in days |
| `card.factor` | `int` | Ease factor x 1000 |
| `card.reps` | `int` | Number of reviews |
| `card.lapses` | `int` | Number of lapses |

#### Card Type Constants (`card.type`)

What kind of card it fundamentally is:

```python
from anki.consts import CARD_TYPE_NEW, CARD_TYPE_LRN, CARD_TYPE_REV, CARD_TYPE_RELEARNING
```

| Constant | Value | Meaning |
|---|---|---|
| `CARD_TYPE_NEW` | 0 | Never studied |
| `CARD_TYPE_LRN` | 1 | In learning steps |
| `CARD_TYPE_REV` | 2 | Graduated to review |
| `CARD_TYPE_RELEARNING` | 3 | Lapsed, relearning |

#### Card Queue Constants (`card.queue`)

Where the card currently sits, including suspended/buried states:

```python
from anki.consts import (
    QUEUE_TYPE_MANUALLY_BURIED,    # -3
    QUEUE_TYPE_SIBLING_BURIED,     # -2
    QUEUE_TYPE_SUSPENDED,          # -1
    QUEUE_TYPE_NEW,                # 0
    QUEUE_TYPE_LRN,                # 1
    QUEUE_TYPE_REV,                # 2
    QUEUE_TYPE_DAY_LEARN_RELEARN,  # 3
)
```

> **Critical distinction**: `card.type` and `card.queue` are independent.
>
> A card suspended by another addon after being deemed known has:
> - `type == CARD_TYPE_NEW` (0) — never studied
> - `queue == QUEUE_TYPE_SUSPENDED` (-1) — currently suspended
>
> Anki's `is:new` search matches on `type == 0`, so it returns both active new cards (`queue == 0`) and suspended-new cards (`queue == -1`). **Always check `card.type`, not `card.queue`,** to distinguish "never studied" from "currently active":

```python
# Correct safety check — only touch cards that have never been studied
if card.type == CARD_TYPE_NEW:
    if card.queue == QUEUE_TYPE_SUSPENDED:
        card.queue = QUEUE_TYPE_NEW   # unsuspend
    card.due = position
    mw.col.update_card(card)
```

### Note Fields

A `Note` object (from `mw.col.get_note(note_id)`):

```python
note = mw.col.get_note(note_id)
note.id           # note ID
note.mid          # model (note type) ID
note.tags         # list of tag strings
note.fields       # list of field values in order
note["Field Name"] # access field by name (raises KeyError if missing)
```

### The Addon Manager

```python
# Redirect the addon list "Config" button to your own dialog
mw.addonManager.setConfigAction(__name__, my_settings_function)

# Get the addon's config (Anki's built-in config system)
config = mw.addonManager.getConfig(__name__)

# Write config
mw.addonManager.writeConfig(__name__, new_config)

# Get the addons21 folder path
addons_path = mw.addonManager.addonsFolder()

# Get this addon's root directory (useful for loading bundled files)
addon_dir = mw.addonManager.addonsFolder(__name__)
```

> **See Also**: [Section 9: Saving Data](#9-saving-data-config--state) for full config patterns.

---

## 6. Reacting to Anki: The Hooks System

### Three Event Systems: When to Use Which

Anki has three event systems. Using the wrong one is a common source of confusion.

| System | Import | Registration | Use For |
|---|---|---|---|
| **`gui_hooks`** | `from aqt import gui_hooks` | `.append(fn)` | Anki UI events: profile opened, card reviewed, sync finished |
| **Collection hooks** | `from anki import hooks` | `.append(fn)` | Backend events: note will be saved, card will be added |
| **Qt signals** | `from aqt.qt import qconnect` | `qconnect(signal, fn)` | Widget events: button clicked, text changed, item selected |

**Rule**: `gui_hooks` and `anki.hooks` use `.append()`. Qt widgets use `qconnect()` or `.connect()`.

### `gui_hooks` — UI-Level Events

```python
from aqt import gui_hooks

def my_function():
    print("profile opened")

gui_hooks.profile_did_open.append(my_function)
```

### Common `gui_hooks`

| Hook | Fires When | Function Signature |
|---|---|---|
| `profile_did_open` | Profile opened (most setup goes here) | `() -> None` |
| `main_window_did_init` | Main window built (for early menu injection) | `() -> None` |
| `browser_will_show_context_menu` | Right-click in card browser | `(browser, menu) -> None` |
| `reviewer_will_show_context_menu` | Right-click during review | `(reviewer, menu) -> None` |
| `reviewer_did_show_question` | Question side shown | `(reviewer) -> None` |
| `reviewer_did_show_answer` | Answer side shown | `(reviewer) -> None` |
| `reviewer_did_answer_card` | Card answered (ease selected) | `(reviewer, card, ease) -> None` |
| `sync_did_finish` | Sync completes | `() -> None` |

Browse all available hooks at: [github.com/ankitects/anki/blob/main/qt/aqt/gui_hooks.py](https://github.com/ankitects/anki/blob/main/qt/aqt/gui_hooks.py)

### Collection Hooks — Backend Events

```python
from anki import hooks

def on_flush(note):
    print(f"Note {note.id} is being saved")

hooks.note_will_flush.append(on_flush)
```

### Hook Lifecycle

Hooks fire in the order functions were appended. If two addons both hook `profile_did_open`, both run — there is no conflict unless one crashes.

To remove a hook (e.g., for cleanup):
```python
gui_hooks.profile_did_open.remove(my_function)
```

> **See Also**: [Section 12: Production Best Practices](#12-production-best-practices) for hook cleanup and error handling.

---

## 7. Building User Interfaces with Qt

Anki's UI is built with Qt (via PyQt6 in modern Anki). Understanding Qt is essential for settings dialogs and UI elements.

### The `aqt.qt` Compatibility Layer

Modern Anki uses PyQt6, but addons should import from `aqt.qt` rather than directly from `PyQt6` or `PyQt5`. This ensures your addon works across Qt5 and Qt6 installations:

```python
from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QSpinBox, QCheckBox, QLineEdit,
    QListWidget, QAction, QMenu, QInputDialog, qconnect
)
```

> **Never do** `from PyQt6.QtWidgets import ...` in a shared addon. Always use `aqt.qt`.

### Layouts

Qt layouts arrange widgets. Think of them as CSS flexbox:

| Qt Class | CSS Equivalent | Use |
|---|---|---|
| `QVBoxLayout` | `flex-direction: column` | Stack widgets vertically |
| `QHBoxLayout` | `flex-direction: row` | Place widgets side by side |
| `QFormLayout` | Two-column label/input grid | Settings forms |

```python
from aqt.qt import QVBoxLayout, QFormLayout, QSpinBox, QLabel

root = QVBoxLayout()
self.setLayout(root)

# Add a label and spinbox stacked vertically
root.addWidget(QLabel("Daily Limit:"))
root.addWidget(QSpinBox())

# Or use a form layout for label | input pairs
form = QFormLayout()
root.addLayout(form)
spin = QSpinBox()
form.addRow("Daily Limit:", spin)

# Push remaining widgets to the bottom (like margin-top: auto)
root.addStretch()
```

### Widgets

Common input widgets:

```python
from aqt.qt import QCheckBox, QSpinBox, QLineEdit, QListWidget, QPushButton

checkbox = QCheckBox("Enable feature")
checkbox.setChecked(True)
is_on = checkbox.isChecked()        # read value

spinbox = QSpinBox()
spinbox.setMinimum(1)
spinbox.setMaximum(999)
spinbox.setValue(20)
current = spinbox.value()           # read value

line_edit = QLineEdit()
line_edit.setText("default text")
text = line_edit.text()             # read value

list_widget = QListWidget()
list_widget.addItem("中文")
list_widget.addItem("日本語")
items = [list_widget.item(i).text() for i in range(list_widget.count())]

button = QPushButton("Click Me")
button.setDefault(True)             # pressing Enter triggers this button
```

### Signals and Slots

**Signal** — something happened (button clicked, value changed).  
**Slot** — a function that responds to the signal.  
**`qconnect()`** — the modern, type-safe way to wire them together.

```python
from aqt.qt import qconnect

qconnect(button.clicked, my_function)        # my_function() called on click
qconnect(checkbox.stateChanged, on_change)   # on_change(state) called on toggle
qconnect(spinbox.valueChanged, on_value)     # on_value(new_int) called on change
```

When the connected function needs extra arguments not provided by the signal, use a lambda:

```python
# 'clicked' passes a bool (checked state), but we need browser and card_ids too
action.triggered.connect(
    lambda: _promote_from_browser(browser, card_ids)
)
```

> **Note on `qconnect` vs `.connect`**: `qconnect()` is type-safe and preferred in modern Anki. Use `.connect()` only when passing a lambda (since `qconnect` validates signatures strictly and may reject lambdas).

### Dialogs

`QDialog` is a popup window. Two display modes:

```python
dialog = MyDialog(parent=mw)

dialog.show()   # non-modal — user can still interact with Anki
dialog.exec()   # modal — blocks Anki until dialog is closed (use for settings)
```

Inside a `QDialog` subclass, use `self.accept()` to close with success (like clicking OK) and `self.reject()` to close without saving (Cancel).

```python
class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)   # always call parent constructor
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        save_btn = QPushButton("Save")
        qconnect(save_btn.clicked, self._save)
        layout.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel")
        qconnect(cancel_btn.clicked, self.reject)
        layout.addWidget(cancel_btn)

    def _save(self):
        # ... write config ...
        self.accept()   # close with success
```

### Input Dialogs

For quick one-off prompts without building a full dialog:

```python
from aqt.qt import QInputDialog

# Free text input
text, confirmed = QInputDialog.getText(parent, "Title", "Label:")

# Dropdown selection
item, confirmed = QInputDialog.getItem(
    parent, "Title", "Label:",
    ["option1", "option2"],
    0,      # default selected index
    False   # editable=False forces selection from list
)

if confirmed:
    use(item)
```

### Adding Menu Items

```python
from aqt import mw
from aqt.qt import QAction, qconnect

# Add to Tools menu
menu = mw.form.menuTools.addMenu("My Addon")

action = QAction("Do Something", mw)
qconnect(action.triggered, my_function)
menu.addAction(action)

# Visual separator
menu.addSeparator()

# Disabled/greyed-out status item
status = QAction("Feature unavailable", mw)
status.setEnabled(False)
menu.addAction(status)
```

### `aqt.utils` Helpers

Anki provides convenience functions so you don't have to build dialogs for simple messages:

```python
from aqt.utils import showInfo, showWarning, showCritical, askUser, tooltip, getFile

showInfo("Operation completed!")                          # OK dialog
showWarning("This deck is very large.")                   # Warning dialog
showCritical("Database is locked.")                       # Error dialog

if askUser("Delete 500 cards? Cannot be undone."):        # Yes/No dialog
    delete_cards()

tooltip("Saved!", period=3000)                            # Transient popup (3 sec)

# File picker
path = getFile(mw, "Select CSV", None, "CSV (*.csv)", key="import_csv")
```

> **See Also**: [Section 11: Debugging](#11-debugging--troubleshooting) for `print()` and logging.

---

## 8. Heavy Operations: Background Threads

### Why Background Threads Matter

Anki runs on one main thread that handles the entire UI. If your code does something slow on that thread (a big database query, processing thousands of cards), Anki freezes until it finishes. The window goes unresponsive.

`QueryOp` and `CollectionOp` run your slow code on a background thread, then call your callback on the main thread when done.

### `QueryOp` — Read-Only Background Work

Use `QueryOp` when you only need to **read** from the collection (find cards, count rows, query data). It does not support writing.

```python
from aqt.operations import QueryOp

def my_slow_operation(col) -> int:
    # Runs in background — do database work here
    # 'col' is the collection, passed automatically
    card_ids = col.find_cards("is:new")
    return len(card_ids)

def on_done(result: int) -> None:
    # Runs on main thread — safe to update UI here
    tooltip(f"Found {result} new cards")

QueryOp(
    parent=mw,           # parent widget (for error dialogs)
    op=my_slow_operation,
    success=on_done,
).run_in_background()
```

The `op` function always receives the collection as its first argument. If your actual function doesn't need it, use a lambda to absorb it:

```python
QueryOp(
    parent=mw,
    op=lambda col: my_function(arg1, arg2),
    success=on_done,
).run_in_background()
```

### `CollectionOp` — Read/Write Background Work

Use `CollectionOp` when you need to **modify** the collection (update cards, add tags, delete notes) from a background thread. It handles collection locking and saving automatically.

```python
from aqt.operations import CollectionOp
from anki.collection import OpChanges

def promote_cards(col) -> OpChanges:
    # Runs in background — safe to modify collection
    card_ids = col.find_cards("is:new")
    for cid in card_ids[:50]:
        card = col.get_card(cid)
        card.due = 0
        col.update_card(card)
    return OpChanges()   # return changes object

def on_done(changes: OpChanges) -> None:
    tooltip("Promoted 50 cards!")
    mw.reset()           # refresh the UI so changes appear

CollectionOp(
    parent=mw,
    op=promote_cards,
).success(on_done).run_in_background()
```

### `mw.progress` — Progress Bars

For operations that take more than a second, show a progress bar so users know Anki hasn't crashed:

```python
def heavy_operation(col) -> int:
    card_ids = col.find_cards("is:new")
    total = len(card_ids)

    mw.progress.start(label="Processing cards...", max=total)

    try:
        for i, cid in enumerate(card_ids):
            if i % 10 == 0:
                mw.progress.update(value=i, label=f"Processed {i}/{total}...")
            # ... do work ...
        return total
    finally:
        mw.progress.finish()   # always clean up, even on error

QueryOp(
    parent=mw,
    op=heavy_operation,
    success=lambda n: tooltip(f"Done: {n}")
).run_in_background()
```

### Thread Safety Rules

| Thread | Safe to do | Forbidden |
|---|---|---|
| **Background (`op`)** | Database queries, file I/O, heavy computation | UI updates, dialogs, `tooltip()`, `showInfo()` |
| **Main thread (`success`)** | UI updates, tooltips, dialogs, `mw.reset()` | Slow work, database queries |

Never update the UI from inside `op`. Never do slow work inside `success`.

> **See Also**: [Section 12: Production Best Practices](#12-production-best-practices) for undo checkpoints and UI refresh patterns.

---

## 9. Saving Data: Config & State

### Three Files, Three Purposes

| File | Purpose | Example Content | Committed? |
|---|---|---|---|
| `config.json` | User settings | Daily limit, deck names | Yes |
| `state.json` | Runtime state | Last run date, counts | No |
| `meta.json` | Anki's metadata | Display name, version | No |

### `config.json` Pattern

```json
{
    "enabled": true,
    "daily_limit": 20,
    "decks": ["中文"],
    "tags": {
        "auto_tag": "AM-sm::reviewed-sibling"
    }
}
```

Reading:
```python
import json, os
from typing import Any

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def get_config() -> dict[str, Any]:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
```

Writing (`ensure_ascii=False` preserves Chinese characters as-is):
```python
def save_config(new_config: dict[str, Any]) -> None:
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(new_config, f, indent=2, ensure_ascii=False)
```

### `state.json` Pattern

```python
_STATE_PATH = os.path.join(os.path.dirname(__file__), "state.json")

def _load_state() -> dict:
    try:
        with open(_STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"last_run": "", "count": 0}   # safe defaults

def _save_state(state: dict) -> None:
    with open(_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
```

### Per-Profile Configuration

By default, `addons21/` is shared across all Anki profiles. To support different settings per profile:

**Option 1 — Config file per profile** (cleanest):

```python
from aqt import mw

def _get_config_path() -> str:
    profile = mw.pm.name if mw and mw.pm else "default"
    return os.path.join(os.path.dirname(__file__), f"config_{profile}.json")
```

This creates `config_MAIN.json`, `config_TEST.json`, etc.

**Option 2 — Single file, keyed by profile**:

```python
def get_config() -> dict:
    all_configs = _read_config_file()
    profile = mw.pm.name
    return all_configs.get(profile, _default_config())

def save_config(new_config: dict) -> None:
    all_configs = _read_config_file()
    all_configs[mw.pm.name] = new_config
    _write_config_file(all_configs)
```

**Option 3 — Store configs in the profile folder** (most architecturally sound):

```python
def _get_config_path() -> str:
    # profileFolder() returns e.g. ~/Library/Application Support/Anki2/MAIN
    profile_dir = mw.pm.profileFolder()
    addon_dir = os.path.join(profile_dir, "ankimorphs_sibling_manager")
    os.makedirs(addon_dir, exist_ok=True)
    return os.path.join(addon_dir, "config.json")
```

This is the most robust approach — each profile's config lives inside that profile's own directory and is backed up with the profile.

### Anki's Built-in Config System

Anki has a built-in config mechanism. Your `config.json` must have a specific schema format and can be validated against a `config.schema.json`. Anki shows a JSON editor when users click "Config" in the addon list.

To use the built-in system:
```python
config = mw.addonManager.getConfig(__name__)   # reads config.json
mw.addonManager.writeConfig(__name__, data)    # writes config.json
```

To replace the config button with your own dialog:
```python
mw.addonManager.setConfigAction(__name__, my_open_settings_function)
```

Call this at module load time (bottom of `__init__.py`) — `mw.addonManager` is available before profiles open.

---

## 10. Integrating with Other Addons

### Importing from Another Addon

If the target addon is installed with its package name as the folder name:
```python
from other_addon_package import some_module
```

If it's installed with a numeric AnkiWeb ID:
```python
import sys
for name, module in sys.modules.items():
    if "distinctive_module_name" in name:
        target_module = module
        break
```

### Monkey-Patching

Monkey-patching is replacing a function at runtime without editing its source file. It's used when an addon (or Anki itself) doesn't provide a hook for the behaviour you want to modify.

```python
import some_module

# Save the original BEFORE replacing
original_function = some_module.target_function

def patched_function(*args, **kwargs):
    original_function(*args, **kwargs)   # still call the original
    my_extra_logic()                     # then do your thing

some_module.target_function = patched_function
```

#### The Fragility Warning

The official Anki addon docs warn: monkey-patching is fragile. If the addon you're patching updates and renames or moves the function, your patch silently breaks. Use it only when no hook is available, and comment clearly:

```python
# Monkey-patching recalc_main._on_success because AnkiMorphs fires no
# hook after recalc completes. This will break if AM renames this function.
# TODO: request a proper hook from AM developers.
```

#### Wrapping Instance Methods

To patch a method on an instance (e.g., the Reviewer):

```python
from aqt import mw

original_show_question = mw.reviewer._showQuestion

def patched_show_question():
    original_show_question()
    my_custom_logic()

mw.reviewer._showQuestion = patched_show_question
```

> **Always save the original before replacing.** If you don't, calling the patched version from inside itself causes infinite recursion.

> **See Also**: [Section 12: Production Best Practices](#12-production-best-practices) for monkey-patch documentation standards.

---

## 11. Debugging & Troubleshooting

### The Console: Your First Line of Defense

Anki's stdout is where `print()` statements appear. Access it by running Anki from the terminal:

| OS | Command |
|---|---|
| macOS | `/Applications/Anki.app/Contents/MacOS/Anki` |
| Windows | `anki-console.exe` (in Anki install folder) |
| Linux | `anki` |

### Python Logging (Production-Grade)

For addons you share with others, `print()` is insufficient. Use Python's `logging` module so users can send you log files:

```python
import logging
import os
from aqt import mw

logger = logging.getLogger(__name__)

log_path = os.path.join(mw.addonManager.addonsFolder(__name__), "addon.log")
handler = logging.FileHandler(log_path, encoding="utf-8")
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

# Usage
logger.info("Addon initialized")
logger.debug(f"Found {len(card_ids)} cards")
logger.error("Database query failed", exc_info=True)   # includes traceback
```

### Common Errors and Fixes

| Error | Cause | Fix |
|---|---|---|
| `ImportError: cannot import name 'X' from 'aqt'` | Anki version too old | Check `aqt.point_version()` and branch code |
| `AttributeError: 'NoneType' object has no attribute 'col'` | `mw.col` not ready | Move logic into `gui_hooks.profile_did_open` |
| `SyntaxError: invalid decimal literal` | Folder name starts with number | Rename to use underscores/letters |
| `ModuleNotFoundError: No module named 'your_addon'` | Absolute import in `__init__.py` | Use `from . import module` |
| `RecursionError` | Monkey-patch called itself | Save `original = module.func` **before** replacing |
| `sqlite3.OperationalError: database is locked` | Writing from background without `CollectionOp` | Use `CollectionOp` for writes |
| `TypeError: qconnect() takes 2 positional arguments` | Passing lambda to `qconnect` | Use `.connect()` for lambdas |

### Inspecting Live Objects

Open the Anki debug console (some setups: **Ctrl+Shift+;**) and inspect live objects:

```python
from aqt import mw
print(mw.col.decks.all_names_and_ids())   # list all decks
print(dir(mw.reviewer))                   # see reviewer attributes
print(mw.reviewer.card.__dict__)          # inspect current card
```

### IDE Debugger (PyCharm)

PyCharm can attach to a running Anki process:

1. Run Anki from the terminal (so stdout is visible)
2. In PyCharm: **Run -> Attach to Process**
3. Select the `Anki` Python process
4. Set breakpoints in your addon code
5. Trigger the breakpoint in Anki

Requires PyCharm Professional or the free `pydevd-pycharm` package.

---

## 12. Production Best Practices

### Before You Ship: Checklist

- [ ] **Profile safety**: Check `if not mw or not mw.col` before collection access
- [ ] **Undo support**: Call `mw.checkpoint("Description")` before bulk writes
- [ ] **UI refresh**: Call `mw.reset()` after modifying cards/notes/decks
- [ ] **Config validation**: Handle missing keys with `.get(key, default)`
- [ ] **Thread safety**: Use `QueryOp` for reads, `CollectionOp` for writes
- [ ] **Graceful degradation**: Wrap optional imports in `try/except ImportError`
- [ ] **Version checks**: Branch code with `aqt.point_version()` for API differences
- [ ] **Hook cleanup**: Remove hooks on shutdown if addon can be disabled at runtime
- [ ] **Unicode safety**: Use `ensure_ascii=False` when writing JSON
- [ ] **Monkey-patch docs**: Comment what, why, and what version it targets

### Detailed Patterns

#### 1. Always Check `mw.col` Exists

```python
from aqt import mw

if not mw or not mw.col:
    showWarning("Please open a profile first.")
    return
```

#### 2. Use `mw.checkpoint()` for Undo Support

Any destructive operation should support undo:

```python
def bulk_reposition(card_ids: list[int]) -> None:
    mw.checkpoint("Reposition cards")   # creates an undo entry
    for cid in card_ids:
        card = mw.col.get_card(cid)
        card.due = 0
        mw.col.update_card(card)
    mw.col.save()                       # commit to DB
    mw.reset()                          # refresh UI
```

Without `mw.checkpoint()`, users cannot undo your changes.

#### 3. Refresh the UI After Changes

After modifying cards, notes, or decks, call `mw.reset()` so the Study screen, Browser, and Deck list reflect the changes:

```python
mw.reset()   # refreshes all active windows
```

#### 4. Validate Config Before Using It

Users will edit `config.json` manually and make mistakes. Validate early:

```python
def get_config_safe() -> dict:
    config = get_config()
    if not isinstance(config.get("daily_limit"), int):
        config["daily_limit"] = 20
    if not isinstance(config.get("decks"), list):
        config["decks"] = ["default"]
    return config
```

#### 5. Graceful Degradation

If your addon depends on another addon, handle its absence gracefully:

```python
try:
    from other_addon import helper
    HAS_HELPER = True
except ImportError:
    HAS_HELPER = False

def do_work():
    if HAS_HELPER:
        helper.optimize()
    else:
        pass  # fallback logic
```

#### 6. Version-Check Your Code

Anki's API changes. Branch your code based on the running version:

```python
from aqt import point_version
from aqt import qt

IS_QT6 = hasattr(qt, "QApplication") and "PyQt6" in str(type(qt.QApplication))

if point_version() >= 60:
    use_modern_api()
else:
    use_legacy_api()
```

#### 7. Don't Block the Main Thread

If an operation touches more than ~100 cards, move it to `QueryOp` or `CollectionOp`. A frozen Anki window makes users think your addon crashed their collection.

#### 8. Clean Up Your Hooks

If your addon can be disabled at runtime, remove hooks to prevent stale callbacks:

```python
def shutdown():
    gui_hooks.profile_did_open.remove(my_setup)
    gui_hooks.reviewer_did_answer_card.remove(my_tracker)
```

#### 9. Use `ensure_ascii=False` for JSON

Always preserve non-ASCII characters in config files:

```python
json.dump(config, f, indent=2, ensure_ascii=False)
```

#### 10. Document Your Monkey Patches

When you must monkey-patch, leave a clear audit trail:

```python
# PATCH START: AnkiMorphs v0.12.0 — no hook available for post-recalc
# See: https://github.com/.../issue/123
# BREAKS IF: recalc_main._on_success is renamed
original = recalc_main._on_success
# ... patch logic ...
# PATCH END
```

---

## 13. Editing and Maintaining Others' Addons

### Code Archaeology: Reading an Unfamiliar Addon

Start with these files in order:

1. `__init__.py` — entry point; shows what hooks are registered and what the addon does at startup
2. `manifest.json` — shows the addon's name, package ID, and conflicts
3. Any file mentioned in a hook callback — trace the call chain

**Quick searches**:
- Search for `gui_hooks.` to find every event the addon listens to
- Search for `def ` to get a quick map of all functions
- Search for `mw.col.` to find all database touch points

### Finding Where Behaviour Lives

| You want to change... | Look for... |
|---|---|
| What happens on startup | `gui_hooks.profile_did_open` |
| What happens after a card is reviewed | `gui_hooks.reviewer_did_answer_card` |
| What happens during recalc | Functions registered with `QueryOp` or background threads |
| Menu items | `QAction` and `mw.form.menuTools` |
| Database reads/writes | `mw.col.find_cards`, `mw.col.db.list`, `mw.col.update_card` |

### Safe Modification Patterns

1. **Prefer hooks over monkey-patching** — if the addon fires a hook at the right moment, use it. Only monkey-patch when no hook exists.
2. **Save the original before patching** — always.
3. **Check the Anki version** — hooks and APIs change between versions. Use `aqt.point_version()`.
4. **Test on a backup** — always test destructive changes on a copy of your collection.
5. **Comment what you changed and why** — future you will thank present you.

### Version Compatibility

When an addon breaks after an Anki update:

- Check the addon's GitHub for an update or open an issue
- Look at Anki's changelog: [github.com/ankitects/anki/blob/main/docs/changelog.md](https://github.com/ankitects/anki/blob/main/docs/changelog.md)
- Search for the broken function name in Anki's source to find the new API

Common breaking changes between versions:
- `exec_()` renamed to `exec()` in PyQt6
- Scheduler API (`mw.col.sched`) changes between v2 and v3
- Hook signatures sometimes gain or lose parameters
- `aqt.qt` compatibility layer changes (always import from `aqt.qt`)

---

## 14. Sharing & Distribution

### Packaging for AnkiWeb

The `.ankiaddon` file is a zip of your addon folder's contents (not the folder itself):

```bash
cd your_addon_name
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
zip -r ../your-addon-name.ankiaddon . -x "*.pyc"
```

Upload at: [ankiweb.net/shared/addons/](https://ankiweb.net/shared/addons/)

### Packaging for GitHub

Your `manifest.json` must include the `package` key for Anki to know the folder name when installing from a `.ankiaddon` file:

```json
{
    "package": "your_addon_name",
    "name": "Your Addon Display Name",
    "conflicts": []
}
```

Users install by double-clicking the `.ankiaddon` file.

### Versioning

Use semantic versioning: `MAJOR.MINOR.PATCH`

- `MAJOR` — breaking changes (users need to update their config)
- `MINOR` — new features, backwards compatible
- `PATCH` — bug fixes

Tag releases in git:
```bash
git tag -a v1.0.0 -m "Initial release"
git push origin main --tags
```

### Writing a Good README

Your `README.md` should include:

1. **What it does** — one sentence, then a short paragraph
2. **Screenshots** — users trust what they can see
3. **Installation** — link to AnkiWeb or double-click instructions
4. **Configuration** — explain `config.json` keys
5. **Compatibility** — which Anki versions are tested
6. **Changelog** — link to `CHANGELOG.md` or list recent changes
7. **Support** — GitHub issues link or Anki Forums thread

---

## 15. Quick Reference Cheat Sheet

### Essential Imports

```python
from aqt import mw, gui_hooks
from aqt.qt import QAction, QDialog, QVBoxLayout, qconnect
from aqt.utils import showInfo, tooltip, askUser
from anki.consts import CARD_TYPE_NEW, QUEUE_TYPE_SUSPENDED
from anki.utils import ids2str
```

### Startup Hook

```python
def init() -> None:
    pass  # setup menus, hooks, etc.

gui_hooks.profile_did_open.append(init)
```

### Menu Item

```python
action = QAction("My Action", mw)
qconnect(action.triggered, my_function)
mw.form.menuTools.addAction(action)
```

### Background Read

```python
from aqt.operations import QueryOp
QueryOp(
    parent=mw,
    op=lambda col: len(col.find_cards("is:new")),
    success=lambda n: tooltip(f"{n} new")
).run_in_background()
```

### Background Write

```python
from aqt.operations import CollectionOp
from anki.collection import OpChanges
CollectionOp(
    parent=mw,
    op=lambda col: (col.update_card(card), OpChanges())[1]
).success(lambda _: mw.reset()).run_in_background()
```

### Config

```python
config = mw.addonManager.getConfig(__name__) or {}
limit = config.get("limit", 20)
```

### Dialog

```python
class MyDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setLayout(QVBoxLayout())
        # ... add widgets ...
        self.exec()
```

### Undo Checkpoint

```python
mw.checkpoint("My operation")
# ... modify collection ...
mw.col.save()
mw.reset()
```

---

## 16. Python Patterns for Anki Developers

> **When to read this**: If you encounter a Python idiom in the guide that you don't recognize, look it up here. This is a condensed reference, not a tutorial.

### Modules and Packages

A **module** is a single `.py` file. A **package** is a folder containing `__init__.py`. Your entire addon is one package.

```
your_addon/
    __init__.py    <- makes this folder a package; Anki runs this first
    tagger.py      <- a module
    config.py      <- another module
```

### Relative Imports

Inside a package, import sibling modules with a leading dot:

```python
# Correct — relative import (looks in the same folder)
from . import tagger
from .config import get_config, save_config

# Wrong — absolute import causes circular import errors inside __init__.py
from your_addon import tagger
```

**Circular imports** happen when module A imports from module B, which imports from module A. Python refuses to resolve this. Fix by using relative imports or moving shared values to a third module (e.g., `config.py`).

### Type Hints

Type hints annotate variables and signatures. They don't enforce anything at runtime, but PyCharm reads them and underlines mismatches before you run:

```python
def tag_reviewed_siblings(decks: list[str]) -> int:
    ...

card_ids: list[int] = mw.col.find_cards("is:new")
```

Unlike Java, Python doesn't enforce types — they're hints, not rules.

### `__file__`

Built-in variable pointing to the current file's path. Use it to find sibling files regardless of where the addon is installed:

```python
import os
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
```

### Dictionary `.get()` with Defaults

Returns a fallback if the key is missing instead of raising `KeyError`:

```python
config.get("daily_limit", 10)     # returns 10 if key doesn't exist
config.get("decks", ["default"])  # returns ["default"] if key doesn't exist
```

### `f`-strings

String interpolation:

```python
deck = "中文"
query = f'deck:{deck} is:new'   # -> 'deck:中文 is:new'
```

### List Comprehensions

Compact list transformations:

```python
deck_query = " OR ".join(f'"deck:{d}"' for d in decks)
items = [widget.item(i).text() for i in range(widget.count())]
```

### `enumerate()`

Iterate with an index:

```python
for position, card_id in enumerate(card_ids):
    card.due = position   # 0, 1, 2...
```

### `try/except`

Catch errors gracefully:

```python
try:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    return {}   # safe default if file missing or corrupted
```

### Lambda

An anonymous function. Used when you need to pass a function that takes arguments to something expecting a no-argument callable:

```python
# connect() expects a callable with no arguments
# but _promote needs browser and card_ids passed to it
action.triggered.connect(
    lambda: _promote_from_browser(browser, card_ids)
)
```

### Tuples vs Lists

| | List `[1, 2, 3]` | Tuple `(1, 2, 3)` |
|---|---|---|
| Mutable | Yes | No |
| Use when | Collection that might change | Fixed group of values |
| Example | `card_ids`, `deck_names` | Return two counts together |

```python
# Tuple: returning two values as a pair
def op(col) -> tuple[int, int]:
    return tagged_count, promoted_count

# Unpack a tuple
tagged, promoted = result
```

### Inner Functions (Closures)

Functions defined inside other functions that capture the outer function's variables:

```python
def run_tagger() -> None:
    decks = get_decks()   # captured by the inner function below

    def on_success(count: int) -> None:
        tooltip(f"Tagged {count} notes in {decks}")   # uses outer 'decks'

    QueryOp(..., success=on_success).run_in_background()
```

### `sys.modules`

Python's dictionary of every loaded module. Useful for finding addons loaded with numeric folder names:

```python
import sys
for module_name, module in sys.modules.items():
    if "recalc_main" in module_name and hasattr(module, "_on_success"):
        # found it
        break
```

---

## 17. Glossary

**API (Application Programming Interface)** — the set of functions and classes a library exposes for you to use. When you call `mw.col.find_cards()`, you're using Anki's API.

**Callback** — a function passed as an argument to be called later. The `success=on_done` in `QueryOp` is a callback.

**Circular import** — when module A imports from module B, which imports from module A. Python refuses to resolve this. Fix by using relative imports or moving shared values to a third module neither owns.

**Closure** — a function that captures variables from the scope where it was defined. Inner functions in Python create closures.

**Collection** — Anki's database of cards, notes, decks, tags, and media. Accessed via `mw.col`.

**Decorator** — the `@something` syntax above a function. Wraps the function in extra behaviour without changing its source.

**Graceful degradation** — when a feature fails, the rest of the program continues working in reduced mode. Using `try/except ImportError` to handle a missing addon is graceful degradation.

**Hook** — a list of functions that gets called at a specific moment. Anki's `gui_hooks` are hooks. You register your function by appending it.

**IDE (Integrated Development Environment)** — a code editor with built-in tools: autocompletion, error highlighting, debugging. PyCharm and VS Code are IDEs.

**Module** — a single `.py` file.

**Monkey-patching** — replacing a function at runtime without editing its source file. Useful when no hook is available; fragile when the patched code is updated.

**Namespace** — the shared Python environment where all code runs. In Anki, all addons share one namespace, which is why keeping code inside your own package matters.

**Package** — a folder containing `__init__.py`. Your addon is a package.

**Profile** — Anki supports multiple user profiles (e.g., "MAIN", "TEST"). Each has its own collection file and media folder.

**Relative import** — importing a sibling module using `.` notation. Inside a package, always use relative imports for sibling modules: `from . import tagger` instead of `from your_addon import tagger`.

**Signal / Slot** — Qt's event system. A signal fires when something happens (button clicked). A slot is a function that responds. Connect them with `qconnect()`.

**Stub** — a type hint file that describes the API of a library. Installing `aqt[qt6]` gives you Anki's stubs so PyCharm can show autocomplete for `mw.col.find_cards()` etc.

**Symbolic link (symlink)** — a file system pointer. The addon folder in `addons21/` points to your project folder, so Anki always reads your live code.

**Thread** — a way to run code in the background without blocking the UI. `QueryOp` and `CollectionOp` manage threading automatically for Anki addon operations.

**Type hint** — an annotation that tells Python (and your IDE) what type a variable or function parameter should be. Optional but strongly recommended.

**Undo checkpoint** — a snapshot of the collection state created by `mw.checkpoint()`. Allows users to undo bulk operations.
