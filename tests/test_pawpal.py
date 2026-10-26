"""Basic tests for the PawPal+ logic layer."""

from datetime import date, time, timedelta

import pytest

from pawpal_system import Category, Frequency, Owner, Pet, Priority, Scheduler, Status, Task


def make_task() -> Task:
    """Return a simple task for testing."""
    return Task(description="Breakfast", category=Category.FEEDING, duration_minutes=10)


def test_mark_complete_changes_status():
    task = make_task()
    assert task.completed is False
    assert task.last_completed is None

    task.mark_complete()

    assert task.completed is True
    assert task.last_completed == date.today()


def test_add_task_increases_pet_task_count():
    pet = Pet(name="Biscuit", species="dog")
    assert len(pet.get_tasks()) == 0

    task = make_task()
    pet.add_task(task)

    assert len(pet.get_tasks()) == 1
    assert task in pet.get_tasks()


def make_owner() -> tuple[Owner, Pet, Pet, Scheduler]:
    """Return an owner with two pets and a scheduler."""
    owner = Owner(name="Jordan", available_minutes=120, day_start=time(7, 0))
    dog, cat = Pet(name="Biscuit", species="dog"), Pet(name="Mochi", species="cat")
    owner.add_pet(dog)
    owner.add_pet(cat)
    return owner, dog, cat, Scheduler(owner)


def test_sort_by_time_puts_untimed_last():
    owner, dog, _, scheduler = make_owner()
    late = Task(description="Dinner", category=Category.FEEDING, duration_minutes=10, preferred_time=time(18, 0))
    anytime = Task(description="Play", category=Category.ENRICHMENT, duration_minutes=10)
    early = Task(description="Breakfast", category=Category.FEEDING, duration_minutes=10, preferred_time=time(7, 0))
    for t in (late, anytime, early):
        dog.add_task(t)

    ordered = [t for _, t in scheduler.sort_by_time(owner.get_all_tasks())]

    assert ordered == [early, late, anytime]


def test_filter_by_pet_and_status():
    _, dog, cat, scheduler = make_owner()
    walk = scheduler.schedule_walk(dog, 30)
    meds = Task(description="Meds", category=Category.MEDS, duration_minutes=5)
    cat.add_task(meds)
    walk.mark_complete()

    assert [t for _, t in scheduler.filter_tasks(pet_name="mochi")] == [meds]
    assert [t for _, t in scheduler.filter_tasks(status="done")] == [walk]
    assert [t for _, t in scheduler.filter_tasks(status="pending")] == [meds]
    # The Status enum and its plain-string form give the same result.
    assert scheduler.filter_tasks(status=Status.DONE) == scheduler.filter_tasks(status="done")
    with pytest.raises(ValueError):
        scheduler.filter_tasks(status="finished")


def test_completing_recurring_task_creates_next_instance():
    day = date(2026, 1, 1)
    _, dog, _, scheduler = make_owner()
    daily = make_task()
    weekly = Task(description="Bath", category=Category.GROOMING, duration_minutes=30, frequency=Frequency.WEEKLY)
    once = Task(description="Vet", category=Category.OTHER, duration_minutes=60, frequency=Frequency.ONCE)
    for t in (daily, weekly, once):
        dog.add_task(t)

    next_daily = scheduler.complete_task(daily.id, on=day)
    next_weekly = scheduler.complete_task(weekly.id, on=day)

    assert scheduler.complete_task(once.id, on=day) is None
    assert next_daily.due_date == day + timedelta(days=1)
    assert next_weekly.due_date == day + timedelta(days=7)
    assert next_daily in dog.tasks and next_daily.id != daily.id
    assert not next_daily.completed and daily.completed
    assert not next_weekly.is_due(day + timedelta(days=6))
    assert next_weekly.is_due(day + timedelta(days=7))
    # Completing the same task twice must not spawn a duplicate.
    assert scheduler.complete_task(daily.id, on=day) is None
    assert len(dog.tasks) == 5


