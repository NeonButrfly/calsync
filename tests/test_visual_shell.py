from __future__ import annotations

import pyotp
import pytest
from fastapi.testclient import TestClient

from test_dashboard_pages import _build_client


@pytest.fixture()
def client(tmp_path) -> TestClient:
    yield from _build_client(tmp_path, seed_mock_account=True)


@pytest.fixture()
def authenticated_client(client: TestClient) -> TestClient:
    password_step = client.post(
        "/login",
        data={"identifier": "admin", "password": "StrongPassword1!"},
        follow_redirects=False,
    )
    assert password_step.status_code == 303

    mfa_step = client.post(
        "/login/mfa",
        data={"code": pyotp.TOTP(client.app.state.test_totp_secret).now()},
        follow_redirects=False,
    )
    assert mfa_step.status_code == 303
    return client


def test_admin_shell_uses_scheduling_navigation_labels(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.get("/admin")

    assert response.status_code == 200
    assert "Scheduling that feels calm and obvious" in response.text
    assert 'href="/admin"' in response.text
    assert ">Home<" in response.text
    assert 'href="/admin/flightboard"' in response.text
    assert ">Calendar<" in response.text
    assert 'href="/admin/accounts"' in response.text
    assert ">Connections<" in response.text
    assert 'href="/admin/calendars"' in response.text
    assert ">Availability<" in response.text
    assert 'href="/admin/problems"' in response.text
    assert ">Trust<" in response.text
    assert 'href="/admin/providers"' in response.text
    assert ">Settings<" in response.text
    assert 'class="app-sidebar__nav-scroll"' in response.text
    assert "Review queue" not in response.text
    assert "Connect calendars" not in response.text
