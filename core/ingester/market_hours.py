"""
Forex Market Session & Weekend Closure Engine.
==============================================
Institutional-grade market schedule awareness for 28 Real Forex pairs.

Forex Market Hours (UTC):
- Opens: Sunday 21:00 UTC (5:00 PM US/Eastern / Monday morning Sydney)
- Closes: Friday 21:00 UTC (5:00 PM US/Eastern / New York close)
- Weekend Standby: Friday 21:00 UTC through Sunday 21:00 UTC
"""
import datetime
from typing import Dict, Any, Optional

def get_forex_market_status(dt: Optional[datetime.datetime] = None) -> Dict[str, Any]:
    """
    Returns accurate real-time market operational state for Interbank Forex.
    """
    if dt is None:
        dt = datetime.datetime.now(datetime.timezone.utc)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)

    # Weekday: Monday is 0, Sunday is 6
    weekday = dt.weekday()
    hour = dt.hour
    minute = dt.minute

    # Friday after 21:00 UTC -> Market Closed
    if weekday == 4 and hour >= 21:
        is_open = False
    # Saturday all day -> Market Closed
    elif weekday == 5:
        is_open = False
    # Sunday before 21:00 UTC -> Market Closed
    elif weekday == 6 and hour < 21:
        is_open = False
    else:
        is_open = True

    if not is_open:
        # Calculate countdown until Sunday 21:00 UTC reopen
        days_until_sunday = (6 - weekday) % 7
        target_sunday = dt.date() + datetime.timedelta(days=days_until_sunday)
        reopen_dt = datetime.datetime(
            target_sunday.year, target_sunday.month, target_sunday.day,
            21, 0, 0, tzinfo=datetime.timezone.utc
        )
        time_left = reopen_dt - dt
        total_seconds = max(0, int(time_left.total_seconds()))
        hours_left = total_seconds // 3600
        mins_left = (total_seconds % 3600) // 60
        reopen_str = f"{hours_left}h {mins_left}m"
        status_label = "WEEKEND_STANDBY"
        status_badge = "🟡 WEEKEND STANDBY"
        status_desc = f"Market Closed (Reopens Sun 21:00 UTC / in {reopen_str})"
    else:
        reopen_str = None
        status_label = "LIVE_OPEN"
        status_badge = "🟢 LIVE MARKET"
        # Determine active global trading session
        # Tokyo: 00:00 - 09:00 UTC
        # London: 08:00 - 16:30 UTC
        # New York: 13:00 - 21:00 UTC
        # Sydney: 21:00 - 06:00 UTC
        sessions = []
        if 8 <= hour < 16 or (hour == 16 and minute <= 30):
            sessions.append("London")
        if 13 <= hour < 21:
            sessions.append("New York")
        if 0 <= hour < 9:
            sessions.append("Tokyo")
        if hour >= 21 or hour < 6:
            sessions.append("Sydney")
        active_session = " / ".join(sessions) if sessions else "Global Markets"
        status_desc = f"Live Real-Time Feed ({active_session} Session)"

    return {
        "is_open": is_open,
        "status": status_label,
        "status_badge": status_badge,
        "status_desc": status_desc,
        "utc_time": dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "time_until_reopen": reopen_str
    }
