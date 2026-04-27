from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException

from backend.app.core.config import Settings
from backend.app.schemas.research import (
    ExportFormat,
    ExportResponse,
    FeedbackRequest,
    KnowledgeEdge,
    KnowledgeGraphResponse,
    KnowledgeNode,
    ResearchQueryRequest,
    ResearchQueryResponse,
    SessionCreateRequest,
    SessionDetail,
    SessionSummary,
    SessionUpdateRequest,
    UserProfile,
)
from backend.app.services.alert_service import AlertService
from backend.app.services.analytics_service import AnalyticsService
from backend.app.services.forecast_service import ForecastService
from backend.app.services.live_provider import LiveDataService
from backend.app.services.research_agent import ResearchAgent
from backend.app.services.research_context import ResearchContextBuilder
from backend.app.services.research_store import ResearchStore
from backend.app.services.repository import DataRepository


class ResearchService:
    def __init__(
        self,
        *,
        store: ResearchStore,
        repository: DataRepository,
        settings: Settings,
        analytics: AnalyticsService,
        forecast_service: ForecastService,
        alert_service: AlertService,
        live_service: LiveDataService,
        context_builder: ResearchContextBuilder,
        agent: ResearchAgent,
    ) -> None:
        self.store = store
        self.repository = repository
        self.settings = settings
        self.analytics = analytics
        self.forecast_service = forecast_service
        self.alert_service = alert_service
        self.live_service = live_service
        self.context_builder = context_builder
        self.agent = agent

    def create_session(self, user: UserProfile, request: SessionCreateRequest) -> SessionSummary:
        title = request.title or f"{request.mode.title()} workspace"
        return self.store.create_session(user.user_id, title, request.mode, request.depth, request.tags)

    def update_session(self, user: UserProfile, session_id: str, request: SessionUpdateRequest) -> SessionSummary:
        return self.store.update_session(user.user_id, session_id, request.model_dump())

    def list_sessions(self, user: UserProfile) -> list[SessionSummary]:
        return self.store.list_sessions(user.user_id)

    def get_session_detail(self, user: UserProfile, session_id: str) -> SessionDetail:
        session = self.store.get_session(user.user_id, session_id)
        return SessionDetail(
            session=session,
            messages=self.store.session_messages(session_id),
            reports=self.store.session_reports(session_id),
            steps=self.store.session_steps(session_id),
        )

    def delete_session(self, user: UserProfile, session_id: str) -> None:
        self.store.delete_session(user.user_id, session_id)

    async def run_query(self, user: UserProfile, request: ResearchQueryRequest) -> ResearchQueryResponse:
        session = (
            self.store.get_session(user.user_id, request.session_id)
            if request.session_id
            else self.store.create_session(
                user.user_id,
                self._default_session_title(request.query),
                request.mode,
                request.depth,
                tags=[request.mode, request.network_scope],
            )
        )
        site_id = request.site_id or self.settings.default_site_id
        self.store.add_message(session.session_id, "user", request.query)
        trend = self.analytics.historical_trend(site_id, hours=self.settings.lookback_hours)
        live = self.live_service.get_live_snapshot(site_id)
        forecast = self.forecast_service.generate_forecast(
            request=self._forecast_request(site_id)
        )
        alerts = self.alert_service.current_alerts(site_id)
        live_network = self.live_service.get_live_network(request.network_scope)
        chunks = self.context_builder.build(
            site_id=site_id,
            trend=trend,
            live=live,
            forecast=forecast,
            alerts=alerts,
            live_network=live_network,
            dashboard_context=request.dashboard_context,
        )
        report, steps, degraded = await self.agent.run(
            session_id=session.session_id,
            query=request.query,
            mode=request.mode,
            depth=request.depth,
            chunks=chunks,
        )
        self.store.add_message(session.session_id, "assistant", report.overview)
        self.store.store_report(session.session_id, report, steps)
        session = self.store.get_session(user.user_id, session.session_id)
        return ResearchQueryResponse(
            session=session,
            messages=self.store.session_messages(session.session_id),
            report=report,
            steps=steps,
            degraded=degraded,
        )

    def export_report(self, user: UserProfile, session_id: str, report_id: str, export_format: ExportFormat) -> ExportResponse:
        session = self.store.get_session(user.user_id, session_id)
        report = next((item for item in self.store.session_reports(session_id) if item.report_id == report_id), None)
        if report is None:
            raise HTTPException(status_code=404, detail="Report not found.")
        filename = f"{session.session_id}_{report_id}.{ 'md' if export_format == 'markdown' else export_format }"
        target = self.settings.research_export_dir / filename
        if export_format == "json":
            target.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        elif export_format == "markdown":
            target.write_text(report.summary_markdown, encoding="utf-8")
        else:
            self._write_pdf(target, report.title, report.summary_markdown)
        return ExportResponse(filename=filename, format=export_format, download_url=f"/research/exports/{filename}")

    def record_feedback(self, feedback: FeedbackRequest) -> None:
        self.store.record_feedback(
            feedback.report_id,
            feedback.target_type,
            feedback.target_key,
            feedback.value,
            feedback.notes,
        )

    def knowledge_graph(self, user: UserProfile) -> KnowledgeGraphResponse:
        raw_nodes, raw_edges = self.store.knowledge_graph(user.user_id)
        return KnowledgeGraphResponse(
            nodes=[KnowledgeNode.model_validate(node) for node in raw_nodes],
            edges=[KnowledgeEdge.model_validate(edge) for edge in raw_edges],
        )

    @staticmethod
    def _default_session_title(query: str) -> str:
        cleaned = " ".join(query.strip().split())
        return cleaned[:72] if cleaned else "New research session"

    def _forecast_request(self, site_id: int):
        from backend.app.schemas.api import ForecastRequest

        return ForecastRequest(site_id=site_id, horizon_hours=self.settings.forecast_horizon_hours)

    @staticmethod
    def _write_pdf(target: Path, title: str, markdown_text: str) -> None:
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas

            pdf = canvas.Canvas(str(target), pagesize=letter)
            width, height = letter
            y = height - 50
            pdf.setFont("Helvetica-Bold", 16)
            pdf.drawString(40, y, title)
            y -= 28
            pdf.setFont("Helvetica", 10)
            for line in markdown_text.splitlines():
                if y < 40:
                    pdf.showPage()
                    pdf.setFont("Helvetica", 10)
                    y = height - 40
                pdf.drawString(40, y, line[:110])
                y -= 14
            pdf.save()
        except Exception:
            target.write_text(markdown_text, encoding="utf-8")
