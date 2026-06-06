from anki.utils import ids2str
from aqt import mw

TAG = "has-reviewed-sibling"

#change to mutiple decks later
def get_review_note_ids(deck: str) -> list[int]:
    """
    Finds all notes in the given deck that have at least
    one card currently in the review queue (is:review).
    Returns a list of note IDs.
    """
    card_ids = mw.col.find_cards(f"deck:{deck} is:review")

    if not card_ids:
        return []

    # Same as: SELECT DISTINCT nid FROM cards WHERE id IN (1, 2, 3, ...)
    # ids2str() converts a Python list to SQL-safe format: [1,2,3] → "(1,2,3)"
    notes_ids = mw.col.db.list(
        f"select distinct nid from cards where id in {ids2str(card_ids)}"
    )

    return notes_ids

def tag_reviewed_siblings(deck: str) -> int:
    """
    Tags all notes in the deck that have a review-state card.
    Returns the number of notes tagged.
    """
    note_ids = get_review_note_ids(deck)

    if not note_ids:
        return 0

    # Anki's built-in bulk tagger - one UPDATE across all note IDs at once
    mw.col.tags.bulk_add(note_ids, TAG)

    return len(note_ids)