from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone, timedelta

from app.db import (
    users_col,
    events_col,
    quizzes_col,
    quiz_attempts_col,
    tracks_col,
    topics_col
)

from app.models import (
    CreateUserIn,
    UserOut,
    AwardIn,
    QuizSubmitIn
)

from app.services import (
    level_from_points,
    compute_daily_streak,
    compute_badges,
    get_streak_reward,   # ADD THIS
    BADGE_META,          # ADD THIS
)

router = APIRouter(prefix="/gamification", tags=["gamification"])

# ==========================================================
# QUIZ ROUTES
# ==========================================================

@router.get("/quizzes")
async def list_quizzes():
    cursor = quizzes_col.find({}, {"_id": 0, "questions": 0})
    items = await cursor.to_list(length=100)
    return {"items": items}


@router.get("/quizzes/{quiz_id}")
async def get_quiz(quiz_id: str, user_id: str):

    quiz = await quizzes_col.find_one({"quiz_id": quiz_id}, {"_id": 0})
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    topic_id = quiz.get("topic_id")
    set_no = quiz.get("set_no")

    # -----------------------------------------
    # QUIZ UNLOCK CHECK
    # -----------------------------------------

    if set_no and set_no > 1:
        previous_set = set_no - 1

        previous_quiz = await quizzes_col.find_one({
            "topic_id": topic_id,
            "set_no": previous_set
        })

        if previous_quiz:
            prev_attempt = await quiz_attempts_col.find_one({
                "user_id": user_id,
                "quiz_id": previous_quiz["quiz_id"],
                "points_awarded": {"$gt": 0}
            })

            if not prev_attempt:
                raise HTTPException(
                    status_code=403,
                    detail=f"Complete set {previous_set} of this topic before opening this quiz."
                )

    # Hide answers before sending quiz
    for q in quiz["questions"]:
        q.pop("correct_answer", None)
        q.pop("explanation", None)

    return quiz



