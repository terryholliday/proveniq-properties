"""Property and Unit schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.base import BaseSchema, IDMixin, TimestampMixin
from app.models.enums import PropertyType, UnitStatus, OccupancyModel


class PropertyCreate(BaseSchema):
    """Create a new property."""

    name: str = Field(..., min_length=2, max_length=255)
    property_type: PropertyType
    occupancy_model: OccupancyModel = OccupancyModel.LONG_TERM_RESIDENTIAL
    
    address_line1: str = Field(..., min_length=5, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=50)
    zip_code: str = Field(..., min_length=5, max_length=20)
    country: str = "USA"
    
    total_leasable_sq_ft: Optional[int] = Field(None, gt=0)
    year_built: Optional[int] = Field(None, ge=1800, le=2100)
    description: Optional[str] = None

    @model_validator(mode="after")
    def validate_commercial_fields(self):
        """Commercial/mixed properties REQUIRE total_leasable_sq_ft."""
        if self.property_type in (PropertyType.COMMERCIAL, PropertyType.MIXED):
            if not self.total_leasable_sq_ft:
                raise ValueError("total_leasable_sq_ft is required for commercial/mixed properties")
        return self


class PropertyUpdate(BaseSchema):
    """Update property."""

    name: Optional[str] = Field(None, min_length=2, max_length=255)
    occupancy_model: Optional[OccupancyModel] = None
    address_line1: Optional[str] = Field(None, min_length=5, max_length=255)
    address_line2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, min_length=2, max_length=100)
    state: Optional[str] = Field(None, min_length=2, max_length=50)
    zip_code: Optional[str] = Field(None, min_length=5, max_length=20)
    total_leasable_sq_ft: Optional[int] = Field(None, gt=0)
    year_built: Optional[int] = Field(None, ge=1800, le=2100)
    description: Optional[str] = None


class PropertyResponse(BaseSchema, IDMixin, TimestampMixin):
    """Property response."""

    org_id: UUID
    name: str
    property_type: PropertyType
    occupancy_model: OccupancyModel
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    zip_code: str
    country: str
    total_leasable_sq_ft: Optional[int] = None
    year_built: Optional[int] = None
    description: Optional[str] = None
    unit_count: int = 0


class UnitCreate(BaseSchema):
    """Create a new unit."""

    unit_number: str = Field(..., min_length=1, max_length=50)
    status: UnitStatus = UnitStatus.VACANT
    bedrooms: Optional[int] = Field(None, ge=0)
    bathrooms: Optional[int] = Field(None, ge=0)  # stored as int (15 = 1.5)
    sq_ft: Optional[int] = Field(None, gt=0)
    description: Optional[str] = None


class UnitUpdate(BaseSchema):
    """Update unit."""

    unit_number: Optional[str] = Field(None, min_length=1, max_length=50)
    status: Optional[UnitStatus] = None
    bedrooms: Optional[int] = Field(None, ge=0)
    bathrooms: Optional[int] = Field(None, ge=0)
    sq_ft: Optional[int] = Field(None, gt=0)
    description: Optional[str] = None


class UnitResponse(BaseSchema, IDMixin, TimestampMixin):
    """Unit response."""

    property_id: UUID
    unit_number: str
    status: UnitStatus
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    sq_ft: Optional[int] = None
    description: Optional[str] = None
