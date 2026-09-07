"""
Growth Group Potluck & RSVP Coordinator
----------------------------------------
Replaces Sign Up Genius for a single church growth group gathering.

Features:
 - Event details (date/time/location/host/notes) set by admin
 - Main dish set by the host, shown to everyone (not claimable)
 - Admin-defined food categories with a set number of open slots
   (e.g. "Side Dish" needs 4, "Dessert" needs 2, "Drinks" needs 2)
 - Members pick their name from a known roster (or add themselves)
 - RSVP: Yes / No / Maybe, headcount (adults + kids), dietary notes
 - Members claim open food slots and say what they're bringing
 - "Who's Coming" board: headcount, attendee list, full food board
 - Admin panel (PIN protected): edit event, manage categories/slots,
   manage the roster of known names, reset everything for next time
 - Data is stored in Firebase Firestore so it survives Streamlit
   Community Cloud reboots/redeploys.

Data model (Firestore collections):
  meta/event            -> single doc: event details + main dish
  roster/{name}          -> known member names
  rsvps/{name}           -> RSVP status + headcount + notes per person
  categories/{auto_id}   -> {name, order}
  slots/{auto_id}        -> {category_id, category_name, index,
                              claimed_by, dish, notes}
"""

import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, date, time as dtime

st.set_page_config(page_title="Growth Group Potluck", page_icon="🍲", layout="wide")

# ----------------------------------------------------------------------
# Firebase setup
# ----------------------------------------------------------------------

@st.cache_resource
def get_db():
    if not firebase_admin._apps:
        if "firebase" not in st.secrets:
            st.error(
                "Firebase isn't configured yet.\n\n"
                "In your Streamlit app's **Settings → Secrets**, add a "
                "`[firebase]` section containing your Firebase service "
                "account JSON key (each field as its own line), for example:\n\n"
                "```\n[firebase]\n"
                'type = "service_account"\n'
                'project_id = "your-project-id"\n'
                'private_key_id = "..."\n'
                'private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"\n'
                'client_email = "...@....iam.gserviceaccount.com"\n'
                'client_id = "..."\n'
                'auth_uri = "https://accounts.google.com/o/oauth2/auth"\n'
                'token_uri = "https://oauth2.googleapis.com/token"\n'
                'auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"\n'
                'client_x509_cert_url = "..."\n'
                "```"
            )
            st.stop()
        cred = credentials.Certificate(dict(st.secrets["firebase"]))
        firebase_admin.initialize_app(cred)
    return firestore.client()


db = get_db()

ADMIN_PIN = st.secrets.get("admin_pin", "1234")

# ----------------------------------------------------------------------
# Data access helpers
# ----------------------------------------------------------------------

DEFAULT_EVENT = {
    "title": "Growth Group Gathering",
    "event_date": date.today().isoformat(),
    "event_time": "18:00",
    "location": "",
    "host": "",
    "notes": "",
    "main_dish": "",
    "main_dish_by": "",
}


def load_event():
    doc = db.collection("meta").document("event").get()
    if doc.exists:
        data = DEFAULT_EVENT.copy()
        data.update(doc.to_dict())
        return data
    return DEFAULT_EVENT.copy()


def save_event(data):
    db.collection("meta").document("event").set(data, merge=True)


def load_roster():
    docs = db.collection("roster").stream()
    names = sorted([d.id for d in docs])
    return names


def add_to_roster(name):
    name = name.strip()
    if name:
        db.collection("roster").document(name).set({"name": name})


def remove_from_roster(name):
    db.collection("roster").document(name).delete()


def load_rsvps():
    docs = db.collection("rsvps").stream()
    return {d.id: d.to_dict() for d in docs}


def save_rsvp(name, status, adults, kids, notes):
    db.collection("rsvps").document(name).set(
        {
            "name": name,
            "status": status,
            "adults": adults,
            "kids": kids,
            "notes": notes,
            "updated_at": datetime.now().isoformat(),
        }
    )


def delete_rsvp(name):
    db.collection("rsvps").document(name).delete()


def load_categories():
    docs = db.collection("categories").order_by("order").stream()
    return [{"id": d.id, **d.to_dict()} for d in docs]


