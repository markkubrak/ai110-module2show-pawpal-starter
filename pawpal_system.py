"""PawPal+ logic layer: backend classes for pets, tasks, and daily scheduling."""

import datetime as dt
from dataclasses import dataclass, field
from datetime import time, timedelta
from enum import IntEnum, StrEnum
from uuid import uuid4


class Priority(IntEnum):
    """Task importance; higher value = more important, so it sorts naturally."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3


class Category(StrEnum):
    """Kinds of pet care a task can be."""

    WALK = "walk"
    FEEDING = "feeding"
    MEDS = "meds"
    ENRICHMENT = "enrichment"
    GROOMING = "grooming"
    OTHER = "other"


class Frequency(StrEnum):
    """How often a task repeats."""

    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"


@dataclass(slots=True, kw_only=True)
class Task:
    """A single pet care activity (walk, feeding, meds, enrichment, grooming, ...)."""

    description: str
    category: Category
    duration_minutes: int
    priority: Priority = Priority.MEDIUM
    preferred_time: time | None = None
    frequency: Frequency = Frequency.DAILY
    completed: bool = False
    last_completed: dt.date | None = None
    id: str = field(default_factory=lambda: uuid4().hex, compare=False)

    def __post_init__(self) -> None:
        """Validate fields (e.g. duration must be positive)."""
        if not self.description.strip():
            raise ValueError("Task description cannot be empty.")
        if self.duration_minutes <= 0:
            raise ValueError("Task duration must be a positive number of minutes.")

    def mark_complete(self, on: dt.date | None = None) -> None:
        """Mark this task as done (on the given day, default today)."""
        self.completed = True
        self.last_completed = on or dt.date.today()

    def is_due(self, day: dt.date) -> bool:
        """Return True if this task still needs doing on the given day."""
        if self.frequency is Frequency.ONCE:
            return not self.completed
        if self.last_completed is None:
            return True
        if self.frequency is Frequency.DAILY:
            return self.last_completed < day
        return (day - self.last_completed).days >= 7


@dataclass(slots=True, kw_only=True)
class Pet:
    """A pet and the care tasks that belong to it."""

    name: str
    species: str
    breed: str = ""
    age: int = 0
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Add a care task to this pet."""
        if any(t.id == task.id for t in self.tasks):
            raise ValueError(f"Task {task.id} is already assigned to {self.name}.")
        self.tasks.append(task)

    def remove_task(self, task_id: str) -> None:
        """Remove a task by its id."""
        for i, t in enumerate(self.tasks):
            if t.id == task_id:
                del self.tasks[i]
                return
        raise KeyError(f"No task with id {task_id} for {self.name}.")

    def get_tasks(self) -> list[Task]:
        """Return all tasks for this pet."""
        return list(self.tasks)


