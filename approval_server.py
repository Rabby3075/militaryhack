import json
import os
from datetime import datetime

from flask import Flask, render_template_string
from flask import request as flask_request

from data_utils import get_on_duty_drivers, load_requests, update_request_by_id
from email_utils import send_driver_assignment_email

app = Flask(__name__)
TOKEN_FILE = 'data/approval_tokens.json'

# Utility to load/save tokens
def load_tokens():
    if not os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'w') as f:
            json.dump({}, f)
    with open(TOKEN_FILE, 'r') as f:
        return json.load(f)

def save_tokens(tokens):
    with open(TOKEN_FILE, 'w') as f:
        json.dump(tokens, f, indent=2)

@app.route('/approve')
def approve():
    token = flask_request.args.get('token')
    tokens = load_tokens()
    req_info = tokens.get(token)
    if not req_info:
        return render_template_string('<h3>Invalid or expired token.</h3>')
    req_type, req_id = req_info['type'], req_info['id']
    manager_name = req_info.get('manager_name')
    manager_email = req_info.get('manager_email')
    
    def updater(r):
        r['status'] = 'Approved'
        r['close_date'] = None
        r['approved_by'] = {'name': manager_name, 'email': manager_email}
        return r
    
    # Update the request
    update_request_by_id(req_type, req_id, updater)
    
    # Get the updated request to send to drivers
    requests = load_requests(req_type)
    updated_request = None
    for req in requests:
        if req.get('request_id') == req_id:
            updated_request = req
            break
    
    # Notify on-duty drivers
    if updated_request:
        on_duty_drivers = get_on_duty_drivers()
        driver_tokens_updated = False
        for driver in on_duty_drivers:
            try:
                send_driver_assignment_email(updated_request, driver, req_type)
                driver_tokens_updated = True
            except Exception as e:
                print(f"Failed to send email to driver {driver['email']}: {e}")
        # Save the updated request with driver_tokens
        if driver_tokens_updated:
            def save_driver_tokens(r):
                r['driver_tokens'] = updated_request.get('driver_tokens', {})
                return r
            update_request_by_id(req_type, req_id, save_driver_tokens)
    
    # Invalidate token
    tokens.pop(token)
    save_tokens(tokens)
    return render_template_string('<h3>Request {{rid}} approved by {{mgr}}. Drivers have been notified!</h3>', rid=req_id, mgr=manager_name)

@app.route('/reject')
def reject():
    token = flask_request.args.get('token')
    tokens = load_tokens()
    req_info = tokens.get(token)
    if not req_info:
        return render_template_string('<h3>Invalid or expired token.</h3>')
    req_type, req_id = req_info['type'], req_info['id']
    manager_name = req_info.get('manager_name')
    manager_email = req_info.get('manager_email')
    def updater(r):
        r['status'] = 'Rejected'
        r['close_date'] = None
        r['approved_by'] = {'name': manager_name, 'email': manager_email}
        return r
    update_request_by_id(req_type, req_id, updater)
    # Invalidate token
    tokens.pop(token)
    save_tokens(tokens)
    return render_template_string('<h3>Request {{rid}} rejected by {{mgr}}.</h3>', rid=req_id, mgr=manager_name)

@app.route('/accept_delivery')
def accept_delivery():
    token = flask_request.args.get('token')
    if not token:
        return render_template_string('<h3>Invalid token.</h3>')
    
    # Find the request with this token
    found_request = None
    found_type = None
    
    for req_type in ['resource', 'service']:
        requests = load_requests(req_type)
        for req in requests:
            if req.get('status') == 'Approved' and 'driver_tokens' in req:
                for driver_email, driver_token in req['driver_tokens'].items():
                    if driver_token == token:
                        found_request = req
                        found_type = req_type
                        break
                if found_request:
                    break
        if found_request:
            break
    
    if not found_request:
        return render_template_string('<h3>Invalid or expired token.</h3>')
    
    # Check if already assigned
    if found_request.get('assigned_driver'):
        return render_template_string('<h3>This assignment has already been accepted by another driver.</h3>')
    
    # Find the driver who accepted
    accepting_driver = None
    for driver_email, driver_token in found_request['driver_tokens'].items():
        if driver_token == token:
            # Find driver details
            from data_utils import load_drivers
            drivers = load_drivers()
            for driver in drivers:
                if driver['email'] == driver_email:
                    accepting_driver = driver
                    break
            break
    
    if not accepting_driver:
        return render_template_string('<h3>Driver not found.</h3>')
    
    # Assign the driver to the request
    def updater(r):
        r['assigned_driver'] = {
            'name': accepting_driver['name'],
            'email': accepting_driver['email']
        }
        r['assignment_date'] = str(datetime.now())
        return r
    
    update_request_by_id(found_type, found_request['request_id'], updater)
    
    return render_template_string('''
    <h3>Assignment Accepted!</h3>
    <p>You have successfully accepted the delivery assignment for request {{rid}}.</p>
    <p>Please proceed with the delivery according to the provided route and equipment details.</p>
    <p><strong>Request ID:</strong> {{rid}}</p>
    <p><strong>Assigned Driver:</strong> {{driver_name}}</p>
    ''', rid=found_request['request_id'], driver_name=accepting_driver['name'])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)