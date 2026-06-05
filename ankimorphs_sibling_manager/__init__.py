from aqt import mw, gui_hooks
from aqt.qt import QAction
from aqt.utils import tooltip

def dry_run_tagger()-> None:
    # guard: make sure a profile is open
    if not mw.col:
        tooltip('no profile open')
        return

    # find all cards in 中文 that are in the review queue
    card_ids = mw.col.find_cards("deck:中文 is:review")
    tooltip(f"Would tag {len(card_ids)} cards' notes")

def setup_menu() -> None:
    # create a top level menu called "AM Sibling Manager"
    menu = mw.form.menuTools.addMenu("AM Sibling Manager")

    # Add an action inside that menu
    dry_run_action = QAction("Tag Reviewed Siblings (Dry Run)", mw)
    dry_run_action.triggered.connect(dry_run_tagger)
    menu.addAction(dry_run_action)

gui_hooks.profile_did_open.append(setup_menu)