@dataclass(slots=True, kw_only=True)
class Owner:
    """A pet owner, their daily time budget, and their pets."""

    name: str
    available_minutes: int
    day_start: time = time(8, 0)
    preferences: list[str] = field(default_factory=list)
    pets: list[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner (reject duplicate names)."""
        if self.get_pet(pet.name) is not None:
            raise ValueError(f"{self.name} already has a pet named {pet.name}.")
        self.pets.append(pet)

    def remove_pet(self, name: str) -> None:
        """Remove a pet by its name."""
        pet = self.get_pet(name)
        if pet is None:
            raise KeyError(f"{self.name} has no pet named {name}.")
        self.pets.remove(pet)

    def get_pet(self, name: str) -> Pet | None:
        """Return the pet with the given name (case-insensitive), or None if not found."""
        key = name.strip().casefold()
        return next((p for p in self.pets if p.name.casefold() == key), None)

    def get_all_tasks(self) -> list[tuple[Pet, Task]]:
        """Return every (pet, task) pair across all of this owner's pets."""
        return [(pet, task) for pet in self.pets for task in pet.tasks]


@dataclass(slots=True, frozen=True)
class ScheduledItem:
    """A task placed in the daily plan, with a start time and the reason it was chosen."""

    pet: Pet
    task: Task
    start_time: time
    reason: str = ""

    @property
    def end_time(self) -> time:
        """When this item finishes."""
        return _add_minutes(self.start_time, self.task.duration_minutes)


@dataclass(slots=True)
class DailyPlan:
    """The scheduler's output: what's planned today, what was skipped, and why."""

    date: dt.date = field(default_factory=dt.date.today)
    available_minutes: int = 0
    items: list[ScheduledItem] = field(default_factory=list)
    skipped: list[tuple[Pet, Task]] = field(default_factory=list)

    @property
    def total_minutes(self) -> int:
        """Total scheduled minutes, computed from items so it can never drift."""
        return sum(item.task.duration_minutes for item in self.items)

    def add_item(self, item: ScheduledItem) -> None:
        """Add a scheduled item to the plan."""
        self.items.append(item)

    def explain(self) -> str:
        """Return a human-readable explanation of why the plan was built this way."""
        if not self.items and not self.skipped:
            return "No tasks are due today."
        lines = [
            f"Tasks were chosen by priority (high first), then preferred time, then shortest "
            f"duration, until the {self.available_minutes} available minutes were used.",
            f"Scheduled {len(self.items)} task(s) using {self.total_minutes} minutes.",
        ]
        lines += [f"- {i.task.description} ({i.pet.name}): {i.reason}" for i in self.items]
        if self.skipped:
            lines.append("Skipped because there wasn't enough time left:")
            lines += [
                f"- {t.description} ({p.name}, {t.duration_minutes} min, {t.priority.name.lower()} priority)"
                for p, t in self.skipped
            ]
        return "\n".join(lines)

    def display(self) -> str:
        """Return the plan formatted for display in the UI."""
        if not self.items:
            return f"Plan for {self.date:%A, %b %d}: nothing scheduled."
        lines = [f"Plan for {self.date:%A, %b %d}:"]
        lines += [
            f"{i.start_time:%H:%M}-{i.end_time:%H:%M}  {i.task.description} for {i.pet.name} "
            f"({i.task.duration_minutes} min) [{i.task.priority.name.lower()}]"
            for i in self.items
        ]
        return "\n".join(lines)


@dataclass(slots=True)
class Scheduler:
    """Builds a daily plan for an owner based on time available, priority, and preferences."""

    owner: Owner

    def schedule_walk(
        self,
        pet: Pet,
        duration_minutes: int,
        preferred_time: time | None = None,
        priority: Priority = Priority.HIGH,
    ) -> Task:
        """Create a walk task, add it to the pet, and return it."""
        task = Task(
            description="Walk",
            category=Category.WALK,
            duration_minutes=duration_minutes,
            priority=priority,
            preferred_time=preferred_time,
        )
        pet.add_task(task)
        return task

    def get_todays_tasks(self, day: dt.date | None = None) -> list[tuple[Pet, Task]]:
        """Return the (pet, task) pairs that are due on the given day (default today)."""
        day = day or dt.date.today()
        return [(p, t) for p, t in self.owner.get_all_tasks() if t.is_due(day)]

    def complete_task(self, task_id: str, on: dt.date | None = None) -> Task:
        """Mark the task with this id complete, whichever pet it belongs to."""
        for _, task in self.owner.get_all_tasks():
            if task.id == task_id:
                task.mark_complete(on)
                return task
        raise KeyError(f"No task with id {task_id}.")

    def generate_plan(self, day: dt.date | None = None) -> DailyPlan:
        """Sort tasks once, then greedily fit them into the owner's available time."""
        day = day or dt.date.today()
        plan = DailyPlan(date=day, available_minutes=self.owner.available_minutes)
        remaining = self.owner.available_minutes

        # Pick which tasks fit, most important first.
        chosen: list[tuple[Pet, Task]] = []
        for pet, task in sorted(self.get_todays_tasks(day), key=self._sort_key):
            if task.duration_minutes <= remaining:
                chosen.append((pet, task))
                remaining -= task.duration_minutes
            else:
                plan.skipped.append((pet, task))

        # Lay the chosen tasks out back to back: preferred times first, in clock order.
        chosen.sort(key=lambda pair: (pair[1].preferred_time or time.max, -pair[1].priority))
        start = self.owner.day_start
        for pet, task in chosen:
            if task.preferred_time and task.preferred_time > start:
                start = task.preferred_time
            plan.add_item(ScheduledItem(pet=pet, task=task, start_time=start, reason=self._reason(task)))
            start = _add_minutes(start, task.duration_minutes)
        return plan

    def _sort_key(self, pair: tuple[Pet, Task]) -> tuple:
        """Sort key: highest priority first, then earliest preferred time, then shortest."""
        _, task = pair
        return (-task.priority, task.preferred_time or time.max, task.duration_minutes)

    def _reason(self, task: Task) -> str:
        """Short explanation of why a task made it into the plan."""
        reason = f"{task.priority.name.lower()} priority"
        if task.preferred_time:
            reason += f", preferred around {task.preferred_time:%H:%M}"
        return reason + f", fits in the time budget ({task.duration_minutes} min)"


def _add_minutes(t: time, minutes: int) -> time:
    """Add minutes to a time of day (wraps past midnight)."""
    return (dt.datetime.combine(dt.date.min, t) + timedelta(minutes=minutes)).time()
