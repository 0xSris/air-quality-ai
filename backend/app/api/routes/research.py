from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from backend.app.core.config import get_settings
from backend.app.core.dependencies import get_current_user, get_research_service
from backend.app.schemas.research import (
    ExportFormat,
    ExportResponse,
    FeedbackRequest,
    KnowledgeGraphResponse,
    ResearchQueryRequest,
    ResearchQueryResponse,
    SessionCreateRequest,
    SessionDetail,
    SessionSummary,
    SessionUpdateRequest,
)
from backend.app.services.research_service import ResearchService

router = APIRouter(prefix="/research", tags=["research"])


@router.get("/sessions", response_model=list[SessionSummary])
def list_sessions(auth=Depends(get_current_user), service: ResearchService = Depends(get_research_service)) -> list[SessionSummary]:
    return service.list_sessions(auth["user"])


@router.post("/sessions", response_model=SessionSummary)
def create_session(
    request: SessionCreateRequest,
    auth=Depends(get_current_user),
    service: ResearchService = Depends(get_research_service),
) -> SessionSummary:
    return service.create_session(auth["user"], request)


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def session_detail(
    session_id: str,
    auth=Depends(get_current_user),
    service: ResearchService = Depends(get_research_service),
) -> SessionDetail:
    return service.get_session_detail(auth["user"], session_id)


@router.patch("/sessions/{session_id}", response_model=SessionSummary)
def update_session(
    session_id: str,
    request: SessionUpdateRequest,
    auth=Depends(get_current_user),
    service: ResearchService = Depends(get_research_service),
) -> SessionSummary:
    return service.update_session(auth["user"], session_id, request)


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    auth=Depends(get_current_user),
    service: ResearchService = Depends(get_research_service),
) -> dict:
    service.delete_session(auth["user"], session_id)
    return {"status": "ok"}


@router.post("/query", response_model=ResearchQueryResponse)
async def run_query(
    request: ResearchQueryRequest,
    auth=Depends(get_current_user),
    service: ResearchService = Depends(get_research_service),
) -> ResearchQueryResponse:
    return await service.run_query(auth["user"], request)


@router.post("/feedback")
def feedback(request: FeedbackRequest, auth=Depends(get_current_user), service: ResearchService = Depends(get_research_service)) -> dict:
    service.record_feedback(request)
    return {"status": "ok"}


@router.get("/graph", response_model=KnowledgeGraphResponse)
def graph(auth=Depends(get_current_user), service: ResearchService = Depends(get_research_service)) -> KnowledgeGraphResponse:
    return service.knowledge_graph(auth["user"])


@router.get("/sessions/{session_id}/reports/{report_id}/export", response_model=ExportResponse)
def export_report(
    session_id: str,
    report_id: str,
    format: ExportFormat = Query(default="markdown"),
    auth=Depends(get_current_user),
    service: ResearchService = Depends(get_research_service),
) -> ExportResponse:
    return service.export_report(auth["user"], session_id, report_id, format)


@router.get("/exports/{filename}")
def serve_export(filename: str) -> FileResponse:
    target = get_settings().research_export_dir / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail="Export file not found.")
    media_type = "application/pdf" if target.suffix == ".pdf" else "text/plain"
    return FileResponse(Path(target), media_type=media_type, filename=filename)