def test_detect_conflicts_flags_overlaps_only():
    _, dog, cat, scheduler = make_owner()
    scheduler.schedule_walk(dog, 30, preferred_time=time(8, 0))
    cat.add_task(Task(description="Meds", category=Category.MEDS, duration_minutes=5, preferred_time=time(8, 15)))
    cat.add_task(Task(description="Dinner", category=Category.FEEDING, duration_minutes=10, preferred_time=time(8, 30)))

    conflicts = scheduler.detect_conflicts()

    assert len(conflicts) == 1
    assert "Walk" in conflicts[0] and "Meds" in conflicts[0]


def test_plan_has_no_overlaps_and_fills_gaps():
    _, dog, cat, scheduler = make_owner()
    scheduler.schedule_walk(dog, 30, preferred_time=time(8, 0))
    cat.add_task(Task(description="Meds", category=Category.MEDS, duration_minutes=5, preferred_time=time(8, 15)))
    litter = Task(description="Litter", category=Category.OTHER, duration_minutes=20)
    cat.add_task(litter)

    plan = scheduler.generate_plan()
    items = plan.items

    for a, b in zip(items, items[1:]):
        assert a.end_time <= b.start_time
    # The untimed task fills the 07:00-08:00 gap instead of waiting until the end.
    assert next(i for i in items if i.task is litter).start_time == time(7, 0)
    assert any("Meds" in c and "08:30" in c for c in plan.conflicts)


DAY = date(2026, 3, 10)


def timed(description: str, at: time | None, minutes: int = 10, **kwargs) -> Task:
    """Return a task due on DAY at the given preferred time (None = anytime)."""
    return Task(
        description=description,
        category=Category.OTHER,
        duration_minutes=minutes,
        preferred_time=at,
        due_date=DAY,
        **kwargs,
    )


# --- Sorting ---


def test_sort_by_time_returns_chronological_order():
    owner, dog, cat, scheduler = make_owner()
    noon, dawn, evening, morning = (
        timed("Noon", time(12, 0)),
        timed("Dawn", time(6, 0)),
        timed("Evening", time(19, 30)),
        timed("Morning", time(9, 15)),
    )
    dog.add_task(noon)
    cat.add_task(dawn)
    dog.add_task(evening)
    cat.add_task(morning)

    ordered = [t for _, t in scheduler.sort_by_time(owner.get_all_tasks())]

    assert [t.description for t in ordered] == ["Dawn", "Morning", "Noon", "Evening"]
    times = [t.preferred_time for t in ordered]
    assert times == sorted(times)


def test_sort_by_time_breaks_ties_by_priority_then_insertion_order():
    owner, dog, _, scheduler = make_owner()
    low = timed("Low", time(8, 0), priority=Priority.LOW)
    high = timed("High", time(8, 0), priority=Priority.HIGH)
    first_medium = timed("Medium 1", time(8, 0))
    second_medium = timed("Medium 2", time(8, 0))
    for t in (low, first_medium, high, second_medium):
        dog.add_task(t)

    ordered = [t for _, t in scheduler.sort_by_time(owner.get_all_tasks())]

    assert [t.description for t in ordered] == ["High", "Medium 1", "Medium 2", "Low"]


def test_sort_by_time_handles_empty_and_all_untimed():
    owner, dog, _, scheduler = make_owner()
    assert scheduler.sort_by_time([]) == []

    a, b = timed("A", None, priority=Priority.LOW), timed("B", None, priority=Priority.HIGH)
    dog.add_task(a)
    dog.add_task(b)

    assert [t for _, t in scheduler.sort_by_time(owner.get_all_tasks())] == [b, a]


# --- Recurrence ---


def test_completing_daily_task_creates_task_for_next_day():
    _, dog, _, scheduler = make_owner()
    breakfast = timed("Breakfast", time(7, 30), priority=Priority.HIGH)
    dog.add_task(breakfast)

    nxt = scheduler.complete_task(breakfast.id, on=DAY)

    assert breakfast.completed and breakfast.last_completed == DAY
    assert nxt is not None and nxt is not breakfast and nxt.id != breakfast.id
    assert nxt.due_date == DAY + timedelta(days=1)
    assert not nxt.completed and nxt.last_completed is None
    # Everything else carries over to the new instance.
    assert (nxt.description, nxt.preferred_time, nxt.priority, nxt.frequency) == (
        "Breakfast", time(7, 30), Priority.HIGH, Frequency.DAILY
    )
    assert any(t is nxt for t in dog.tasks)
    # Not due today any more, due tomorrow.
    assert [t for _, t in scheduler.get_todays_tasks(DAY)] == []
    assert [t for _, t in scheduler.get_todays_tasks(DAY + timedelta(days=1))] == [nxt]


