"""High-level orchestrator: dispatches a TranslationRequest to the
category-specific pipelines."""
import logging

from app.models.schemas import TranslationRequest, TranslationResponse
from app.services import attendee_service, location_service, summary_service

logger = logging.getLogger(__name__)


def translate(request: TranslationRequest) -> TranslationResponse:
    logger.info(
        "=== New request: language=%s | summary='%s' | location='%s' | attendees='%s'",
        request.language.value, request.summary, request.location, request.attendees,
    )

    summary_result = summary_service.translate(request.summary, request.language)
    # Pass summary text into the location pipeline so it can disambiguate
    # ambiguous location words (e.g. English/German "bank").
    location_result = location_service.translate(
        request.location, request.language, summary_context=request.summary,
    )
    attendee_results = attendee_service.translate(request.attendees, request.language)

    logger.info("=== Request complete: %d summary, %d location, %d attendee results",
                len(summary_result.matches), len(location_result.matches),
                len(attendee_results))

    return TranslationResponse(
        language=request.language,
        summary=summary_result,
        location=location_result,
        attendees=attendee_results,
    )
