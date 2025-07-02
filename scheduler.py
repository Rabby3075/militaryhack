from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from data_utils import load_requests, update_request_by_id
from email_utils import send_notification_email

REMINDER_HOURS = 24


def check_stalled_requests():
    now = datetime.now()
    for req_type in ['resource', 'service']:
        requests = load_requests(req_type)
        for req in requests:
            status = req.get('status')
            request_date = req.get('request_date')
            last_update = req.get('last_update_time', request_date)
            if status in ["Pending", "Approved", "In Progress"]:
                # If more than REMINDER_HOURS since last update, send reminder
                if last_update:
                    try:
                        last_dt = datetime.fromisoformat(last_update)
                    except Exception:
                        last_dt = now
                    if (now - last_dt) > timedelta(hours=REMINDER_HOURS):
                        to_email = req.get('manager', {}).get('email')
                        if to_email:
                            send_notification_email(
                                to_email,
                                f"Reminder: Request {req.get('request_id')} is stalled",
                                f"Request {req.get('request_id')} has not been updated in over {REMINDER_HOURS} hours. Please review."
                            )
                            # Update last_update_time to avoid spamming
                            def updater(r):
                                r['last_update_time'] = now.isoformat()
                                return r
                            update_request_by_id(req_type, req.get('request_id'), updater)


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_stalled_requests, 'interval', hours=1)
    scheduler.start()
    return scheduler 