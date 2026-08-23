# backend/app/schemas/dashboard.py
from pydantic import BaseModel
from typing import List
from datetime import datetime

class DashboardStats(BaseModel):
    total_assets: int
    last_scan: str
    reports_generated: int
    system_status: str

class ActivityItem(BaseModel):
    id: int
    type: str
    description: str
    timestamp: datetime

class DashboardData(BaseModel):
    stats: DashboardStats
    recent_activity: List[ActivityItem]