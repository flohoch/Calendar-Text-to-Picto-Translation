from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (Language, TranslationRequest,
                                 TranslationResponse)
from app.services import index_service, translation_service

router = APIRouter(prefix="/api")


@router.post("/translate", response_model=TranslationResponse)
def translate(request: TranslationRequest):
    return translation_service.translate(request)


@router.get("/pictograms/{pictogram_id}")
def get_pictogram(pictogram_id: int,
                  language: Language = Query(Language.DE)):
    p = index_service.get_pictogram_by_id(pictogram_id, language)
    if p is None:
        raise HTTPException(status_code=404, detail="Pictogram not found")
    return p.model_dump(by_alias=True)


@router.get("/status")
def status():
    return {
        "status": "ok",
        "pictogramCount": {
            "de": index_service.get_total(Language.DE),
            "en": index_service.get_total(Language.EN),
        },
    }
