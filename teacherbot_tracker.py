from __future__ import annotations
import json
from pathlib import Path

TRACKER_PATH = Path("/Users/higabot1/jarvis1-1/teacherbot_tracker.json")

DEFAULT_TRACKER = {
    "students": [
        {
            "name": "default",
            "subjects": {
                "python": {
                    "level": "beginner",
                    "goals": ["functions", "loops", "basic debugging"],
                    "next_lesson": "writing simple functions",
                    "completed": ["variables", "conditionals"]
                }
            }
        }
    ]
}

def ensure_tracker():
    if not TRACKER_PATH.exists():
        TRACKER_PATH.write_text(json.dumps(DEFAULT_TRACKER, indent=2))
    return TRACKER_PATH

def load_tracker():
    ensure_tracker()
    return json.loads(TRACKER_PATH.read_text())

def save_tracker(data):
    TRACKER_PATH.write_text(json.dumps(data, indent=2))

def get_subject_record(student_name="default", subject=None):
    data = load_tracker()
    student = next((s for s in data.get("students", []) if s.get("name") == student_name), None)
    if not student:
        return None, None, data
    subjects = student.get("subjects", {})
    if subject and subject in subjects:
        return subject, subjects[subject], data
    if subjects:
        first = next(iter(subjects))
        return first, subjects[first], data
    return None, None, data

def progress_summary(student_name="default", subject=None):
    subject_name, record, _ = get_subject_record(student_name, subject)
    if not record:
        return "No study tracker found."
    completed = ", ".join(record.get("completed", [])) or "None"
    goals = ", ".join(record.get("goals", [])) or "None"
    return (
        f"Student: {student_name}\n"
        f"Subject: {subject_name}\n"
        f"Level: {record.get('level', 'unknown')}\n"
        f"Next lesson: {record.get('next_lesson', 'not set')}\n"
        f"Goals: {goals}\n"
        f"Completed: {completed}"
    )

def next_lesson_summary(student_name="default", subject=None):
    subject_name, record, _ = get_subject_record(student_name, subject)
    if not record:
        return "No study tracker found."
    return (
        f"Next lesson for {subject_name}: {record.get('next_lesson', 'not set')}\n"
        f"Level: {record.get('level', 'unknown')}\n"
        f"Goals: {', '.join(record.get('goals', [])) or 'None'}"
    )

def mark_completed(lesson_name, student_name="default", subject=None):
    subject_name, record, data = get_subject_record(student_name, subject)
    if not record:
        return "No study tracker found."
    completed = record.setdefault("completed", [])
    if lesson_name not in completed:
        completed.append(lesson_name)
    if record.get("next_lesson") == lesson_name:
        record["next_lesson"] = "choose next lesson"
    save_tracker(data)
    return f"Marked completed: {lesson_name} ({subject_name})"

def teacher_context(student_name="default", subject=None):
    subject_name, record, _ = get_subject_record(student_name, subject)
    if not record:
        return "No tracker data available."
    return (
        f"TRACKED STUDENT: {student_name}\n"
        f"TRACKED SUBJECT: {subject_name}\n"
        f"LEVEL: {record.get('level', 'unknown')}\n"
        f"GOALS: {', '.join(record.get('goals', [])) or 'None'}\n"
        f"NEXT LESSON: {record.get('next_lesson', 'not set')}\n"
        f"COMPLETED: {', '.join(record.get('completed', [])) or 'None'}"
    )
