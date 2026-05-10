from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import json
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_FILE = "/data/tickets.json"


def load_tickets():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_tickets(tickets):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(tickets, f, ensure_ascii=False, indent=2)


class TicketRequest(BaseModel):
    subject: str
    block_number: int
    score: int
    total: int
    device_info: str
    fingerprint: str


@app.post("/api/tickets")
async def issue_ticket(ticket_req: TicketRequest, request: Request):
    ip = request.headers.get("x-forwarded-for", request.client.host)
    if "," in ip:
        ip = ip.split(",")[0].strip()

    ticket_id = f"T-{datetime.now().strftime('%Y%m%d%H%M%S')}-{len(load_tickets()) + 1:04d}"

    ticket = {
        "id": ticket_id,
        "subject": ticket_req.subject,
        "block_number": ticket_req.block_number,
        "score": ticket_req.score,
        "total": ticket_req.total,
        "percentage": round(ticket_req.score / ticket_req.total * 100, 1) if ticket_req.total > 0 else 0,
        "device_info": ticket_req.device_info,
        "fingerprint": ticket_req.fingerprint,
        "ip": ip,
        "issued_at": datetime.now().isoformat(),
    }

    tickets = load_tickets()
    tickets.append(ticket)
    save_tickets(tickets)

    return {"status": "ok", "ticket": ticket}


@app.get("/api/tickets")
async def get_tickets(password: str = ""):
    if password != os.environ.get("ADMIN_PASSWORD", "admin2024"):
        return {"error": "unauthorized"}
    return {"tickets": load_tickets()}


@app.get("/api/stats")
async def get_stats(password: str = ""):
    if password != os.environ.get("ADMIN_PASSWORD", "admin2024"):
        return {"error": "unauthorized"}
    tickets = load_tickets()
    unique_ips = set(t["ip"] for t in tickets)
    unique_devices = set(t["fingerprint"] for t in tickets)
    return {
        "total_tickets": len(tickets),
        "unique_ips": len(unique_ips),
        "unique_devices": len(unique_devices),
        "tickets_by_subject": {
            "biochem": len([t for t in tickets if t["subject"] == "biochem"]),
            "physiology": len([t for t in tickets if t["subject"] == "physiology"]),
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