def load_slots():
    docs = db.collection("slots").stream()
    slots = [{"id": d.id, **d.to_dict()} for d in docs]
    slots.sort(key=lambda s: (s.get("category_name", ""), s.get("index", 0)))
    return slots


def add_category(name, num_slots):
    cats = load_categories()
    order = len(cats)
    cat_ref = db.collection("categories").document()
    cat_ref.set({"name": name, "order": order})
    for i in range(num_slots):
        db.collection("slots").document().set(
            {
                "category_id": cat_ref.id,
                "category_name": name,
                "index": i + 1,
                "claimed_by": "",
                "dish": "",
                "notes": "",
            }
        )


def add_slots_to_category(cat_id, cat_name, additional):
    existing = [s for s in load_slots() if s["category_id"] == cat_id]
    start = len(existing)
    for i in range(additional):
        db.collection("slots").document().set(
            {
                "category_id": cat_id,
                "category_name": cat_name,
                "index": start + i + 1,
                "claimed_by": "",
                "dish": "",
                "notes": "",
            }
        )


def remove_category(cat_id):
    for s in db.collection("slots").where("category_id", "==", cat_id).stream():
        s.reference.delete()
    db.collection("categories").document(cat_id).delete()


def claim_slot(slot_id, name, dish, notes=""):
    db.collection("slots").document(slot_id).update(
        {"claimed_by": name, "dish": dish, "notes": notes}
    )


def unclaim_slot(slot_id):
    db.collection("slots").document(slot_id).update(
        {"claimed_by": "", "dish": "", "notes": ""}
    )


def reset_event_data():
    for r in db.collection("rsvps").stream():
        r.reference.delete()
    for s in db.collection("slots").stream():
        s.reference.update({"claimed_by": "", "dish": "", "notes": ""})


# ----------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------

event = load_event()
roster = load_roster()

st.title(f"🍲 {event['title']}")

info_cols = st.columns(4)
try:
    pretty_date = datetime.fromisoformat(event["event_date"]).strftime("%A, %B %d, %Y")
except Exception:
    pretty_date = event["event_date"]
info_cols[0].metric("Date", pretty_date or "TBD")
info_cols[1].metric("Time", event["event_time"] or "TBD")
info_cols[2].metric("Location", event["location"] or "TBD")
info_cols[3].metric("Host", event["host"] or "TBD")

if event["notes"]:
    st.info(event["notes"])

if event["main_dish"]:
    st.success(
        f"🍽️ **Main dish is covered:** {event['main_dish']}"
        + (f" (thanks to {event['main_dish_by']}!)" if event["main_dish_by"] else "")
    )

st.divider()

tab_signup, tab_board, tab_admin = st.tabs(["📋 RSVP & Sign Up", "👀 Who's Coming", "⚙️ Admin"])

