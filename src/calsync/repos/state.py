from __future__ import annotations

from sqlalchemy.orm import Session

from calsync.models import AppState


def get_app_state(session: Session, key: str) -> AppState | None:
    return session.get(AppState, key)


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
