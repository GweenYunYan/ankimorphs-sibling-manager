import json
import os
from datetime import date
import time

from anki.consts import CARD_TYPE_NEW, CARD_TYPE_LRN, QUEUE_TYPE_NEW, QUEUE_TYPE_SUSPENDED, QUEUE_TYPE_LRN
from anki.utils import ids2str
from aqt import mw

from .config import get_tags, get_daily_limit

TAGS = get_tags()
AUTO_TAG = TAGS.get("auto_tag")
PROMOTE_TAG = TAGS.get("promote_tag")
NEVER_PROMOTE_TAG = TAGS.get("never_promote_tag")

# ── State persistence ─────────────────────────────────────────────────────────
#
# state.json tracks how many cards were promoted today so the daily
# limit persists across Anki restarts.
#
# config.json = settings the user controls
# state.json  = what the addon remembers automatically

_STATE_PATH = os.path.join(os.path.dirname(__file__), "state.json")

def _load_state() -> dict:
    """
    Reads state.json. Returns safe defaults if the file
    doesn't exist yet or is corrupted.
    """
    try:
        with open(_STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"last_run": "", "promoted_today": 0}

def _save_state(state: dict) -> None:
    with open(_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

# ── Core promotion logic ──────────────────────────────────────────────────────

def _get_promotable_card_ids(limit: int) -> list[int]:
    """
    Finds new cards (including suspended-new) tagged for promotion.

    is:new matches type == 0 (never studied). This intentionally
    includes suspended-new cards (queue == -1, type == 0) because
    those are exactly what AM suspends when it deems a morph known -
    and surfacing them is the entire point of this addon.

    Never-promote notes are excluded so permanently excluded notes
    aren't promoted even if they somehow kept their auto_tag.
    """

    query = (
        f'(tag:{AUTO_TAG} OR tag:{PROMOTE_TAG}) '
        f'is:new -tag:{NEVER_PROMOTE_TAG}'
    )
    card_ids = mw.col.find_cards(query)
    return list(card_ids[:limit])

def _promote_to_learning(card_ids: list[int]) -> None:
    """
    Moves new and suspended-new cards directly into the learning queue
    by setting their type and queue to LRN with an immediate due timestamp.

    A small timestamp offset (+ position) preserves the relative order
    of promoted cards within the batch
    """
    now = int(time.time())

    for position, card_id in enumerate(card_ids):
        card = mw.col.get_card(card_id)
        if card.type == CARD_TYPE_NEW:
            card.type = CARD_TYPE_LRN
            card.queue = QUEUE_TYPE_LRN
            card.due = now + position  # offset keeps batch order intact
            mw.col.update_card(card)

def _reposition_cards(card_ids: list[int]) -> None:
    """
    *** OBSOLETE ***
    Moves new cards to the front of the new queue, unsuspending
    suspended-new cards in the process.

    Safety check: card.type == CARD_TYPE_NEW ensures we only touch
    cards that have never been studied, regardless of queue state.
    This prevents accidental modification of review cards (type == 2)
    which would corrupt FSRS scheduling data.

    For suspended-new cards (queue == -1, type == 0):
        → set queue to QUEUE_TYPE_NEW to unsuspend
        → then set due position

    For active-new cards (queue == 0, type == 0):
        → just set due position
    """
    for position, card_id in enumerate(card_ids):
        card = mw.col.get_card(card_id)
        if card.type == CARD_TYPE_NEW:
            if card.queue == QUEUE_TYPE_SUSPENDED:
                card.queue = QUEUE_TYPE_NEW
            card.due = position
            mw.col.update_card(card)

def promote_daily_batch() -> int:
    """
    *** UPDATED TO WORK WITH _promote_to_learning ***
    Promotes up to daily_limit new cards per day. Unsuspends
    suspended-new cards in the process.

    Tracks count in state.json so the limit persists across restarts.
    :return: Number of cards promoted this call.
    """
    state = _load_state()
    today = str(date.today())

    if state.get("last_run") == today:
        already_promoted = state.get("promoted_today", 0)
        remaining = get_daily_limit() - already_promoted
    else:
        remaining = get_daily_limit()
        state["promoted_today"] = 0

    if remaining <= 0:
        return 0

    card_ids = _get_promotable_card_ids(remaining)
    if not card_ids:
        return 0

    _promote_to_learning(card_ids)

    state["last_run"] = today
    state["promoted_today"] = state.get("promoted_today", 0) + len(card_ids)
    _save_state(state)

    return len(card_ids)

# ── Manual tagging ────────────────────────────────────────────────────────────

def tag_cards_for_promotion(card_ids: list[int]) -> int:
    """
    Tags selected cards' notes with promote_tag so the promoter
    picks them up on the next run.

    Does NOT immediately reposition or unsuspend — the daily limit
    in promote_daily_batch() controls when and how many actually move.
    Think of it as adding to a queue, not jumping it.

    :return: Number of notes tagged.
    """
    if not card_ids:
        return 0

    note_ids = mw.col.db.list(
        f"select distinct nid from cards where id in {ids2str(card_ids)}"
    )

    if not note_ids:
        return 0

    mw.col.tags.bulk_add(note_ids, PROMOTE_TAG)

    return len(note_ids)

def tag_never_promote(card_ids: list[int]) -> int:
    """
    Permanently excludes notes from promotion.

    Applies never_promote_tag and removes auto_tag and promote_tag
    so the exclusion takes effect immediately without waiting for
    the next tagger cycle.

    :return: Number of notes tagged.
    """
    if not card_ids:
        return 0

    note_ids = mw.col.db.list(
        f"select distinct nid from cards where id in {ids2str(card_ids)}"
    )

    if not note_ids:
        return 0

    mw.col.tags.bulk_add(note_ids, NEVER_PROMOTE_TAG)
    mw.col.tags.bulk_remove(note_ids, AUTO_TAG)
    mw.col.tags.bulk_remove(note_ids, PROMOTE_TAG)

    return len(note_ids)