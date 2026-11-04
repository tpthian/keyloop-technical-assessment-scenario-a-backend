"""Availability route (design §3 API table, ADR-010, SPEC-001 Wire formats).

``GET /dealerships/{dealership_id}/availability?service_type_id&from&to``. ``from`` and ``to``
are query aliases (``from`` is a Python keyword); a missing or mistyped query parameter is a
``RequestValidationError`` and answers 422 ``validation`` through ``errors.py``. An unknown
dealership is 404 ``not_found``; the business rules of the use case are 422 ``validation``.

``AvailabilityOut`` and ``WindowOut`` document the 200 body in ``/docs``; the handler returns
the use case's dict, so nothing is re-serialised through them.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from scheduler.interfaces.http.dependencies import UseCases
from scheduler.interfaces.http.schemas import ErrorOut


class WindowOut(BaseModel):
    """One pair's inclusive start window on one local day; instants in UTC with ``Z``."""

    bay_id: int
    technician_id: int
    date: date
    earliest_start: datetime
    latest_start: datetime


class AvailabilityOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    dealership_id: int
    service_type_id: int
    from_: date = Field(alias="from")
    to: date
    as_of: datetime  # data watermark (ADR-010), not the response time
    windows: list[WindowOut]


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
    ) -> dict[str, Any]:
        request.state.ev["service_type_id"] = service_type_id  # after query validation
        body = await uc.get_availability.execute(dealership_id, service_type_id, from_, to)
        return dict(body)

    return router
