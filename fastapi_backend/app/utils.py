from datetime import datetime, timezone

from fastapi.routing import APIRoute


def datetime_as_utc_aware(d: datetime) -> datetime:
    """
    asyncpg + TIMESTAMPTZ: naive datetime는 UTC wall time으로 간주해 timezone-aware로 만든다.
    (offset-naive / offset-aware 혼용으로 인한 인코딩 오류 방지)
    """
    if d.tzinfo is None:
        return d.replace(tzinfo=timezone.utc)
    return d


def simple_generate_unique_route_id(route: APIRoute):
    return f"{route.tags[0]}-{route.name}"