@router.post("/quizzes/submit")
async def submit_quiz(payload: QuizSubmitIn):
 
    user_id = payload.user_id
    quiz_id = payload.quiz_id
 
    quiz = await quizzes_col.find_one({"quiz_id": quiz_id})
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
 
    topic_id = quiz.get("topic_id")
    set_no = quiz.get("set_no")
 
    # Unlock check
    if set_no and set_no > 1:
        previous_quiz = await quizzes_col.find_one({
            "topic_id": topic_id,
            "set_no": set_no - 1
        })
        if previous_quiz:
            prev_attempt = await quiz_attempts_col.find_one({
                "user_id": user_id,
                "quiz_id": previous_quiz["quiz_id"],
                "points_awarded": {"$gt": 0}
            })
            if not prev_attempt:
                raise HTTPException(
                    status_code=403,
                    detail=f"Complete set {set_no - 1} of this topic before attempting this quiz."
                )
 
    # Evaluate answers
    question_map = {q["question_id"]: q for q in quiz["questions"]}
    submitted_ids = [a.question_id for a in payload.answers]
    quiz_ids = list(question_map.keys())
 
    if set(submitted_ids) != set(quiz_ids):
        raise HTTPException(status_code=400, detail="All questions must be answered exactly once.")
    if len(submitted_ids) != len(set(submitted_ids)):
        raise HTTPException(status_code=400, detail="Duplicate question answers detected.")
 
    score = 0
    results = []
 
    for ans in payload.answers:
        qid = ans.question_id
        selected = ans.selected_option
        question = question_map[qid]
 
        if question["type"] == "fill_blank":
            acceptable = [str(x).strip().lower() for x in (question.get("acceptable_answers") or [])]
            is_correct = str(selected).strip().lower() in acceptable
            correct_answer = acceptable[0] if acceptable else None
        else:
            correct_answer = question.get("correct_option_id")
            is_correct = selected == correct_answer
 
        if is_correct:
            score += question.get("w", 1)
 
        results.append({
            "question_id": qid,
            "selected_option": selected,
            "is_correct": is_correct,
            "correct_answer": None if is_correct else correct_answer,
            "explanation": question["reason_correct"] if is_correct else question["reason_wrong"]
        })
 
    total_questions = len(quiz["questions"])
    points_awarded = score * quiz.get("base_points", 10)
 
    previous_award = await quiz_attempts_col.find_one({
        "user_id": user_id,
        "quiz_id": quiz_id,
        "points_awarded": {"$gt": 0}
    })
 
    awarded_this_attempt = False
    streak_reward = None
    now = datetime.now(timezone.utc)
 
    if not previous_award and points_awarded > 0:
        user = await users_col.find_one({"user_id": user_id})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
 
        old_points = int(user.get("points", 0))
        old_streak = int(user.get("streak", 0))
        last_streak_date = user.get("last_streak_date")
        current_badges = user.get("badges", [])
 
        # Compute streak
        new_streak, new_last_streak_date = compute_daily_streak(
            old_streak, last_streak_date, now
        )
 
        # Check for streak milestone reward
        streak_reward = get_streak_reward(new_streak)
        bonus_points = streak_reward["bonus_points"] if streak_reward else 0
 
        new_points = old_points + points_awarded + bonus_points
        new_level = level_from_points(new_points)
        new_badges = compute_badges(new_points, new_streak, current_badges)
 
        await users_col.update_one(
            {"user_id": user_id},
            {"$set": {
                "points": new_points,
                "level": new_level,
                "streak": new_streak,
                "last_streak_date": new_last_streak_date,
                "badges": new_badges,
                "updated_at": now,
            }}
        )
 
        # Log quiz completion event
        await events_col.insert_one({
            "user_id": user_id,
            "type": "quiz_completion",
            "points_delta": points_awarded,
            "reason": f"Completed {quiz_id}",
            "meta": {"quiz_id": quiz_id},
            "created_at": now,
        })
 
        # Log streak bonus event separately (if milestone hit)
        if streak_reward:
            await events_col.insert_one({
                "user_id": user_id,
                "type": "streak_bonus",
                "points_delta": bonus_points,
                "reason": streak_reward["message"],
                "meta": {"streak": new_streak},
                "created_at": now,
            })
 
        awarded_this_attempt = True
 
    else:
        points_awarded = 0
 
    await quiz_attempts_col.insert_one({
        "user_id": user_id,
        "quiz_id": quiz_id,
        "score": score,
        "total_questions": total_questions,
        "points_awarded": points_awarded,
        "created_at": now
    })
 
    return {
        "score": score,
        "total_questions": total_questions,
        "points_awarded": points_awarded,
        "awarded_this_attempt": awarded_this_attempt,
        "streak_reward": streak_reward,   # Flutter reads this to show milestone popup
        "results": results
    }
 
 


# ==========================================================
# USER & GAMIFICATION ROUTES
# ==========================================================
@router.post("/users", response_model=UserOut)
async def create_user(payload: CreateUserIn):
    existing = await users_col.find_one({"user_id": payload.user_id})
    if existing:
        raise HTTPException(status_code=409, detail="user_id already exists")
 
    now = datetime.now(timezone.utc)
 
    doc = {
        "user_id": payload.user_id,
        "name": payload.name,
        "points": 0,
        "level": 1,
        "streak": 0,
        "last_streak_date": None,
        "badges": [],
        "created_at": now,
        "updated_at": now,
    }
 
    await users_col.insert_one(doc)
    return UserOut(**{k: doc[k] for k in ["user_id", "name", "points", "level", "streak", "badges"]})

# ── 4. ADD this new route — GET /users/{user_id} ──────────────────────────────
# Used by LearnPage to load real streak, XP, level, badges for the current user
 
