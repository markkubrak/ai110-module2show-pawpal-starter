import datetime as dt

import streamlit as st

from pawpal_system import Category, Frequency, Owner, Pet, Priority, Scheduler, Task

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")

st.caption(
    "Plan your pets' care for the day: add pets and tasks, then let PawPal+ build a schedule "
    "that fits your time, puts important care first, and explains its choices."
)

st.divider()

# --- Owner (kept in session_state so it survives reruns) ---
if "owner" not in st.session_state:
    st.session_state.owner = Owner(name="Jordan", available_minutes=90)
owner = st.session_state.owner
scheduler = Scheduler(owner)

st.subheader("Owner")
col1, col2, col3 = st.columns(3)
with col1:
    owner.name = st.text_input("Owner name", value=owner.name)
with col2:
    owner.available_minutes = int(
        st.number_input("Minutes available today", min_value=0, max_value=1440, value=owner.available_minutes)
    )
with col3:
    owner.day_start = st.time_input("Day starts at", value=owner.day_start)

# --- Add a pet ---
st.subheader("Add a Pet")
with st.form("add_pet", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        pet_name = st.text_input("Pet name")
        species = st.selectbox("Species", ["dog", "cat", "other"])
    with col2:
        breed = st.text_input("Breed (optional)")
        age = st.number_input("Age", min_value=0, max_value=40, value=1)
    if st.form_submit_button("Add pet"):
        if not pet_name.strip():
            st.error("Pet name is required.")
        else:
            try:
                owner.add_pet(Pet(name=pet_name.strip(), species=species, breed=breed.strip(), age=int(age)))
                st.success(f"Added {pet_name}.")
            except ValueError as e:
                st.error(str(e))

if owner.pets:
    st.write("Your pets: " + ", ".join(f"**{p.name}** ({p.species})" for p in owner.pets))
else:
    st.info("No pets yet. Add one above.")

st.divider()

# --- Schedule a task ---
st.subheader("Schedule a Task")
if not owner.pets:
    st.caption("Add a pet first.")
else:
    with st.form("add_task", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            pet_choice = st.selectbox("Pet", [p.name for p in owner.pets])
            category = st.selectbox("Category", list(Category), format_func=lambda c: c.value.title())
            description = st.text_input("Description", placeholder="Leave blank for a walk")
            frequency = st.selectbox("Repeats", list(Frequency), index=1, format_func=lambda f: f.value.title())
        with col2:
            duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
            priority = st.selectbox("Priority", list(Priority), index=2, format_func=lambda p: p.name.title())
            has_time = st.checkbox("Has a preferred time")
            preferred = st.time_input("Preferred time", value=owner.day_start)
        if st.form_submit_button("Add task"):
            pet = owner.get_pet(pet_choice)
            preferred_time = preferred if has_time else None
            try:
                if category is Category.WALK and not description.strip():
                    scheduler.schedule_walk(pet, int(duration), preferred_time, priority)
                else:
                    pet.add_task(Task(
                        description=description,
                        category=category,
                        duration_minutes=int(duration),
                        priority=priority,
                        preferred_time=preferred_time,
                        frequency=frequency,
                    ))
                st.success(f"Task added for {pet.name}.")
            except ValueError as e:
                st.error(str(e))

# --- Today's tasks ---
st.subheader("Today's Tasks")
col1, col2 = st.columns(2)
with col1:
    pet_filter = st.selectbox("Show pet", ["All pets"] + [p.name for p in owner.pets])
with col2:
    status_filter = st.selectbox("Show status", ["pending", "done", "all"])
todays = scheduler.sort_by_time(scheduler.filter_tasks(
    pet_name=None if pet_filter == "All pets" else pet_filter,
    status=None if status_filter == "all" else status_filter,
))
overlaps = scheduler.detect_conflicts()
if overlaps:
    st.warning(
        f"**{len(overlaps)} time conflict(s) today.** You can't do these at the same time:\n\n"
        + "\n".join(f"- {w}" for w in overlaps)
        + "\n\nThe schedule will start the later task when the earlier one ends. "
        "To avoid that, change a preferred time or mark a task done."
    )
elif any(t.preferred_time for _, t in scheduler.get_todays_tasks()):
    st.success("No time conflicts today.")
if todays:
    for pet, task in todays:
        col1, col2 = st.columns([4, 1])
        with col1:
            when = f" @ {task.preferred_time:%H:%M}" if task.preferred_time else ""
            st.write(
                f"**{task.description}** for {pet.name}{when} · {task.duration_minutes} min · "
                f"{task.priority.name.lower()} · {task.frequency.value}"
            )
        with col2:
            if task.is_due(dt.date.today()):
                if st.button("Done", key=f"done_{task.id}"):
                    scheduler.complete_task(task.id)
                    st.rerun()
            else:
                st.caption("Finished" if task.completed else f"Due {task.due_date:%b %d}")
else:
    st.info("No tasks match these filters.")

st.divider()

# --- Build schedule ---
st.subheader("Build Schedule")
if st.button("Generate schedule", type="primary"):
    plan = scheduler.generate_plan()
    if plan.items:
        st.success(
            f"Scheduled {len(plan.items)} task(s) for {plan.date:%A, %b %d}, using "
            f"{plan.total_minutes} of {plan.available_minutes} available minutes."
        )
        st.table([
            {
                "Time": i.time_range,
                "Task": i.task.description,
                "Pet": i.pet.name,
                "Minutes": i.task.duration_minutes,
                "Priority": i.task.priority.name.lower(),
                "Why": i.reason,
            }
            for i in plan.items
        ])
    elif not plan.skipped:
        st.info("No tasks are due today.")
    else:
        st.error("Nothing fit in your available time.")

    # Overlaps were already shown above; here only say what the scheduler changed.
    adjustments = [c for c in plan.conflicts if c not in overlaps]
    if adjustments:
        st.info("**Adjusted to avoid overlaps:**\n\n" + "\n".join(f"- {c}" for c in adjustments))
    if plan.skipped:
        st.warning(
            f"**{len(plan.skipped)} task(s) skipped** because they didn't fit in your "
            f"{plan.available_minutes} minutes. Lower-priority tasks are dropped first."
        )
        st.table([
            {
                "Task": t.description,
                "Pet": p.name,
                "Minutes": t.duration_minutes,
                "Priority": t.priority.name.lower(),
            }
            for p, t in plan.skipped
        ])
    with st.expander("Full explanation"):
        st.text(plan.explain())
