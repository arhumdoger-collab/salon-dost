import streamlit as st
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv
import os
from openai import OpenAI
from datetime import datetime

try:
    groq_api_key = st.secrets["GROQ_API_KEY"]
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_KEY"]
except:
    load_dotenv()
    groq_api_key = os.getenv("GROQ_API_KEY")
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

if not all([groq_api_key, supabase_url, supabase_key]):
    st.error("Keys nahi mili! Streamlit Secrets mein GROQ_API_KEY, SUPABASE_URL, SUPABASE_KEY daalo.")
    st.stop()

client = OpenAI(api_key=groq_api_key, base_url="https://api.groq.com/openai/v1")
supabase: Client = create_client(supabase_url, supabase_key)

@st.cache_data(ttl=60)
def load_barbers():
    try:
        res = supabase.table("barbers").select("*").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception as e:
        st.error(f"Barbers load nahi hue: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=60)
def load_services():
    try:
        res = supabase.table("barber_services").select("*, barbers(name)").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

barbers_df = load_barbers()
services_df = load_services()

now = datetime.now()
today_name = now.strftime("%A")
today_date = now.strftime("%d %B %Y")

if not barbers_df.empty:
    info = []
    available_today = []
    off_today = []
    for _, row in barbers_df.iterrows():
        n = row['name']
        t = row.get('timing', 'N/A')
        o = row.get('off_day', 'N/A')
        p = row.get('phone_number', 'N/A')
        info.append(f"{n}: Timing {t}, Off day {o}, Phone {p}")
        off_days = [d.strip() for d in str(o).split(",")] if o else []
        if today_name in off_days:
            off_today.append(n)
        else:
            available_today.append(n)
    barber_details_str = "\n".join(info)
    barber_names_str = ", ".join(barbers_df['name'].tolist())
    available_today_str = ", ".join(available_today) if available_today else "Koi nahi"
    off_today_str = ", ".join(off_today) if off_today else "Koi nahi"
else:
    barber_details_str = "Koi barber nahi hai abhi."
    barber_names_str = ""
    available_today_str = "Koi nahi"
    off_today_str = "Koi nahi"

if not services_df.empty:
    svc_lines = []
    for _, row in services_df.iterrows():
        barber_name = row.get('barbers', {}).get('name', f"Barber ID {row.get('barber_id', '?')}") if isinstance(row.get('barbers'), dict) else f"Barber ID {row.get('barber_id', '?')}"
        dur = row.get('duration_minutes', 30)
        svc_lines.append(f"{barber_name}: {row.get('service_name','?')} - Rs.{row.get('charge','?')} ({dur} min)")
    services_str = "\n".join(svc_lines)
else:
    services_str = "Koi services data nahi."

# ---- SYSTEM PROMPT: Strict rules taake AI booking flow hijack na kare ----
system_prompt = f"""
Tu Salon Dost hai – polite aur helpful salon assistant.

Aaj ki date: {today_date} ({today_name})

Available barbers aur unki details:
{barber_details_str}

Barber services aur charges (Rs. mein):
{services_str}

Aaj ({today_name}) available barbers: {available_today_str}
Aaj ({today_name}) off par hain: {off_today_str}

=== STRICT RULES - IN RULES KO BILKUL MAT TODNA ===

1. BOOKING FLOW KABHI KHUD SHURU MAT KARNA. Agar user booking karna chahta hai to SIRF yeh ek sawaal puchna:
   "Booking karwni hai? (Haan/Nahi)"
   Naam, phone, service, barber, date, time KABHI mat poochna. Yeh system khud handle karta hai.

2. Agar user "haan", "han", "yes", "ok", "hna" bole to SIRF yeh likho:
   "Theek hai, system booking shuru karega!"
   Kuch aur mat poochna.

3. Info queries ka jawab do: barber details, services, charges, off days, timing.

4. Off-topic baat pe: "Main sirf salon info ke liye hoon."

5. Hinglish mein jawab dena. Chhota aur clear.

6. EK hi reply dena, double message bilkul nahi.
"""

st.title("✂️ Salon Dost - Booking App")
st.caption("Assalam o Alaikum! Poocho kuch bhi 😊")

with st.sidebar:
    st.header("💈 Available Barbers")
    if not barbers_df.empty:
        st.dataframe(barbers_df[['name', 'timing', 'off_day', 'phone_number']], hide_index=True)
    else:
        st.info("Koi barber nahi database mein")
    if not services_df.empty:
        st.divider()
        st.subheader("🛎️ Services & Charges")
        display_svc = services_df.copy()
        if 'barbers' in display_svc.columns:
            display_svc['barber_name'] = display_svc['barbers'].apply(lambda x: x.get('name', '') if isinstance(x, dict) else '')
            st.dataframe(display_svc[['barber_name', 'service_name', 'charge']], hide_index=True)
    st.divider()
    st.markdown(f"📅 **Aaj:** {today_date} ({today_name})")
    st.markdown(f"✅ **Available aaj:** {available_today_str}")
    st.markdown(f"❌ **Off aaj:** {off_today_str}")

# Session state
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": system_prompt}]
if "booking_step" not in st.session_state:
    st.session_state.booking_step = 0
if "booking_data" not in st.session_state:
    st.session_state.booking_data = {}
if "booking_asked" not in st.session_state:
    st.session_state.booking_asked = False

# ---- Chat history display ----
for msg in st.session_state.messages[1:]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ---- AI reply ----
def get_ai_reply(messages):
    try:
        with st.chat_message("assistant"):
            placeholder = st.empty()
            full = ""
            stream = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=0.3,
                max_tokens=150,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    full += delta
                    placeholder.markdown(full + "▌")
            placeholder.markdown(full)
        return full.strip()
    except Exception as e:
        err = f"AI error: {e}"
        with st.chat_message("assistant"):
            st.markdown(err)
        return err

def show_direct_reply(text):
    with st.chat_message("assistant"):
        st.markdown(text)
    return text

# ---- Service Selection UI (step 2) ----
if st.session_state.get("booking_step") == 2:
    services_list = []
    if not services_df.empty:
        services_list = sorted(services_df["service_name"].dropna().unique().tolist())

    if "svc_selections" not in st.session_state:
        st.session_state.svc_selections = {s: False for s in services_list}

    with st.container(border=True):
        st.markdown("💇 **Kaunsi service(s) chahiye?**")
        st.caption("Ek ya zyada select karein, phir Confirm dabayein")
        cols = st.columns(2)
        for idx, svc in enumerate(services_list):
            st.session_state.svc_selections[svc] = cols[idx % 2].checkbox(
                svc,
                value=st.session_state.svc_selections.get(svc, False),
                key=f"chk_{svc}"
            )
        selected_svcs = [s for s, v in st.session_state.svc_selections.items() if v]
        if selected_svcs:
            st.success("✅ Selected: " + ", ".join(selected_svcs))
        col1, col2 = st.columns([1, 3])
        if col1.button("✅ Confirm", key="confirm_svc_btn", type="primary"):
            if selected_svcs:
                st.session_state.booking_data["service"] = ", ".join(selected_svcs)
                if "svc_selections" in st.session_state:
                    del st.session_state.svc_selections
                st.session_state.booking_step = 3
                svc_msg = "✅ Services: **" + ", ".join(selected_svcs) + "**\n\n📞 Ab apna **phone number** bataiye:"
                st.session_state.messages.append({"role": "assistant", "content": svc_msg})
                st.rerun()
            else:
                st.warning("⚠️ Kam se kam ek service select karein!")

# ---- Barber bookings fetch ----
def fetch_barber_bookings(barber_name, date_str=None):
    try:
        res = supabase.table("barbers").select("id, name, timing").ilike("name", f"%{barber_name}%").limit(1).execute()
        if not res.data:
            return None, None, None
        barber_id = res.data[0]["id"]
        bname = res.data[0]["name"]
        timing = res.data[0].get("timing", "N/A")
        from datetime import datetime as dt
        if not date_str:
            date_str = dt.now().strftime("%d %B %Y")
        bookings_res = supabase.table("bookings").select("booking_time, customer_name, service_name").eq("barber_id", barber_id).eq("booking_date", date_str).execute()
        return bname, timing, bookings_res.data if bookings_res.data else []
    except Exception as e:
        return None, None, None

# ---- YES words check (FIX: more comprehensive) ----
YES_WORDS = ["haan", "han", "yes", "hna", "okay", "bilkul", "zaroor", "sure", "ji", "ji haan", "ha"]

def is_yes_response(text):
    """Check karo kya user ne haan kaha"""
    text = text.lower().strip()
    # Exact match
    if text in YES_WORDS:
        return True
    # Word boundary match
    words = text.split()
    for w in words:
        if w in YES_WORDS:
            return True
    return False

# ---- BOOKING TRIGGER WORDS ----
BOOKING_WORDS = ["book", "booking", "appointment", "reserve", "buking", "apointment", "apointmnt"]

# ---- Main chat ----
if prompt := st.chat_input("Kya poochna hai?", disabled=(st.session_state.get("booking_step") == 2)):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    reply = ""
    lower_prompt = prompt.lower().strip()

    # ============ BOOKING FLOW (jab step > 0 ho) ============
    if st.session_state.booking_step > 0:
        step = st.session_state.booking_step
        data = st.session_state.booking_data

        if step == 1:
            # Naam lena
            data["name"] = prompt
            st.session_state.booking_step = 2
            reply_text = f"👋 Shukriya **{prompt}**! Ab service select karein:"
            with st.chat_message("assistant"):
                st.markdown(reply_text)
            reply = reply_text

        elif step == 2:
            reply = ""

        elif step == 3:
            # Phone lena
            data["phone"] = prompt
            chosen_services = [s.strip() for s in data.get("service", "").split(",") if s.strip()]
            if not services_df.empty and chosen_services:
                sets = []
                for cs in chosen_services:
                    ids = set(services_df[services_df["service_name"].str.lower() == cs.lower()]["barber_id"].tolist())
                    sets.append(ids)
                valid_barber_ids = set.union(*sets) if sets else set()
                valid_barber_names = []
                if not barbers_df.empty:
                    valid_barber_names = barbers_df[barbers_df["id"].isin(valid_barber_ids)]["name"].tolist()
                data["valid_barbers"] = valid_barber_names
                names_str = ", ".join(valid_barber_names) if valid_barber_names else barber_names_str
            else:
                names_str = barber_names_str
                data["valid_barbers"] = barbers_df["name"].tolist() if not barbers_df.empty else []
            services_display = data.get("service", "")
            reply = show_direct_reply(f"💈 **{services_display}** ke liye yeh barbers available hain:\n\n**{names_str}**\n\nKaunsa barber chahiye?")
            st.session_state.booking_step = 4

        elif step == 4:
            # Barber select karna
            chosen = prompt.strip()
            valid = data.get("valid_barbers", [])
            match = [b for b in valid if chosen.lower() in b.lower()]
            if not match:
                valid_str = ", ".join(valid) if valid else barber_names_str
                reply = show_direct_reply(f"❌ **{chosen}** yeh service nahi karta.\n\n**{data.get('service','')}** ke liye yeh barbers hain: **{valid_str}**\n\nInmein se choose karein:")
            else:
                data["barber"] = match[0]
                reply = show_direct_reply("📅 Date bataiye (jaise: 10 March 2026)")
                st.session_state.booking_step = 6

        elif step == 6:
            # Date lena
            from dateutil import parser as date_parser
            parsed_date = None
            try:
                parsed_date = date_parser.parse(prompt, dayfirst=True)
            except Exception:
                parsed_date = None

            if parsed_date is None:
                reply = show_direct_reply("❌ Date samajh nahi aaya. Dobara likhiye (jaise: 10 March 2026):")
            elif parsed_date.date() < datetime.now().date():
                reply = show_direct_reply(
                    f"❌ Yeh date ({parsed_date.strftime('%d %B %Y')}) guzar chuki hai! "
                    f"Aaj ya aage ki date dein (aaj: {datetime.now().strftime('%d %B %Y')}):"
                )
            else:
                chosen_day = parsed_date.strftime("%A")
                barber_off = ""
                if not barbers_df.empty:
                    brow = barbers_df[barbers_df["name"].str.lower() == data.get("barber", "").lower()]
                    if not brow.empty:
                        barber_off = brow.iloc[0].get("off_day", "")
                off_days_list = [d.strip().lower() for d in str(barber_off).split(",") if d.strip()]
                if chosen_day.lower() in off_days_list:
                    reply = show_direct_reply(
                        f"❌ **{data.get('barber','')}** ka {chosen_day} off hota hai! "
                        f"(Off days: {barber_off})\n\nKoi aur date dein:"
                    )
                else:
                    data["date"] = parsed_date.strftime("%d %B %Y")
                    reply = show_direct_reply("⏰ Time bataiye (jaise: 4:00 PM)")
                    st.session_state.booking_step = 7

        elif step == 7:
            # Time lena aur booking save karna
            from dateutil import parser as date_parser
            import re

            def parse_time(t_str):
                try:
                    return date_parser.parse(t_str)
                except:
                    return None

            def parse_barber_timing(timing_str):
                try:
                    parts = re.split(r'[-–]', timing_str)
                    if len(parts) == 2:
                        start = date_parser.parse(parts[0].strip())
                        end = date_parser.parse(parts[1].strip())
                        return start, end
                except:
                    pass
                return None, None

            user_time = parse_time(prompt)

            if user_time is None:
                reply = show_direct_reply("❌ Time samajh nahi aaya. Dobara likhiye (jaise: 4:00 PM):")
            else:
                barber_id = None
                barber_name = data["barber"]
                barber_timing = None
                try:
                    res = supabase.table("barbers").select("id, name, timing").ilike("name", f"%{data['barber']}%").limit(1).execute()
                    if res.data:
                        barber_id = res.data[0]["id"]
                        barber_name = res.data[0]["name"]
                        barber_timing = res.data[0].get("timing", "")
                except Exception as e:
                    pass

                t_start, t_end = parse_barber_timing(barber_timing) if barber_timing else (None, None)
                in_range = True
                if t_start and t_end:
                    user_t = user_time.replace(year=t_start.year, month=t_start.month, day=t_start.day)
                    in_range = t_start <= user_t <= t_end

                if not in_range:
                    reply = show_direct_reply(
                        f"❌ {barber_name} sirf **{barber_timing}** tak available hai. "
                        f"Is range ke andar time dein:"
                    )
                else:
                    chosen_services = [s.strip() for s in data.get("service", "").split(",") if s.strip()]
                    user_duration = 30
                    if not services_df.empty and chosen_services:
                        matched = services_df[
                            (services_df["service_name"].isin(chosen_services)) &
                            (services_df["barber_id"] == barber_id)
                        ]
                        if not matched.empty and "duration_minutes" in matched.columns:
                            user_duration = int(matched["duration_minutes"].sum())

                    user_start = user_time.hour * 60 + user_time.minute
                    user_end = user_start + user_duration

                    already_booked = False
                    booked_slots = []
                    try:
                        existing = supabase.table("bookings").select("booking_time, service_name").eq("barber_id", barber_id).eq("booking_date", data["date"]).execute()
                        if existing.data:
                            for b in existing.data:
                                bt = parse_time(b["booking_time"])
                                if bt:
                                    b_start = bt.hour * 60 + bt.minute
                                    b_duration = 30
                                    b_svcs = [s.strip() for s in (b.get("service_name") or "").split(",") if s.strip()]
                                    if not services_df.empty and b_svcs:
                                        bm = services_df[
                                            (services_df["service_name"].isin(b_svcs)) &
                                            (services_df["barber_id"] == barber_id)
                                        ]
                                        if bm.empty:
                                            bm = services_df[services_df["service_name"].isin(b_svcs)]
                                        if not bm.empty and "duration_minutes" in bm.columns:
                                            b_duration = int(bm["duration_minutes"].sum())
                                    elif not b_svcs:
                                        b_duration = 60
                                    b_end = b_start + b_duration
                                    booked_slots.append((b_start, b_end))
                                    if user_start < b_end and user_end > b_start:
                                        already_booked = True
                    except Exception as e:
                        pass

                    if already_booked:
                        next_slot_min = user_start
                        max_iter = 48
                        iterations = 0
                        while iterations < max_iter:
                            slot_end = next_slot_min + user_duration
                            conflict = any(next_slot_min < be and slot_end > bs for bs, be in booked_slots)
                            if not conflict:
                                break
                            next_slot_min = min(be for bs, be in booked_slots if next_slot_min < be and slot_end > bs)
                            iterations += 1
                        next_h = next_slot_min // 60
                        next_m = next_slot_min % 60
                        next_time_str = f"{next_h % 12 or 12}:{next_m:02d} {'AM' if next_h < 12 else 'PM'}"
                        reply = show_direct_reply(
                            f"❌ Yeh slot ({prompt}) already book hai!\n"
                            f"💡 Agla available slot: **{next_time_str}** ({user_duration} min ke liye).\n"
                            f"Koi aur time likhiye:"
                        )
                    else:
                        data["time"] = user_time.strftime("%I:%M %p")
                        save_data = {
                            "customer_name": data["name"],
                            "customer_phone": data["phone"],
                            "barber_id": barber_id,
                            "booking_date": data["date"],
                            "booking_time": data["time"],
                            "service_name": data.get("service", "")
                        }
                        try:
                            response = supabase.table("bookings").insert(save_data).execute()
                            if response.data:
                                row_id = response.data[0]["id"]
                                reply = show_direct_reply(f"""✅ **Booking Confirm Ho Gayi!**

👤 Naam: {data['name']}
📞 Phone: {data['phone']}
✂️ Service: {data.get('service', 'N/A')}
💈 Barber: {barber_name}
📅 Date: {data['date']}
⏰ Time: {data['time']}
🆔 Booking ID: `{row_id}`

Database mein save ho chuki hai! Shukriya 🙏""")
                                st.success(f"✅ Booking saved! ID: {row_id}")
                            else:
                                reply = show_direct_reply("❌ Booking save nahi hui. Dobara try karo.")
                        except Exception as e:
                            reply = show_direct_reply(f"❌ Booking save nahi hui.\nError: `{str(e)}`")

                        st.session_state.booking_step = 0
                        st.session_state.booking_data = {}
                        st.session_state.booking_asked = False

    # ============ NORMAL FLOW ============
    else:
        # ---- YES check: booking_asked flag se track karo ----
        if is_yes_response(lower_prompt) and st.session_state.booking_asked:
            st.session_state.booking_step = 1
            st.session_state.booking_data = {}
            st.session_state.booking_asked = False
            reply = show_direct_reply("👍 Theek hai! Pehle apna **naam** bataiye:")

        # ---- Booking words detect karo ----
        elif any(word in lower_prompt for word in BOOKING_WORDS):
            st.session_state.booking_asked = True
            booking_hint = {
                "role": "system",
                "content": "User booking karna chahta hai. SIRF yeh likho: 'Booking karwni hai? (Haan/Nahi)' — Kuch aur mat likho."
            }
            temp_messages = [st.session_state.messages[0]] + [booking_hint] + st.session_state.messages[1:-1] + [st.session_state.messages[-1]]
            reply = get_ai_reply(temp_messages)

        # ---- Schedule/availability check ----
        else:
            found_barber = None
            if not barbers_df.empty:
                for _, row in barbers_df.iterrows():
                    if row['name'].lower() in lower_prompt:
                        found_barber = row['name']
                        break

            info_patterns = ["off", "timing", "phone", "number", "charge", "kitna", "din", "day",
                             "kab se", "kab tak", "batao", "batana", "kya hai", "kia ha",
                             "service", "karta", "krta"]
            is_info_only = any(w in lower_prompt for w in info_patterns)

            schedule_words = ["free ha", "free hai", "available ha", "available hai",
                              "koi booking", "koi appointment", "koi slot",
                              "schedule ha", "schedule hai", "aaj koi", "abhi koi"]
            is_schedule_query = (found_barber and not is_info_only and
                                 any(w in lower_prompt for w in schedule_words))

            if is_schedule_query:
                from datetime import datetime as dt
                today_str = dt.now().strftime("%d %B %Y")
                bname, timing, bookings = fetch_barber_bookings(found_barber, today_str)
                if bname is None:
                    reply = get_ai_reply(st.session_state.messages)
                elif not bookings:
                    reply = show_direct_reply(
                        f"✅ **{bname}** aaj ({today_str}) bilkul free hai!\n\n"
                        f"⏰ Timing: {timing}\n"
                        f"Abhi koi appointment book nahi hai."
                    )
                else:
                    booked_slots_str = ""
                    for b in bookings:
                        svc = b.get('service_name') or 'N/A'
                        booked_slots_str += f"• {b['booking_time']} — {svc}\n"
                    reply = show_direct_reply(
                        f"📋 **{bname}** ki aaj ({today_str}) ki appointments:\n\n"
                        f"{booked_slots_str}\n"
                        f"⏰ Timing: {timing}\n\n"
                        f"💡 Booking karwni hai? Upar wale slots chhod ke koi aur time choose karein."
                    )
            else:
                # Reset booking_asked agar koi aur baat kar raha hai
                st.session_state.booking_asked = False
                reply = get_ai_reply(st.session_state.messages)

    if reply:
        st.session_state.messages.append({"role": "assistant", "content": reply})
