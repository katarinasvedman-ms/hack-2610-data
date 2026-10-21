from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Connector(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector_id: str
    rated_kw: float = Field(gt=0)
    state: Literal["available", "in_use", "unknown"]


class AttemptCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    successful_starts: int | None = Field(ge=0)
    failed_starts: int | None = Field(ge=0)
    failure_categories: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_categories(self):
        if any(value < 0 for value in self.failure_categories.values()):
            raise ValueError("failure category counts cannot be negative")
        if (
            self.failed_starts is not None
            and sum(self.failure_categories.values()) > self.failed_starts
        ):
            raise ValueError("failure categories cannot exceed failed starts")
        return self


class FaultEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fault_id: str
    occurred_at: datetime
    code: str
    category: Literal["station_side", "auth_roaming_payment"]
    scope: Literal["station", "connector"]
    connector_id: str | None = None
    description: str

    @model_validator(mode="after")
    def validate_scope(self):
        if self.scope == "connector" and self.connector_id is None:
            raise ValueError("connector faults require a connector_id")
        if self.scope == "station" and self.connector_id is not None:
            raise ValueError("station faults cannot specify a connector_id")
        return self


class DailyObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    eligible_minutes: int | None = Field(default=None, ge=0)
    available_minutes: int | None = Field(default=None, ge=0)
    attempts: AttemptCounts
    connector_attempts: dict[str, AttemptCounts]
    faults: list[FaultEvent] | None

    @model_validator(mode="after")
    def validate_availability(self):
        if (
            self.available_minutes is not None
            and self.eligible_minutes is not None
            and self.available_minutes > self.eligible_minutes
        ):
            raise ValueError("available minutes cannot exceed eligible minutes")
        return self


class MaintenanceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str
    station_id: str
    occurred_at: datetime
    status: Literal["completed", "scheduled", "open"]
    summary: str
    connector_id: str | None = None


class Station(BaseModel):
    model_config = ConfigDict(extra="forbid")

    station_id: str
    classification: Literal["MOCK"]
    site_name: str
    region: str
    connectors: list[Connector]
    importance: int = Field(ge=1, le=5)
    importance_explanation: str
    safety_escalation: bool
    daily: list[DailyObservation]
    maintenance: list[MaintenanceRecord]

    @model_validator(mode="after")
    def validate_relationships(self):
        ids = [connector.connector_id for connector in self.connectors]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("connectors must have unique identifiers")
        for day in self.daily:
            if set(day.connector_attempts) != set(ids):
                raise ValueError("daily connector attempts must match station connectors")
            for field in ("successful_starts", "failed_starts"):
                station_count = getattr(day.attempts, field)
                connector_counts = [
                    getattr(attempts, field) for attempts in day.connector_attempts.values()
                ]
                if station_count is not None and all(value is not None for value in connector_counts):
                    if sum(connector_counts) != station_count:
                        raise ValueError("connector attempt totals must match station totals")
            for fault in day.faults or []:
                if fault.connector_id is not None and fault.connector_id not in ids:
                    raise ValueError("fault references an unknown connector")
        for record in self.maintenance:
            if record.station_id != self.station_id:
                raise ValueError("maintenance record station_id does not match station")
            if record.connector_id is not None and record.connector_id not in ids:
                raise ValueError("maintenance record references an unknown connector")
        return self


class Snapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: Literal["MOCK"]
    snapshot_at: datetime
    window_days: int = Field(gt=0)
    stations: list[Station]

    @model_validator(mode="after")
    def validate_snapshot(self):
        ids = [station.station_id for station in self.stations]
        if len(ids) != len(set(ids)):
            raise ValueError("station identifiers must be unique")
        if any(len(station.daily) != self.window_days for station in self.stations):
            raise ValueError("each station must have exactly window_days observations")
        for station in self.stations:
            dates = [day.date for day in station.daily]
            if len(set(dates)) != len(dates):
                raise ValueError("station daily dates must be unique")
        return self
