from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

from src.db.models import Card, ReviewState, Topic


@dataclass
class QuizSelectionConfig:
    """Configuration for how many cards to surface per session."""

    default_limit: int = 20


class QuizService:
    """
    In-memory selection logic for quiz cards.

    This service is intentionally DB-agnostic: it operates on collections
    of `Card` and `ReviewState` objects provided by the caller. API layers
    can fetch data from the database, call this service to choose cards,
    and then persist any changes.
    """

    def __init__(self, config: Optional[QuizSelectionConfig] = None) -> None:
        self.config = config or QuizSelectionConfig()

    def get_next_cards(
        self,
        *,
        user_id: int,
        cards: Sequence[Card],
        review_states: Iterable[ReviewState],
        topics: Optional[Sequence[str]] = None,
        limit: Optional[int] = None,
        now: Optional[dt.datetime] = None,
    ) -> List[Card]:
        """
        Select the next set of cards for a user.

        Strategy:
        - Prioritize cards with due `ReviewState` (due_at <= now).
        - Fill remaining slots with new cards (no ReviewState for this user).
        - Optionally filter by topic names (Topic.name).
        """
        if limit is None or limit <= 0:
            limit = self.config.default_limit

        now = now or dt.datetime.now(dt.timezone.utc)

        topic_filter = set(topics) if topics else None

        def _topic_name(card: Card) -> Optional[str]:
            topic: Optional[Topic] = getattr(card, "topic", None)
            if topic is None:
                return None
            return getattr(topic, "name", None)

        # Filter cards by topic if requested.
        filtered_cards: List[Card] = []
        for card in cards:
            if topic_filter is None:
                filtered_cards.append(card)
            else:
                name = _topic_name(card)
                if name in topic_filter:
                    filtered_cards.append(card)

        # Map of card_id -> ReviewState for this user.
        user_states = {
            rs.card_id: rs
            for rs in review_states
            if rs.user_id == user_id
        }

        # 1) Due cards: states with due_at <= now.
        due_cards: List[Card] = []
        due_entries = []
        for card in filtered_cards:
            state = user_states.get(card.id)
            if state and state.due_at is not None and state.due_at <= now:
                due_entries.append((state.due_at, card))

        # Sort due cards by due_at earliest first.
        for _, card in sorted(due_entries, key=lambda x: x[0]):
            due_cards.append(card)
            if len(due_cards) >= limit:
                return due_cards

        # 2) New cards: cards with no ReviewState for this user.
        new_cards: List[Card] = []
        for card in filtered_cards:
            if card.id not in user_states:
                new_cards.append(card)
                if len(due_cards) + len(new_cards) >= limit:
                    break

        return due_cards + new_cards