def test_recurring_task_chains_and_crosses_year_boundary():
    _, dog, _, scheduler = make_owner()
    nye = date(2026, 12, 31)
    task = Task(description="Walk", category=Category.WALK, duration_minutes=20, due_date=nye)
    dog.add_task(task)

    second = scheduler.complete_task(task.id, on=nye)
    third = scheduler.complete_task(second.id, on=second.due_date)

    assert second.due_date == date(2027, 1, 1)
    assert third.due_date == date(2027, 1, 2)
    assert len(dog.tasks) == 3


def test_late_completion_counts_from_completion_day():
    _, dog, _, scheduler = make_owner()
    weekly = timed("Bath", None, frequency=Frequency.WEEKLY)
    dog.add_task(weekly)

    nxt = scheduler.complete_task(weekly.id, on=DAY + timedelta(days=4))

    assert nxt.due_date == DAY + timedelta(days=11)


def test_overdue_task_is_still_due_but_future_task_is_not():
    _, dog, _, scheduler = make_owner()
    overdue = Task(description="Meds", category=Category.MEDS, duration_minutes=5,
                   due_date=DAY - timedelta(days=2))
    future = Task(description="Bath", category=Category.GROOMING, duration_minutes=30,
                  due_date=DAY + timedelta(days=1))
    dog.add_task(overdue)
    dog.add_task(future)

    assert [t for _, t in scheduler.get_todays_tasks(DAY)] == [overdue]


def test_complete_unknown_task_raises():
    _, _, _, scheduler = make_owner()
    with pytest.raises(KeyError):
        scheduler.complete_task("no-such-id", on=DAY)


# --- Conflict detection ---


def test_detect_conflicts_flags_duplicate_times_same_and_different_pets():
    _, dog, cat, scheduler = make_owner()
    dog.add_task(timed("Walk", time(8, 0), minutes=30))
    dog.add_task(timed("Flea treatment", time(8, 0), minutes=5))  # same pet, same time
    dog.add_task(timed("Evening walk", time(18, 0), minutes=20))
    cat.add_task(timed("Play", time(18, 0), minutes=20))  # other pet, same time

    conflicts = scheduler.detect_conflicts(DAY)

    assert len(conflicts) == 2
    morning = next(c for c in conflicts if "Flea treatment" in c)
    evening = next(c for c in conflicts if "Play" in c)
    assert "Walk" in morning and "both for Biscuit" in morning
    assert "Evening walk" in evening and "Biscuit and Mochi" in evening


def test_detect_conflicts_long_task_overlapping_several():
    _, dog, cat, scheduler = make_owner()
    dog.add_task(timed("Hike", time(8, 0), minutes=120))
    cat.add_task(timed("Meds", time(8, 10), minutes=5))
    cat.add_task(timed("Brush", time(9, 0), minutes=10))
    cat.add_task(timed("Lunch", time(10, 0), minutes=10))  # starts as the hike ends

    conflicts = scheduler.detect_conflicts(DAY)

    assert len(conflicts) == 2
    assert all("Hike" in c for c in conflicts)
    assert not any("Lunch" in c for c in conflicts)


def test_detect_conflicts_ignores_completed_and_untimed_tasks():
    _, dog, _, scheduler = make_owner()
    walk = timed("Walk", time(8, 0), minutes=30, frequency=Frequency.ONCE)
    dog.add_task(walk)
    dog.add_task(timed("Meds", time(8, 0), minutes=5))
    dog.add_task(timed("Litter", None, minutes=30))
    walk.mark_complete(on=DAY)

    assert scheduler.detect_conflicts(DAY) == []


# --- Plan building ---