@router.get("/users/{user_id}")
async def get_user(user_id: str):
    user = await users_col.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
 
    # Attach badge metadata for the UI
    badges_with_meta = []
    for badge_name in user.get("badges", []):
        meta = BADGE_META.get(badge_name, {})
        badges_with_meta.append({
            "name": badge_name,
            "emoji": meta.get("emoji", "🏅"),
            "color": meta.get("color", "#6366F1"),
            "desc": meta.get("desc", ""),
        })
 
    return {
        "user_id": user["user_id"],
        "name": user.get("name", ""),
        "points": user.get("points", 0),
        "level": user.get("level", 1),
        "streak": user.get("streak", 0),
        "badges": badges_with_meta,
        "last_streak_date": str(user.get("last_streak_date", "")),
    }

@router.post("/award")
async def award_points(payload: AwardIn):
    user = await users_col.find_one({"user_id": payload.user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.now(timezone.utc)

    old_points = int(user.get("points", 0))
    old_streak = int(user.get("streak", 0))
    last_streak_date = user.get("last_streak_date")
    current_badges = user.get("badges", [])

    new_points = old_points + payload.points
    new_level = level_from_points(new_points)

    new_streak, new_last_streak_date = compute_daily_streak(
        old_streak, last_streak_date, now
    )

    new_badges = compute_badges(new_points, new_streak, current_badges)

    await users_col.update_one(
        {"user_id": payload.user_id},
        {"$set": {
            "points": new_points,
            "level": new_level,
            "streak": new_streak,
            "last_streak_date": new_last_streak_date,
            "badges": new_badges,
            "updated_at": now,
        }}
    )

    await events_col.insert_one({
        "user_id": payload.user_id,
        "type": payload.event_type,
        "points_delta": payload.points,
        "reason": payload.reason,
        "meta": payload.meta,
        "created_at": now,
    })

    return {"message": "Points awarded"}


@router.get("/leaderboard")
async def leaderboard(limit: int = 10, page: int = 1):
    lim = max(1, min(limit, 50))
    skip = (max(page, 1) - 1) * lim

    cursor = (
        users_col.find({}, {"_id": 0})
        .sort("points", -1)
        .skip(skip)
        .limit(lim)
    )

    items = await cursor.to_list(length=lim)
    return {"page": page, "limit": lim, "items": items}


@router.get("/quizzes/user/{user_id}")
async def user_quiz_status(user_id: str):

    user = await users_col.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    quizzes_cursor = quizzes_col.find({}, {"_id": 0})
    quizzes = await quizzes_cursor.to_list(length=100)

    attempts_cursor = quiz_attempts_col.find({
        "user_id": user_id,
        "points_awarded": {"$gt": 0}
    })

    attempts = await attempts_cursor.to_list(length=500)

    completed_quiz_ids = {a["quiz_id"] for a in attempts}

    result = []

    for quiz in quizzes:

        topic_id = quiz.get("topic_id")
        set_no = quiz.get("set_no")
        quiz_id = quiz.get("quiz_id")

        status = "locked"

        if quiz_id in completed_quiz_ids:
            status = "completed"

        elif set_no == 1:
            status = "unlocked"

        else:
            prev_quiz = await quizzes_col.find_one({
                "topic_id": topic_id,
                "set_no": set_no - 1
            })

            if prev_quiz and prev_quiz["quiz_id"] in completed_quiz_ids:
                status = "unlocked"

        result.append({
            "quiz_id": quiz_id,
            "topic_id": topic_id,
            "set_no": set_no,
            "title": quiz.get("title"),
            "status": status
        })

    return {"items": result}
@router.get("/events/{user_id}")
async def user_events(user_id: str):
    cursor = (
        events_col.find({"user_id": user_id}, {"_id": 0})
        .sort("created_at", -1)
    )

    items = await cursor.to_list(length=100)
    return {"user_id": user_id, "items": items}


@router.get("/topics/{topic_id}")
async def get_topic(topic_id: str):

    topic = await topics_col.find_one({"topic_id": topic_id}, {"_id": 0})

    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    return topic

@router.get("/tracks")
async def list_tracks():

    cursor = tracks_col.find({}, {"_id": 0})
    items = await cursor.to_list(length=50)

    return {"items": items}

@router.get("/tracks/{track_id}")
async def get_track(track_id: str):
    track = await tracks_col.find_one({"track_id": track_id}, {"_id": 0})
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    return track