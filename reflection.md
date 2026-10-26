# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

My first UML design is built around three things a user has to be able to do: add a pet, schedule a walk, and see today's tasks. An `Owner` has many `Pet`s, and each `Pet` has many `Task`s. A `Scheduler` reads from the owner and produces a `DailyPlan`. The plan is made of `ScheduledItem`s, and each item has a start time and a reason it was chosen.

- **Owner**: holds the owner's name, the minutes they have free each day, and their preferences (for example, "morning walks"). It keeps the list of pets (`add_pet`, `remove_pet`, `get_pet`) and can collect every pet's tasks (`get_all_tasks`). This covers **adding a pet**.
- **Pet**: holds the pet's details (name, species, breed, age) and its own task list (`add_task`, `remove_task`, `get_tasks`).
- **Task**: one care activity, such as a walk, feeding, meds, enrichment or grooming. It stores a title, category, duration, priority, preferred time and whether it's done. `mark_complete` updates the status, and `priority_value` turns "high/medium/low" into a number the scheduler can sort by.
- **Scheduler**: holds the scheduling logic. `schedule_walk` creates a walk task and adds it to a pet, which covers **scheduling a walk**. `get_todays_tasks` returns the tasks that still need doing, which covers **seeing today's tasks**. `generate_plan` sorts tasks by priority and fits them into the owner's available time.
- **DailyPlan**: the result of scheduling. It stores the scheduled items, the tasks that were skipped because there wasn't enough time, and the total minutes used. `explain()` describes why the plan was built this way, and `display()` formats it for the UI.
- **ScheduledItem**: links a task to a pet, a start time and a short reason (for example, "high priority, fits before 9am preference").

**b. Design changes**

- Did your design change during implementation?
- If yes, describe at least one change and why you made it.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
