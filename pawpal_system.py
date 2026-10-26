"""PawPal+ logic layer: backend classes for pets, tasks, and daily scheduling."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as Date


@dataclass
class Task:
    """A single pet care activity (walk, feeding, meds, enrichment, grooming, ...)."""

    title: str
    category: str
    duration_minutes: int
    priority: str = "medium"  # "high", "medium", or "low"
    preferred_time: str | None = None  # e.g. "08:00" or "morning"
    completed: bool = False

    def mark_complete(self) -> None:
        """Mark this task as done."""
        pass

    def priority_value(self) -> int:
        """Return a numeric rank for sorting (higher = more important)."""
        pass


@dataclass
class Pet:
    """A pet and the care tasks that belong to it."""

    name: str
    species: str
    breed: str = ""
    age: int = 0
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Add a care task to this pet."""
        pass

    def remove_task(self, title: str) -> None:
        """Remove a task by its title."""
        pass

    def get_tasks(self) -> list[Task]:
        """Return all tasks for this pet."""
        pass


@dataclass
class Owner:
    """A pet owner, their daily time budget, and their pets."""

    name: str
    available_minutes: int
    preferences: list[str] = field(default_factory=list)
    pets: list[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner."""
        pass

    def remove_pet(self, name: str) -> None:
        """Remove a pet by its name."""
        pass

    def get_pet(self, name: str) -> Pet | None:
        """Return the pet with the given name, or None if not found."""
        pass

    def get_all_tasks(self) -> list[Task]:
        """Return every task across all of this owner's pets."""
        pass


@dataclass
class ScheduledItem:
    """A task placed in the daily plan, with a start time and the reason it was chosen."""

    task: Task
    pet: Pet
    start_time: str
    reason: str = ""


@dataclass
class DailyPlan:
    """The scheduler's output: what's planned today, what was skipped, and why."""

    date: Date = field(default_factory=Date.today)
    items: list[ScheduledItem] = field(default_factory=list)
    skipped: list[Task] = field(default_factory=list)
    total_minutes: int = 0

    def add_item(self, item: ScheduledItem) -> None:
        """Add a scheduled item to the plan and update the total minutes."""
        pass

    def explain(self) -> str:
        """Return a human-readable explanation of why the plan was built this way."""
        pass

    def display(self) -> str:
        """Return the plan formatted for display in the UI."""
        pass


class Scheduler:
    """Builds a daily plan for an owner based on time available, priority, and preferences."""

    def __init__(self, owner: Owner) -> None:
        self.owner = owner

    def schedule_walk(
        self,
        pet: Pet,
        duration_minutes: int,
        preferred_time: str | None = None,
        priority: str = "high",
    ) -> Task:
        """Create a walk task, add it to the pet, and return it."""
        pass

    def get_todays_tasks(self) -> list[Task]:
        """Return all incomplete tasks across the owner's pets."""
        pass

    def generate_plan(self) -> DailyPlan:
        """Sort tasks by priority and fit them into the owner's available time."""
        pass

    def _sort_by_priority(self, tasks: list[Task]) -> list[Task]:
        """Return tasks ordered from highest to lowest priority."""
        pass
