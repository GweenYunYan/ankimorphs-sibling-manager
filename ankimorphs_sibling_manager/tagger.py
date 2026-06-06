from anki.utils import ids2str
from aqt import mw

from ankimorphs_sibling_manager.config import get_tag


#change to mutiple decks later
def get_review_note_ids(decks: list[str]) -> list[int]:
    """
    Finds all notes across the given decks that have at least
    one card in the review queue.
    Returns a list of note IDs.
    """
    if not decks:
        return []

    # Build a combined search query across all decks:
    # ("deck:中文" OR "deck:日本語") is:review
    deck_query = " OR ".join(f'"deck:{deck}"' for deck in decks)
    card_ids = mw.col.find_cards(f"({deck_query}) is:review")

    if not card_ids:
        return []

    # Same as: SELECT DISTINCT nid FROM cards WHERE id IN (1, 2, 3, ...)
    # ids2str() converts a Python list to SQL-safe format: [1,2,3] → "(1,2,3)"
    notes_ids = mw.col.db.list(
         f"select distinct nid from cards where id in {ids2str(card_ids)}"
    )

    return notes_ids

def tag_reviewed_siblings(decks: list[str]) -> int:
    """
    Tags all qualifying notes across the given decks.
    Returns the number of notes tagged.
    """
    note_ids = get_review_note_ids(decks)

    if not note_ids:
        return 0

    # Anki's built-in bulk tagger - one UPDATE across all note IDs at once
    mw.col.tags.bulk_add(note_ids, get_tag())

    return len(note_ids)