"""Demo script: build an owner with pets and tasks, then show sorting, filtering,
recurring tasks, conflict detection, and today's schedule."""

import datetime as dt
from datetime import time

from pawpal_system import Category, Frequency, Owner, Pet, Priority, Scheduler, Task


def section(title: str) -> None:
    """Print a section header."""
    print()
    print("=" * 50)
    print(title)
    print("=" * 50)


def show(pairs: list[tuple[Pet, Task]]) -> None:
    """Print (pet, task) pairs one per line."""
    if not pairs:
        print("(none)")
    for pet, task in pairs:
        when = f"{task.preferred_time:%H:%M}" if task.preferred_time else "anytime"
        print(f"{when:>7}  {task.description} for {pet.name} [{task.priority.name.lower()}, {task.frequency.value}]")


def main() -> None:
    today = dt.date.today()
    owner = Owner(name="Jordan", available_minutes=90, day_start=time(7, 30))

    biscuit = Pet(name="Biscuit", species="dog", breed="Golden Retriever", age=3)
    mochi = Pet(name="Mochi", species="cat", breed="Siamese", age=5)
    owner.add_pet(biscuit)
    owner.add_pet(mochi)

    scheduler = Scheduler(owner)
    # Tasks are added out of time order on purpose, so sorting has something to do.
    mochi.add_task(Task(
        description="Feather toy play",
        category=Category.ENRICHMENT,
        duration_minutes=20,
        priority=Priority.MEDIUM,
        preferred_time=time(18, 0),
    ))
    scheduler.schedule_walk(biscuit, duration_minutes=30, preferred_time=time(8, 0))
    biscuit.add_task(Task(
        description="Breakfast",
        category=Category.FEEDING,
        duration_minutes=10,
        priority=Priority.HIGH,
        preferred_time=time(7, 30),
    ))
    mochi.add_task(Task(
        description="Thyroid medication",
        category=Category.MEDS,
        duration_minutes=5,
        priority=Priority.HIGH,
        preferred_time=time(8, 15),  # overlaps Biscuit's walk -> conflict
    ))
    mochi.add_task(Task(
        description="Litter box",
        category=Category.OTHER,
        duration_minutes=10,
        priority=Priority.MEDIUM,  # no preferred time -> fills a gap
    ))
    biscuit.add_task(Task(
        description="Brush coat",
        category=Category.GROOMING,
        duration_minutes=45,
        priority=Priority.LOW,
        frequency=Frequency.WEEKLY,
    ))
    # Two exact same-time clashes for the conflict check:
    biscuit.add_task(Task(  # same pet: 08:00, same as Biscuit's walk
        description="Flea treatment",
        category=Category.MEDS,
        duration_minutes=5,
        priority=Priority.MEDIUM,
        preferred_time=time(8, 0),
    ))
    biscuit.add_task(Task(  # different pet: 18:00, same as Mochi's play time
        description="Evening walk",
        category=Category.WALK,
        duration_minutes=20,
        priority=Priority.MEDIUM,
        preferred_time=time(18, 0),
    ))

    section("All tasks, sorted by time")
    show(scheduler.sort_by_time(owner.get_all_tasks()))

    section("Filter: Mochi's tasks only")
    show(scheduler.filter_tasks(pet_name="Mochi"))

    section("Recurring tasks: complete breakfast and brushing")
    next_breakfast = scheduler.complete_task(biscuit.tasks[1].id, on=today)
    next_brushing = scheduler.complete_task(biscuit.tasks[2].id, on=today)
    print(f"New Breakfast instance (daily) due:   {next_breakfast.due_date}  (today + 1 day)")
    print(f"New Brush coat instance (weekly) due: {next_brushing.due_date}  (today + 7 days)")
    print(f"Biscuit now has {len(biscuit.tasks)} task instances.")
    print("Done:")
    show(scheduler.filter_tasks(status="done"))
    print("Due tomorrow:")
    show(scheduler.sort_by_time(scheduler.get_todays_tasks(today + dt.timedelta(days=1))))

    section("Conflict check")
    for warning in scheduler.detect_conflicts(today) or ["No conflicts."]:
        print(f"! {warning}")

    plan = scheduler.generate_plan(today)
    section(f"Today's Schedule for {owner.name}")
    print(plan.display())
    print()
    print("Why this plan:")
    print(plan.explain())


if __name__ == "__main__":
    main()
