from typing import Optional
from pydantic import BaseModel


class AnalyzeUrlRequest(BaseModel):
    url: str
    user_id: Optional[str] = None
    cookies_file: Optional[str] = None
    proxy: Optional[str] = None


class JobResponse(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    trip_id: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None
