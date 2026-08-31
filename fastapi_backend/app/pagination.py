"""Project-wide pagination params (max page size 500)."""

from __future__ import annotations

from fastapi import Query
from fastapi_pagination import Page as _Page
from fastapi_pagination import Params as _Params

MAX_PAGE_SIZE = 500


class Params(_Params):
    size: int = Query(50, ge=1, le=MAX_PAGE_SIZE, description="Page size")


class Page(_Page):
    __params_type__ = Params


Page.set_params(Params)
