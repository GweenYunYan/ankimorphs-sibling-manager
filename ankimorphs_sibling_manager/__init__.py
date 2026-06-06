from aqt import mw, gui_hooks
from aqt.qt import QAction
from aqt.utils import tooltip
from aqt.operations import QueryOp

from ankimorphs_sibling_manager import tagger

DECK = "中文"

def run_tagger() -> None:
    if not mw.col:
        tooltip("no profile open.")
        return

    # this runs after tag_reviewed_siblings() finished in the background
    def on_success(notes_tagged: int) -> None:
        if notes_tagged == 0:
            tooltip("no review cards found | nothing tagged.")
        else:
            tooltip(f"tagged {notes_tagged} notes with 'has-reviewed-sibling'.")

    # op      → runs in the background thread (the slow database work)
    # success → runs on main thread when op finishes (the UI update)
    QueryOp(
        parent=mw,
        op=lambda col: tagger.tag_reviewed_siblings("中文"),
        success=on_success,
    ).run_in_background()

def run_dry_run() -> None:
    if not mw.col:
        return
    note_ids = tagger.get_review_note_ids(DECK)
    tooltip(f"would tag {len(note_ids)} notes.")

def setup_menu() -> None:
    menu = mw.form.menuTools.addMenu("AM Sibling Manager")

    tag_action = QAction("Tag Reviewed Siblings", mw)
    tag_action.triggered.connect(run_tagger)
    menu.addAction(tag_action)

    dry_run_action = QAction("Dry Run (count only)", mw)
    dry_run_action.triggered.connect(run_dry_run)
    menu.addAction(dry_run_action)

gui_hooks.profile_did_open.append(setup_menu)