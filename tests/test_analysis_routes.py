from unittest.mock import AsyncMock

import pytest

from app.core.dependencies import get_analysis_service, get_classified_email_repository
from app.models.db import Analysis, User
from app.services.analysis_service import AnalysisService


class TestCreateAnalysis:
    @pytest.mark.asyncio
    async def test_creates_analysis_returns_202(
        self, authenticated_client, mock_analysis_service: AnalysisService
    ) -> None:
        authenticated_client._transport.app.dependency_overrides[get_analysis_service] = (
            lambda: mock_analysis_service
        )
        response = await authenticated_client.post(
            "/api/v1/analysis",
            json={"query": "is:unread", "max_emails": 50},
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert data["query"] == "is:unread"
        assert "id" in data
        mock_analysis_service.start_analysis.assert_called_once()

    @pytest.mark.asyncio
    async def test_defaults_to_unread_query(
        self, authenticated_client, mock_analysis_service: AnalysisService
    ) -> None:
        authenticated_client._transport.app.dependency_overrides[get_analysis_service] = (
            lambda: mock_analysis_service
        )
        response = await authenticated_client.post(
            "/api/v1/analysis",
            json={"max_emails": 50},
        )
        assert response.status_code == 202
        assert response.json()["query"] == "is:unread"
        call_kwargs = mock_analysis_service.start_analysis.call_args.kwargs
        assert call_kwargs["query"] == "is:unread"

    @pytest.mark.asyncio
    async def test_creates_analysis_with_custom_categories(
        self, authenticated_client, mock_analysis_service: AnalysisService
    ) -> None:
        authenticated_client._transport.app.dependency_overrides[get_analysis_service] = (
            lambda: mock_analysis_service
        )
        response = await authenticated_client.post(
            "/api/v1/analysis",
            json={
                "query": "is:unread",
                "max_emails": 50,
                "custom_categories": ["receipts", "travel"],
            },
        )
        assert response.status_code == 202
        call_kwargs = mock_analysis_service.start_analysis.call_args.kwargs
        assert call_kwargs["custom_categories"] == ["receipts", "travel"]

    @pytest.mark.asyncio
    async def test_creates_inbox_scan_analysis(
        self, authenticated_client, mock_analysis_service: AnalysisService
    ) -> None:
        # Arrange
        authenticated_client._transport.app.dependency_overrides[get_analysis_service] = (
            lambda: mock_analysis_service
        )

        # Act
        response = await authenticated_client.post(
            "/api/v1/analysis",
            json={
                "query": "is:unread",
                "max_emails": 50,
                "analysis_type": "inbox_scan",
            },
        )

        # Assert
        assert response.status_code == 202
        data = response.json()
        assert data["analysis_type"] == "inbox_scan"
        call_kwargs = mock_analysis_service.start_analysis.call_args.kwargs
        assert call_kwargs["analysis_type"] == "inbox_scan"

    @pytest.mark.asyncio
    async def test_defaults_to_ai_analysis_type(
        self, authenticated_client, mock_analysis_service: AnalysisService
    ) -> None:
        # Arrange
        authenticated_client._transport.app.dependency_overrides[get_analysis_service] = (
            lambda: mock_analysis_service
        )

        # Act
        response = await authenticated_client.post(
            "/api/v1/analysis",
            json={"query": "is:unread", "max_emails": 50},
        )

        # Assert
        assert response.status_code == 202
        data = response.json()
        assert data["analysis_type"] == "ai"
        call_kwargs = mock_analysis_service.start_analysis.call_args.kwargs
        assert call_kwargs["analysis_type"] == "ai"

    @pytest.mark.asyncio
    async def test_rejects_unauthenticated(self, test_client) -> None:
        response = await test_client.post(
            "/api/v1/analysis",
            json={"query": "is:unread"},
        )
        assert response.status_code in (401, 403)


class TestListAnalyses:
    @pytest.mark.asyncio
    async def test_returns_user_analyses(
        self, authenticated_client, analysis_with_classified_emails: Analysis
    ) -> None:
        response = await authenticated_client.get("/api/v1/analysis")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert any(
            a["id"] == analysis_with_classified_emails.id for a in data["analyses"]
        )

    @pytest.mark.asyncio
    async def test_returns_analysis_type_in_list(
        self, authenticated_client, analysis_with_classified_emails: Analysis
    ) -> None:
        # Arrange / Act
        response = await authenticated_client.get("/api/v1/analysis")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        analysis_data = next(
            a for a in data["analyses"]
            if a["id"] == analysis_with_classified_emails.id
        )
        assert "analysis_type" in analysis_data
        assert analysis_data["analysis_type"] == "ai"

    @pytest.mark.asyncio
    async def test_returns_empty_for_new_user(self, authenticated_client) -> None:
        response = await authenticated_client.get("/api/v1/analysis")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["analyses"] == []


class TestGetAnalysis:
    @pytest.mark.asyncio
    async def test_returns_detail_with_emails(
        self, authenticated_client, analysis_with_classified_emails: Analysis
    ) -> None:
        aid = analysis_with_classified_emails.id
        response = await authenticated_client.get(f"/api/v1/analysis/{aid}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == aid
        assert data["status"] == "completed"
        assert len(data["classified_emails"]) == 2

    @pytest.mark.asyncio
    async def test_returns_summary_in_response(
        self, authenticated_client, analysis_with_classified_emails: Analysis
    ) -> None:
        aid = analysis_with_classified_emails.id
        response = await authenticated_client.get(f"/api/v1/analysis/{aid}")
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert isinstance(data["summary"], list)
        assert len(data["summary"]) >= 1
        summary_item = data["summary"][0]
        assert "category" in summary_item
        assert "count" in summary_item
        assert "recommended_actions" in summary_item
        assert summary_item["category"] == "promotions"
        assert summary_item["count"] == 2

    @pytest.mark.asyncio
    async def test_summary_includes_category_actions(
        self, authenticated_client, db_session, analysis_with_classified_emails: Analysis
    ) -> None:
        analysis_with_classified_emails.category_actions = {
            "promotions": ["mark_read", "move_to_category"]
        }
        await db_session.commit()

        aid = analysis_with_classified_emails.id
        response = await authenticated_client.get(f"/api/v1/analysis/{aid}")
        data = response.json()
        promo_summary = next(
            s for s in data["summary"] if s["category"] == "promotions"
        )
        assert promo_summary["recommended_actions"] == ["mark_read", "move_to_category"]

    @pytest.mark.asyncio
    async def test_returns_analysis_type_in_detail(
        self, authenticated_client, analysis_with_classified_emails: Analysis
    ) -> None:
        # Arrange
        aid = analysis_with_classified_emails.id

        # Act
        response = await authenticated_client.get(f"/api/v1/analysis/{aid}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "analysis_type" in data
        assert data["analysis_type"] == "ai"

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent(self, authenticated_client) -> None:
        response = await authenticated_client.get("/api/v1/analysis/99999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_404_for_other_user(
        self, authenticated_client, db_session, security_service
    ) -> None:
        other_user = User(
            email="other@example.com",
            google_id="google-other",
            display_name="Other User",
            encrypted_access_token=security_service.encrypt_token(token="fake"),
            encrypted_refresh_token=security_service.encrypt_token(token="fake"),
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        analysis = Analysis(
            user_id=other_user.id, status="completed", query="test"
        )
        db_session.add(analysis)
        await db_session.commit()
        await db_session.refresh(analysis)

        response = await authenticated_client.get(
            f"/api/v1/analysis/{analysis.id}"
        )
        assert response.status_code == 404


class TestApplyActions:
    @pytest.mark.asyncio
    async def test_validates_ownership(self, authenticated_client) -> None:
        response = await authenticated_client.post(
            "/api/v1/analysis/99999/apply",
            json={"action": "mark_read"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_rejects_if_not_completed(
        self, authenticated_client, db_session, test_user
    ) -> None:
        analysis = Analysis(
            user_id=test_user.id, status="processing", query="test"
        )
        db_session.add(analysis)
        await db_session.commit()
        await db_session.refresh(analysis)

        response = await authenticated_client.post(
            f"/api/v1/analysis/{analysis.id}/apply",
            json={"action": "mark_read"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_apply_with_action_and_email_ids(
        self,
        authenticated_client,
        analysis_with_classified_emails: Analysis,
        mock_analysis_service: AnalysisService,
    ) -> None:
        authenticated_client._transport.app.dependency_overrides[get_analysis_service] = (
            lambda: mock_analysis_service
        )
        aid = analysis_with_classified_emails.id
        email_id = analysis_with_classified_emails.classified_emails[0].id

        response = await authenticated_client.post(
            f"/api/v1/analysis/{aid}/apply",
            json={"action": "mark_read", "email_ids": [email_id]},
        )
        assert response.status_code == 200
        mock_analysis_service.apply_actions_for_analysis.assert_awaited_once()
        call_kwargs = mock_analysis_service.apply_actions_for_analysis.call_args.kwargs
        assert call_kwargs["action"] == "mark_read"

    @pytest.mark.asyncio
    async def test_apply_by_category(
        self,
        authenticated_client,
        analysis_with_classified_emails: Analysis,
        mock_analysis_service: AnalysisService,
    ) -> None:
        mock_repo = AsyncMock()
        mock_repo.find_by_category_and_analysis = AsyncMock(
            return_value=list(analysis_with_classified_emails.classified_emails)
        )

        authenticated_client._transport.app.dependency_overrides[get_analysis_service] = (
            lambda: mock_analysis_service
        )
        authenticated_client._transport.app.dependency_overrides[
            get_classified_email_repository
        ] = lambda: mock_repo

        aid = analysis_with_classified_emails.id
        response = await authenticated_client.post(
            f"/api/v1/analysis/{aid}/apply",
            json={"action": "move_to_category", "category": "promotions"},
        )
        assert response.status_code == 200
        mock_repo.find_by_category_and_analysis.assert_awaited_once_with(
            category="promotions", analysis_id=aid
        )

    @pytest.mark.asyncio
    async def test_apply_by_sender_domain(
        self,
        authenticated_client,
        analysis_with_classified_emails: Analysis,
        mock_analysis_service: AnalysisService,
    ) -> None:
        mock_repo = AsyncMock()
        mock_repo.find_by_sender_domain_and_analysis = AsyncMock(
            return_value=list(analysis_with_classified_emails.classified_emails)
        )

        authenticated_client._transport.app.dependency_overrides[get_analysis_service] = (
            lambda: mock_analysis_service
        )
        authenticated_client._transport.app.dependency_overrides[
            get_classified_email_repository
        ] = lambda: mock_repo

        aid = analysis_with_classified_emails.id
        response = await authenticated_client.post(
            f"/api/v1/analysis/{aid}/apply",
            json={"action": "mark_spam", "sender_domain": "example.com"},
        )
        assert response.status_code == 200
        mock_repo.find_by_sender_domain_and_analysis.assert_awaited_once_with(
            sender_domain="example.com", analysis_id=aid
        )

    @pytest.mark.asyncio
    async def test_apply_all(
        self,
        authenticated_client,
        analysis_with_classified_emails: Analysis,
        mock_analysis_service: AnalysisService,
    ) -> None:
        authenticated_client._transport.app.dependency_overrides[get_analysis_service] = (
            lambda: mock_analysis_service
        )
        aid = analysis_with_classified_emails.id

        response = await authenticated_client.post(
            f"/api/v1/analysis/{aid}/apply",
            json={"action": "mark_read"},
        )
        assert response.status_code == 200
        mock_analysis_service.apply_actions_for_analysis.assert_awaited_once()
        call_kwargs = mock_analysis_service.apply_actions_for_analysis.call_args.kwargs
        assert len(call_kwargs["classified_emails"]) == 2
        assert call_kwargs["action"] == "mark_read"

    @pytest.mark.asyncio
    async def test_rejects_invalid_action(
        self, authenticated_client, analysis_with_classified_emails: Analysis
    ) -> None:
        aid = analysis_with_classified_emails.id
        response = await authenticated_client.post(
            f"/api/v1/analysis/{aid}/apply",
            json={"action": "invalid_action"},
        )
        assert response.status_code == 422


class TestDeleteAnalysis:
    @pytest.mark.asyncio
    async def test_deletes_analysis(
        self, authenticated_client, analysis_with_classified_emails: Analysis
    ) -> None:
        aid = analysis_with_classified_emails.id
        response = await authenticated_client.delete(f"/api/v1/analysis/{aid}")
        assert response.status_code == 200

        response = await authenticated_client.get(f"/api/v1/analysis/{aid}")
        assert response.status_code == 404
