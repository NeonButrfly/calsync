from __future__ import annotations

from sqlalchemy.orm import Session

from calsync.models import AppState


def get_app_state(session: Session, key: str) -> AppState | None:
    return session.get(AppState, key)


def get_app_state_text(session: Session, key: str) -> str | None:
    state = get_app_state(session, key)
    if state is None or state.value_text is None:
        return None

    value = state.value_text.strip()
    return value or None


def require_app_state(session: Session, key: str) -> AppState:
    state = get_app_state(session, key)
    if state is None:
        raise KeyError(key)
    return state


def set_app_state(
    session: Session,
    *,
    key: str,
    value_text: str | None = None,
    value_json: dict[str, object] | None = None,
) -> AppState:
    state = session.get(AppState, key)
    if state is None:
        state = AppState(key=key)
        session.add(state)

    state.value_text = value_text
    state.value_json = value_json
    session.flush()
    return state
