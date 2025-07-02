import json
import os
from datetime import datetime
from uuid import uuid4

DATA_DIR = 'data'
RESOURCE_FILE = os.path.join(DATA_DIR, 'resource_requests.json')
SERVICE_FILE = os.path.join(DATA_DIR, 'service_requests.json')
DRIVERS_FILE = os.path.join(DATA_DIR, 'drivers.json')

# Ensure data directory exists
def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

# Load all requests from file
def load_requests(request_type):
    ensure_data_dir()
    file = RESOURCE_FILE if request_type == 'resource' else SERVICE_FILE
    if not os.path.exists(file):
        with open(file, 'w') as f:
            json.dump([], f)
    with open(file, 'r') as f:
        return json.load(f)

# Save all requests to file
def save_requests(request_type, requests):
    ensure_data_dir()
    file = RESOURCE_FILE if request_type == 'resource' else SERVICE_FILE
    with open(file, 'w') as f:
        json.dump(requests, f, indent=2)

# Add a new request
def add_request(request_type, request_data):
    requests = load_requests(request_type)
    requests.append(request_data)
    save_requests(request_type, requests)

# Generate unique request ID
def generate_request_id(request_type):
    prefix = 'R' if request_type == 'resource' else 'S'
    return f"{prefix}-{datetime.now().year}-{str(uuid4())[:8]}"

# Find a request by ID
def find_request_by_id(request_type, request_id):
    requests = load_requests(request_type)
    for req in requests:
        if req.get('request_id') == request_id:
            return req
    return None

# Update a request by ID
def update_request_by_id(request_type, request_id, update_fn):
    requests = load_requests(request_type)
    for i, req in enumerate(requests):
        if req.get('request_id') == request_id:
            requests[i] = update_fn(req)
            save_requests(request_type, requests)
            return True
    return False

def load_managers():
    with open(os.path.join(DATA_DIR, 'managers.json'), 'r') as f:
        return json.load(f)

def load_drivers():
    """Load all drivers from the drivers.json file."""
    ensure_data_dir()
    if not os.path.exists(DRIVERS_FILE):
        with open(DRIVERS_FILE, 'w') as f:
            json.dump([], f)
    with open(DRIVERS_FILE, 'r') as f:
        return json.load(f)

def get_on_duty_drivers(now=None):
    """Return a list of drivers on duty at the current time."""
    if now is None:
        now = datetime.now()
    drivers = load_drivers()
    time_str = now.strftime('%H:%M')
    on_duty = []
    
    for driver in drivers:
        start = driver.get('shift_start', '00:00')
        end = driver.get('shift_end', '23:59')
        
        if start < end:
            # Same day shift
            if start <= time_str < end:
                on_duty.append(driver)
        else:
            # Overnight shift (e.g., 22:00 to 06:00)
            if time_str >= start or time_str < end:
                on_duty.append(driver)
    
    return on_duty

def get_on_duty_managers(now=None):
    """Return a list of managers on duty at the current day/time."""
    if now is None:
        now = datetime.now()
    managers = load_managers()
    day = now.strftime('%a')  # e.g., 'Mon', 'Tue', ...
    time_str = now.strftime('%H:%M')
    on_duty = []
    for m in managers:
        for shift in m.get('shifts', []):
            if shift['day'] == day:
                start = shift['start']
                end = shift['end']
                if start < end:
                    if start <= time_str < end:
                        on_duty.append(m)
                else:  # overnight shift
                    if time_str >= start or time_str < end:
                        on_duty.append(m)
    return on_duty 