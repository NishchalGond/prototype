# 🏔️ DataLink Engine — Real Estate Data Normalization & Ingestion Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg?style=for-the-badge&logo=react&logoColor=black)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-5.0-646CFF.svg?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev/)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E.svg?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Design](https://img.shields.io/badge/UI/UX-White%20Neumorphism-2563EB.svg?style=for-the-badge)](https://neumorphism.io/)

A commercial-grade, multi-register real estate data ingestion, normalization, and deduplication engine built with a **FastAPI + Supabase PostgreSQL** backend and a **White & Light Grey Neumorphic Soft 3D React** frontend.

---

## 🌟 Key Features

### 🎨 1. Premium White & Light Grey Neumorphic UI (`#EEF0F4`)
- **Tactile Soft 3D Design**: Crafted with soft dual-shadow neumorphic cards, debossed inset controls (`neumorph-inset`), tactile buttons, and clean dark slate typography (`#1F2937`).
- **Fixed 100vh Layout Architecture**: Page titles, navigation sidebar, search bars, and filter controls remain 100% fixed on screen while dataset tables scroll internally.
- **Custom Neumorphic Dropdown Controls (`CustomSelect.jsx`)**: Replaces standard native browser select popups with floating Neumorphic popover cards (`bg-[#EEF0F4]`, soft shadow `9px 9px 18px #CBD2DC, -9px -9px 18px #FFFFFF`).
- **Record Inspector & Modal Shortcuts**: Click any row to view complete record details. Click outside on the backdrop or press `Escape` to close instantly.

### ⚡ 2. Automated Multi-Register Batch Studio
- **Multi-File Drag & Drop**: Ingest 1 to 20+ Excel (`.xlsx`, `.xls`) or CSV (`.csv`) builder registers simultaneously.
- **Header Remapping Studio**: Inspect raw column headers across files, compare against 23 standard canonical fields, and set custom overrides before execution.
- **Batch Processing Engine**: Processes records in configurable chunk sizes (250, 500, or 1000 rows/batch) with live progress tracking.

### 🧹 3. Smart Data Cleaning & Normalization Engine
- **International Phone Standardizer**: Cleans UAE and global international phone numbers (`+1`, `+44`, `+91`, `+966`, `+971`, `00...`) according to ITU E.164 standards (8 to 15 digits).
- **Unit Area Standardizer**: Converts Square Meters (`sqm`, `sq.m`, `m2`, `m²`) to **Square Feet (sq.ft)** using $1 \text{ sq.m} = 10.7639 \text{ sq.ft}$.
- **Developer Reference Resolver**: Maps varied developer naming variations (e.g., `EMAAR`, `Emaar Properties PJSC`) to standard canonical developer entities.
- **Separate Name & Developer Fields**: Keeps owner/buyer names (`name`) and master builders (`developer`) strictly decoupled.

---

## 🏗️ Architecture Overview

```
                          ┌──────────────────────────────────────────┐
                          │   React 18 + Vite Neumorphic Frontend    │
                          │        (http://localhost:3000)           │
                          └────────────────────┬─────────────────────┘
                                               │
                                       REST API / Async HTTP
                                               │
                          ┌────────────────────▼─────────────────────┐
                          │      FastAPI Python 3.12 Backend         │
                          │        (http://127.0.0.1:8001)           │
                          └──────────┬───────────────────┬───────────┘
                                     │                   │
                        ┌────────────▼─────┐       ┌─────▼──────────────────┐
                        │ Cleaning Engine  │       │ Supabase PostgreSQL DB │
                        │ (Pandas / Regex) │       │   (Production Storage) │
                        └──────────────────┘       └────────────────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technology | Description |
| :--- | :--- | :--- |
| **Frontend Framework** | React 18, Vite 5 | Fast component rendering & hot module replacement |
| **Styling** | Tailwind CSS 3, Custom CSS | Pure Vanilla CSS Neumorphism (`index.css`) |
| **Icons** | Lucide React | Modern crisp icon system |
| **Backend API** | FastAPI, Uvicorn | Async Python 3.12 REST microservice |
| **Database ORM** | SQLModel / SQLAlchemy | Database models and migration management |
| **Cloud Database** | Supabase PostgreSQL | AWS-hosted cloud PostgreSQL cluster |
| **Data Engine** | Pandas, OpenPyXL | High-throughput data transformation engine |

---

## 🚀 Getting Started

### Prerequisites
- **Node.js**: v18.0.0 or higher
- **Python**: v3.12 or higher
- **Git**

---

### 1. Clone the Repository
```bash
git clone https://github.com/NishchalGond/prototype.git
cd prototype
```

---

### 2. Backend Setup
```bash
# Create Python virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# macOS / Linux:
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt

# Configure Environment Variables
# Copy example environment file or create .env in project root:
```

Create `.env` in project root:
```env
DATABASE_URL=postgresql://postgres.lghmffcxtytdacdearuo:Rio%409535266172@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres
ENVIRONMENT=development
```

Run FastAPI Backend:
```bash
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001 --reload
```
API Documentation will be live at `http://127.0.0.1:8001/docs`.

---

### 3. Frontend Setup
```bash
cd frontend

# Install Node dependencies
npm install

# Start Vite Development Server
npm run dev
```
The application interface will open at **`http://localhost:3000/`**.

---

## 🌐 Deploying to Vercel

### Step 1: Import Project to Vercel
1. Log in to [Vercel](https://vercel.com).
2. Click **Add New...** ➔ **Project**.
3. Select your GitHub repository: `NishchalGond/prototype`.

### Step 2: Configure Environment Variables
In the Vercel deployment settings, expand **Environment Variables** and add:
- **`DATABASE_URL`**: `postgresql://postgres.lghmffcxtytdacdearuo:Rio%409535266172@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres`

### Step 3: Deploy
- Click **Deploy**. Vercel will automatically read `vercel.json`, build the Vite frontend, spin up the Python backend serverless function, and issue your live production URL!

---

## 📡 API Endpoint Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/dashboard/stats` | Fetches overall database statistics and community distributions |
| `POST` | `/api/upload/inspect` | Inspects raw file column headers and estimates row counts |
| `POST` | `/api/upload` | Uploads register file to batch engine queue |
| `POST` | `/api/jobs/{id}/start` | Triggers Python processing pipeline for a queued job |
| `GET` | `/api/jobs/{id}` | Polls real-time progress and batch metrics |
| `GET` | `/api/jobs/{id}/errors` | Retrieves row-level error audit logs for a job |
| `GET` | `/api/records` | Paginated search & filtering across normalized records |
| `PUT` | `/api/records/{id}` | Updates normalized record fields directly in Supabase |
| `GET` | `/api/column-mappings` | Returns canonical target fields catalog and alias definitions |

---

## 📁 Repository Structure

```
prototype/
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI API routes (records, jobs, upload)
│   │   ├── database/        # Supabase PostgreSQL session manager
│   │   ├── models/          # SQLModel database schemas
│   │   └── main.py          # FastAPI application entrypoint
│   └── requirements.txt     # Python backend dependencies
├── engine/
│   ├── cleaning.py          # E.164 phone cleaning & sq.m conversion logic
│   ├── detection.py         # Column header detection & matching algorithms
│   ├── processor.py         # Batch execution processor
│   ├── reference.py         # Developer & community lookup catalogs
│   └── validation.py        # Record validation rules engine
├── frontend/
│   ├── src/
│   │   ├── components/      # Neumorphic React components (RecordsExplorer, CustomSelect, etc.)
│   │   ├── App.jsx          # Root application container & fixed layout grid
│   │   └── index.css        # Core Neumorphism utility classes & CSS variables
│   ├── package.json         # Node dependencies
│   └── vite.config.js       # Vite development proxy configuration
├── column_mapping.json      # Canonical target fields & alias definitions
├── .gitignore               # Ignored files (secrets, database, node_modules)
└── README.md                # Platform documentation
```

---

## 🔒 Copyright & License

© 2026 **LPH** & **Nishchal Gond**. All Rights Reserved.

All intellectual property, source code, normalization algorithms, design systems, and software assets contained within this platform are proprietary and strictly owned by **LPH** and **Nishchal Gond**. Unauthorized copying, distribution, reverse engineering, or commercial deployment without explicit written authorization is strictly prohibited.
