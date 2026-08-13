from datetime import date, datetime, time


# ══════════════════════════════════════════════════════════════════
#  LEVEL
# ══════════════════════════════════════════════════════════════════

def level_from_points(points: int) -> int:
    return max(1, (points // 100) + 1)


# ══════════════════════════════════════════════════════════════════
#  STREAK
# ══════════════════════════════════════════════════════════════════

def compute_daily_streak(old_streak: int, last_streak_date, now: datetime):
    """
    Returns (new_streak, new_last_streak_datetime).
    Stores last_streak_date as datetime(YYYY-MM-DD 00:00:00) for MongoDB.
    """
    today_date = now.date()
    today_dt = datetime.combine(today_date, time.min)

    if last_streak_date is None:
        return 1, today_dt

    if isinstance(last_streak_date, datetime):
        last_date = last_streak_date.date()
    elif isinstance(last_streak_date, date):
        last_date = last_streak_date
    else:
        last_date = date.fromisoformat(str(last_streak_date)[:10])

    if last_date == today_date:
        return old_streak, today_dt   # already counted today

    diff = (today_date - last_date).days
    if diff == 1:
        return old_streak + 1, today_dt   # continued
    return 1, today_dt                    # broken — reset


# ══════════════════════════════════════════════════════════════════
#  STREAK REWARDS
#  Returns a reward dict if this streak hits a milestone, else None
# ══════════════════════════════════════════════════════════════════

STREAK_REWARDS = {
    3:  {"bonus_points": 10,  "message": "3-day streak! +10 bonus XP 🔥"},
    7:  {"bonus_points": 25,  "message": "7-day streak! +25 bonus XP 🔥🔥"},
    14: {"bonus_points": 50,  "message": "2-week streak! +50 bonus XP ⚡"},
    30: {"bonus_points": 100, "message": "30-day streak! +100 bonus XP 🏆"},
    60: {"bonus_points": 200, "message": "60-day streak! +200 bonus XP 👑"},
}

def get_streak_reward(new_streak: int) -> dict | None:
    """Returns reward dict if new_streak is a milestone, else None."""
    return STREAK_REWARDS.get(new_streak, None)


# ══════════════════════════════════════════════════════════════════
#  BADGES
# ══════════════════════════════════════════════════════════════════

def compute_badges(points: int, streak: int, current_badges: list) -> list:
    badges = set(current_badges or [])

    # Points-based badges
    if points >= 100:
        badges.add("Bronze Learner")
    if points >= 300:
        badges.add("Silver Scholar")
    if points >= 500:
        badges.add("Gold Achiever")
    if points >= 1000:
        badges.add("Platinum Expert")

    # Streak-based badges
    if streak >= 7:
        badges.add("Consistency Star")
    if streak >= 30:
        badges.add("Discipline Master")

    return sorted(list(badges))


# ══════════════════════════════════════════════════════════════════
#  BADGE METADATA  (for UI display — icon + colour)
# ══════════════════════════════════════════════════════════════════

BADGE_META = {
    "Bronze Learner":    {"emoji": "🥉", "color": "#CD7F32", "desc": "Earned 100 XP"},
    "Silver Scholar":    {"emoji": "🥈", "color": "#9CA3AF", "desc": "Earned 300 XP"},
    "Gold Achiever":     {"emoji": "🥇", "color": "#F59E0B", "desc": "Earned 500 XP"},
    "Platinum Expert":   {"emoji": "💎", "color": "#6366F1", "desc": "Earned 1000 XP"},
    "Consistency Star":  {"emoji": "⭐", "color": "#F59E0B", "desc": "7-day streak"},
    "Discipline Master": {"emoji": "🏆", "color": "#EF4444", "desc": "30-day streak"},
}