import sys

from aqt import mw, gui_hooks
from aqt.browser import Browser
from aqt.qt import QAction, QMenu
from aqt.reviewer import Reviewer
from aqt.utils import tooltip
from aqt.operations import QueryOp

from . import tagger
from . import promoter
from .config import get_decks, get_tags, is_enabled
from .settings_dialog import SettingsDialog

# ── AnkiMorphs integration ──────────────────────────────────────────────────

_AM_AVAILABLE = False

def _find_recalc_main() -> object | None:
    """
    AnkiMorphs is installed with a numeric folder ID so we can't import
    it by name. We scan sys.modules and find the module that has
    _on_success on it. Runs after all addons are loaded.
    """
    for module_name, module in sys.modules.items():
        if "recalc_main" in module_name and hasattr(module, "_on_success"):
            return module
    return None

def _patch_ankimorphs() -> None:
    """
    Monkey-patches AM's recalc success callback so our tagger
    and promoter run automatically after every recalc.
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
            _run_post_recalc()

    recalc_main._on_success = patched_on_success

# ── Background operations ─────────────────────────────────────────────────────

def _run_post_recalc() -> None:
    """Runs tagger then promoter after every AM recalc"""
    if not mw.col:
        return

    def op(col) -> tuple[int, int]:
        tagged = tagger.tag_reviewed_siblings(get_decks())
        promoted = promoter.promote_daily_batch()
        return tagged, promoted

    def on_success(result: tuple[int, int]) -> None:
        tagged, promoted = result
        parts = []
        if tagged > 0:
            parts.append(f"tagged {tagged} notes")
        if promoted > 0:
            parts.append(f"promoted {promoted} cards")
        if parts:
            tooltip(
                f"[AnkiMorphs Sibling Manager] "
                f"{', '.join(parts).capitalize()}."
            )
    QueryOp(parent=mw, op=op, success=on_success).run_in_background()

def _run_startup_promoter() -> None:
    """
    Runs the promoter when Anki opens so cards get promoted even
    on days when the user doesn't run a recalc.
    """
    if not mw.col:
        return

    def on_success(promoted: int) -> None:
        if promoted > 0:
            tooltip(
                f"[AnkiMorphs Sibling Manager] Promoted {promoted} cards."
            )

    QueryOp(
        parent=mw,
        op=lambda col: promoter.promote_daily_batch(),
        success=on_success,
    ).run_in_background()

# ── Never promote (shared logic) ──────────────────────────────────────────────

def _run_never_promote(parent, card_ids: list[int]) -> None:
    """Shared by browser and reviewer menus."""
    def on_success(notes_tagged: int) -> None:
        tooltip(
            f"{notes_tagged} note(s) marked to never promote. "
            f"Existing promotion tags removed."
        )

    QueryOp(
        parent=parent,
        op=lambda col:promoter.tag_never_promote(card_ids),
        success=on_success,
    ).run_in_background()

# ── Tools menu ────────────────────────────────────────────────────────────────

def _run_tagger_manual() -> None:
    """Triggered from the menu - always shows a result tooltip"""
    if not mw.col:
        return

    def on_success(notes_tagged: int) -> None:
        if notes_tagged == 0:
            tooltip("No review cards found — nothing tagged.")
        else:
            auto_tag = get_tags().get("auto_tag")
            tooltip(f"Tagged {notes_tagged} notes with '{auto_tag}'.")

    QueryOp(
        parent=mw,
        op=lambda col: tagger.tag_reviewed_siblings(get_decks()),
        success=on_success,
    ).run_in_background()

def _run_dry_run() -> None:
    if not mw.col:
        return
    note_ids = tagger.get_review_note_ids(get_decks())
    tooltip(f"Would tag {len(note_ids)} notes.")

def setup_menu() -> None:
    menu = mw.form.menuTools.addMenu("AnkiMorphs Sibling Manager")

    settings_action = QAction("Settings...", mw)
    settings_action.triggered.connect(_open_settings)
    menu.addAction(settings_action)

    menu.addSeparator() # visual dividing line between settings and actions

    tag_action = QAction("Tag Reviewed Siblings", mw)
    tag_action.triggered.connect(_run_tagger_manual)
    menu.addAction(tag_action)

    dry_run_action = QAction("Dry Run (count only)", mw)
    dry_run_action.triggered.connect(_run_dry_run)
    menu.addAction(dry_run_action)

    if not _AM_AVAILABLE:
        # Warn the user that auto-tagging after recalc won't work
        no_am_action = QAction(
            "⚠️ AnkiMorphs not detected — manual mode only", mw
        )
        no_am_action.setEnabled(False)
        menu.addAction(no_am_action)

# ── Browser context menu ──────────────────────────────────────────────────────

def setup_browser_context_menu(browser: Browser, menu: QMenu) -> None:
    """
        Promote New Cards: queues notes for promotion. Does not immediately
        reposition or unsuspend — the daily limit controls that.

        Never Promote This Note: permanently excludes from promotion system.
    """
    selected = browser.selected_cards()
    if not selected:
        return

    card_ids = list(selected)

    promote_action = QAction("Promote New Cards", browser)
    promote_action.triggered.connect(
        lambda: _promote_from_browser(browser, card_ids)
    )
    menu.addAction(promote_action)

    never_action = QAction("Never Promote This Note", browser)
    never_action.triggered.connect(
        lambda: _run_never_promote(browser, card_ids)
    )
    menu.addAction(never_action)

def _promote_from_browser(browser: Browser, card_ids: list[int]) -> None:
    def on_success(notes_tagged: int) -> None:
        tooltip(f"Marked {notes_tagged} note(s) for promotion.")

    QueryOp(
        parent=browser,
        op=lambda col: promoter.tag_cards_for_promotion(card_ids),
        success=on_success,
    ).run_in_background()

# ── Reviewer context menu ─────────────────────────────────────────────────────

def setup_reviewer_context_menu(reviewer: Reviewer, menu: QMenu) -> None:
    """
    Never Promote This Note only — during review you're already studying
    a card that's in your queue. The useful action here is excluding a
    note you realize mid-review shouldn't feed into the promotion system.
    """
    card = reviewer.card
    if not card:
        return

    never_action = QAction("Never Promote This Note", reviewer.mw)
    never_action.triggered.connect(
        lambda: _run_never_promote(reviewer.mw, [card.id])
    )
    menu.addAction(never_action)
# ── Settings Menu ──────────────────────────────────────────────────────────────────

def _open_settings() -> None:
    dialog = SettingsDialog(mw)
    dialog.exec()

# ── Startup ──────────────────────────────────────────────────────────────────

def on_profile_open() -> None:
    _patch_ankimorphs() # must run before setup_menu so _AM_AVAILABLE is set
    setup_menu()

    if is_enabled():
        _run_startup_promoter()

gui_hooks.profile_did_open.append(on_profile_open)
gui_hooks.browser_will_show_context_menu.append(setup_browser_context_menu)
gui_hooks.reviewer_will_show_context_menu.append(setup_reviewer_context_menu)
# Redirect the "Config" button in the addon manager to our settings dialog
mw.addonManager.setConfigAction(__name__, _open_settings)