from __future__ import annotations

from fastapi import APIRouter

from ..adapters.llm import llm_status

router = APIRouter()


@router.get("/health")
def health() -> dict:
    status = llm_status()
    return {
        "ok": True,
        "service": "wakili",
        "version": "0.2.0",
        "llm": status,
    }
