 QueueFlow Pro — Full-Stack Queue Management System

A responsive, bug-free Full-Stack Queue Management & Real-Time Analytics application developed for the **Rugas Team** technical evaluation.

Features Implemented
1. **Queue Manager Authentication:** Secure manager portal login (`admin` / `admin123`).
2. **Multi-Queue Management:** Create and switch between multiple named queues with custom token prefixes.
3. **Instant Token Generation:** Add visitors with optional contact/service notes to automatically generate sequential tokens (`OPD-101`, `CSD-102`).
4. **Live Waiting Lineup:** Real-time view of waiting tokens with elapsed wait time indicators.
5. **Priority Reordering (Move Up / Down):** Atomic position swapping allows managers to move tokens up or down with boundary protection.
6. **One-Click Service Assignment:** Assign the top token (`#1`) to active service with a single click.
7. **Token Cancellation:** Cancel waiting tokens while automatically normalizing remaining queue positions.
8. **Analytics Dashboard:** Interactive charts (Chart.js) and KPI cards tracking Average Wait Times, Hourly Traffic Trends, Active Queue Lengths, and Cancellation Rates.

Tech Stack
- **Backend:** Python, FastAPI, SQLite3, Pydantic
- **Frontend:** React 18, Tailwind CSS, Chart.js, FontAwesome
- **Architecture:** Zero-config unified Single-Script Full-Stack deployment with automatic database seeding.

Quick Start (Run in 30 Seconds)

bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the server (auto-creates & seeds SQLite database)
python app.py