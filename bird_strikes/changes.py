"""Pure change planning. All rejection checks precede mutation of current state."""

from dataclasses import dataclass
from typing import Any
from .identity import canonical, key

Payload = dict[str, str]
State = dict[str, Payload]


@dataclass(frozen=True)
class Change:
    record_id: str
    action: str
    fields: list[str]
    before: dict[str, Any] | None
    after: dict[str, Any] | None


class ValidationError(ValueError):
    """The delivery cannot safely replace the currently published state."""


def validate_policy(max_delete_fraction: float, override_reason: str = "") -> None:
    if not 0 <= max_delete_fraction <= 1:
        raise ValidationError("Deletion threshold must be between 0 and 1")
    if max_delete_fraction > 0.05 and not override_reason.strip():
        raise ValidationError(
            "A threshold above 5% requires a recorded override reason"
        )


def apply_batch(
    state: State,
    rows: list[tuple[int, Payload]],
    snapshot: bool = False,
    max_delete_fraction: float = 0.05,
    override_reason: str = "",
) -> list[Change]:
    """Apply supplied-column changes and optionally reconcile a complete snapshot.

    Audit patches keep only changed fields. Inserts keep the complete new value;
    deletes keep the complete old value so removal remains auditable.
    """
    validate_policy(max_delete_fraction, override_reason)
    ids = [r.get("Record ID", "") for _, r in rows]
    if (
        not ids
        or any(not i.isascii() or not i.isdigit() for i in ids)
        or len(set(ids)) != len(ids)
    ):
        raise ValidationError("A nonempty batch of unique numeric IDs is required")
    deleted = sorted(state.keys() - set(ids)) if snapshot else []
    if state and len(deleted) / len(state) > max_delete_fraction:
        raise ValidationError(
            f"Snapshot would delete {len(deleted)}/{len(state)} records; exceeds {max_delete_fraction:.1%} threshold"
        )
    events = []
    for _, incoming in rows:
        rid = incoming["Record ID"]
        old = state.get(rid)
        merged = dict(incoming) if snapshot or old is None else {**old, **incoming}
        if old is None:
            events.append(Change(rid, "INSERT", sorted(merged), None, merged.copy()))
        elif old != merged:
            fields = sorted(
                k
                for k in old.keys() | merged.keys()
                if k not in old or k not in merged or old[k] != merged[k]
            )
            # Presence is explicit: an absent field differs from a present JSON null.
            before = {k: {"present": k in old, "value": old.get(k)} for k in fields}
            after = {
                k: {"present": k in merged, "value": merged.get(k)} for k in fields
            }
            events.append(Change(rid, "UPDATE", fields, before, after))
        state[rid] = merged
    for rid in deleted:
        events.append(Change(rid, "DELETE", [], state.pop(rid), None))
    return events
