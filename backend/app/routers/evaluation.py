from fastapi import APIRouter, HTTPException

from app.models.schemas import Language
from app.services import evaluation_service

router = APIRouter(prefix="/api/evaluation")


@router.post("/run/{language}")
def run_evaluation(language: Language):
    """Trigger a new evaluation run for the given language."""
    try:
        run = evaluation_service.run_evaluation(language)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "run_id": run.run_id,
        "language": run.language.value,
        "timestamp": run.timestamp,
        "metrics": run.metrics.model_dump(by_alias=True),
        "filename": f"eval_{run.run_id}.json",
    }


@router.get("/runs")
def list_runs():
    """Return metadata for all stored runs."""
    return {"runs": evaluation_service.list_runs()}


@router.get("/runs/{filename}")
def get_run(filename: str):
    """Load a stored run for display."""
    data = evaluation_service.get_run(filename)
    if data is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return data
