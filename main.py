"""Demo script: build an owner with pets and tasks, then print today's schedule."""

from datetime import time

from pawpal_system import Category, Frequency, Owner, Pet, Priority, Scheduler, Task


def main() -> None:
    owner = Owner(name="Jordan", available_minutes=90, day_start=time(7, 30))

    biscuit = Pet(name="Biscuit", species="dog", breed="Golden Retriever", age=3)
    mochi = Pet(name="Mochi", species="cat", breed="Siamese", age=5)
    owner.add_pet(biscuit)
    owner.add_pet(mochi)

    scheduler = Scheduler(owner)
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
        preferred_time=time(9, 0),
    ))
    mochi.add_task(Task(
        description="Feather toy play",
        category=Category.ENRICHMENT,
        duration_minutes=20,
        priority=Priority.MEDIUM,
        preferred_time=time(18, 0),
    ))
    biscuit.add_task(Task(
        description="Brush coat",
        category=Category.GROOMING,
        duration_minutes=45,
        priority=Priority.LOW,
        frequency=Frequency.WEEKLY,
    ))

    plan = scheduler.generate_plan()

    print("=" * 50)
    print(f"Today's Schedule for {owner.name}")
    print("=" * 50)
    print(plan.display())
    print()
    print("Why this plan:")
    print(plan.explain())


if __name__ == "__main__":
    main()
