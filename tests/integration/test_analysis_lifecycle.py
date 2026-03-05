from httpx import AsyncClient
from sqlalchemy import select

from app.models.db import Analysis, ClassifiedEmail
from tests.conftest import test_session_maker
from tests.integration.conftest import wait_for_analysis
from tests.integration.fakes import FakeClassificationService, FakeEmailService


async def test_full_analysis_creates_and_completes(
    authenticated_integration_client: AsyncClient,
    fake_email_service: FakeEmailService,
) -> None:
    client = authenticated_integration_client

    response = await client.post(
        "/api/v1/analysis",
        json={"query": "is:unread", "max_emails": 100},
    )
    assert response.status_code == 202
    data = response.json()
    analysis_id = data["id"]
    assert data["status"] == "pending"

    result = await wait_for_analysis(client=client, analysis_id=analysis_id)

    assert result["status"] == "completed"
    assert result["total_emails"] == len(fake_email_service.emails)
    assert result["processed_emails"] == len(fake_email_service.emails)
    assert result["error_message"] is None

    assert len(result["classified_emails"]) == 5
    categories = {e["category"] for e in result["classified_emails"]}
    assert "newsletters" in categories
    assert "promotions" in categories
    assert "primary" in categories
    assert "social" in categories
    assert "updates" in categories

    assert result["summary"] is not None
    summary_map = {s["category"]: s for s in result["summary"]}
    assert summary_map["newsletters"]["count"] == 1
    assert summary_map["promotions"]["count"] == 1
    assert summary_map["primary"]["count"] == 1

    for summary_item in result["summary"]:
        assert len(summary_item["recommended_actions"]) > 0


async def test_analysis_with_no_emails(
    authenticated_integration_client: AsyncClient,
    fake_email_service: FakeEmailService,
) -> None:
    fake_email_service.emails = []
    client = authenticated_integration_client

    response = await client.post(
        "/api/v1/analysis",
        json={"query": "is:unread", "max_emails": 100},
    )
    assert response.status_code == 202
    analysis_id = response.json()["id"]

    result = await wait_for_analysis(client=client, analysis_id=analysis_id)

    assert result["status"] == "completed"
    assert result["total_emails"] == 0
    assert result["processed_emails"] == 0
    assert result["classified_emails"] == []


async def test_analysis_failure_sets_error_status(
    authenticated_integration_client: AsyncClient,
    fake_classification_service: FakeClassificationService,
) -> None:
    fake_classification_service.should_fail = True
    client = authenticated_integration_client

    response = await client.post(
        "/api/v1/analysis",
        json={"query": "is:unread", "max_emails": 100},
    )
    assert response.status_code == 202
    analysis_id = response.json()["id"]

    result = await wait_for_analysis(client=client, analysis_id=analysis_id)

    assert result["status"] == "failed"
    assert "Classification API unavailable" in result["error_message"]


async def test_analysis_persists_classified_emails_to_db(
    authenticated_integration_client: AsyncClient,
) -> None:
    client = authenticated_integration_client

    response = await client.post(
        "/api/v1/analysis",
        json={"query": "is:unread", "max_emails": 100},
    )
    analysis_id = response.json()["id"]
    await wait_for_analysis(client=client, analysis_id=analysis_id)

    async with test_session_maker() as session:
        emails = (
            await session.execute(
                select(ClassifiedEmail).where(
                    ClassifiedEmail.analysis_id == analysis_id
                )
            )
        ).scalars().all()

        assert len(emails) == 5
        for email in emails:
            assert email.category is not None
            assert email.importance is not None
            assert email.sender_type is not None
            assert email.confidence is not None


async def test_analysis_stores_category_actions_in_db(
    authenticated_integration_client: AsyncClient,
) -> None:
    client = authenticated_integration_client

    response = await client.post(
        "/api/v1/analysis",
        json={"query": "is:unread", "max_emails": 100},
    )
    analysis_id = response.json()["id"]
    await wait_for_analysis(client=client, analysis_id=analysis_id)

    async with test_session_maker() as session:
        analysis = (
            await session.execute(
                select(Analysis).where(Analysis.id == analysis_id)
            )
        ).scalar_one()

        assert analysis.category_actions is not None
        assert "newsletters" in analysis.category_actions
        assert "promotions" in analysis.category_actions
        assert "primary" in analysis.category_actions


async def test_list_analyses_returns_created_analysis(
    authenticated_integration_client: AsyncClient,
) -> None:
    client = authenticated_integration_client

    await client.post(
        "/api/v1/analysis",
        json={"query": "is:unread", "max_emails": 100},
    )

    response = await client.get("/api/v1/analysis")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(a["query"] == "is:unread" for a in data["analyses"])


async def test_delete_analysis_removes_from_db(
    authenticated_integration_client: AsyncClient,
) -> None:
    client = authenticated_integration_client

    response = await client.post(
        "/api/v1/analysis",
        json={"query": "is:unread", "max_emails": 100},
    )
    analysis_id = response.json()["id"]
    await wait_for_analysis(client=client, analysis_id=analysis_id)

    delete_response = await client.delete(f"/api/v1/analysis/{analysis_id}")
    assert delete_response.status_code == 200

    get_response = await client.get(f"/api/v1/analysis/{analysis_id}")
    assert get_response.status_code == 404

    async with test_session_maker() as session:
        emails = (
            await session.execute(
                select(ClassifiedEmail).where(
                    ClassifiedEmail.analysis_id == analysis_id
                )
            )
        ).scalars().all()
        assert len(emails) == 0
