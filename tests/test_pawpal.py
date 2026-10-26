"""Basic tests for the PawPal+ logic layer."""

from datetime import date, time, timedelta

import pytest

from pawpal_system import Category, Frequency, Owner, Pet, Scheduler, Status, Task


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
