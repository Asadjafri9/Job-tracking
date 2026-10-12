from fastapi import FastAPI
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str


app = FastAPI(
    title="Job Tracking API",
    summary="API foundation for the career workspace.",
    version="0.1.0",
)


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    """Return process health without depending on future services."""
    return HealthResponse(status="ok", service="job-tracking-api")
