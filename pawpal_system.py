"""PawPal+ logic layer: backend classes for pets, tasks, and daily scheduling."""

import bisect
import datetime as dt
from dataclasses import dataclass, field, replace
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


class Status(StrEnum):
    """Task status filter: still due, or marked complete."""

    PENDING = "pending"
    DONE = "done"


# Days between occurrences for each recurring frequency.
_INTERVAL_DAYS = {Frequency.DAILY: 1, Frequency.WEEKLY: 7}

# Minutes in a day; a plan never runs past midnight.
_DAY_MINUTES = 24 * 60


@dataclass(slots=True, kw_only=True)
class Task:
    """A single pet care activity (walk, feeding, meds, enrichment, grooming, ...)."""

    description: str
    category: Category
    duration_minutes: int
    priority: Priority = Priority.MEDIUM
    preferred_time: time | None = None
    frequency: Frequency = Frequency.DAILY
    due_date: dt.date = field(default_factory=dt.date.today)
    completed: bool = False
    last_completed: dt.date | None = None
    id: str = field(default_factory=lambda: uuid4().hex, compare=False)

    def __post_init__(self) -> None:
        """Validate fields (e.g. duration must be positive)."""
        if not self.description.strip():
            raise ValueError("Task description cannot be empty.")
        if self.duration_minutes <= 0:
            raise ValueError("Task duration must be a positive number of minutes.")

    def mark_complete(self, on: dt.date | None = None) -> "Task | None":
        """Mark this task as done (on the given day, default today).

        Returns the next occurrence for daily/weekly tasks, or None for one-off
        tasks or a task that was already complete (so nothing is duplicated).
        """
        if self.completed:
            return None
        self.completed = True
        self.last_completed = on or dt.date.today()
        return self.next_occurrence()

    def next_occurrence(self) -> "Task | None":
        """Return a fresh, incomplete copy of this task due one interval after it was completed."""
        if self.frequency is Frequency.ONCE:
            return None
        base = self.last_completed or self.due_date
        return replace(
            self,
            due_date=base + timedelta(days=_INTERVAL_DAYS[self.frequency]),
            completed=False,
            last_completed=None,
            id=uuid4().hex,
        )

    def is_due(self, day: dt.date) -> bool:
        """Return True if this task still needs doing on the given day."""
        return not self.completed and self.due_date <= day

    def time_window(self) -> tuple[int, int] | None:
        """Return (start, end) in minutes after midnight if this task has a preferred time."""
        if self.preferred_time is None:
            return None
        start = _to_minutes(self.preferred_time)
        return start, start + self.duration_minutes


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

    @property
    def ends_next_day(self) -> bool:
        """True if this item runs past midnight."""
        return _to_minutes(self.start_time) + self.task.duration_minutes > _DAY_MINUTES

    @property
    def time_range(self) -> str:
        """Start-end as HH:MM-HH:MM, marking an end time on the next day."""
        suffix = " (+1 day)" if self.ends_next_day else ""
        return f"{self.start_time:%H:%M}-{self.end_time:%H:%M}{suffix}"