def test_plan_with_zero_budget_skips_everything():
    owner, dog, _, scheduler = make_owner()
    owner.available_minutes = 0
    dog.add_task(timed("Walk", time(8, 0)))

    plan = scheduler.generate_plan(DAY)

    assert plan.items == [] and len(plan.skipped) == 1
    assert "Skipped" in plan.explain()


def test_plan_with_no_tasks_explains_itself():
    _, _, _, scheduler = make_owner()
    assert scheduler.generate_plan(DAY).explain() == "No tasks are due today."


def test_budget_exact_fit_and_greedy_skip():
    owner, dog, _, scheduler = make_owner()
    owner.available_minutes = 60
    big = timed("Big", None, minutes=50, priority=Priority.HIGH)
    too_big = timed("Too big", None, minutes=20, priority=Priority.MEDIUM)
    exact = timed("Exact", None, minutes=10, priority=Priority.LOW)
    for t in (big, too_big, exact):
        dog.add_task(t)

    plan = scheduler.generate_plan(DAY)

    assert [i.task for i in plan.items] == [big, exact]
    assert plan.total_minutes == 60
    assert [t for _, t in plan.skipped] == [too_big]


def test_plan_keeps_timed_task_before_day_start():
    owner, dog, _, scheduler = make_owner()
    owner.day_start = time(8, 0)
    early = timed("Early meds", time(7, 0), minutes=5)
    anytime = timed("Litter", None, minutes=10)
    dog.add_task(early)
    dog.add_task(anytime)

    plan = scheduler.generate_plan(DAY)

    assert [(i.task, i.start_time) for i in plan.items] == [(early, time(7, 0)), (anytime, time(8, 0))]
    assert plan.conflicts == []


def test_plan_keeps_timed_task_that_ends_after_midnight():
    owner, dog, _, scheduler = make_owner()
    late_walk = timed("Late walk", time(23, 30), minutes=60)
    dog.add_task(late_walk)

    plan = scheduler.generate_plan(DAY)

    item = plan.items[0]
    assert item.task is late_walk and item.start_time == time(23, 30)
    assert item.ends_next_day and item.time_range == "23:30-00:30 (+1 day)"
    assert "23:30-00:30 (+1 day)  Late walk" in plan.display()
    assert plan.skipped == [] and plan.conflicts == []


def test_task_ending_exactly_at_midnight_is_same_day():
    _, dog, _, scheduler = make_owner()
    dog.add_task(timed("Night meds", time(23, 55), minutes=5))

    item = scheduler.generate_plan(DAY).items[0]

    assert not item.ends_next_day and item.time_range == "23:55-00:00"


def test_plan_skips_tasks_pushed_past_midnight():
    owner, dog, _, scheduler = make_owner()
    owner.day_start = time(23, 50)
    late_walk = timed("Late walk", time(23, 30), minutes=40, priority=Priority.HIGH)  # ends 00:10
    pushed = timed("Night meds", time(23, 45), minutes=5)  # would be pushed to 00:10
    anytime = timed("Litter", None, minutes=15)  # no room before midnight
    for t in (late_walk, pushed, anytime):
        dog.add_task(t)

    plan = scheduler.generate_plan(DAY)

    assert [i.task for i in plan.items] == [late_walk]
    assert {t.description for _, t in plan.skipped} == {"Night meds", "Litter"}
    assert any("Night meds" in c and "pushed past midnight" in c for c in plan.conflicts)
    assert any("Litter" in c and "before midnight" in c for c in plan.conflicts)


# --- Validation ---


@pytest.mark.parametrize("description, minutes", [("", 10), ("   ", 10), ("Walk", 0), ("Walk", -5)])
def test_invalid_task_raises(description, minutes):
    with pytest.raises(ValueError):
        Task(description=description, category=Category.WALK, duration_minutes=minutes)


def test_duplicate_pet_name_is_case_insensitive():
    owner, _, _, _ = make_owner()
    with pytest.raises(ValueError):
        owner.add_pet(Pet(name="mochi", species="cat"))


def test_same_task_cannot_be_added_twice():
    _, dog, _, _ = make_owner()
    task = make_task()
    dog.add_task(task)
    with pytest.raises(ValueError):
        dog.add_task(task)
