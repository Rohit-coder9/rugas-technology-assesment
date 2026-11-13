import sqlite3
import datetime
import random
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

# ==============================================================================
# 1. APPLICATION & DATABASE CONFIGURATION
# ==============================================================================
app = FastAPI(
    title="QueueFlow Pro - Enterprise Queue Management System",
    description="Full-Stack Queue Management & Analytics API built for Rugas Assignment",
    version="1.0.0"
)

DB_NAME = "queue_management.db"

def get_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_and_seed_db():
    """Initializes database tables and populates realistic seed data if empty."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Users Table (Manager Auth)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT NOT NULL
        )
    """)

    # 2. Queues Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS queues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            prefix TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL
        )
    """)

    # 3. Tokens Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            queue_id INTEGER NOT NULL,
            token_number TEXT NOT NULL,
            person_name TEXT NOT NULL,
            phone TEXT,
            notes TEXT,
            status TEXT NOT NULL, -- WAITING, SERVING, SERVED, CANCELLED
            position INTEGER NOT NULL,
            created_at TIMESTAMP NOT NULL,
            served_at TIMESTAMP,
            cancelled_at TIMESTAMP,
            FOREIGN KEY (queue_id) REFERENCES queues (id)
        )
    """)

    # Check if seed data is needed
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO users (username, password, full_name) VALUES (?, ?, ?)",
            ("admin", "admin123", "Rohit Bhalekar (Queue Manager)")
        )

    cursor.execute("SELECT COUNT(*) FROM queues")
    if cursor.fetchone()[0] == 0:
        now = datetime.datetime.now()
        queues_data = [
            ("General OPD Consultation", "OPD", (now - datetime.timedelta(hours=5)).isoformat()),
            ("Customer Support Desk", "CSD", (now - datetime.timedelta(hours=4)).isoformat()),
            ("VIP Billing & Accounts", "VIP", (now - datetime.timedelta(hours=3)).isoformat()),
        ]
        cursor.executemany("INSERT INTO queues (name, prefix, created_at) VALUES (?, ?, ?)", queues_data)

        # Seed realistic historical & active tokens for rich Analytics Dashboard
        names = [
            "Aarav Sharma", "Priya Patel", "Vikram Singh", "Neha Gupta", "Rohan Deshmukh",
            "Ananya Joshi", "Karan Malhotra", "Sneha Kulkarni", "Rahul Verma", "Pooja Nair",
            "Aditya Rao", "Ishita Mehta", "Siddharth Jain", "Kavya Reddy", "Manish Tiwari",
            "Divya Choudhary", "Nikhil Pawar", "ritika Shinde", "Gaurav Bansal", "Meera Iyer"
        ]

        token_rows = []
        # Past SERVED & CANCELLED tokens across queues for Analytics
        for i in range(1, 16):
            q_id = (i % 3) + 1
            prefix = "OPD" if q_id == 1 else ("CSD" if q_id == 2 else "VIP")
            created_dt = now - datetime.timedelta(minutes=random.randint(45, 240))
            wait_mins = random.randint(6, 28)
            served_dt = created_dt + datetime.timedelta(minutes=wait_mins)
            status = "CANCELLED" if i in [4, 11] else "SERVED"

            token_rows.append((
                q_id,
                f"{prefix}-{100 + i}",
                names[i - 1],
                f"98{random.randint(10000000, 99999999)}",
                "Priority Checkup" if i % 4 == 0 else "Standard Visit",
                status,
                0,
                created_dt.isoformat(),
                served_dt.isoformat() if status == "SERVED" else None,
                served_dt.isoformat() if status == "CANCELLED" else None
            ))

        # Currently SERVING tokens (1 in Queue 1, 1 in Queue 2)
        token_rows.append((
            1, "OPD-116", "Suresh Raina", "9823456712", "Regular Consultation",
            "SERVING", 0, (now - datetime.timedelta(minutes=18)).isoformat(),
            (now - datetime.timedelta(minutes=2)).isoformat(), None
        ))
        token_rows.append((
            2, "CSD-117", "Deepika Padukone", "9765432109", "Account Verification",
            "SERVING", 0, (now - datetime.timedelta(minutes=14)).isoformat(),
            (now - datetime.timedelta(minutes=4)).isoformat(), None
        ))

        # Currently WAITING tokens in Queue 1 (OPD)
        waiting_q1 = [
            ("OPD-118", "Rajesh Khanna", "9811122233", "Follow-up Report", 1, 22),
            ("OPD-119", "Sunita Williams", "9822233344", "General Checkup", 2, 16),
            ("OPD-120", "Amitabh Bachchan", "9833344455", "Prescription Renewal", 3, 11),
            ("OPD-121", "Kriti Sanon", "9844455566", "First Consultation", 4, 5),
        ]
        for t_num, p_name, phone, notes, pos, mins_ago in waiting_q1:
            token_rows.append((
                1, t_num, p_name, phone, notes, "WAITING", pos,
                (now - datetime.timedelta(minutes=mins_ago)).isoformat(), None, None
            ))

        # Currently WAITING tokens in Queue 2 (CSD)
        waiting_q2 = [
            ("CSD-122", "Hardik Pandya", "9911223344", "Refund Inquiry", 1, 15),
            ("CSD-123", "Shraddha Kapoor", "9922334455", "Technical Support", 2, 8),
        ]
        for t_num, p_name, phone, notes, pos, mins_ago in waiting_q2:
            token_rows.append((
                2, t_num, p_name, phone, notes, "WAITING", pos,
                (now - datetime.timedelta(minutes=mins_ago)).isoformat(), None, None
            ))

        cursor.executemany("""
            INSERT INTO tokens (
                queue_id, token_number, person_name, phone, notes,
                status, position, created_at, served_at, cancelled_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, token_rows)

    conn.commit()
    conn.close()

init_and_seed_db()

# ==============================================================================
# 2. PYDANTIC MODELS & AUTH DEPENDENCY
# ==============================================================================
class LoginRequest(BaseModel):
    username: str
    password: str

class QueueCreateRequest(BaseModel):
    name: str
    prefix: Optional[str] = None

class TokenCreateRequest(BaseModel):
    person_name: str
    phone: Optional[str] = ""
    notes: Optional[str] = ""

class MoveTokenRequest(BaseModel):
    direction: str  # "up" or "down"

def verify_manager(x_auth_token: Optional[str] = Header(None)):
    if x_auth_token != "rugas-manager-session-token":
        raise HTTPException(status_code=401, detail="Unauthorized Manager Access")
    return True

# ==============================================================================
# 3. REST API ENDPOINTS (REQUIREMENTS #1 TO #8)
# ==============================================================================

@app.post("/api/login")
def login(req: LoginRequest, db: sqlite3.Connection = Depends(get_db)):
    """Requirement #1: Queue Manager can login."""
    cursor = db.cursor()
    cursor.execute(
        "SELECT id, username, full_name FROM users WHERE username = ? AND password = ?",
        (req.username.strip(), req.password)
    )
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return {
        "token": "rugas-manager-session-token",
        "user": dict(user)
    }

@app.get("/api/queues")
def list_queues(db: sqlite3.Connection = Depends(get_db), _: bool = Depends(verify_manager)):
    """Lists all queues with real-time counts of waiting and serving tokens."""
    cursor = db.cursor()
    cursor.execute("""
        SELECT q.id, q.name, q.prefix, q.created_at,
               SUM(CASE WHEN t.status = 'WAITING' THEN 1 ELSE 0 END) as waiting_count,
               SUM(CASE WHEN t.status = 'SERVING' THEN 1 ELSE 0 END) as serving_count,
               SUM(CASE WHEN t.status = 'SERVED' THEN 1 ELSE 0 END) as served_count
        FROM queues q
        LEFT JOIN tokens t ON q.id = t.queue_id
        GROUP BY q.id
        ORDER BY q.id ASC
    """)
    return [dict(row) for row in cursor.fetchall()]

@app.post("/api/queues")
def create_queue(req: QueueCreateRequest, db: sqlite3.Connection = Depends(get_db), _: bool = Depends(verify_manager)):
    """Requirement #1 & #2: Manager can create Queues with a Name."""
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Queue name cannot be empty")

    prefix = (req.prefix or "".join([w[0] for w in name.split()[:3]])).upper()
    if len(prefix) < 2:
        prefix = name[:3].upper()

    cursor = db.cursor()
    try:
        now_iso = datetime.datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO queues (name, prefix, created_at) VALUES (?, ?, ?)",
            (name, prefix, now_iso)
        )
        db.commit()
        return {"id": cursor.lastrowid, "name": name, "prefix": prefix, "created_at": now_iso}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="A queue with this name already exists")

