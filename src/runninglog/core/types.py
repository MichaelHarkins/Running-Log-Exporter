import datetime as dt
from typing import Optional

from pydantic import BaseModel, Field, validator


class WorkoutSegment(BaseModel):
    date: dt.datetime = Field(..., description="Workout date and time")
    exercise: str = Field(..., description="Type of exercise (e.g., Running, Biking)")
    comment: str = Field("", description="Workout comments")
    miles: float = Field(..., description="Distance in miles")
    secs: int = Field(..., description="Duration in seconds")
    index: int = Field(1, description="Segment index for multi-segment workouts")
    weather: Optional[str] = Field(
        None, description="Weather conditions (if available)"
    )
    interval_type: Optional[str] = Field(
        None, description="Interval type (if available)"
    )

    @validator("miles")
    def miles_non_negative(cls, v):
        if v < 0:
            raise ValueError("Miles must be non-negative")
        return v

    @validator("secs")
    def secs_non_negative(cls, v):
        if v < 0:
            raise ValueError("Seconds must be non-negative")
        return v
