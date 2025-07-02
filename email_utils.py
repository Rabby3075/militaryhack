import os
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from uuid import uuid4

import matplotlib
import matplotlib.pyplot as plt

matplotlib.use('Agg')  # Use non-interactive backend for server environments

from dotenv import load_dotenv

from generate_route import draw_supply_graph

load_dotenv()

SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
APPROVAL_BASE_URL = os.getenv('APPROVAL_BASE_URL', 'http://localhost:5000')


def send_email(to_email, subject, html_body, plain_body=None):
    msg = MIMEMultipart('alternative')
    msg['From'] = SMTP_USER
    msg['To'] = to_email
    msg['Subject'] = subject
    part1 = MIMEText(plain_body or html_body, 'plain')
    part2 = MIMEText(html_body, 'html')
    msg.attach(part1)
    msg.attach(part2)
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, to_email, msg.as_string())


def send_approval_email(request, token, request_type, to_email):
    subject = f"Approval Needed: {request.get('request_id')}"
    approve_url = f"{APPROVAL_BASE_URL}/approve?token={token}"
    reject_url = f"{APPROVAL_BASE_URL}/reject?token={token}"

    # Get manager name for greeting
    manager_name = None
    for m in request.get('managers', []):
        if m['email'] == to_email:
            manager_name = m['name']
            break
    if not manager_name:
        manager_name = "Manager"

    # Format request details for email
    if request_type == 'resource':
        items = request.get('items')
        if items:
            items_html = ''.join([f'<li><b>Resource:</b> {item['resource']} | <b>Quantity:</b> {item['quantity']}</li>' for item in items])
        else:
            items_html = f'<li><b>Resource:</b> {request.get('resource')} | <b>Quantity:</b> {request.get('quantity')}</li>'
        details = f"""
        <ul>
            {items_html}
            <li><b>Base Location:</b> {request.get('base_location')}</li>
            <li><b>Destination:</b> {request.get('destination')}</li>
            <li><b>Managers on Duty:</b> {', '.join([m['name'] for m in request.get('managers', [])])}</li>
            <li><b>Status:</b> {request.get('status')}</li>
            <li><b>Request Date:</b> {request.get('request_date')}</li>
        </ul>
        """
    else:
        services = request.get('services')
        if services:
            services_html = ''.join([f'<li><b>Action:</b> {s['action']} | <b>Target:</b> {s['target']}</li>' for s in services])
        else:
            services_html = f'<li><b>Description:</b> {request.get('description')} | <b>Location:</b> {request.get('location')} | <b>Requester:</b> {request.get('requester')}</li>'
        details = f"""
        <ul>
            {services_html}
            <li><b>Managers on Duty:</b> {', '.join([m['name'] for m in request.get('managers', [])])}</li>
            <li><b>Status:</b> {request.get('status')}</li>
            <li><b>Request Date:</b> {request.get('request_date')}</li>
        </ul>
        """

    html_body = f"""
    <p>Hi {manager_name},</p>
    <h3>Request Approval Needed</h3>
    <p><b>Request ID:</b> {request.get('request_id')}</p>
    {details}
    <a href='{approve_url}' style='padding:10px 20px;background:green;color:white;text-decoration:none;'>Approve</a>
    <a href='{reject_url}' style='padding:10px 20px;background:red;color:white;text-decoration:none;margin-left:10px;'>Reject</a>
    """
    send_email(to_email, subject, html_body)


def send_notification_email(to_email, subject, message):
    html_body = f"<p>{message}</p>"
    send_email(to_email, subject, html_body)