@app.get("/api/queues/{queue_id}/tokens")
def get_queue_tokens(queue_id: int, db: sqlite3.Connection = Depends(get_db), _: bool = Depends(verify_manager)):
    """Requirement #4: Display the list of people/tokens waiting in the queue."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM queues WHERE id = ?", (queue_id,))
    queue = cursor.fetchone()
    if not queue:
        raise HTTPException(status_code=404, detail="Queue not found")

    # Currently serving token
    cursor.execute("""
        SELECT * FROM tokens
        WHERE queue_id = ? AND status = 'SERVING'
        ORDER BY served_at DESC LIMIT 1
    """, (queue_id,))
    serving = cursor.fetchone()

    # Waiting tokens ordered by position
    cursor.execute("""
        SELECT * FROM tokens
        WHERE queue_id = ? AND status = 'WAITING'
        ORDER BY position ASC
    """, (queue_id,))
    waiting = [dict(r) for r in cursor.fetchall()]

    # Recent history (served / cancelled)
    cursor.execute("""
        SELECT * FROM tokens
        WHERE queue_id = ? AND status IN ('SERVED', 'CANCELLED')
        ORDER BY COALESCE(served_at, cancelled_at) DESC LIMIT 15
    """, (queue_id,))
    history = [dict(r) for r in cursor.fetchall()]

    return {
        "queue": dict(queue),
        "serving": dict(serving) if serving else None,
        "waiting": waiting,
        "history": history
    }

@app.post("/api/queues/{queue_id}/tokens")
def add_token_to_queue(
    queue_id: int,
    req: TokenCreateRequest,
    db: sqlite3.Connection = Depends(get_db),
    _: bool = Depends(verify_manager)
):
    """Requirement #3: Manager can add new persons into the queue & generate a token."""
    person_name = req.person_name.strip()
    if not person_name:
        raise HTTPException(status_code=400, detail="Person name is required")

    cursor = db.cursor()
    cursor.execute("SELECT prefix FROM queues WHERE id = ?", (queue_id,))
    q_row = cursor.fetchone()
    if not q_row:
        raise HTTPException(status_code=404, detail="Queue not found")

    # Generate sequential token number
    cursor.execute("SELECT COUNT(*) FROM tokens")
    total_tokens = cursor.fetchone()[0]
    token_number = f"{q_row['prefix']}-{101 + total_tokens}"

    # Determine next position at the bottom of the waiting queue
    cursor.execute("SELECT COALESCE(MAX(position), 0) FROM tokens WHERE queue_id = ? AND status = 'WAITING'", (queue_id,))
    next_position = cursor.fetchone()[0] + 1

    now_iso = datetime.datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO tokens (queue_id, token_number, person_name, phone, notes, status, position, created_at)
        VALUES (?, ?, ?, ?, ?, 'WAITING', ?, ?)
    """, (queue_id, token_number, person_name, req.phone.strip(), req.notes.strip(), next_position, now_iso))
    db.commit()

    return {
        "id": cursor.lastrowid,
        "token_number": token_number,
        "person_name": person_name,
        "position": next_position,
        "status": "WAITING"
    }

@app.put("/api/tokens/{token_id}/move")
def move_token(
    token_id: int,
    req: MoveTokenRequest,
    db: sqlite3.Connection = Depends(get_db),
    _: bool = Depends(verify_manager)
):
    """Requirement #5: Manager can move tokens up and down in the queue."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM tokens WHERE id = ? AND status = 'WAITING'", (token_id,))
    current_token = cursor.fetchone()
    if not current_token:
        raise HTTPException(status_code=404, detail="Waiting token not found")

    queue_id = current_token["queue_id"]
    curr_pos = current_token["position"]

    if req.direction == "up":
        cursor.execute("""
            SELECT * FROM tokens
            WHERE queue_id = ? AND status = 'WAITING' AND position < ?
            ORDER BY position DESC LIMIT 1
        """, (queue_id, curr_pos))
    elif req.direction == "down":
        cursor.execute("""
            SELECT * FROM tokens
            WHERE queue_id = ? AND status = 'WAITING' AND position > ?
            ORDER BY position ASC LIMIT 1
        """, (queue_id, curr_pos))
    else:
        raise HTTPException(status_code=400, detail="Direction must be 'up' or 'down'")

    adjacent_token = cursor.fetchone()
    if not adjacent_token:
        return {"message": "Token is already at the boundary"}

    # Atomic swap of positions
    adj_pos = adjacent_token["position"]
    cursor.execute("UPDATE tokens SET position = ? WHERE id = ?", (adj_pos, current_token["id"]))
    cursor.execute("UPDATE tokens SET position = ? WHERE id = ?", (curr_pos, adjacent_token["id"]))
    db.commit()

    return {"message": f"Moved token {current_token['token_number']} {req.direction}"}

