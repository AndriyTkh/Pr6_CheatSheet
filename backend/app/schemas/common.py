"""Shapes shared by every route.

These are the wire contract Role 5 generates TypeScript from
(`openapi-typescript`, tech-stack-decision.md "Shared FE/BE types"), so the
names here end up as TS type names — keep them stable and boring.
"""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """A slice of a listing plus enough to ask for the next one.

    `total` is the unpaginated count, so the grid can size its scrollbar
    without walking every page.
    """

    items: list[T]
    total: int
    limit: int
    offset: int


class PageParams(BaseModel):
    """Query parameters every listing route accepts."""

    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
