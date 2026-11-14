"""Aggregate independently computed dimensions over assessed weights only."""
from typing import Any, Dict, Iterable, List, Optional, Tuple


def aggregate_dimensions(dimensions: Iterable[Tuple[str, Optional[int], int]],
                         minimum_assessed_weight: int = 25) -> Dict[str, Any]:
    dimensions = list(dimensions)
    active_weight = sum(weight for _, value, weight in dimensions if value is not None)
    earned = sum(value for _, value, _ in dimensions if value is not None)
    provisional = int(round(100.0 * earned / active_weight)) if active_weight else None
    assessable = active_weight >= minimum_assessed_weight
    breakdown = [{
        "key": key, "label": key.replace("_", " ").title(),
        "earned": value if value is not None else None,
        "possible": weight if value is not None else 0,
        "weight": weight,
        "deducted": weight - value if value is not None else None,
        "assessed": value is not None,
    } for key, value, weight in dimensions]
    return {
        "score": provisional if assessable else None,
        "score_status": "assessed" if assessable else "insufficient_data",
        "provisional_score": provisional if not assessable else None,
        "active_weight": active_weight,
        "earned": earned,
        "breakdown": breakdown,
    }