@app.post("/api/queues/{queue_id}/assign-top")
def assign_top_token(queue_id: int, db: sqlite3.Connection = Depends(get_db), _: bool = Depends(verify_manager)):
    """Requirement #6: Assign the token at the top of the queue for service with a button click."""
    cursor = db.cursor()
    now_iso = datetime.datetime.now().isoformat()

    # Complete any currently SERVING token in this queue first
    cursor.execute("""
        UPDATE tokens SET status = 'SERVED'
        WHERE queue_id = ? AND status = 'SERVING'
    """, (queue_id,))

    # Fetch the top WAITING token (lowest position value)
    cursor.execute("""
        SELECT * FROM tokens
        WHERE queue_id = ? AND status = 'WAITING'
        ORDER BY position ASC LIMIT 1
    """, (queue_id,))
    top_token = cursor.fetchone()

    if not top_token:
        db.commit()
        raise HTTPException(status_code=400, detail="No waiting tokens in this queue to assign")

    # Assign top token to SERVING and record served_at timestamp
    cursor.execute("""
        UPDATE tokens
        SET status = 'SERVING', position = 0, served_at = ?
        WHERE id = ?
    """, (now_iso, top_token["id"]))

    # Normalize remaining waiting positions (1, 2, 3...)
    cursor.execute("""
        SELECT id FROM tokens
        WHERE queue_id = ? AND status = 'WAITING'
        ORDER BY position ASC
    """, (queue_id,))
    remaining = cursor.fetchall()
    for idx, row in enumerate(remaining, start=1):
        cursor.execute("UPDATE tokens SET position = ? WHERE id = ?", (idx, row["id"]))

    db.commit()
    return {"message": f"Token {top_token['token_number']} ({top_token['person_name']}) assigned for service!"}

@app.post("/api/queues/{queue_id}/complete-current")
def complete_current_service(queue_id: int, db: sqlite3.Connection = Depends(get_db), _: bool = Depends(verify_manager)):
    """Marks the currently serving token as completed without calling the next one."""
    cursor = db.cursor()
    cursor.execute("UPDATE tokens SET status = 'SERVED' WHERE queue_id = ? AND status = 'SERVING'", (queue_id,))
    db.commit()
    return {"message": "Current service marked as completed"}

@app.put("/api/tokens/{token_id}/cancel")
def cancel_token(token_id: int, db: sqlite3.Connection = Depends(get_db), _: bool = Depends(verify_manager)):
    """Requirement #7: Manager shall be able to cancel a token from the queue."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM tokens WHERE id = ? AND status = 'WAITING'", (token_id,))
    token = cursor.fetchone()
    if not token:
        raise HTTPException(status_code=404, detail="Waiting token not found")

    now_iso = datetime.datetime.now().isoformat()
    cursor.execute("""
        UPDATE tokens
        SET status = 'CANCELLED', position = 0, cancelled_at = ?
        WHERE id = ?
    """, (now_iso, token_id))

    # Re-normalize positions for remaining waiting tokens
    cursor.execute("""
        SELECT id FROM tokens
        WHERE queue_id = ? AND status = 'WAITING'
        ORDER BY position ASC
    """, (token["queue_id"],))
    for idx, row in enumerate(cursor.fetchall(), start=1):
        cursor.execute("UPDATE tokens SET position = ? WHERE id = ?", (idx, row["id"]))

    db.commit()
    return {"message": f"Token {token['token_number']} has been cancelled"}

@app.get("/api/analytics")
def get_analytics(db: sqlite3.Connection = Depends(get_db), _: bool = Depends(verify_manager)):
    """Requirement #8: Dashboard showing analytics on wait times, queue length trends, etc."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM tokens")
    all_tokens = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT * FROM queues")
    queues = {r["id"]: r["name"] for r in cursor.fetchall()}

    waiting_count = sum(1 for t in all_tokens if t["status"] == "WAITING")
    serving_count = sum(1 for t in all_tokens if t["status"] == "SERVING")
    served_count = sum(1 for t in all_tokens if t["status"] == "SERVED")
    cancelled_count = sum(1 for t in all_tokens if t["status"] == "CANCELLED")
    total_count = len(all_tokens)

    # Calculate Wait Times (in minutes) for tokens that were served/serving
    wait_times = []
    queue_wait_map = {q_id: [] for q_id in queues}

    for t in all_tokens:
        if t["served_at"] and t["created_at"]:
            c_dt = datetime.datetime.fromisoformat(t["created_at"])
            s_dt = datetime.datetime.fromisoformat(t["served_at"])
            diff_mins = max(1.0, round((s_dt - c_dt).total_seconds() / 60.0, 1))
            wait_times.append(diff_mins)
            if t["queue_id"] in queue_wait_map:
                queue_wait_map[t["queue_id"]].append(diff_mins)

    avg_wait_time = round(sum(wait_times) / len(wait_times), 1) if wait_times else 0.0
    cancellation_rate = round((cancelled_count / total_count) * 100, 1) if total_count > 0 else 0.0

    # 1. Per-Queue Breakdown (Wait Time & Queue Lengths)
    queue_metrics = []
    for q_id, q_name in queues.items():
        q_waits = queue_wait_map[q_id]
        q_avg = round(sum(q_waits) / len(q_waits), 1) if q_waits else 0.0
        q_waiting = sum(1 for t in all_tokens if t["queue_id"] == q_id and t["status"] == "WAITING")
        q_served = sum(1 for t in all_tokens if t["queue_id"] == q_id and t["status"] in ("SERVED", "SERVING"))
        queue_metrics.append({
            "queue_name": q_name,
            "avg_wait_mins": q_avg,
            "currently_waiting": q_waiting,
            "total_served": q_served
        })

    # 2. Hourly Queue Length / Token Arrival Trend (Last 6 Hours)
    now = datetime.datetime.now()
    hourly_trend = []
    for i in range(5, -1, -1):
        slot_dt = now - datetime.timedelta(hours=i)
        label = slot_dt.strftime("%I:00 %p")
        count_in_hour = 0
        for t in all_tokens:
            c_dt = datetime.datetime.fromisoformat(t["created_at"])
            if c_dt.hour == slot_dt.hour and c_dt.date() == slot_dt.date():
                count_in_hour += 1
        hourly_trend.append({"hour": label, "tokens_generated": count_in_hour})

    return {
        "kpis": {
            "total_tokens": total_count,
            "currently_waiting": waiting_count,
            "currently_serving": serving_count,
            "total_served": served_count,
            "cancelled_count": cancelled_count,
            "avg_wait_time_mins": avg_wait_time,
            "cancellation_rate_pct": cancellation_rate
        },
        "queue_metrics": queue_metrics,
        "hourly_trend": hourly_trend
    }

