from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ResearchMode = Literal["environment", "company", "person", "market", "job", "product"]
DepthMode = Literal["quick", "standard", "deep"]
StepStatus = Literal["pending", "running", "completed", "failed", "partial"]
ExportFormat = Literal["json", "markdown", "pdf"]


class SignUpRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    display_name: str | None = None


class SignInRequest(BaseModel):
    email: str
    password: str


class UserProfile(BaseModel):
    user_id: int
    email: str
    display_name: str
    created_at: datetime


class AuthResponse(BaseModel):
    token: str
    user: UserProfile


class SourceItem(BaseModel):
    source_id: str
    title: str
    source_type: str
    snippet: str
    credibility: float
    url: str | None = None
    cluster: str | None = None
    agreement: Literal["supports", "mixed", "weak"] = "supports"
    metadata: dict | None = None


class AgentStep(BaseModel):
    step_id: str
    name: str
    status: StepStatus
    summary: str
    started_at: datetime
    finished_at: datetime | None = None
    payload: dict | None = None


class ConfidenceBreakdown(BaseModel):
    overall: float
    data_quality: float
    coverage: float
    reasoning_strength: float


class ClaimScore(BaseModel):
    claim: str
    confidence: float
    supporting_sources: list[str]
    contradiction_sources: list[str] = []


class ReportSection(BaseModel):
    key: str
    title: str
    content: str
    sources: list[str] = []


class ResearchReport(BaseModel):
    report_id: str
    session_id: str
    query: str
    title: str
    mode: ResearchMode
    depth: DepthMode
    overview: str
    sections: list[ReportSection]
    follow_ups: list[str]
    sources: list[SourceItem]
    claims: list[ClaimScore]
    contradictions: list[str]
    confidence: ConfidenceBreakdown
    summary_markdown: str
    created_at: datetime


class SessionSummary(BaseModel):
    session_id: str
    title: str
    mode: ResearchMode
    depth: DepthMode
    created_at: datetime
    updated_at: datetime
    pinned: bool = False
    bookmarked: bool = False
    compare_selected: bool = False
    tags: list[str] = []
    latest_query: str | None = None


class ResearchMessage(BaseModel):
    message_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class SessionDetail(BaseModel):
    session: SessionSummary
    messages: list[ResearchMessage]
    reports: list[ResearchReport]
    steps: list[AgentStep]


class SessionCreateRequest(BaseModel):
    title: str | None = None
    mode: ResearchMode = "environment"
    depth: DepthMode = "standard"
    tags: list[str] = []


class SessionUpdateRequest(BaseModel):
    title: str | None = None
    pinned: bool | None = None
    bookmarked: bool | None = None
    compare_selected: bool | None = None
    tags: list[str] | None = None


class ResearchQueryRequest(BaseModel):
    session_id: str | None = None
    query: str
    mode: ResearchMode = "environment"
    depth: DepthMode = "standard"
    site_id: int | None = None
    network_scope: Literal["india", "global"] = "india"
    dashboard_context: dict[str, Any] | None = None


class ResearchQueryResponse(BaseModel):
    session: SessionSummary
    messages: list[ResearchMessage]
    report: ResearchReport
    steps: list[AgentStep]
    degraded: bool = False


class FeedbackRequest(BaseModel):
    report_id: str
    target_type: Literal["summary", "section", "source"]
    target_key: str
    value: Literal["positive", "negative"]
    notes: str | None = None


class ExportResponse(BaseModel):
    filename: str
    format: ExportFormat
    download_url: str


class KnowledgeNode(BaseModel):
    node_id: str
    label: str
    group: Literal["session", "mode", "tag", "source"]


class KnowledgeEdge(BaseModel):
    source: str
    target: str
    weight: float = 1.0


class KnowledgeGraphResponse(BaseModel):
    nodes: list[KnowledgeNode]
    edges: list[KnowledgeEdge]
