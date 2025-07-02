# Military Resource/Service Request Chatbot 🚀

A full-stack, AI-powered workflow automation system for military/defense resource and service requests. Features a modern chat UI, automated email approval, dynamic route visualization, and real-time status tracking—all powered by Python, spaCy, and LLMs.

---

## ✨ Features
- **Streamlit Chatbot UI**: Natural language interface for submitting resource/service requests
- **AI/NLP-Powered Slot Extraction**: Uses spaCy and rules to extract intent, equipment, locations, and urgency from user input
- **Automatic Priority Detection**: AI determines if a request is urgent (Air) or normal (Road) based on context and keywords
- **Dynamic Route Visualization**: Generates and emails optimal supply routes (Air/Road) to drivers, with military-themed maps
- **Email Approval Workflow**: Managers approve/reject requests via secure email links (Flask server)
- **Driver Notification**: Approved requests trigger assignment emails to on-duty drivers, including the optimal route map
- **JSON Data Storage**: Lightweight, file-based database for requests, drivers, and managers
- **Background Scheduling**: Automated reminders and escalations using APScheduler
- **Robust Error Handling**: Handles missing data, email failures, and edge cases gracefully

---

## 🛠️ Setup
1. **Clone the repo and enter the directory:**
   ```
   git clone <repo-url>
   cd military-hackathon
   ```
2. **Create and activate a virtual environment:**
   ```
   python -m venv venv
   venv\Scripts\activate  # On Windows
   # or
   source venv/bin/activate  # On Mac/Linux
   ```
3. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```
4. **Download the spaCy English model:**
   ```
   python -m spacy download en_core_web_sm
   ```
5. **Configure your `.env` file:**
   ```
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your_email@gmail.com
   SMTP_PASSWORD=your_app_password
   APPROVAL_BASE_URL=http://localhost:5000
   ```

---

## 🚦 Running the System
- **Start the chat UI:**
  ```
  streamlit run app.py
  ```
- **Start the approval server:**
  ```
  python approval_server.py
  ```

---

## 🗺️ How It Works
1. **User submits a request** (e.g., "Request 5 radios and 20 batteries from HQ to Outpost Alpha. Manager: Col. Smith, Email: smith@army.mil")
2. **AI extracts details** (items, quantities, locations, urgency) and determines priority (Air/Road)
3. **Request is stored** and managers receive approval emails with secure links
4. **Upon approval**, on-duty drivers are notified by email—including a dynamically generated route map (Air or Road, based on priority)
5. **Users see real-time status updates** in the chat UI

---

## 📦 Project Structure
- `app.py` — Streamlit chat UI and backend logic
- `approval_server.py` — Flask server for approval/rejection links
- `nlu.py` — AI/NLP for intent, slot, and priority extraction
- `data_utils.py` — JSON data utilities
- `email_utils.py` — Email and route map sending
- `generate_route.py` — Supply network and route visualization
- `scheduler.py` — Background jobs (reminders, escalations)
- `route_optimizer.py` — (Optional) Advanced route planning
- `data/` — JSON files for requests, drivers, managers

---

## 📊 Data Files
- `data/resource_requests.json` — Resource requests
- `data/service_requests.json` — Service requests
- `data/drivers.json` — Driver info
- `data/managers.json` — Manager info
- `data/approval_tokens.json` — Approval tokens

---

## 🧠 AI Priority Logic
- **Air Priority:** Triggered by keywords like "urgent", "medical", "radio", "ASAP", etc.
- **Road Priority:** Default for non-urgent items (e.g., batteries, food, tents)
- **Fully automated**—no manual selection needed!

---

## 📣 Example Prompts
- `Request 3 medical kits and 2 radios from HQ to Outpost Bravo. This is urgent and needed ASAP.`
- `Request 10 boxes of batteries and 5 tents from Main Base 2 to Outpost Charlie.`
- `Request 4 laptops, 1 medkit, and 20 bottles of water from HQ to Outpost Delta. Please deliver immediately.`

---

## 🛡️ License
MIT

---

## 👨‍💻 Hackathon Ready!
- Modern, military-themed UI
- AI-powered, end-to-end workflow
- Easy to demo and extend

---

**Built for rapid, reliable, and intelligent military logistics.** 