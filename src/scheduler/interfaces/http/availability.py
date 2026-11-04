"""Availability route (design §3 API table, ADR-010, SPEC-001 Wire formats).

``GET /dealerships/{dealership_id}/availability?service_type_id&from&to``. ``from`` and ``to``
are query aliases (``from`` is a Python keyword); a missing or mistyped query parameter is a
``RequestValidationError`` and answers 422 ``validation`` through ``errors.py``. An unknown
dealership is 404 ``not_found``; the business rules of the use case are 422 ``validation``.

``AvailabilityOut`` (in ``schemas.py``) documents the 200 body in ``/docs``; the handler returns
the use case's dict, so nothing is re-serialised through it.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Request

from scheduler.interfaces.http.dependencies import UseCases
from scheduler.interfaces.http.schemas import AvailabilityOut, ErrorOut


def build_router(uc: UseCases) -> APIRouter:
    router = APIRouter(prefix="/dealerships/{dealership_id}/availability")

    @router.get(
        "",
        name="get_availability",
        responses={
            200: {"model": AvailabilityOut},
            **{status: {"model": ErrorOut} for status in (404, 422)},
        },
    )
    async def get_availability(
        dealership_id: int,
        request: Request,
        service_type_id: int,
        from_: Annotated[date, Query(alias="from")],
        to: Annotated[date, Query(alias="to")],
    ) -> dict[str, object]:
        request.state.ev["service_type_id"] = service_type_id  # after query validation
        body = await uc.get_availability.execute(dealership_id, service_type_id, from_, to)
        return dict(body)

    return router