@dataclass(slots=True)
class DailyPlan:
    """The scheduler's output: what's planned today, what was skipped, and why."""

    date: dt.date = field(default_factory=dt.date.today)
    available_minutes: int = 0
    items: list[ScheduledItem] = field(default_factory=list)
    skipped: list[tuple[Pet, Task]] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)

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
            f"duration, until the {self.available_minutes} available minutes were used. "
            f"Timed tasks were placed at their preferred times; flexible tasks fill the gaps.",
            f"Scheduled {len(self.items)} task(s) using {self.total_minutes} minutes.",
        ]
        lines += [f"- {i.task.description} ({i.pet.name}): {i.reason}" for i in self.items]
        if self.skipped:
            lines.append("Skipped because there wasn't enough time left:")
            lines += [
                f"- {t.description} ({p.name}, {t.duration_minutes} min, {t.priority.name.lower()} priority)"
                for p, t in self.skipped
            ]
        if self.conflicts:
            lines.append("Conflicts:")
            lines += [f"- {c}" for c in self.conflicts]
        return "\n".join(lines)

    def display(self) -> str:
        """Return the plan formatted for display in the UI."""
        if not self.items:
            return f"Plan for {self.date:%A, %b %d}: nothing scheduled."
        lines = [f"Plan for {self.date:%A, %b %d}:"]
        lines += [
            f"{i.time_range}  {i.task.description} for {i.pet.name} "
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
        return self.filter_tasks(status=Status.PENDING, day=day)

    def filter_tasks(
        self,
        pet_name: str | None = None,
        status: Status | str | None = None,
        day: dt.date | None = None,
    ) -> list[tuple[Pet, Task]]:
        """Return (pet, task) pairs matching a pet name and/or status.

        status is Status.PENDING (due on the day and not complete) or Status.DONE
        (marked complete); plain "pending"/"done" strings work too. None means any
        status. Filters combine with AND.
        """
        try:
            status = Status(status) if status is not None else None
        except ValueError:
            raise ValueError(f"Unknown status {status!r}; use 'pending' or 'done'.") from None
        day = day or dt.date.today()
        key = pet_name.strip().casefold() if pet_name else None

        def matches(pet: Pet, task: Task) -> bool:
            """True if this pair passes both the pet-name and status filters."""
            if key is not None and pet.name.casefold() != key:
                return False
            if status is Status.PENDING:
                return task.is_due(day)
            if status is Status.DONE:
                return task.completed
            return True

        return [(pet, task) for pet, task in self.owner.get_all_tasks() if matches(pet, task)]

    @staticmethod
    def sort_by_time(pairs: list[tuple[Pet, Task]]) -> list[tuple[Pet, Task]]:
        """Return pairs ordered by preferred time; untimed tasks go last, higher priority first on ties."""

        def by_time(pair: tuple[Pet, Task]) -> tuple:
            """Sort key: preferred time (untimed = end of day), then higher priority first."""
            _, task = pair
            return (task.preferred_time or time.max, -task.priority)

        return sorted(pairs, key=by_time)

    def detect_conflicts(
        self, day: dt.date | None = None, tasks: list[tuple[Pet, Task]] | None = None
    ) -> list[str]:
        """Return warnings for due tasks whose preferred time windows overlap.

        Lightweight: never raises, just returns messages (empty list = no conflicts).
        Pass tasks to reuse an already-computed due list instead of fetching it again.
        Sweep line: sort windows by start, then compare each one only with the
        tasks that start before it ends, so non-overlapping tasks are never compared.
        """
        if tasks is None:
            tasks = self.get_todays_tasks(day)
        # Sort on the window only: comparing whole tuples would compare Pet objects on ties.
        timed = sorted(
            ((task.time_window(), pet, task) for pet, task in tasks if task.preferred_time),
            key=lambda entry: entry[0],
        )
        warnings = []
        for i, ((start, end), pet, task) in enumerate(timed):
            for j in range(i + 1, len(timed)):
                (other_start, other_end), other_pet, other = timed[j]
                if other_start >= end:
                    break
                who = f"both for {pet.name}" if pet is other_pet else f"{pet.name} and {other_pet.name}"
                warnings.append(
                    f"{task.description} ({_fmt(start)}-{_fmt(end)}) overlaps "
                    f"{other.description} ({_fmt(other_start)}-{_fmt(other_end)}), {who}."
                )
        return warnings

    def complete_task(self, task_id: str, on: dt.date | None = None) -> Task | None:
        """Mark the task with this id complete, whichever pet it belongs to.

        For daily/weekly tasks the next occurrence is added to the same pet and
        returned; one-off tasks return None.
        """
        for pet, task in self.owner.get_all_tasks():
            if task.id == task_id:
                next_task = task.mark_complete(on)
                if next_task is not None:
                    pet.add_task(next_task)
                return next_task
        raise KeyError(f"No task with id {task_id}.")

    def generate_plan(self, day: dt.date | None = None) -> DailyPlan:
        """Find due tasks, flag conflicts, fit tasks into the time budget, then lay them out."""
        day = day or dt.date.today()
        plan = DailyPlan(date=day, available_minutes=self.owner.available_minutes)
        due = self.get_todays_tasks(day)
        plan.conflicts = self.detect_conflicts(day, tasks=due)
        chosen, plan.skipped = self._select_within_budget(due)
        for item in self._layout(chosen, plan):
            plan.add_item(item)
        return plan

    def _select_within_budget(
        self, due: list[tuple[Pet, Task]]
    ) -> tuple[list[tuple[Pet, Task]], list[tuple[Pet, Task]]]:
        """Greedy pick: most important tasks first, keep each one that still fits the budget."""
        remaining = self.owner.available_minutes
        chosen, skipped = [], []
        for pet, task in sorted(due, key=self._sort_key):
            if task.duration_minutes <= remaining:
                chosen.append((pet, task))
                remaining -= task.duration_minutes
            else:
                skipped.append((pet, task))
        return chosen, skipped

    def _layout(self, chosen: list[tuple[Pet, Task]], plan: DailyPlan) -> list[ScheduledItem]:
        """Give each chosen task a start time, in clock order.

        Timed tasks go at their preferred time (or as soon after as possible),
        even if that is before day_start; flexible tasks then fill the earliest
        gap from day_start on. Pushed timed tasks are noted in plan.conflicts.
        Timed tasks may end after midnight but must start before it; flexible
        tasks must finish by midnight. Anything else is moved to plan.skipped.
        """
        timed = [(pet, task) for pet, task in chosen if task.preferred_time]
        flexible = [(pet, task) for pet, task in chosen if not task.preferred_time]
        day_start = _to_minutes(self.owner.day_start)
        busy: list[tuple[int, int]] = []
        placed: list[tuple[int, Pet, Task, str]] = []
        cursor = 0
        for pet, task in self.sort_by_time(timed):
            wanted = _to_minutes(task.preferred_time)
            start = max(wanted, cursor)
            if start >= _DAY_MINUTES:
                self._drop_past_midnight(plan, pet, task, "would be pushed past midnight")
                continue
            reason = self._reason(task)
            if start > wanted:
                reason += f", moved to {_fmt(start)} because the earlier slot was taken"
                plan.conflicts.append(
                    f"{task.description} for {pet.name} wanted {_fmt(wanted)} but starts at {_fmt(start)}."
                )
            cursor = start + task.duration_minutes
            busy.append((start, cursor))
            placed.append((start, pet, task, reason))

        for pet, task in sorted(flexible, key=self._sort_key):
            start = _earliest_gap(busy, day_start, task.duration_minutes)
            if start + task.duration_minutes > _DAY_MINUTES:
                self._drop_past_midnight(plan, pet, task, "doesn't fit before midnight")
                continue
            bisect.insort(busy, (start, start + task.duration_minutes))
            placed.append((start, pet, task, self._reason(task)))

        placed.sort(key=lambda entry: entry[0])
        return [
            ScheduledItem(pet=pet, task=task, start_time=_from_minutes(start), reason=reason)
            for start, pet, task, reason in placed
        ]

    @staticmethod
    def _drop_past_midnight(plan: DailyPlan, pet: Pet, task: Task, why: str) -> None:
        """Skip a task that can't be placed today and say why in plan.conflicts."""
        plan.skipped.append((pet, task))
        plan.conflicts.append(f"{task.description} for {pet.name} {why}, so it was skipped.")

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


def _to_minutes(t: time) -> int:
    """Minutes after midnight for a time of day."""
    return t.hour * 60 + t.minute


def _from_minutes(minutes: int) -> time:
    """Time of day for a count of minutes after midnight (wraps past midnight)."""
    hours, mins = divmod(minutes % (24 * 60), 60)
    return time(hours, mins)


def _fmt(minutes: int) -> str:
    """Format minutes after midnight as HH:MM."""
    hours, mins = divmod(minutes % (24 * 60), 60)
    return f"{hours:02d}:{mins:02d}"


def _earliest_gap(busy: list[tuple[int, int]], not_before: int, duration: int) -> int:
    """Return the earliest start >= not_before where duration fits between sorted busy intervals."""
    candidate = not_before
    for start, end in busy:
        if candidate + duration <= start:
            return candidate
        candidate = max(candidate, end)
    return candidate
