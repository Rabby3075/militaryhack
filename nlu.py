import re
from typing import Any, Dict

import spacy

# Load spaCy English model
nlp = spacy.load('en_core_web_sm')

RESOURCE_KEYWORDS = ["deliver", "resource", "send", "supply", "equipment", "item", "laptop", "projector", "generator", "radio", "radios", "printer", "vehicle", "truck", "fuel", "medkit"]
SERVICE_KEYWORDS = ["fix", "repair", "maintenance", "service", "inspect", "engineer", "quality"]

RESOURCE_REGEX = re.compile(r"(?:need|request|send|deliver|supply|provide)\s+(\d+)\s+([\w\- ]+)", re.IGNORECASE)
MULTI_ITEM_REGEX = re.compile(r"(\d+)\s+([\w\- ]+)", re.IGNORECASE)
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
MANAGER_REGEX = re.compile(r"manager(?: is|:)?\s*([A-Za-z .'-]+)", re.IGNORECASE)
DEST_REGEX = re.compile(r"to ([A-Za-z0-9 .#-]+)", re.IGNORECASE)
SERVICE_ITEM_REGEX = re.compile(r"(repair|fix|inspect|service|maintain|clean|install|replace|upgrade)\s+([\w\- ]+)", re.IGNORECASE)


def classify_intent(text: str) -> str:
    """Classify intent as 'resource' or 'service' based on keywords."""
    text_lower = text.lower()
    if any(word in text_lower for word in RESOURCE_KEYWORDS):
        return "resource"
    if any(word in text_lower for word in SERVICE_KEYWORDS):
        return "service"
    # Default fallback (could use LLM or zero-shot here)
    return "resource"


def extract_items(text: str):
    """Extract multiple resource items from text."""
    matches = MULTI_ITEM_REGEX.findall(text)
    items = []
    for qty, resource in matches:
        items.append({"resource": resource.strip(), "quantity": int(qty)})
    return items


def extract_service_items(text: str):
    """Extract multiple service items from text."""
    matches = SERVICE_ITEM_REGEX.findall(text)
    services = []
    for action, target in matches:
        services.append({"action": action.strip(), "target": target.strip()})
    return services


def ai_priority_from_text(request_text: str) -> int:
    """AI-based priority extraction using spaCy and rules. Returns 1 for Air, 0 for Road."""
    doc = nlp(request_text.lower())
    # High-priority keywords
    high_priority_keywords = {"urgent", "immediate", "critical", "medical", "medkit", "radio", "radios", "life-saving", "emergency", "satellite"}
    for token in doc:
        if token.text in high_priority_keywords:
            return 1  # Air
    # Also check for explicit urgency in the text
    if any(word in request_text.lower() for word in ["asap", "as soon as possible", "immediately", "priority air"]):
        return 1
    return 0  # Road


def extract_slots(text: str) -> Dict[str, Any]:
    """Extract entities/slots from user text using spaCy NER."""
    doc = nlp(text)
    slots = {
        "items": [],
        "services": [],
        "resource": None,
        "quantity": None,
        "base_location": None,
        "destination": None,
        "manager_name": None,
        "manager_email": None,
        "description": None,
        "location": None,
        "requester": None,
        "date": None,
        "priority": None,  # Add priority slot
    }
    # 1. Regex for multiple items (resource)
    items = extract_items(text)
    if items:
        slots["items"] = items
        slots["resource"] = items[0]["resource"]
        slots["quantity"] = items[0]["quantity"]
    else:
        match = RESOURCE_REGEX.search(text)
        if match:
            slots["quantity"] = int(match.group(1))
            slots["resource"] = match.group(2).strip()
            slots["items"] = [{"resource": slots["resource"], "quantity": slots["quantity"]}]
    # 1b. Regex for multiple service items
    services = extract_service_items(text)
    if services:
        slots["services"] = services
    # 2. Regex for email
    email_match = EMAIL_REGEX.search(text)
    if email_match:
        email = email_match.group(0).strip().rstrip('.,;:')
        slots["manager_email"] = email
    # 3. Regex for manager name
    manager_match = MANAGER_REGEX.search(text)
    if manager_match:
        slots["manager_name"] = manager_match.group(1).strip()
    # 4. Regex for destination
    dest_match = DEST_REGEX.search(text)
    if dest_match:
        slots["destination"] = dest_match.group(1).strip()
    # 5. Regex for base location (look for 'from ...')
    from_match = re.search(r"from ([A-Za-z0-9 .#-]+)", text, re.IGNORECASE)
    if from_match:
        slots["base_location"] = from_match.group(1).strip()
    # 6. spaCy for locations, dates, people
    gpe_locs = []
    for ent in doc.ents:
        if ent.label_ == "PERSON" and not slots["manager_name"]:
            slots["manager_name"] = ent.text
        elif ent.label_ in ["GPE", "LOC", "ORG"]:
            gpe_locs.append(ent.text)
        elif ent.label_ == "DATE":
            slots["date"] = ent.text
        elif ent.label_ == "CARDINAL" and not slots["quantity"]:
            try:
                slots["quantity"] = int(ent.text)
            except Exception:
                pass
    # Assign GPE/LOC/ORG entities to missing location slots
    if len(gpe_locs) == 1:
        # If only one location found, use for all missing location slots
        loc = gpe_locs[0]
        if not slots["base_location"]:
            slots["base_location"] = loc
        if not slots["destination"]:
            slots["destination"] = loc
        if not slots["location"]:
            slots["location"] = loc
    else:
        for loc in gpe_locs:
            if not slots["base_location"]:
                slots["base_location"] = loc
            elif not slots["destination"]:
                slots["destination"] = loc
            elif not slots["location"]:
                slots["location"] = loc
    # If still missing base_location or destination, but location is present, use it
    if slots["location"]:
        if not slots["base_location"]:
            slots["base_location"] = slots["location"]
        if not slots["destination"]:
            slots["destination"] = slots["location"]
    # 7. Handle 'at the same location' for hybrid requests
    if "at the same location" in text.lower():
        # If resource destination is present, use it for service location
        if slots["destination"]:
            slots["location"] = slots["destination"]
    # 8. Fallback: description
    if not slots["description"]:
        slots["description"] = text
    # 9. AI-based priority extraction
    slots["priority"] = ai_priority_from_text(text)
    return slots 