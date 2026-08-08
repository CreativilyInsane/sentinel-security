# backend/app/services/dashboard_service.py
from datetime import datetime, timedelta, timezone
from app.schemas.dashboard import DashboardData, DashboardStats, ActivityItem

class DashboardService:
    async def get_dashboard_data(self) -> DashboardData:
        """Returns mock dashboard data. To be replaced with real metrics later."""
        now = datetime.now(timezone.utc)
        
        stats = DashboardStats(
            total_assets=142,
            last_scan="2 hours ago",
            reports_generated=38,
            system_status="Operational"
        )
        
        recent_activity = [
            ActivityItem(id=1, type="Scan", description="Network scan completed on 192.168.1.0/24", timestamp=now - timedelta(hours=2)),
            ActivityItem(id=2, type="Report", description="Vulnerability report generated for Web Server 01", timestamp=now - timedelta(hours=5)),
            ActivityItem(id=3, type="Alert", description="New asset discovered: 192.168.1.55", timestamp=now - timedelta(days=1)),
            ActivityItem(id=4, type="User", description="Admin user logged in", timestamp=now - timedelta(days=2)),
        ]
        
        return DashboardData(stats=stats, recent_activity=recent_activity)