def send_driver_assignment_email(request, driver, request_type):
    """Send delivery assignment email to driver after manager approval."""
    subject = f"Delivery Assignment: {request.get('request_id')}"
    
    # Generate unique acceptance token
    accept_token = str(uuid4())
    
    # Store the acceptance token in the request for later verification
    if 'driver_tokens' not in request:
        request['driver_tokens'] = {}
    request['driver_tokens'][driver['email']] = accept_token
    
    accept_url = f"{APPROVAL_BASE_URL}/accept_delivery?token={accept_token}"
    
    # Generate shortest path image for resource requests
    route_image_path = None
    if request_type == 'resource':
        try:
            destination = request.get('destination', 'Forward Base Alpha')
            mobile_idx = hash(destination) % 15
            # Use the priority from the request, default to 0 (Road)
            priority = request.get('priority', 0)
            fig = draw_supply_graph(selected_mobile_idx=mobile_idx, priority=priority)
            route_image_path = f"temp_route_{request.get('request_id')}.png"
            fig.savefig(route_image_path, dpi=150, bbox_inches='tight')
            plt.close(fig)
        except Exception as e:
            print(f"Failed to generate route image: {e}")
            route_image_path = None
    
    # Format request details for email
    if request_type == 'resource':
        items = request.get('items')
        if items:
            items_html = ''.join([f'<li><b>Resource:</b> {item["resource"]} | <b>Quantity:</b> {item["quantity"]}</li>' for item in items])
        else:
            items_html = f'<li><b>Resource:</b> {request.get("resource")} | <b>Quantity:</b> {request.get("quantity")}</li>'
        
        route_section = ""
        if route_image_path:
            route_section = f"""
            <h3>Optimal Route</h3>
            <p>Below is the shortest path from main supply bases to your destination:</p>
            <img src="cid:route_image" alt="Supply Route Map" style="max-width:100%; height:auto; border:2px solid #333;">
            <p><small><b>Legend:</b> Yellow node = Destination, White nodes = Main bases, Grey nodes = Mobile units<br>
            <b>Best route:</b> Black dashed line shows optimal path with Air priority</small></p>
            """
        
        details = f"""
        <h3>Delivery Details</h3>
        <ul>
            {items_html}
            <li><b>Base Location:</b> {request.get('base_location')}</li>
            <li><b>Destination:</b> {request.get('destination')}</li>
            <li><b>Request ID:</b> {request.get('request_id')}</li>
            <li><b>Approved by:</b> {request.get('approved_by', 'Manager')}</li>
        </ul>
        {route_section}
        """
    else:
        services = request.get('services')
        if services:
            services_html = ''.join([f'<li><b>Action:</b> {s["action"]} | <b>Target:</b> {s["target"]}</li>' for s in services])
        else:
            services_html = f'<li><b>Description:</b> {request.get("description")} | <b>Location:</b> {request.get("location")}</li>'
        
        details = f"""
        <h3>Service Details</h3>
        <ul>
            {services_html}
            <li><b>Request ID:</b> {request.get('request_id')}</li>
            <li><b>Approved by:</b> {request.get('approved_by', 'Manager')}</li>
        </ul>
        """
    
    html_body = f"""
    <p>Hi {driver['name']},</p>
    <p>A new delivery assignment has been approved and is available for pickup.</p>
    {details}
    <br>
    <p>Click the button below to accept this assignment:</p>
    <a href='{accept_url}' style='padding:15px 30px;background:#007bff;color:white;text-decoration:none;border-radius:5px;font-size:16px;font-weight:bold;'>Accept Assignment</a>
    <br><br>
    <p><small>Note: This assignment can only be accepted by one driver. First come, first served.</small></p>
    """
    
    # Create email with optional image attachment
    msg = MIMEMultipart('alternative')
    msg['From'] = SMTP_USER
    msg['To'] = driver['email']
    msg['Subject'] = subject
    
    # Add text and HTML parts
    part1 = MIMEText(html_body, 'html')
    msg.attach(part1)
    
    # Add image attachment if available
    if route_image_path and os.path.exists(route_image_path):
        try:
            with open(route_image_path, 'rb') as img_file:
                img_data = img_file.read()
                image = MIMEImage(img_data)
                image.add_header('Content-ID', '<route_image>')
                image.add_header('Content-Disposition', 'inline', filename='supply_route.png')
                msg.attach(image)
            
            # Clean up temporary file
            os.remove(route_image_path)
        except Exception as e:
            print(f"Failed to attach route image: {e}")
    
    # Send email
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, driver['email'], msg.as_string()) 