# ==============================================================================
# 4. FRONTEND SINGLE-PAGE APPLICATION (REACT 18 + TAILWIND + CHART.JS)
# ==============================================================================
FRONTEND_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>QueueFlow Pro | Enterprise Queue Management</title>
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- React & ReactDOM -->
    <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <!-- Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <!-- FontAwesome Icons -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        body { font-family: 'Inter', sans-serif; }
        .pulse-border { animation: pulse-ring 2s infinite; }
        @keyframes pulse-ring {
            0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); }
            70% { box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
            100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }
    </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen">
    <div id="root"></div>

    <script type="text/babel">
        const { useState, useEffect, useRef } = React;

        function App() {
            const [authToken, setAuthToken] = useState(localStorage.getItem("qf_token") || null);
            const [managerName, setManagerName] = useState(localStorage.getItem("qf_user") || "Queue Manager");
            const [loginForm, setLoginForm] = useState({ username: "admin", password: "admin123" });
            const [loginError, setLoginError] = useState("");

            const [activeTab, setActiveTab] = useState("workspace"); // "workspace" | "analytics"
            const [queues, setQueues] = useState([]);
            const [selectedQueueId, setSelectedQueueId] = useState(null);
            const [queueData, setQueueData] = useState({ queue: null, serving: null, waiting: [], history: [] });
            const [analytics, setAnalytics] = useState(null);

            // Modals & Forms
            const [newQueueName, setNewQueueName] = useState("");
            const [newQueuePrefix, setNewQueuePrefix] = useState("");
            const [personForm, setPersonForm] = useState({ person_name: "", phone: "", notes: "" });
            const [toast, setToast] = useState(null);
            const [loading, setLoading] = useState(false);

            // Chart Refs
            const waitChartRef = useRef(null);
            const trendChartRef = useRef(null);
            const waitChartInstance = useRef(null);
            const trendChartInstance = useRef(null);

            const showToast = (msg, type = "success") => {
                setToast({ msg, type });
                setTimeout(() => setToast(null), 3200);
            };

            const apiFetch = async (url, options = {}) => {
                const headers = {
                    "Content-Type": "application/json",
                    ...(authToken ? { "X-Auth-Token": authToken } : {})
                };
                const res = await fetch(url, { ...options, headers });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || "Something went wrong");
                return data;
            };

            // 1. Login Handler
            const handleLogin = async (e) => {
                e.preventDefault();
                setLoginError("");
                try {
                    const data = await apiFetch("/api/login", {
                        method: "POST",
                        body: JSON.stringify(loginForm)
                    });
                    localStorage.setItem("qf_token", data.token);
                    localStorage.setItem("qf_user", data.user.full_name);
                    setAuthToken(data.token);
                    setManagerName(data.user.full_name);
                    showToast("Welcome back, Manager!");
                } catch (err) {
                    setLoginError(err.message);
                }
            };

            const handleLogout = () => {
                localStorage.removeItem("qf_token");
                localStorage.removeItem("qf_user");
                setAuthToken(null);
            };

            // 2. Fetch Queues
            const loadQueues = async (keepSelected = true) => {
                try {
                    const data = await apiFetch("/api/queues");
                    setQueues(data);
                    if (data.length > 0 && (!keepSelected || !selectedQueueId)) {
                        setSelectedQueueId(data[0].id);
                    }
                } catch (err) {
                    showToast(err.message, "error");
                }
            };

            // 3. Fetch Selected Queue Tokens
            const loadQueueDetails = async (qId) => {
                if (!qId) return;
                try {
                    const data = await apiFetch(`/api/queues/${qId}/tokens`);
                    setQueueData(data);
                } catch (err) {
                    showToast(err.message, "error");
                }
            };

            // 4. Fetch Analytics
            const loadAnalytics = async () => {
                try {
                    const data = await apiFetch("/api/analytics");
                    setAnalytics(data);
                } catch (err) {
                    showToast(err.message, "error");
                }
            };

            useEffect(() => {
                if (authToken) {
                    loadQueues(false);
                    loadAnalytics();
                }
            }, [authToken]);

            useEffect(() => {
                if (authToken && selectedQueueId) {
                    loadQueueDetails(selectedQueueId);
                }
            }, [selectedQueueId, authToken]);

            // Render Charts when Analytics tab is active
            useEffect(() => {
                if (activeTab === "analytics" && analytics) {
                    if (waitChartInstance.current) waitChartInstance.current.destroy();
                    if (trendChartInstance.current) trendChartInstance.current.destroy();

                    if (waitChartRef.current) {
                        waitChartInstance.current = new Chart(waitChartRef.current, {
                            type: "bar",
                            data: {
                                labels: analytics.queue_metrics.map(q => q.queue_name),
                                datasets: [
                                    {
                                        label: "Avg Wait Time (Mins)",
                                        data: analytics.queue_metrics.map(q => q.avg_wait_mins),
                                        backgroundColor: "rgba(99, 102, 241, 0.8)",
                                        borderColor: "#6366f1",
                                        borderWidth: 1,
                                        borderRadius: 6
                                    },
                                    {
                                        label: "Currently Waiting",
                                        data: analytics.queue_metrics.map(q => q.currently_waiting),
                                        backgroundColor: "rgba(245, 158, 11, 0.8)",
                                        borderColor: "#f59e0b",
                                        borderWidth: 1,
                                        borderRadius: 6
                                    }
                                ]
                            },
                            options: {
                                responsive: true,
                                plugins: { legend: { labels: { color: "#cbd5e1" } } },
                                scales: {
                                    x: { ticks: { color: "#94a3b8" }, grid: { color: "#1e293b" } },
                                    y: { beginAtZero: true, ticks: { color: "#94a3b8" }, grid: { color: "#1e293b" } }
                                }
                            }
                        });
                    }

                    if (trendChartRef.current) {
                        trendChartInstance.current = new Chart(trendChartRef.current, {
                            type: "line",
                            data: {
                                labels: analytics.hourly_trend.map(h => h.hour),
                                datasets: [{
                                    label: "Tokens Generated (Queue Traffic Trend)",
                                    data: analytics.hourly_trend.map(h => h.tokens_generated),
                                    borderColor: "#10b981",
                                    backgroundColor: "rgba(16, 185, 129, 0.15)",
                                    fill: true,
                                    tension: 0.35,
                                    pointRadius: 5,
                                    pointBackgroundColor: "#10b981"
                                }]
                            },
                            options: {
                                responsive: true,
                                plugins: { legend: { labels: { color: "#cbd5e1" } } },
                                scales: {
                                    x: { ticks: { color: "#94a3b8" }, grid: { color: "#1e293b" } },
                                    y: { beginAtZero: true, ticks: { color: "#94a3b8", stepSize: 1 }, grid: { color: "#1e293b" } }
                                }
                            }
                        });
                    }
                }
            }, [activeTab, analytics]);

            // Create New Queue
            const handleCreateQueue = async (e) => {
                e.preventDefault();
                if (!newQueueName.trim()) return;
                try {
                    const created = await apiFetch("/api/queues", {
                        method: "POST",
                        body: JSON.stringify({ name: newQueueName, prefix: newQueuePrefix })
                    });
                    setNewQueueName("");
                    setNewQueuePrefix("");
                    await loadQueues(true);
                    setSelectedQueueId(created.id);
                    loadAnalytics();
                    showToast(`Queue "${created.name}" created!`);
                } catch (err) {
                    showToast(err.message, "error");
                }
            };

            // Add Person / Token
            const handleAddToken = async (e) => {
                e.preventDefault();
                if (!personForm.person_name.trim() || !selectedQueueId) return;
                setLoading(true);
                try {
                    const created = await apiFetch(`/api/queues/${selectedQueueId}/tokens`, {
                        method: "POST",
                        body: JSON.stringify(personForm)
                    });
                    setPersonForm({ person_name: "", phone: "", notes: "" });
                    await loadQueueDetails(selectedQueueId);
                    await loadQueues(true);
                    loadAnalytics();
                    showToast(`Token ${created.token_number} added for ${created.person_name}`);
                } catch (err) {
                    showToast(err.message, "error");
                } finally {
                    setLoading(false);
                }
            };

            // Move Token Up or Down
            const handleMoveToken = async (tokenId, direction) => {
                try {
                    await apiFetch(`/api/tokens/${tokenId}/move`, {
                        method: "PUT",
                        body: JSON.stringify({ direction })
                    });
                    await loadQueueDetails(selectedQueueId);
                    showToast(`Token position moved ${direction}`);
                } catch (err) {
                    showToast(err.message, "error");
                }
            };

            // Assign Top Token for Service
            const handleAssignTop = async () => {
                if (!selectedQueueId) return;
                try {
                    const res = await apiFetch(`/api/queues/${selectedQueueId}/assign-top`, { method: "POST" });
                    await loadQueueDetails(selectedQueueId);
                    await loadQueues(true);
                    loadAnalytics();
                    showToast(res.message);
                } catch (err) {
                    showToast(err.message, "error");
                }
            };

            // Complete Current Serving Token
            const handleCompleteServing = async () => {
                try {
                    await apiFetch(`/api/queues/${selectedQueueId}/complete-current`, { method: "POST" });
                    await loadQueueDetails(selectedQueueId);
                    await loadQueues(true);
                    loadAnalytics();
                    showToast("Current token marked as completed!");
                } catch (err) {
                    showToast(err.message, "error");
                }
            };

            // Cancel Token
            const handleCancelToken = async (tokenId, tokenNum) => {
                try {
                    await apiFetch(`/api/tokens/${tokenId}/cancel`, { method: "PUT" });
                    await loadQueueDetails(selectedQueueId);
                    await loadQueues(true);
                    loadAnalytics();
                    showToast(`Token ${tokenNum} cancelled`, "error");
                } catch (err) {
                    showToast(err.message, "error");
                }
            };

            const getElapsedMins = (isoString) => {
                if (!isoString) return "Just now";
                const diff = Math.max(1, Math.round((new Date() - new Date(isoString)) / 60000));
                return `${diff} min${diff > 1 ? 's' : ''} ago`;
            };

            // ==================================================================
            // LOGIN SCREEN
            // ==================================================================
            if (!authToken) {
                return (
                    <div className="min-h-screen flex items-center justify-center bg-slate-950 px-4">
                        <div className="max-w-md w-full bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-8">
                            <div className="flex items-center gap-3 mb-6">
                                <div className="w-11 h-11 rounded-xl bg-indigo-600 flex items-center justify-center text-white text-xl font-bold shadow-lg shadow-indigo-500/30">
                                    <i className="fa-solid fa-layer-group"></i>
                                </div>
                                <div>
                                    <h1 className="text-xl font-bold text-white tracking-tight">QueueFlow Pro</h1>
                                    <p className="text-xs text-slate-400">Enterprise Queue & Token Management</p>
                                </div>
                            </div>

                            <form onSubmit={handleLogin} className="space-y-4">
                                <div>
                                    <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">Manager Username</label>
                                    <input
                                        type="text"
                                        value={loginForm.username}
                                        onChange={e => setLoginForm({ ...loginForm, username: e.target.value })}
                                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500"
                                        required
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">Password</label>
                                    <input
                                        type="password"
                                        value={loginForm.password}
                                        onChange={e => setLoginForm({ ...loginForm, password: e.target.value })}
                                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500"
                                        required
                                    />
                                </div>
                                {loginError && (
                                    <div className="text-xs text-rose-400 bg-rose-950/50 border border-rose-800 rounded-lg p-2.5">
                                        <i className="fa-solid fa-circle-exclamation mr-1.5"></i>{loginError}
                                    </div>
                                )}
                                <button
                                    type="submit"
                                    className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2.5 rounded-lg transition shadow-lg shadow-indigo-600/25"
                                >
                                    Sign In as Queue Manager
                                </button>
                            </form>

                            <div className="mt-6 pt-5 border-t border-slate-800 text-xs text-slate-400 flex items-center justify-between">
                                <span>Demo Credentials Pre-filled:</span>
                                <span className="font-mono bg-slate-950 px-2.5 py-1 rounded border border-slate-800 text-indigo-400">admin / admin123</span>
                            </div>
                        </div>
                    </div>
                );
            }

            // ==================================================================
            // MAIN AUTHENTICATED DASHBOARD
            // ==================================================================
            return (
                <div className="min-h-screen flex flex-col bg-slate-950">
                    {/* Toast Notification */}
                    {toast && (
                        <div className={`fixed bottom-5 right-5 z-50 px-4 py-3 rounded-xl shadow-2xl border flex items-center gap-2.5 text-sm font-medium transition-all ${
                            toast.type === "error"
                                ? "bg-rose-950 border-rose-700 text-rose-200"
                                : "bg-emerald-950 border-emerald-700 text-emerald-200"
                        }`}>
                            <i className={`fa-solid ${toast.type === "error" ? "fa-circle-xmark text-rose-400" : "fa-circle-check text-emerald-400"}`}></i>
                            <span>{toast.msg}</span>
                        </div>
                    )}

                    {/* Top Navigation Bar */}
                    <header className="bg-slate-900/90 backdrop-blur border-b border-slate-800 px-6 py-3.5 sticky top-0 z-30 flex flex-wrap items-center justify-between gap-4">
                        <div className="flex items-center gap-3">
                            <div className="w-9 h-9 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold shadow-md shadow-indigo-500/20">
                                <i className="fa-solid fa-layer-group"></i>
                            </div>
                            <div>
                                <span className="font-bold text-white text-base tracking-tight">QueueFlow Pro</span>
                                <span className="ml-2 text-[11px] bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 px-2 py-0.5 rounded-full font-medium">Manager Portal</span>
                            </div>
                        </div>

                        {/* Center Switcher: Queue Operations vs Analytics Dashboard */}
                        <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800">
                            <button
                                onClick={() => setActiveTab("workspace")}
                                className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-2 ${
                                    activeTab === "workspace" ? "bg-indigo-600 text-white shadow" : "text-slate-400 hover:text-white"
                                }`}
                            >
                                <i className="fa-solid fa-people-arrows"></i> Queue Operations
                            </button>
                            <button
                                onClick={() => { setActiveTab("analytics"); loadAnalytics(); }}
                                className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-2 ${
                                    activeTab === "analytics" ? "bg-indigo-600 text-white shadow" : "text-slate-400 hover:text-white"
                                }`}
                            >
                                <i className="fa-solid fa-chart-line"></i> Analytics Dashboard
                            </button>
                        </div>

                        <div className="flex items-center gap-4">
                            <div className="text-right hidden sm:block">
                                <div className="text-xs font-semibold text-slate-200">{managerName}</div>
                                <div className="text-[11px] text-emerald-400 flex items-center justify-end gap-1">
                                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block"></span> System Online
                                </div>
                            </div>
                            <button
                                onClick={handleLogout}
                                className="bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium px-3 py-2 rounded-lg border border-slate-700 transition"
                            >
                                <i className="fa-solid fa-right-from-bracket mr-1"></i> Logout
                            </button>
                        </div>
                    </header>

                    {/* ========================================================== */}
                    {/* VIEW 1: QUEUE OPERATIONS WORKSPACE (REQ #1 TO #7)          */}
                    {/* ========================================================== */}
                    {activeTab === "workspace" && (
                        <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-6 p-6 max-w-[1600px] w-full mx-auto">

                            {/* LEFT SIDEBAR: CREATE & SELECT QUEUES (REQ #1 & #2) */}
                            <div className="lg:col-span-3 space-y-6">
                                <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
                                    <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3 flex items-center justify-between">
                                        <span>Active Queues ({queues.length})</span>
                                        <i className="fa-solid fa-list-ol text-indigo-400"></i>
                                    </h2>
                                    <div className="space-y-2">
                                        {queues.map(q => (
                                            <button
                                                key={q.id}
                                                onClick={() => setSelectedQueueId(q.id)}
                                                className={`w-full text-left p-3 rounded-xl border transition flex items-center justify-between ${
                                                    selectedQueueId === q.id
                                                        ? "bg-indigo-600/15 border-indigo-500 text-white"
                                                        : "bg-slate-950/60 border-slate-800/80 text-slate-300 hover:border-slate-700"
                                                }`}
                                            >
                                                <div>
                                                    <div className="font-semibold text-sm">{q.name}</div>
                                                    <div className="text-[11px] text-slate-400 mt-0.5">
                                                        Prefix: <span className="font-mono text-slate-300">{q.prefix}</span> • Served: {q.served_count || 0}
                                                    </div>
                                                </div>
                                                <div className="flex flex-col items-end">
                                                    <span className={`text-xs font-bold px-2.5 py-0.5 rounded-full ${
                                                        q.waiting_count > 0 ? "bg-amber-500/20 text-amber-300 border border-amber-500/30" : "bg-slate-800 text-slate-400"
                                                    }`}>
                                                        {q.waiting_count || 0} waiting
                                                    </span>
                                                </div>
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                {/* Create New Queue Form */}
                                <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
                                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">
                                        <i className="fa-solid fa-plus-circle mr-1.5 text-indigo-400"></i>Create New Queue
                                    </h3>
                                    <form onSubmit={handleCreateQueue} className="space-y-3">
                                        <div>
                                            <label className="block text-xs text-slate-400 mb-1">Queue Name *</label>
                                            <input
                                                type="text"
                                                placeholder="e.g., Pharmacy Counter 2"
                                                value={newQueueName}
                                                onChange={e => setNewQueueName(e.target.value)}
                                                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                                                required
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-xs text-slate-400 mb-1">Token Prefix (Optional)</label>
                                            <input
                                                type="text"
                                                placeholder="e.g., PHM"
                                                maxLength={4}
                                                value={newQueuePrefix}
                                                onChange={e => setNewQueuePrefix(e.target.value)}
                                                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white uppercase focus:outline-none focus:border-indigo-500"
                                            />
                                        </div>
                                        <button
                                            type="submit"
                                            className="w-full bg-slate-800 hover:bg-indigo-600 text-white text-xs font-semibold py-2.5 rounded-lg border border-slate-700 hover:border-indigo-500 transition"
                                        >
                                            + Create Queue
                                        </button>
                                    </form>
                                </div>
                            </div>

                            {/* CENTER & RIGHT AREA: ACTIVE QUEUE MANAGEMENT */}
                            <div className="lg:col-span-9 space-y-6">
                                {/* Top Action Banner: Currently Serving + Assign Top Button (REQ #6) */}
                                <div className="grid grid-cols-1 md:grid-cols-12 gap-4 bg-slate-900 border border-slate-800 rounded-2xl p-5 items-center">
                                    <div className="md:col-span-7 flex items-center gap-4">
                                        <div className={`w-14 h-14 rounded-2xl flex items-center justify-center text-2xl font-bold ${
                                            queueData.serving
                                                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 pulse-border"
                                                : "bg-slate-800 text-slate-500"
                                        }`}>
                                            <i className="fa-solid fa-bell-concierge"></i>
                                        </div>
                                        <div>
                                            <div className="text-xs uppercase tracking-wider font-bold text-slate-400">
                                                {queueData.queue ? queueData.queue.name : "Select a Queue"} — Active Service Counter
                                            </div>
                                            {queueData.serving ? (
                                                <div className="mt-1 flex flex-wrap items-center gap-2.5">
                                                    <span className="text-2xl font-extrabold text-emerald-400 font-mono">
                                                        {queueData.serving.token_number}
                                                    </span>
                                                    <span className="text-base font-semibold text-white">
                                                        {queueData.serving.person_name}
                                                    </span>
                                                    {queueData.serving.notes && (
                                                        <span className="text-xs bg-slate-800 text-slate-300 px-2 py-0.5 rounded">
                                                            {queueData.serving.notes}
                                                        </span>
                                                    )}
                                                </div>
                                            ) : (
                                                <div className="text-sm text-slate-400 mt-1">
                                                    No token is currently assigned to service. Click <b>"Assign Top Token"</b> to call the next person.
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    <div className="md:col-span-5 flex flex-wrap items-center justify-end gap-3">
                                        {queueData.serving && (
                                            <button
                                                onClick={handleCompleteServing}
                                                className="bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold px-3.5 py-3 rounded-xl border border-slate-700 transition"
                                            >
                                                <i className="fa-solid fa-check mr-1.5 text-emerald-400"></i>Complete Current
                                            </button>
                                        )}
                                        <button
                                            onClick={handleAssignTop}
                                            disabled={queueData.waiting.length === 0}
                                            className={`px-5 py-3 rounded-xl font-bold text-sm flex items-center gap-2 shadow-lg transition ${
                                                queueData.waiting.length > 0
                                                    ? "bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/25 cursor-pointer"
                                                    : "bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700"
                                            }`}
                                        >
                                            <i className="fa-solid fa-bullhorn"></i>
                                            Assign Top Token for Service
                                        </button>
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                                    {/* ADD NEW PERSON / TOKEN FORM (REQ #3) */}
                                    <div className="lg:col-span-4 bg-slate-900 border border-slate-800 rounded-2xl p-5 h-fit">
                                        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-4 flex items-center gap-2">
                                            <i className="fa-solid fa-user-plus text-indigo-400"></i>
                                            Add Person to Queue
                                        </h3>
                                        <form onSubmit={handleAddToken} className="space-y-3.5">
                                            <div>
                                                <label className="block text-xs text-slate-300 mb-1">Person Full Name *</label>
                                                <input
                                                    type="text"
                                                    placeholder="Enter visitor / patient name"
                                                    value={personForm.person_name}
                                                    onChange={e => setPersonForm({ ...personForm, person_name: e.target.value })}
                                                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500"
                                                    required
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-xs text-slate-300 mb-1">Phone Number (Optional)</label>
                                                <input
                                                    type="text"
                                                    placeholder="e.g., 9876543210"
                                                    value={personForm.phone}
                                                    onChange={e => setPersonForm({ ...personForm, phone: e.target.value })}
                                                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                                                />
                                            </div>
                                            <div>
                                                <label className="block text-xs text-slate-300 mb-1">Service Note / Purpose</label>
                                                <input
                                                    type="text"
                                                    placeholder="e.g., General Consultation"
                                                    value={personForm.notes}
                                                    onChange={e => setPersonForm({ ...personForm, notes: e.target.value })}
                                                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                                                />
                                            </div>
                                            <button
                                                type="submit"
                                                disabled={loading}
                                                className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-2.5 rounded-xl text-sm shadow-lg shadow-indigo-600/25 transition flex items-center justify-center gap-2"
                                            >
                                                <i className="fa-solid fa-ticket"></i>
                                                {loading ? "Generating Token..." : "Generate & Add Token"}
                                            </button>
                                        </form>
                                    </div>

                                    {/* WAITING TOKENS LIST WITH UP/DOWN & CANCEL (REQ #4, #5, #7) */}
                                    <div className="lg:col-span-8 bg-slate-900 border border-slate-800 rounded-2xl p-5">
                                        <div className="flex items-center justify-between mb-4">
                                            <div>
                                                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                                                    <span>Waiting Queue Lineup</span>
                                                    <span className="bg-indigo-500/20 text-indigo-300 text-xs px-2.5 py-0.5 rounded-full font-semibold">
                                                        {queueData.waiting.length} Waiting
                                                    </span>
                                                </h3>
                                                <p className="text-xs text-slate-400">Use ↑ / ↓ arrows to reorder priority, or assign #1 directly to service.</p>
                                            </div>
                                        </div>

                                        {queueData.waiting.length === 0 ? (
                                            <div className="text-center py-12 border border-dashed border-slate-800 rounded-xl">
                                                <i className="fa-solid fa-mug-hot text-3xl text-slate-600 mb-2"></i>
                                                <div className="text-sm font-medium text-slate-400">No tokens waiting in this queue</div>
                                                <div className="text-xs text-slate-500 mt-1">Add a new person on the left to generate a token.</div>
                                            </div>
                                        ) : (
                                            <div className="space-y-2.5">
                                                {queueData.waiting.map((token, index) => (
                                                    <div
                                                        key={token.id}
                                                        className={`p-3.5 rounded-xl border transition flex flex-wrap sm:flex-nowrap items-center justify-between gap-3 ${
                                                            index === 0
                                                                ? "bg-indigo-950/30 border-indigo-500/50"
                                                                : "bg-slate-950/70 border-slate-800"
                                                        }`}
                                                    >
                                                        <div className="flex items-center gap-3.5">
                                                            <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold ${
                                                                index === 0 ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-400"
                                                            }`}>
                                                                #{index + 1}
                                                            </div>
                                                            <div>
                                                                <div className="flex items-center gap-2">
                                                                    <span className="font-mono font-bold text-sm text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
                                                                        {token.token_number}
                                                                    </span>
                                                                    <span className="font-semibold text-sm text-white">{token.person_name}</span>
                                                                    {index === 0 && (
                                                                        <span className="text-[10px] uppercase tracking-wider font-bold bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded-full">
                                                                            Next in Line
                                                                        </span>
                                                                    )}
                                                                </div>
                                                                <div className="text-xs text-slate-400 mt-1 flex items-center gap-3">
                                                                    <span><i className="fa-regular fa-clock mr-1"></i>Joined {getElapsedMins(token.created_at)}</span>
                                                                    {token.phone && <span><i className="fa-solid fa-phone mr-1"></i>{token.phone}</span>}
                                                                    {token.notes && <span className="text-slate-300">• {token.notes}</span>}
                                                                </div>
                                                            </div>
                                                        </div>

                                                        {/* Action Buttons: Move Up, Move Down, Cancel */}
                                                        <div className="flex items-center gap-1.5 ml-auto">
                                                            <button
                                                                onClick={() => handleMoveToken(token.id, "up")}
                                                                disabled={index === 0}
                                                                title="Move Token Up"
                                                                className={`w-8 h-8 rounded-lg border flex items-center justify-center text-xs transition ${
                                                                    index === 0
                                                                        ? "border-slate-800 text-slate-700 cursor-not-allowed"
                                                                        : "border-slate-700 bg-slate-800 hover:bg-indigo-600 hover:border-indigo-500 text-slate-200"
                                                                }`}
                                                            >
                                                                <i className="fa-solid fa-arrow-up"></i>
                                                            </button>
                                                            <button
                                                                onClick={() => handleMoveToken(token.id, "down")}
                                                                disabled={index === queueData.waiting.length - 1}
                                                                title="Move Token Down"
                                                                className={`w-8 h-8 rounded-lg border flex items-center justify-center text-xs transition ${
                                                                    index === queueData.waiting.length - 1
                                                                        ? "border-slate-800 text-slate-700 cursor-not-allowed"
                                                                        : "border-slate-700 bg-slate-800 hover:bg-indigo-600 hover:border-indigo-500 text-slate-200"
                                                                }`}
                                                            >
                                                                <i className="fa-solid fa-arrow-down"></i>
                                                            </button>
                                                            <button
                                                                onClick={() => handleCancelToken(token.id, token.token_number)}
                                                                title="Cancel Token"
                                                                className="px-2.5 h-8 rounded-lg border border-rose-800/60 bg-rose-950/40 hover:bg-rose-600 text-rose-300 hover:text-white text-xs font-medium transition flex items-center gap-1 ml-1"
                                                            >
                                                                <i className="fa-solid fa-xmark"></i> Cancel
                                                            </button>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        )}

                                        {/* Recent Activity Log */}
                                        {queueData.history.length > 0 && (
                                            <div className="mt-6 pt-5 border-t border-slate-800">
                                                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">
                                                    Recent Queue Activity (Served & Cancelled)
                                                </h4>
                                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                                    {queueData.history.slice(0, 6).map(item => (
                                                        <div key={item.id} className="bg-slate-950/50 border border-slate-800/80 rounded-lg px-3 py-2 flex items-center justify-between text-xs">
                                                            <div>
                                                                <span className="font-mono font-semibold text-slate-300 mr-2">{item.token_number}</span>
                                                                <span className="text-slate-400">{item.person_name}</span>
                                                            </div>
                                                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                                                                item.status === "SERVED"
                                                                    ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                                                                    : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                                                            }`}>
                                                                {item.status}
                                                            </span>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* ========================================================== */}
                    {/* VIEW 2: ANALYTICS DASHBOARD (REQUIREMENT #8)               */}
                    {/* ========================================================== */}
                    {activeTab === "analytics" && analytics && (
                        <div className="flex-1 p-6 max-w-[1600px] w-full mx-auto space-y-6">
                            {/* Top KPI Summary Cards */}
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                                <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
                                    <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase">
                                        <span>Average Wait Time</span>
                                        <i className="fa-regular fa-clock text-indigo-400 text-base"></i>
                                    </div>
                                    <div className="text-3xl font-extrabold text-white mt-2">
                                        {analytics.kpis.avg_wait_time_mins} <span className="text-sm font-normal text-slate-400">mins</span>
                                    </div>
                                    <div className="text-xs text-emerald-400 mt-1">
                                        Calculated across {analytics.kpis.total_served + analytics.kpis.currently_serving} served tokens
                                    </div>
                                </div>

                                <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
                                    <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase">
                                        <span>Currently Waiting</span>
                                        <i className="fa-solid fa-users-line text-amber-400 text-base"></i>
                                    </div>
                                    <div className="text-3xl font-extrabold text-white mt-2">
                                        {analytics.kpis.currently_waiting} <span className="text-sm font-normal text-slate-400">people</span>
                                    </div>
                                    <div className="text-xs text-slate-400 mt-1">
                                        +{analytics.kpis.currently_serving} actively being served right now
                                    </div>
                                </div>

                                <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
                                    <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase">
                                        <span>Total Tokens Served</span>
                                        <i className="fa-solid fa-circle-check text-emerald-400 text-base"></i>
                                    </div>
                                    <div className="text-3xl font-extrabold text-white mt-2">
                                        {analytics.kpis.total_served}
                                    </div>
                                    <div className="text-xs text-slate-400 mt-1">
                                        Out of {analytics.kpis.total_tokens} total tokens generated
                                    </div>
                                </div>

                                <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
                                    <div className="flex items-center justify-between text-slate-400 text-xs font-semibold uppercase">
                                        <span>Cancellation Rate</span>
                                        <i className="fa-solid fa-ban text-rose-400 text-base"></i>
                                    </div>
                                    <div className="text-3xl font-extrabold text-white mt-2">
                                        {analytics.kpis.cancellation_rate_pct}%
                                    </div>
                                    <div className="text-xs text-slate-400 mt-1">
                                        {analytics.kpis.cancelled_count} tokens cancelled by manager
                                    </div>
                                </div>
                            </div>

                            {/* Charts Grid */}
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
                                    <h3 className="text-sm font-bold text-white mb-1">Wait Time & Active Queue Length by Queue</h3>
                                    <p className="text-xs text-slate-400 mb-4">Compares average service wait time (minutes) and current waiting load per queue.</p>
                                    <canvas ref={waitChartRef} height="130"></canvas>
                                </div>

                                <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
                                    <h3 className="text-sm font-bold text-white mb-1">Hourly Queue Traffic & Token Generation Trend</h3>
                                    <p className="text-xs text-slate-400 mb-4">Tracks peak hours and token inflow over the last 6 hours.</p>
                                    <canvas ref={trendChartRef} height="130"></canvas>
                                </div>
                            </div>

                            {/* Queue Performance Breakdown Table */}
                            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
                                <h3 className="text-sm font-bold text-white mb-3">Queue-Wise Performance Breakdown</h3>
                                <div className="overflow-x-auto">
                                    <table className="w-full text-left border-collapse text-sm">
                                        <thead>
                                            <tr className="border-b border-slate-800 text-xs uppercase text-slate-400">
                                                <th className="py-3 px-4">Queue Name</th>
                                                <th className="py-3 px-4">Currently Waiting</th>
                                                <th className="py-3 px-4">Total Served</th>
                                                <th className="py-3 px-4">Average Wait Time</th>
                                                <th className="py-3 px-4">Efficiency Status</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-800/60">
                                            {analytics.queue_metrics.map((qm, i) => (
                                                <tr key={i} className="hover:bg-slate-950/40">
                                                    <td className="py-3 px-4 font-semibold text-white">{qm.queue_name}</td>
                                                    <td className="py-3 px-4">{qm.currently_waiting} tokens</td>
                                                    <td className="py-3 px-4">{qm.total_served} tokens</td>
                                                    <td className="py-3 px-4 font-mono text-indigo-400">{qm.avg_wait_mins} mins</td>
                                                    <td className="py-3 px-4">
                                                        <span className={`text-xs px-2.5 py-0.5 rounded-full font-semibold ${
                                                            qm.avg_wait_mins <= 15
                                                                ? "bg-emerald-500/15 text-emerald-400"
                                                                : "bg-amber-500/15 text-amber-400"
                                                        }`}>
                                                            {qm.avg_wait_mins <= 15 ? "Optimal Speed" : "Moderate Load"}
                                                        </span>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            );
        }

        const root = ReactDOM.createRoot(document.getElementById("root"));
        root.render(<App />);
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def serve_spa():
    """Serves the Full-Stack React & Tailwind Single-Page Application."""
    return HTMLResponse(content=FRONTEND_HTML)

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🚀 QUEUEFLOW PRO - FULL-STACK SERVER STARTING...")
    print("👉 Open Application UI : http://127.0.0.1:8000")
    print("👉 Interactive API Docs: http://127.0.0.1:8000/docs")
    print("🔑 Manager Credentials : admin / admin123")
    print("=" * 70 + "\n")
    uvicorn.run(app, host="127.0.0.1", port=8000)