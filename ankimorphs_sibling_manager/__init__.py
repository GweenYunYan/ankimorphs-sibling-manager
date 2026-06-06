import sys
from aqt import mw, gui_hooks
from aqt.qt import QAction
from aqt.utils import tooltip, showWarning
from aqt.operations import QueryOp


from ankimorphs_sibling_manager import tagger
from ankimorphs_sibling_manager.config import get_decks, get_tag, is_enabled

# ── AnkiMorphs integration ──────────────────────────────────────────────────

# We wrap the import in try/except because AM might not be installed.
# If it isn't, the addon still works — you just trigger tagging manually
# from the menu instead of it running automatically after recalc.


_AM_AVAILABLE = False

def _find_recalc_main() -> object | None:
    """
    AnkiMorphs is installed with a numeric folder ID, so we can't import
    it by name. Instead we scan sys.modules — Python's registry of all
    loaded modules — and find the one that has _on_success on it.

    This runs after profile_did_open, so all addons are already loaded.
    """
    for module_name, module in sys.modules.items():
        if "recalc_main" in module_name and hasattr(module, "_on_success"):
            return module
    return None

def _patch_ankimorphs() -> None:
    """
    Moneky-patches AM's recalc success callback so our tagger
    runs automatically after every recalc.
    """
    global _AM_AVAILABLE

    recalc_main = _find_recalc_main()

    if recalc_main is None:
        _AM_AVAILABLE = False
        return
    _AM_AVAILABLE = True

    # Save a reference to the original function before we replace it.
    # If we don't do this, calling the original becomes impossible.

    original_on_success = recalc_main._on_success

    def patched_on_success(start_time: object) -> None:
        # Always call the original first — AM needs to do its own cleanup
        original_on_success(start_time)

        # Then run our tagger if the addon is enabled
        if is_enabled():
            _run_tagger_silent()

    recalc_main._on_success = patched_on_success

def _run_tagger_silent() -> None:
    """Runs tagger after recalc - no tooltip on 0 results, avoid noise"""
    if not mw.col:
        return

    def on_success(notes_tagged: int) -> None:
        if notes_tagged > 0:
            tooltip(f"[AnkiMorphs Sibling Manager] Tagged {notes_tagged} notes.")

    QueryOp(
        parent=mw,
        op=lambda col: tagger.tag_reviewed_siblings(get_decks()),
        success=on_success,
    ).run_in_background()

# ── Manual menu ─────────────────────────────────────────────────────────────

def run_tagger_manual() -> None:
    """Triggered from the menu - always shows a result tooltip"""
    if not mw.col:
        return

    def on_success(notes_tagged: int) -> None:
        if notes_tagged == 0:
            tooltip("No review cards found — nothing tagged.")
        else:
            tooltip(f"Tagged {notes_tagged} notes with {get_tag()}.")

    QueryOp(
        parent=mw,
        op=lambda col: tagger.tag_reviewed_siblings(get_decks()),
        success=on_success,
    ).run_in_background()

def run_dry_run() -> None:
    if not mw.col:
        return
    note_ids = tagger.get_review_note_ids(get_decks())
    tooltip(f"Would tag {len(note_ids)} notes.")

def setup_menu() -> None:
    menu = mw.form.menuTools.addMenu("AnkiMorphs Sibling Manager")

    tag_action = QAction("Tag Reviewed Siblings", mw)
    tag_action.triggered.connect(run_tagger_manual)
    menu.addAction(tag_action)

    dry_run_action = QAction("Dry Run (count only)", mw)
    dry_run_action.triggered.connect(run_dry_run)
    menu.addAction(dry_run_action)

    if not _AM_AVAILABLE:
        # Warn the user that auto-tagging after recalc won't work
        no_am_action = QAction("⚠️ AnkiMorphs not detected — manual mode only", mw)
        no_am_action.setEnabled(False)
        menu.addAction(no_am_action)

# ── Startup ──────────────────────────────────────────────────────────────────

def on_profile_open() -> None:
    _patch_ankimorphs() # must run before setup_menu so _AM_AVAILABLE is set
    setup_menu()


gui_hooks.profile_did_open.append(on_profile_open)