# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Standardized Pagination Schemas for API Responses
Provides consistent pagination metadata across all endpoints
"""

from typing import TypeVar, Generic, List
from pydantic import BaseModel, Field


class PaginationMetadata(BaseModel):
    """
    Standardized pagination metadata

    Used across all paginated API responses for consistency
    """
    total: int = Field(..., description="Total items in database (before filtering)")
    filtered: int = Field(..., description="Total items matching filters")
    page: int = Field(..., ge=1, description="Current page number (1-indexed)")
    page_size: int = Field(..., ge=1, description="Items per page")
    total_pages: int = Field(..., ge=0, description="Total pages available")
    has_more: bool = Field(..., description="Whether there are more pages")


T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Generic pagination wrapper for API responses

    All paginated endpoints should use this wrapper for consistency.

    Example usage:
        ```python
        from backend.api.schemas.pagination import PaginatedResponse

        @router.get("/items/", response_model=PaginatedResponse[ItemResponse])
        def list_items(page: int = 1, page_size: int = 50):
            items, filtered_count, total_pages = paginate(query, page, page_size)

            return {
                "data": items,
                "pagination": {
                    "total": total_count,
                    "filtered": filtered_count,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages,
                    "has_more": page < total_pages
                }
            }
        ```
    """
    data: List[T] = Field(..., description="List of items for current page")
    pagination: PaginationMetadata = Field(..., description="Pagination metadata")

    class Config:
        from_attributes = True
