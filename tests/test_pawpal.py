"""Basic tests for the PawPal+ logic layer."""

from datetime import date

from pawpal_system import Category, Pet, Task


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
