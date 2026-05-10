from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime
import json
import os
import threading

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_FILE = "/data/tickets.json"
_file_lock = threading.Lock()


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

    with _file_lock:
        tickets = load_tickets()
        ticket_id = f"T-{datetime.now().strftime('%Y%m%d%H%M%S')}-{len(tickets) + 1:04d}"

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

        tickets.append(ticket)
        save_tickets(tickets)

    return {"status": "ok", "ticket": ticket}


def _check_auth(authorization: str | None) -> bool:
    if not authorization:
        return False
    expected = os.environ.get("ADMIN_PASSWORD", "admin2024")
    if authorization.startswith("Bearer "):
        return authorization[7:] == expected
    return authorization == expected


@app.get("/api/tickets")
async def get_tickets(authorization: str | None = Header(default=None)):
    if not _check_auth(authorization):
        return JSONResponse(status_code=401, content={"error": "unauthorized"})
    with _file_lock:
        tickets = load_tickets()
    return {"tickets": tickets}


@app.get("/api/stats")
async def get_stats(authorization: str | None = Header(default=None)):
    if not _check_auth(authorization):
        return JSONResponse(status_code=401, content={"error": "unauthorized"})
    with _file_lock:
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
