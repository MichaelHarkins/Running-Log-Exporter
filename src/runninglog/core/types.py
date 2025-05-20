import datetime as dt
from typing import Optional, List

from pydantic import BaseModel, Field, validator


class WorkoutSegment(BaseModel):
    distance_miles: float = Field(..., description="Distance in miles for this segment")
    duration_seconds: Optional[int] = Field(None, description="Duration in seconds for this segment")
    interval_type: Optional[str] = Field(None, description="Interval type (e.g., Warmup, Interval, Cooldown)")
    shoes: Optional[str] = Field(None, description="Shoes used for this segment")
    pace: Optional[str] = Field(None, description="Pace for this segment (if available)")

    @validator("distance_miles")
    def miles_non_negative(cls, v):
        if v < 0:
            raise ValueError("Miles must be non-negative")
        return v

    @validator("duration_seconds")
    def secs_non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError("Seconds must be non-negative")
        return v


class Workout(BaseModel):
    title: Optional[str] = Field(None, description="Workout title")
    date: dt.datetime = Field(..., description="Workout date and time")
    exercise_type: str = Field(..., description="Type of exercise (e.g., Run, Bike)")
    weather: Optional[str] = Field(None, description="Weather conditions")
    comments: Optional[str] = Field(None, description="Workout comments")
    total_distance_miles: float = Field(..., description="Total distance in miles")
    total_duration_seconds: Optional[int] = Field(None, description="Total duration in seconds")
    segments: List[WorkoutSegment] = Field(..., description="List of workout segments")
    exported_from: Optional[str] = Field("running-log", description="Provenance tag")