# ----------------------------------------------------------------------
# TAB 1: RSVP & Sign up for food
# ----------------------------------------------------------------------
with tab_signup:
    st.subheader("1. Who are you?")
    name_choice = st.selectbox(
        "Select your name",
        ["-- choose --"] + roster + ["+ Add a new name"],
        key="name_choice",
    )
    current_name = None
    if name_choice == "+ Add a new name":
        new_name = st.text_input("Type your name")
        if new_name:
            current_name = new_name.strip()
            if st.button("Add me to the group list"):
                add_to_roster(current_name)
                st.success(f"Added {current_name} to the group list.")
                st.rerun()
    elif name_choice != "-- choose --":
        current_name = name_choice

    if current_name:
        st.subheader("2. Are you coming?")
        rsvps = load_rsvps()
        existing = rsvps.get(current_name, {})
        with st.form("rsvp_form"):
            status = st.radio(
                "RSVP",
                ["Yes", "No", "Maybe"],
                index=["Yes", "No", "Maybe"].index(existing.get("status", "Yes")),
                horizontal=True,
            )
            c1, c2 = st.columns(2)
            adults = c1.number_input(
                "Adults attending (including you)", min_value=0, max_value=20,
                value=int(existing.get("adults", 1)),
            )
            kids = c2.number_input(
                "Kids attending", min_value=0, max_value=20,
                value=int(existing.get("kids", 0)),
            )
            notes = st.text_area(
                "Notes (allergies, dietary needs, etc.)",
                value=existing.get("notes", ""),
            )
            submitted = st.form_submit_button("Save my RSVP")
            if submitted:
                save_rsvp(current_name, status, adults, kids, notes)
                st.success("RSVP saved!")
                st.rerun()

        st.subheader("3. What will you bring?")
        categories = load_categories()
        slots = load_slots()
        if not categories:
            st.caption("The host hasn't set up food categories yet.")
        for cat in categories:
            cat_slots = [s for s in slots if s["category_id"] == cat["id"]]
            filled = len([s for s in cat_slots if s["claimed_by"]])
            st.markdown(f"**{cat['name']}** — {filled}/{len(cat_slots)} filled")
            for s in cat_slots:
                cols = st.columns([3, 2, 2])
                if s["claimed_by"] == current_name:
                    cols[0].write(f"✅ You: **{s['dish'] or '(no dish name yet)'}**")
                    if cols[1].button("Edit", key=f"edit_{s['id']}"):
                        st.session_state[f"editing_{s['id']}"] = True
                    if cols[2].button("Remove my item", key=f"unclaim_{s['id']}"):
                        unclaim_slot(s["id"])
                        st.rerun()
                    if st.session_state.get(f"editing_{s['id']}"):
                        new_dish = st.text_input(
                            "What are you bringing?", value=s["dish"], key=f"dish_{s['id']}"
                        )
                        if st.button("Save item", key=f"save_{s['id']}"):
                            claim_slot(s["id"], current_name, new_dish)
                            st.session_state[f"editing_{s['id']}"] = False
                            st.rerun()
                elif s["claimed_by"]:
                    cols[0].write(f"🔒 Claimed by {s['claimed_by']}: {s['dish']}")
                else:
                    dish_input = cols[0].text_input(
                        "Item you'll bring", key=f"input_{s['id']}", label_visibility="collapsed",
                        placeholder=f"e.g. potato salad ({cat['name']})",
                    )
                    if cols[1].button("Claim this slot", key=f"claim_{s['id']}"):
                        claim_slot(s["id"], current_name, dish_input or cat["name"])
                        st.rerun()
    else:
        st.info("Choose or add your name above to RSVP and sign up for food.")

# ----------------------------------------------------------------------
# TAB 2: Who's coming + food board (read only overview)
# ----------------------------------------------------------------------
with tab_board:
    rsvps = load_rsvps()
    yes_people = {k: v for k, v in rsvps.items() if v.get("status") == "Yes"}
    maybe_people = {k: v for k, v in rsvps.items() if v.get("status") == "Maybe"}
    no_people = {k: v for k, v in rsvps.items() if v.get("status") == "No"}

    total_adults = sum(v.get("adults", 0) for v in yes_people.values())
    total_kids = sum(v.get("kids", 0) for v in yes_people.values())

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Confirmed (Yes)", len(yes_people))
    m2.metric("Total adults", total_adults)
    m3.metric("Total kids", total_kids)
    m4.metric("Maybe", len(maybe_people))

    st.subheader("Attendee list")
    if rsvps:
        rows = []
        for n, v in sorted(rsvps.items()):
            rows.append(
                {
                    "Name": n,
                    "Status": v.get("status", ""),
                    "Adults": v.get("adults", 0),
                    "Kids": v.get("kids", 0),
                    "Notes": v.get("notes", ""),
                }
            )
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.caption("No RSVPs yet.")

    st.subheader("Food board")
    categories = load_categories()
    slots = load_slots()
    if event["main_dish"]:
        st.write(f"🍽️ **{event['main_dish']}** — {event['main_dish_by'] or 'Host'}")
    for cat in categories:
        cat_slots = [s for s in slots if s["category_id"] == cat["id"]]
        filled = len([s for s in cat_slots if s["claimed_by"]])
        st.progress(
            filled / len(cat_slots) if cat_slots else 0,
            text=f"{cat['name']}: {filled}/{len(cat_slots)} filled",
        )
        for s in cat_slots:
            if s["claimed_by"]:
                st.write(f"- {s['dish']} — *{s['claimed_by']}*")
            else:
                st.write("- _open slot_")

