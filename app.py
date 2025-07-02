import json
import os
import re
import time
import uuid

import streamlit as st

from data_utils import (add_request, generate_request_id, get_on_duty_managers,
                        load_requests)
from email_utils import send_approval_email
from nlu import classify_intent, extract_slots
from route_optimizer import compute_delivery_route
from scheduler import start_scheduler

# --- THEME SETTINGS ---
st.set_page_config(
    page_title="Military Resource/Service Request Chatbot",
    page_icon="🪖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for military theme
st.markdown(
    """
    <style>
    body, .stApp {
        background-color: #181c16;
        color: #d0e0c0;
        font-family: 'Segoe UI', 'Consolas', 'Courier New', monospace;
    }
    .block-container {
        background-color: #23281e;
        border-radius: 10px;
        padding: 2rem;
    }
    .stButton>button {
        background-color: #556b2f;
        color: #fff;
        border-radius: 5px;
        border: 1px solid #333;
        font-weight: bold;
    }
    .stTextInput>div>div>input {
        background-color: #23281e;
        color: #d0e0c0;
    }
    .stChatMessage {
        background-color: #23281e;
        border-left: 5px solid #556b2f;
        margin-bottom: 1rem;
        border-radius: 5px;
    }
    .stSidebar {
        background-color: #23281e;
    }
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: #b3c686;
        font-family: 'Consolas', 'Courier New', monospace;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --- LOGO/HEADER ---
st.markdown("""
<h1 style='text-align: center; color: #b3c686;'>🪖 Military Resource/Service Request Chatbot</h1>
<hr style='border: 1px solid #556b2f;'>
""", unsafe_allow_html=True)

# Start scheduler in background
start_scheduler()

# --- SLOT EXTRACTION IMPROVEMENT ---
def extract_direct_slots(text, slots):
    # Look for patterns like "field: value"
    for field in slots.keys():
        match = re.search(rf"{field}:\s*([^\n,]+)", text, re.IGNORECASE)
        if match:
            slots[field] = match.group(1).strip()
    return slots

# Chat history in session
if 'history' not in st.session_state:
    st.session_state['history'] = []

# --- SIDEBAR ---
st.sidebar.header("🪖 Request Status Lookup")
lookup_id = st.sidebar.text_input("Enter Request ID")
if st.sidebar.button("Check Status") and lookup_id:
    found = False
    for req_type in ['resource', 'service']:
        reqs = load_requests(req_type)
        for req in reqs:
            if req.get('request_id') == lookup_id:
                st.sidebar.success(f"Status: {req.get('status')}")
                st.sidebar.json(req)
                found = True
                break
    if not found:
        st.sidebar.error("Request ID not found.")

# --- POLLING FOR STATUS UPDATE ---
# Support polling for multiple request IDs (hybrid requests)
if 'last_request_ids' in st.session_state:
    req_ids = st.session_state['last_request_ids']
    if not isinstance(req_ids, list):
        req_ids = [req_ids]
    last_statuses = st.session_state.get('last_known_statuses', {})
    any_pending = False
    for req_id in req_ids:
        found = False
        for req_type in ['resource', 'service']:
            reqs = load_requests(req_type)
            for req in reqs:
                if req.get('request_id') == req_id:
                    found = True
                    current_status = req.get('status')
                    approver = req.get('approved_by', {})
                    approver_name = approver.get('name') if isinstance(approver, dict) and approver else None
                    # Remove 'Bot: typing...' if present and status is not Pending
                    if st.session_state['history'] and st.session_state['history'][-1]['content'] == 'Bot: typing...' and current_status in ['Approved', 'Rejected']:
                        st.session_state['history'].pop()
                    if req_id not in last_statuses or current_status != last_statuses[req_id]:
                        if current_status in ['Approved', 'Rejected']:
                            if approver_name:
                                msg = f"🟢 Your request {req_id} was <b>{current_status}</b> by <b>{approver_name}</b>." if current_status == 'Approved' else f"🔴 Your request {req_id} was <b>{current_status}</b> by <b>{approver_name}</b>."
                            else:
                                msg = f"🟢 Your request {req_id} was <b>{current_status}</b> by the manager." if current_status == 'Approved' else f"🔴 Your request {req_id} was <b>{current_status}</b> by the manager."
                            
                            # Add driver assignment info if approved and assigned
                            if current_status == 'Approved' and req.get('assigned_driver'):
                                driver_info = req['assigned_driver']
                                msg += f"<br>🚚 <b>Assigned Driver:</b> {driver_info['name']} ({driver_info['email']})"
                                # Notify requester that driver is on the way (only once per request)
                                driver_msg = f"{driver_info['name']} received your request and is coming to you."
                                if not any(driver_msg in h['content'] for h in st.session_state['history'] if h['role'] == 'assistant'):
                                    st.session_state['history'].append({'role': 'assistant', 'content': driver_msg})
                            st.session_state['history'].append({'role': 'assistant', 'content': msg})
                        last_statuses[req_id] = current_status
                    # Always check for new driver assignment and notify if not already shown
                    if current_status == 'Approved' and req.get('assigned_driver'):
                        driver_info = req['assigned_driver']
                        driver_msg = f"{driver_info['name']} received your request and is coming to you."
                        if not any(driver_msg in h['content'] for h in st.session_state['history'] if h['role'] == 'assistant'):
                            st.session_state['history'].append({'role': 'assistant', 'content': driver_msg})
                    if current_status == 'Pending' or (current_status == 'Approved' and not req.get('assigned_driver')):
                        any_pending = True
                    break
            if found:
                break
    st.session_state['last_known_statuses'] = last_statuses
    # Poll every 1 second if any are still pending
    if any_pending:
        time.sleep(1)
        st.rerun()

# --- CHAT UI ---
for msg in st.session_state['history']:
    if msg['role'] == 'user':
        st.chat_message('user').markdown(f"<b style='color:#b3c686'>You:</b> {msg['content']}", unsafe_allow_html=True)
    else:
        st.chat_message('assistant').markdown(f"<b style='color:#556b2f'>Bot:</b> {msg['content']}", unsafe_allow_html=True)

user_input = st.chat_input("Type your request (e.g., 'Request 2 radios from HQ to Outpost Alpha. Manager: Col. Smith, Email: smith@army.mil')...")

if user_input:
    # Show user message instantly
    st.session_state['history'].append({'role': 'user', 'content': user_input})
    st.chat_message('user').markdown(f"<b style='color:#b3c686'>You:</b> {user_input}", unsafe_allow_html=True)
    # Show 'Bot: typing...' message
    st.session_state['history'].append({'role': 'assistant', 'content': 'Bot: typing...'})
    st.chat_message('assistant').markdown('Bot: typing...')
    # NLU
    intent = classify_intent(user_input)
    slots = extract_slots(user_input)
    slots = extract_direct_slots(user_input, slots)
    # --- Check for missing info and prompt accordingly ---
    missing = []
    if intent == "resource":
        if not slots.get("items") or len(slots["items"]) == 0:
            missing.append("resource, quantity, destination")
        else:
            if not slots.get("base_location"):
                missing.append("base location")
            if not slots.get("destination"):
                missing.append("destination")
        if missing:
            bot_msg = f"⚠️ I need more info: {', '.join(missing)}. Please provide these (e.g., '5 radios from HQ to Outpost Alpha')."
            st.session_state['history'].append({'role': 'assistant', 'content': bot_msg})
            st.chat_message('assistant').markdown(bot_msg, unsafe_allow_html=True)
            st.stop()
    elif intent == "service":
        if not slots.get("services") or len(slots["services"]) == 0:
            missing.append("service action(s) and target(s)")
        if not slots.get("location"):
            missing.append("location")
        if missing:
            bot_msg = f"⚠️ I need more info: {', '.join(missing)}. Please provide these (e.g., 'repair the generator at Outpost Bravo')."
            st.session_state['history'].append({'role': 'assistant', 'content': bot_msg})
            st.chat_message('assistant').markdown(bot_msg, unsafe_allow_html=True)
            st.stop()
    # Find on-duty managers
    on_duty_managers = get_on_duty_managers()
    if not on_duty_managers:
        bot_msg = "<span style='color:#ffcc00'>⚠️ No manager is currently on duty. Your request will be queued for the next available manager.</span>"
        st.session_state['history'].append({'role': 'assistant', 'content': bot_msg})
        st.chat_message('assistant').markdown(bot_msg, unsafe_allow_html=True)
    manager_list = [{"name": m["name"], "email": m["email"]} for m in on_duty_managers]
    created_ids = []
    # Hybrid: both resource and service in one message
    if slots.get('items') and slots.get('services'):
        # Resource request
        resource_request_id = generate_request_id('resource')
        resource_request = {
            "request_id": resource_request_id,
            "items": slots.get('items', []),
            "base_location": slots['base_location'],
            "destination": slots['destination'],
            "managers": manager_list,
            "approved_by": None,
            "delivery_person": {"name": None, "email": None},
            "delivery_route": [],
            "request_date": str(st.session_state.get('today', '2025-07-01')),
            "close_date": None,
            "status": "Pending",
            "priority": slots.get('priority', 0)
        }
        add_request('resource', resource_request)
        # Service request
        service_request_id = generate_request_id('service')
        service_request = {
            "request_id": service_request_id,
            "services": slots.get('services', []),
            "description": slots['description'],
            "location": slots['location'],
            "requester": slots['requester'],
            "managers": manager_list,
            "approved_by": None,
            "quality_engineer": None,
            "service_engineer": None,
            "request_date": str(st.session_state.get('today', '2025-07-01')),
            "close_date": None,
            "status": "Pending"
        }
        add_request('service', service_request)
        # Send approval emails for both
        tokens_path = 'data/approval_tokens.json'
        if not os.path.exists(tokens_path):
            with open(tokens_path, 'w') as f:
                json.dump({}, f)
        with open(tokens_path, 'r') as f:
            tokens = json.load(f)
        for m in manager_list:
            # Resource
            token_r = str(uuid.uuid4())
            tokens[token_r] = {'type': 'resource', 'id': resource_request_id, 'manager_email': m['email'], 'manager_name': m['name']}
            send_approval_email(resource_request, token_r, 'resource', m['email'])
            # Service
            token_s = str(uuid.uuid4())
            tokens[token_s] = {'type': 'service', 'id': service_request_id, 'manager_email': m['email'], 'manager_name': m['name']}
            send_approval_email(service_request, token_s, 'service', m['email'])
        with open(tokens_path, 'w') as f:
            json.dump(tokens, f, indent=2)
        bot_msg = f"<span style='color:#b3c686'>✅ Your <b>resource</b> request has been created with ID <b>{resource_request_id}</b> and your <b>service</b> request with ID <b>{service_request_id}</b>. Both have been sent for manager approval.</span>"
        st.session_state['history'].append({'role': 'assistant', 'content': bot_msg})
        st.chat_message('assistant').markdown(bot_msg, unsafe_allow_html=True)
        # Store last request for polling (resource by default)
        st.session_state['last_request_ids'] = [resource_request_id, service_request_id]
        st.session_state['last_known_statuses'] = {resource_request_id: "Pending", service_request_id: "Pending"}
        st.session_state['history'].append({'role': 'assistant', 'content': 'Bot: typing...'})
        st.chat_message('assistant').markdown('Bot: typing...')
    else:
        # Only one type present, proceed as before
        if slots.get('items'):
            intent = 'resource'
            request_id = generate_request_id(intent)
            request = {
                "request_id": request_id,
                "items": slots.get('items', []),
                "base_location": slots['base_location'],
                "destination": slots['destination'],
                "managers": manager_list,
                "approved_by": None,
                "delivery_person": {"name": None, "email": None},
                "delivery_route": [],
                "request_date": str(st.session_state.get('today', '2025-07-01')),
                "close_date": None,
                "status": "Pending",
                "priority": slots.get('priority', 0)
            }
        else:
            intent = 'service'
            request_id = generate_request_id(intent)
            request = {
                "request_id": request_id,
                "services": slots.get('services', []),
                "description": slots['description'],
                "location": slots['location'],
                "requester": slots['requester'],
                "managers": manager_list,
                "approved_by": None,
                "quality_engineer": None,
                "service_engineer": None,
                "request_date": str(st.session_state.get('today', '2025-07-01')),
                "close_date": None,
                "status": "Pending"
            }
        add_request(intent, request)
        tokens_path = 'data/approval_tokens.json'
        if not os.path.exists(tokens_path):
            with open(tokens_path, 'w') as f:
                json.dump({}, f)
        with open(tokens_path, 'r') as f:
            tokens = json.load(f)
        for m in manager_list:
            token = str(uuid.uuid4())
            tokens[token] = {'type': intent, 'id': request_id, 'manager_email': m['email'], 'manager_name': m['name']}
            send_approval_email(request, token, intent, m['email'])
        with open(tokens_path, 'w') as f:
            json.dump(tokens, f, indent=2)
        bot_msg = f"<span style='color:#b3c686'>✅ Your <b>{intent}</b> request has been created with ID <b>{request_id}</b> and sent for manager approval.</span>"
        st.session_state['history'].append({'role': 'assistant', 'content': bot_msg})
        st.chat_message('assistant').markdown(bot_msg, unsafe_allow_html=True)
        st.session_state['last_request_ids'] = [request_id]
        st.session_state['last_known_statuses'] = {request_id: "Pending"}
        st.session_state['history'].append({'role': 'assistant', 'content': 'Bot: typing...'})
        st.chat_message('assistant').markdown('Bot: typing...')
