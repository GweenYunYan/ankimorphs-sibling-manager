from anki.utils import ids2str
from aqt import mw


from .config import get_tags


def get_review_note_ids(decks: list[str]) -> list[int]:
    """
    Finds all notes across the given decks that have at least one card
    in the review queue. Excludes never-promote notes so the tagger
    doesn't re-tag them on future recalcs.

    :return: List of note IDs.
    """
    if not decks:
        return []

    tags = get_tags()
    never_promote_tag = tags.get("never_promote_tag")

    # Build a combined search query across all decks:
    # ("deck:中文" OR "deck:日本語") is:review
    deck_query = " OR ".join(f'"deck:{deck}"' for deck in decks)
    card_ids = mw.col.find_cards(
        f'({deck_query}) is:review -tag:{never_promote_tag}'
    )

    if not card_ids:
        return []

    # Same as: SELECT DISTINCT nid FROM cards WHERE id IN (1, 2, 3, ...)
    # ids2str() converts a Python list to SQL-safe format: [1,2,3] → "(1,2,3)"
    note_ids = mw.col.db.list(
        f"select distinct nid from cards where id in {ids2str(card_ids)}"
    )
    return note_ids

def tag_reviewed_siblings(decks: list[str]) -> int:
    """
    Tags qualifying notes with auto_tag.
    :return: Number of notes tagged.
    """
    note_ids = get_review_note_ids(decks)

    if not note_ids:
        return 0

    # Anki's built-in bulk tagger - one UPDATE across all note IDs at once
    auto_tag = get_tags().get("auto_tag")
    mw.col.tags.bulk_add(note_ids, auto_tag)
    return len(note_ids)
