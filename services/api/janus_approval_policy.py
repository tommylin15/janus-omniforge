"""Janus domain operations that an assistant approval cannot grant."""

FORBIDDEN_APPROVAL_OPERATIONS = frozenset({
    "admin",
    "mutate_trade",
    "mutate_note",
    "mutate_watchlist",
    "place_order",
})
