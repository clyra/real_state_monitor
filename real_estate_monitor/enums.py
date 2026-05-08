from enum import Enum


class ListingEventType(Enum):
    NEW = "new"
    UPDATED = "updated"
    PRICE_CHANGED = "price_changed"
    REMOVED = "removed"
    REACTIVATED = "reactivated"
