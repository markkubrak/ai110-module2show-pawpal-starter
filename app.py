import datetime as dt

import streamlit as st

from pawpal_system import Category, Frequency, Owner, Pet, Priority, Scheduler, Task

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")

st.markdown(
    """
Welcome to the PawPal+ starter app.

This file is intentionally thin. It gives you a working Streamlit app so you can start quickly,
but **it does not implement the project logic**. Your job is to design the system and build it.

Use this app as your interactive demo once your backend classes/functions exist.
"""
)

with st.expander("Scenario", expanded=True):
    st.markdown(
        """
**PawPal+** is a pet care planning assistant. It helps a pet owner plan care tasks
for their pet(s) based on constraints like time, priority, and preferences.

You will design and implement the scheduling logic and connect it to this Streamlit UI.
"""
    )

with st.expander("What you need to build", expanded=True):
    st.markdown(
        """
At minimum, your system should:
- Represent pet care tasks (what needs to happen, how long it takes, priority)
- Represent the pet and the owner (basic info and preferences)
- Build a plan/schedule for a day that chooses and orders tasks based on constraints
- Explain the plan (why each task was chosen and when it happens)
"""
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
for warning in scheduler.detect_conflicts():
    st.warning(f"Time conflict: {warning}")
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
        st.table([
            {
                "Time": f"{i.start_time:%H:%M}-{i.end_time:%H:%M}",
                "Task": i.task.description,
                "Pet": i.pet.name,
                "Minutes": i.task.duration_minutes,
                "Priority": i.task.priority.name.lower(),
            }
            for i in plan.items
        ])
    else:
        st.warning("Nothing could be scheduled.")
    st.markdown("**Why this plan**")
    st.text(plan.explain())
