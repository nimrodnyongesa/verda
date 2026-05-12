from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CaseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    jurisdiction: str = "ke"
    legal_track: str = "article_22_petition"
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    folder_id: int | None = None


class CaseRow(BaseModel):
    id: int
    title: str
    jurisdiction: str
    legal_track: str
    description: str
    status: str
    filing_deadline_date: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class CaseFileRow(BaseModel):
    id: int
    case_id: int
    original_name: str
    stored_name: str
    mime_type: str
    evidence_kind: str
    size_bytes: int
    sha256: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class CaseDetail(CaseRow):
    files: list[CaseFileRow] = Field(default_factory=list)
    plan: dict[str, Any] | None = None
    latest_run: dict[str, Any] | None = None


class PlanModule(BaseModel):
    key: Literal[
        "evidence_codex",
        "procedural_engine",
        "precedent_linker",
        "defender_safety_build",
    ]
    name: str
    rationale: str
    estimated_minutes: int


class ToolkitPlan(BaseModel):
    case_id: int
    legal_track_label: str
    summary: str
    modules: list[PlanModule]
    deadlines: list[dict[str, Any]]
    risks: list[str]
    approved: bool = False


class GenerationEvent(BaseModel):
    sequence: int
    actor: str
    kind: str
    title: str
    detail: str = ""
    file_path: str | None = None
    delay_ms: int = 0
    created_at: str


class ExportRequest(BaseModel):
    target: Literal["zip", "encrypted", "docker", "usb"] = "zip"
    passphrase: str | None = None