# ----------------------------------------------------------------------
# TAB 3: Admin
# ----------------------------------------------------------------------
with tab_admin:
    if "admin_ok" not in st.session_state:
        st.session_state.admin_ok = False

    if not st.session_state.admin_ok:
        pin = st.text_input("Admin PIN", type="password")
        if st.button("Unlock admin panel"):
            if pin == str(ADMIN_PIN):
                st.session_state.admin_ok = True
                st.rerun()
            else:
                st.error("Incorrect PIN.")
    else:
        st.success("Admin panel unlocked.")

        st.subheader("Event details")
        with st.form("event_form"):
            title = st.text_input("Title", value=event["title"])
            try:
                d_val = datetime.fromisoformat(event["event_date"]).date()
            except Exception:
                d_val = date.today()
            ev_date = st.date_input("Date", value=d_val)
            try:
                h, m = [int(x) for x in event["event_time"].split(":")]
                t_val = dtime(h, m)
            except Exception:
                t_val = dtime(18, 0)
            ev_time = st.time_input("Time", value=t_val)
            location = st.text_input("Location", value=event["location"])
            host = st.text_input("Host", value=event["host"])
            notes = st.text_area("Notes shown to everyone", value=event["notes"])
            st.markdown("**Main dish (provided by the host, not claimable)**")
            main_dish = st.text_input("Main dish", value=event["main_dish"])
            main_dish_by = st.text_input("Main dish provided by", value=event["main_dish_by"])
            if st.form_submit_button("Save event details"):
                save_event(
                    {
                        "title": title,
                        "event_date": ev_date.isoformat(),
                        "event_time": ev_time.strftime("%H:%M"),
                        "location": location,
                        "host": host,
                        "notes": notes,
                        "main_dish": main_dish,
                        "main_dish_by": main_dish_by,
                    }
                )
                st.success("Event details saved.")
                st.rerun()

        st.divider()
        st.subheader("Food categories & slots")
        categories = load_categories()
        for cat in categories:
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.write(f"**{cat['name']}**")
            add_n = c2.number_input(
                "Add more slots", min_value=0, max_value=20, value=0, key=f"addn_{cat['id']}"
            )
            if c2.button("Add slots", key=f"addbtn_{cat['id']}") and add_n > 0:
                add_slots_to_category(cat["id"], cat["name"], add_n)
                st.rerun()
            if c3.button("Delete category", key=f"del_{cat['id']}"):
                remove_category(cat["id"])
                st.rerun()

        with st.form("new_category_form"):
            st.write("Add a new category")
            cat_name = st.text_input("Category name (e.g. Side Dish, Dessert, Drinks)")
            cat_slots = st.number_input("Number of slots needed", min_value=1, max_value=30, value=2)
            if st.form_submit_button("Add category") and cat_name.strip():
                add_category(cat_name.strip(), int(cat_slots))
                st.success(f"Added {cat_name} with {cat_slots} slots.")
                st.rerun()

        st.divider()
        st.subheader("Group roster (known names)")
        for n in roster:
            c1, c2 = st.columns([4, 1])
            c1.write(n)
            if c2.button("Remove", key=f"rm_{n}"):
                remove_from_roster(n)
                st.rerun()
        with st.form("add_roster_form"):
            new_r = st.text_input("Add a name to the group list")
            if st.form_submit_button("Add name") and new_r.strip():
                add_to_roster(new_r.strip())
                st.rerun()

        st.divider()
        st.subheader("Reset for next gathering")
        st.caption(
            "Clears all RSVPs and un-claims every food slot, but keeps your "
            "categories/slots and the group roster so you can reuse them."
        )
        confirm = st.checkbox("I understand this will clear RSVPs and food claims.")
        if st.button("Reset event data", disabled=not confirm):
            reset_event_data()
            st.success("Event data reset. Ready for the next gathering!")
            st.rerun()

        if st.button("Lock admin panel"):
            st.session_state.admin_ok = False
            st.rerun()
