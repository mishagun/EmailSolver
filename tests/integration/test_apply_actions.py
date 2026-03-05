from httpx import AsyncClient
from sqlalchemy import select

from app.models.db import ClassifiedEmail
from tests.conftest import test_session_maker
from tests.integration.conftest import wait_for_analysis
from tests.integration.fakes import FakeEmailService


async def _create_completed_analysis(client: AsyncClient) -> int:
    response = await client.post(
        "/api/v1/analysis",
        json={"query": "is:unread", "max_emails": 100},
    )
    analysis_id = response.json()["id"]
    await wait_for_analysis(client=client, analysis_id=analysis_id)
    return analysis_id


async def test_apply_move_to_category_updates_db_and_calls_gmail(
    authenticated_integration_client: AsyncClient,
    fake_email_service: FakeEmailService,
) -> None:
    client = authenticated_integration_client
    analysis_id = await _create_completed_analysis(client=client)

    response = await client.post(
        f"/api/v1/analysis/{analysis_id}/apply",
        json={"action": "move_to_category", "category": "promotions"},
    )
    assert response.status_code == 200

    assert len(fake_email_service.labels_created) > 0
    assert "promotions" in fake_email_service.labels_created

    modify_msg_ids = []
    for call in fake_email_service.modify_calls:
        if call["add_labels"]:
            modify_msg_ids.extend(call["message_ids"])
    assert "msg-1" in modify_msg_ids

    async with test_session_maker() as session:
        promo_emails = (
            await session.execute(
                select(ClassifiedEmail).where(
                    ClassifiedEmail.analysis_id == analysis_id,
                    ClassifiedEmail.category == "promotions",
                )
            )
        ).scalars().all()
        for email in promo_emails:
            assert email.action_taken == "move_to_category"


async def test_apply_mark_read_removes_unread_label(
    authenticated_integration_client: AsyncClient,
    fake_email_service: FakeEmailService,
) -> None:
    client = authenticated_integration_client
    analysis_id = await _create_completed_analysis(client=client)

    response = await client.post(
        f"/api/v1/analysis/{analysis_id}/apply",
        json={"action": "mark_read", "category": "newsletters"},
    )
    assert response.status_code == 200

    found_unread_removal = any(
        "UNREAD" in (call.get("remove_labels") or [])
        for call in fake_email_service.modify_calls
    )
    assert found_unread_removal

    async with test_session_maker() as session:
        newsletter_emails = (
            await session.execute(
                select(ClassifiedEmail).where(
                    ClassifiedEmail.analysis_id == analysis_id,
                    ClassifiedEmail.category == "newsletters",
                )
            )
        ).scalars().all()
        for email in newsletter_emails:
            assert email.action_taken == "mark_read"


async def test_apply_mark_spam_adds_spam_label(
    authenticated_integration_client: AsyncClient,
    fake_email_service: FakeEmailService,
) -> None:
    client = authenticated_integration_client
    analysis_id = await _create_completed_analysis(client=client)

    response = await client.post(
        f"/api/v1/analysis/{analysis_id}/apply",
        json={"action": "mark_spam", "category": "promotions"},
    )
    assert response.status_code == 200

    found_spam_add = any(
        "SPAM" in (call.get("add_labels") or [])
        for call in fake_email_service.modify_calls
    )
    assert found_spam_add


async def test_apply_actions_to_specific_email_ids(
    authenticated_integration_client: AsyncClient,
    fake_email_service: FakeEmailService,
) -> None:
    client = authenticated_integration_client
    analysis_id = await _create_completed_analysis(client=client)

    get_response = await client.get(f"/api/v1/analysis/{analysis_id}")
    classified = get_response.json()["classified_emails"]
    target_id = classified[0]["id"]

    fake_email_service.modify_calls.clear()

    response = await client.post(
        f"/api/v1/analysis/{analysis_id}/apply",
        json={"action": "mark_read", "email_ids": [target_id]},
    )
    assert response.status_code == 200

    all_modified_msg_ids = []
    for call in fake_email_service.modify_calls:
        all_modified_msg_ids.extend(call["message_ids"])
    assert len(all_modified_msg_ids) == 1


async def test_apply_actions_on_incomplete_analysis_fails(
    authenticated_integration_client: AsyncClient,
) -> None:
    client = authenticated_integration_client

    response = await client.post(
        "/api/v1/analysis",
        json={"query": "is:unread", "max_emails": 100},
    )
    analysis_id = response.json()["id"]

    apply_response = await client.post(
        f"/api/v1/analysis/{analysis_id}/apply",
        json={"action": "mark_read"},
    )
    assert apply_response.status_code == 400


async def test_apply_keep_action_does_not_modify_gmail(
    authenticated_integration_client: AsyncClient,
    fake_email_service: FakeEmailService,
) -> None:
    client = authenticated_integration_client
    analysis_id = await _create_completed_analysis(client=client)

    fake_email_service.modify_calls.clear()

    response = await client.post(
        f"/api/v1/analysis/{analysis_id}/apply",
        json={"action": "keep", "category": "primary"},
    )
    assert response.status_code == 200
    assert len(fake_email_service.modify_calls) == 0
