# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🖥️ Sample Output

Paste a sample of your app's CLI or Streamlit output here so a reader can see what a generated plan looks like:

==================================================
Today's Schedule for Jordan
==================================================
Plan for Sunday, Oct 25:
07:30-07:40  Breakfast for Biscuit (10 min) [high]
08:00-08:30  Walk for Biscuit (30 min) [high]
09:00-09:05  Thyroid medication for Mochi (5 min) [high]
18:00-18:20  Feather toy play for Mochi (20 min) [medium]

Why this plan:
Tasks were chosen by priority (high first), then preferred time, then shortest duration, until the 90 available minutes were used.
Scheduled 4 task(s) using 65 minutes.
- Breakfast (Biscuit): high priority, preferred around 07:30, fits in the time budget (10 min)
- Walk (Biscuit): high priority, preferred around 08:00, fits in the time budget (30 min)
- Thyroid medication (Mochi): high priority, preferred around 09:00, fits in the time budget (5 min)
- Feather toy play (Mochi): medium priority, preferred around 18:00, fits in the time budget (20 min)
Skipped because there wasn't enough time left:
- Brush coat (Biscuit, 45 min, low priority)

## 🧪 Testing PawPal+

```bash
# Run the full test suite:
pytest

# Run with coverage:
pytest --cov
```

Sample test output:

```
# Paste your pytest output here
```

## 📐 Smarter Scheduling

All scheduling logic lives in `pawpal_system.py`.

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Task sorting | `Scheduler.sort_by_time()` | Clock order by preferred time; untimed tasks last; higher priority wins ties |
| Filtering | `Scheduler.filter_tasks()`, `Scheduler.get_todays_tasks()` | By pet name and/or status (`pending` / `done`); filters combine |
| Conflict handling | `Scheduler.detect_conflicts()` | Flags overlapping preferred times, for the same pet or different pets; returns warnings, never crashes |
| Recurring tasks | `Task.mark_complete()`, `Task.next_occurrence()`, `Scheduler.complete_task()` | Completing a daily/weekly task creates the next instance (+1 / +7 days) |
| Budget & layout | `Scheduler.generate_plan()`, `_select_within_budget()`, `_layout()` | Highest priority first until time runs out; flexible tasks fill gaps |

### Sorting: `Scheduler.sort_by_time()`

Returns `(pet, task)` pairs in clock order using Python's `sorted()` with a key function. The key is a tuple:
`(preferred_time or time.max, -priority)`. Tasks with no preferred time get `time.max`, so they sort to the end.
When two tasks share a time, the higher-priority one comes first. `preferred_time` is a `datetime.time`, so it
compares in clock order without any string parsing.

### Filtering: `Scheduler.filter_tasks(pet_name=None, status=None, day=None)`

- `pet_name` matches without regard to upper/lower case (`"mochi"` finds Mochi).
- `status` is `Status.PENDING` (due on `day` and not yet complete) or `Status.DONE` (marked complete).
  The plain strings `"pending"` / `"done"` also work. An unknown status raises a clear `ValueError`.
- Both filters can be combined, e.g. `filter_tasks(pet_name="Mochi", status="pending")`.
- `get_todays_tasks(day)` is shorthand for "pending tasks on this day". The planner uses it.

### Conflict detection: `Scheduler.detect_conflicts(day=None, tasks=None)`

A lightweight check that **returns warning strings instead of raising**, so the app always keeps running.

1. Take the due tasks that have a preferred time and turn each into a time window: `Task.time_window()` → `(start, end)` in minutes.
2. Sort the windows by start time.
3. Compare each window only with the tasks that start before it ends, then `break`. Tasks far apart in the day are never compared.

It catches exact same-time clashes (08:00 vs 08:00) and partial overlaps (08:00–08:30 vs 08:15). Each warning says whether the clash is
for one pet or two. `generate_plan()` also stores these warnings in `DailyPlan.conflicts`. It adds a note there whenever a timed task had to be pushed later.
The Streamlit app shows them as warning banners.

### Recurring tasks: `Task.mark_complete()` → `Task.next_occurrence()` → `Scheduler.complete_task()`

- Each `Task` has a `due_date` and a `frequency` (`once`, `daily`, `weekly`). `Task.is_due(day)` is simply
  "not completed and `due_date <= day`".
- `Task.mark_complete(on)` marks the task done and returns the next occurrence. That is a fresh copy with a new id,
  due `on + timedelta(days=1)` for daily tasks or `on + timedelta(days=7)` for weekly ones. One-off tasks return `None`.
  Completing an already-completed task also returns `None`, so duplicates can't be created.
- `Scheduler.complete_task(task_id)` finds the task across all pets, completes it, and adds the new instance to the same pet.
- Using `timedelta` means month ends, leap years, and year boundaries are handled correctly.

### Building the plan: `Scheduler.generate_plan()`

1. **Select** (`_select_within_budget`): sort by priority (high first), then preferred time, then shortest. Keep each task that still fits the
   owner's minutes, and list the rest as skipped. This greedy rule is predictable, so the most important care always gets in.
2. **Lay out** (`_layout`): timed tasks are placed at their preferred time, or as soon after as the previous task allows.
   Flexible tasks then fill the earliest free gap that fits (`_earliest_gap`). They don't all get pushed to the end of the day.
3. **Explain** (`DailyPlan.explain()`): gives the reason for each task, lists skipped tasks, and lists conflicts.

## 📸 Demo Walkthrough

Describe your app in numbered steps so a reader can follow along without watching a video:

1. <!-- Describe this step -->
2. <!-- Describe this step -->
3. <!-- Describe this step -->
4. <!-- Describe this step -->
5. <!-- Add more steps as needed -->

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
