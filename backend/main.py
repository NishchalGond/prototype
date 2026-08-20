import os
import json
import time
import uuid
import sqlite3
import threading
import io
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, File, UploadFile, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd

app = FastAPI(title="Data Processing Engine & Admin API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "prototype.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAPPING_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "column_mapping.json")

def load_column_mappings() -> Dict[str, Any]:
    paths = [
        MAPPING_FILE_PATH,
        "column_mapping.json",
        os.path.join(os.path.dirname(__file__), "..", "column_mapping.json")
    ]
    for p in paths:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    return {"target_fields": [], "aliases": {}}

COLUMN_MAPPING_DATA = load_column_mappings()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS source_files (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            file_path TEXT DEFAULT '',
            file_size INTEGER NOT NULL,
            detected_format TEXT,
            header_count INTEGER DEFAULT 0,
            mapped_count INTEGER DEFAULT 0,
            total_rows INTEGER DEFAULT 0,
            uploaded_at TEXT NOT NULL
        );
    """)

    # Ensure missing columns exist on existing table
    cursor.execute("PRAGMA table_info(source_files)")
    cols = [r['name'] for r in cursor.fetchall()]
    if 'file_path' not in cols:
        cursor.execute("ALTER TABLE source_files ADD COLUMN file_path TEXT DEFAULT ''")
    if 'total_rows' not in cols:
        cursor.execute("ALTER TABLE source_files ADD COLUMN total_rows INTEGER DEFAULT 0")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processing_jobs (
            id TEXT PRIMARY KEY,
            file_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            status TEXT NOT NULL,
            total_rows INTEGER DEFAULT 0,
            processed_rows INTEGER DEFAULT 0,
            valid_rows INTEGER DEFAULT 0,
            error_rows INTEGER DEFAULT 0,
            duplicate_rows INTEGER DEFAULT 0,
            batch_size INTEGER DEFAULT 1000,
            current_batch INTEGER DEFAULT 0,
            total_batches INTEGER DEFAULT 0,
            started_at TEXT,
            completed_at TEXT,
            error_summary TEXT,
            FOREIGN KEY (file_id) REFERENCES source_files(id)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processing_errors (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            batch_num INTEGER DEFAULT 1,
            row_index INTEGER DEFAULT 0,
            field_name TEXT,
            error_message TEXT NOT NULL,
            raw_data TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES processing_jobs(id)
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            source_file TEXT NOT NULL,
            name TEXT,
            community TEXT,
            sub_community TEXT,
            building_cluster TEXT,
            unit_number TEXT,
            size TEXT,
            plot_reg_no TEXT,
            plot_number TEXT,
            bedroom_type TEXT,
            mobile TEXT,
            email TEXT,
            nationality TEXT,
            developer TEXT,
            project TEXT,
            record_status TEXT NOT NULL,
            processed_timestamp TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES processing_jobs(id)
        );
    """)

    conn.commit()
    conn.close()

init_db()

# --- Format & Column Matching Helpers ---
def detect_file_format(file_bytes: bytes, filename: str) -> str:
    if file_bytes.startswith(b'PK\x03\x04'):
        return 'XLSX'
    elif file_bytes.startswith(b'\xd0\xcf\x11\xe0'):
        return 'XLS/OLE'
    elif b'<html' in file_bytes[:500].lower() or b'<table' in file_bytes[:500].lower():
        return 'HTML_TABLE'
    elif filename.endswith('.csv'):
        return 'CSV'
    return 'EXCEL'

def map_raw_header(raw_col: str) -> Optional[str]:
    clean = str(raw_col).strip().upper()
    aliases = COLUMN_MAPPING_DATA.get("aliases", {})
    for target_field, alias_list in aliases.items():
        for alias in alias_list:
            if str(alias).strip().upper() == clean:
                return target_field
    return None

def read_file_dataframe(file_path: str, detected_format: str) -> pd.DataFrame:
    try:
        if detected_format == 'HTML_TABLE':
            dfs = pd.read_html(file_path)
            return dfs[0] if dfs else pd.DataFrame()
        elif detected_format == 'CSV':
            return pd.read_csv(file_path, low_memory=False)
        else:
            # Excel (.xlsx / .xls) multi-sheet support
            excel_file = pd.ExcelFile(file_path)
            all_dfs = []

            for sheet in excel_file.sheet_names:
                # Skip cover / legend / readme sheets if other data sheets exist
                if len(excel_file.sheet_names) > 1 and any(skip in sheet.lower() for skip in ['readme', 'legend', 'method', 'instruction', 'cover']):
                    continue
                try:
                    df_sheet = pd.read_excel(excel_file, sheet_name=sheet)
                    if not df_sheet.empty:
                        df_sheet['_sheet_name'] = sheet
                        all_dfs.append(df_sheet)
                except Exception as sheet_err:
                    print(f"Error reading sheet {sheet}: {sheet_err}")

            if all_dfs:
                return pd.concat(all_dfs, ignore_index=True, sort=False)
            return pd.read_excel(file_path, sheet_name=0)
    except Exception as e:
        print(f"Error reading dataframe for {file_path}: {e}")
        return pd.DataFrame()

# --- Processing Background Loop ---
def process_real_file_in_background(job_id: str, batch_size: int = 500):
    def runner():
        conn = get_db_connection()
        cursor = conn.cursor()
        now_str = datetime.now().isoformat()

        # Reset progress counters to 0 for background batch run
        cursor.execute("""
            UPDATE processing_jobs
            SET status = 'READING', processed_rows = 0, valid_rows = 0, error_rows = 0, duplicate_rows = 0, current_batch = 0, started_at = ?
            WHERE id = ?
        """, (now_str, job_id))
        conn.commit()

        # Get file details
        cursor.execute("""
            SELECT sf.file_path, sf.detected_format, sf.filename
            FROM source_files sf
            JOIN processing_jobs pj ON pj.file_id = sf.id
            WHERE pj.id = ?
        """, (job_id,))
        row = cursor.fetchone()

        if not row or not os.path.exists(row['file_path']):
            cursor.execute("UPDATE processing_jobs SET status = 'FAILED', message = 'File not found on disk' WHERE id = ?", (job_id,))
            conn.commit()
            conn.close()
            return

        file_path = row['file_path']
        detected_format = row['detected_format']
        filename = row['filename']

        # Read actual full dataset using Pandas
        df = read_file_dataframe(file_path, detected_format)
        total_rows = len(df)

        if total_rows == 0:
            cursor.execute("UPDATE processing_jobs SET status = 'COMPLETED', total_rows = 0, completed_at = ? WHERE id = ?", (datetime.now().isoformat(), job_id))
            conn.commit()
            conn.close()
            return

        # Map DataFrame columns to target schema fields
        mapped_columns = {}
        for col in df.columns:
            target = map_raw_header(str(col))
            if target:
                mapped_columns[col] = target

        # Calculate total batches
        total_batches = (total_rows + batch_size - 1) // batch_size
        cursor.execute("""
            UPDATE processing_jobs
            SET status = 'PROCESSING', total_rows = ?, total_batches = ?, batch_size = ?, processed_rows = 0
            WHERE id = ?
        """, (total_rows, total_batches, batch_size, job_id))
        conn.commit()

        valid_cnt = 0
        error_cnt = 0
        dup_cnt = 0
        seen_keys = set()

        for b in range(total_batches):
            start_idx = b * batch_size
            end_idx = min(start_idx + batch_size, total_rows)
            batch_df = df.iloc[start_idx:end_idx]

            cursor.execute("UPDATE processing_jobs SET current_batch = ?, status = 'PROCESSING' WHERE id = ?", (b + 1, job_id))
            conn.commit()

            for row_num, (orig_idx, row_data) in enumerate(batch_df.iterrows(), start=start_idx + 1):
                # Extract values using mapped columns or row lookup
                row_dict = {str(k): ("" if pd.isna(v) else str(v).strip()) for k, v in row_data.items()}

                # Extract mapped standard fields
                name = ""
                community = ""
                sub_community = ""
                building = ""
                unit = ""
                size = ""
                plot_reg = ""
                plot_num = ""
                bedroom = ""
                mobile = ""
                email = ""
                nationality = ""
                developer = ""
                project = ""

                for orig_col, target_field in mapped_columns.items():
                    val = row_dict.get(str(orig_col), "")
                    if target_field == "Name": name = val
                    elif target_field == "Community": community = val
                    elif target_field == "Sub-Community": sub_community = val
                    elif target_field == "Building/Cluster": building = val
                    elif target_field == "Unit Number": unit = val
                    elif target_field == "Size": size = val
                    elif target_field == "Plot Reg. No": plot_reg = val
                    elif target_field == "Plot Number": plot_num = val
                    elif target_field == "Bedroom": bedroom = val
                    elif target_field in ["Mobile 1", "Mobile 2", "Mobile 3"]:
                        if not mobile and val: mobile = val
                    elif target_field == "Email Address": email = val
                    elif target_field == "Nationality": nationality = val
                    elif target_field == "Developer": developer = val
                    elif target_field == "Project": project = val

                # Fallback heuristics for unmapped headers
                if not name:
                    name = row_dict.get("NAME", row_dict.get("FULL NAME", row_dict.get("OWNER NAME", row_dict.get("CUSTOMER NAME", row_dict.get("BUILDING NAME", row_dict.get("PROJECT", row_dict.get("DEVELOPMENT", "")))))))
                if not mobile:
                    mobile = row_dict.get("MOBILE", row_dict.get("PHONE", row_dict.get("CONTACT", "")))
                if not community:
                    community = row_dict.get("COMMUNITY", row_dict.get("AREA", row_dict.get("LOCATION", "")))
                if not unit:
                    unit = row_dict.get("UNIT NO", row_dict.get("FLAT NO", row_dict.get("FLAT NUMBER", row_dict.get("UNIT NUMBER", ""))))
                if not building:
                    building = row_dict.get("BUILDING NAME", row_dict.get("BUILDING", row_dict.get("CLUSTER", "")))
                if not size:
                    size = row_dict.get("ACTUAL AREA", row_dict.get("GROSS AREA", row_dict.get("SIZE", "")))
                if not project:
                    project = row_dict.get("MASTER PROJECT", row_dict.get("PROJECT", ""))

                # Validation & Duplicate Rules
                is_error = False
                error_msg = ""
                field_in_error = ""

                # Row is valid if it contains ANY primary identifying field
                if not name and not mobile and not unit and not developer and not building and not community and not project:
                    is_error = True
                    field_in_error = "Identifier"
                    error_msg = f"Empty row missing developer, name, building, or location info (Row #{row_num})"

                if is_error:
                    error_cnt += 1
                    cursor.execute("""
                        INSERT INTO processing_errors (id, job_id, batch_num, row_index, field_name, error_message, raw_data, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (str(uuid.uuid4()), job_id, b + 1, row_num, field_in_error, error_msg, json.dumps({k: v for k, v in row_dict.items() if v}), datetime.now().isoformat()))
                else:
                    # Check deduplication key (Name + Mobile or Unit + Building)
                    dedup_key = f"{name.lower()}|{mobile.lower()}" if (name and mobile) else f"{unit.lower()}|{building.lower()}"
                    
                    if dedup_key in seen_keys or (dedup_key != "|" and len(dedup_key) > 3):
                        cursor.execute("SELECT 1 FROM records WHERE name = ? AND mobile = ? LIMIT 1", (name, mobile))
                        if cursor.fetchone() or dedup_key in seen_keys:
                            status = "DUPLICATE"
                            dup_cnt += 1
                        else:
                            status = "VALID"
                            valid_cnt += 1
                            seen_keys.add(dedup_key)
                    else:
                        status = "VALID"
                        valid_cnt += 1
                        if len(dedup_key) > 3:
                            seen_keys.add(dedup_key)

                    rec_id = f"REC-{job_id[-4:]}-{row_num}"
                    cursor.execute("""
                        INSERT INTO records (
                            id, job_id, source_file, name, community, sub_community, building_cluster,
                            unit_number, size, plot_reg_no, plot_number, bedroom_type, mobile, email,
                            nationality, developer, project, record_status, processed_timestamp
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        rec_id, job_id, filename, name, community, sub_community, building,
                        unit, size, plot_reg, plot_num, bedroom, mobile, email,
                        nationality, developer, project, status, datetime.now().isoformat()
                    ))

            # Update batch progress after each batch insert
            processed_so_far = end_idx
            cursor.execute("""
                UPDATE processing_jobs
                SET processed_rows = ?, valid_rows = ?, error_rows = ?, duplicate_rows = ?, status = 'PROCESSING'
                WHERE id = ?
            """, (processed_so_far, valid_cnt, error_cnt, dup_cnt, job_id))
            conn.commit()
            time.sleep(0.1)

        final_status = "COMPLETED_WITH_ERRORS" if error_cnt > 0 else "COMPLETED"
        cursor.execute("""
            UPDATE processing_jobs
            SET status = ?, completed_at = ?
            WHERE id = ?
        """, (final_status, datetime.now().isoformat(), job_id))
        conn.commit()
        conn.close()

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()


# --- API Endpoints ---

@app.get("/api/dashboard/stats")
def get_dashboard_stats():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM records")
    total_records = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM source_files")
    total_files = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM processing_jobs")
    total_jobs = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM records WHERE record_status = 'VALID'")
    valid_records = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM records WHERE record_status = 'DUPLICATE'")
    duplicate_records = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM processing_errors")
    total_errors = cursor.fetchone()[0]

    cursor.execute("""
        SELECT community, COUNT(*) as count 
        FROM records 
        WHERE community IS NOT NULL AND community != ''
        GROUP BY community 
        ORDER BY count DESC 
        LIMIT 6
    """)
    community_distribution = [{"name": row["community"], "count": row["count"]} for row in cursor.fetchall()]

    cursor.execute("""
        SELECT id, filename, status, total_rows, valid_rows, error_rows, duplicate_rows, started_at, completed_at
        FROM processing_jobs
        ORDER BY started_at DESC
        LIMIT 5
    """)
    recent_jobs = [dict(row) for row in cursor.fetchall()]

    conn.close()

    success_rate = round((valid_records / total_records * 100), 1) if total_records > 0 else 100.0

    return {
        "total_records": total_records,
        "total_files": total_files,
        "total_jobs": total_jobs,
        "valid_records": valid_records,
        "duplicate_records": duplicate_records,
        "total_errors": total_errors,
        "success_rate": success_rate,
        "community_distribution": community_distribution,
        "recent_jobs": recent_jobs,
    }


@app.post("/api/files/upload")
def upload_file(file: UploadFile = File(...)):
    file_content = file.file.read()
    file_size = len(file_content)
    filename = file.filename or "uploaded_data.xlsx"

    file_id = "file_" + str(uuid.uuid4())[:8]
    job_id = "job_" + str(uuid.uuid4())[:8]
    now_str = datetime.now().isoformat()

    file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{filename}")
    with open(file_path, "wb") as f:
        f.write(file_content)

    detected_format = detect_file_format(file_content, filename)
    df = read_file_dataframe(file_path, detected_format)

    header_count = len(df.columns)
    mapped_count = 0
    mapped_columns_preview = []

    for col in df.columns:
        col_str = str(col)
        target = map_raw_header(col_str)
        if target:
            mapped_count += 1
            mapped_columns_preview.append({
                "raw_header": col_str,
                "target_field": target,
                "confidence": 100,
                "status": "EXACT_ALIAS_MATCH"
            })
        else:
            mapped_columns_preview.append({
                "raw_header": col_str,
                "target_field": None,
                "confidence": 0,
                "status": "UNMAPPED_EXTRA"
            })

    total_rows = len(df)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO source_files (id, filename, file_path, file_size, detected_format, header_count, mapped_count, total_rows, uploaded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (file_id, filename, file_path, file_size, detected_format, header_count, mapped_count, total_rows, now_str))

    cursor.execute("""
        INSERT INTO processing_jobs (id, file_id, filename, status, total_rows, processed_rows, valid_rows, error_rows, duplicate_rows, batch_size, current_batch, total_batches, started_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (job_id, file_id, filename, "UPLOADED", total_rows, 0, 0, 0, 0, 500, 0, (total_rows + 499) // 500 if total_rows > 0 else 1, now_str))

    conn.commit()
    conn.close()

    return {
        "file_id": file_id,
        "job_id": job_id,
        "filename": filename,
        "file_size": file_size,
        "detected_format": detected_format,
        "header_count": header_count,
        "mapped_count": mapped_count,
        "total_rows": total_rows,
        "mapped_columns_preview": mapped_columns_preview,
        "status": "UPLOADED",
        "message": f"File '{filename}' inspected successfully. Detected {total_rows} rows and {header_count} headers ({mapped_count} mapped)."
    }


@app.post("/api/jobs/{job_id}/start")
def start_job(job_id: str, batch_size: Optional[int] = Query(500)):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, status FROM processing_jobs WHERE id = ?", (job_id,))
    job = cursor.fetchone()

    if not job:
        conn.close()
        raise HTTPException(status_code=404, detail="Job not found")

    process_real_file_in_background(job_id, batch_size=batch_size or 500)
    conn.close()

    return {"job_id": job_id, "status": "READING", "message": "Batch processing engine started reading real Excel rows."}


@app.get("/api/jobs")
def list_jobs():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, file_id, filename, status, total_rows, processed_rows, valid_rows, error_rows, duplicate_rows, batch_size, current_batch, total_batches, started_at, completed_at
        FROM processing_jobs
        ORDER BY started_at DESC
    """)
    jobs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"jobs": jobs}


@app.get("/api/jobs/{job_id}")
def get_job_status(job_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, file_id, filename, status, total_rows, processed_rows, valid_rows, error_rows, duplicate_rows, batch_size, current_batch, total_batches, started_at, completed_at
        FROM processing_jobs
        WHERE id = ?
    """, (job_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    job_data = dict(row)
    total_rows = job_data["total_rows"] or 1
    processed_rows = job_data["processed_rows"] or 0
    job_data["progress_pct"] = min(100.0, round((processed_rows / total_rows) * 100, 1))

    return job_data


@app.get("/api/jobs/{job_id}/errors")
def get_job_errors(job_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, job_id, batch_num, row_index, field_name, error_message, raw_data, created_at
        FROM processing_errors
        WHERE job_id = ?
        ORDER BY batch_num ASC, row_index ASC
    """, (job_id,))
    errors = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"job_id": job_id, "errors": errors}


@app.get("/api/records")
def get_records(
    q: Optional[str] = None,
    community: Optional[str] = None,
    sub_community: Optional[str] = None,
    bedroom_type: Optional[str] = None,
    record_status: Optional[str] = None,
    source_file: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100)
):
    conn = get_db_connection()
    cursor = conn.cursor()

    where_clauses = []
    params = []

    if q:
        where_clauses.append("(name LIKE ? OR community LIKE ? OR building_cluster LIKE ? OR unit_number LIKE ? OR mobile LIKE ? OR plot_number LIKE ?)")
        search_pattern = f"%{q}%"
        params.extend([search_pattern] * 6)

    if community:
        where_clauses.append("community = ?")
        params.append(community)

    if sub_community:
        where_clauses.append("sub_community = ?")
        params.append(sub_community)

    if bedroom_type:
        where_clauses.append("bedroom_type = ?")
        params.append(bedroom_type)

    if record_status:
        where_clauses.append("record_status = ?")
        params.append(record_status)

    if source_file:
        where_clauses.append("source_file = ?")
        params.append(source_file)

    where_str = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    count_sql = f"SELECT COUNT(*) FROM records{where_str}"
    cursor.execute(count_sql, params)
    total_count = cursor.fetchone()[0]

    offset = (page - 1) * limit
    select_sql = f"""
        SELECT id, job_id, source_file, name, community, sub_community, building_cluster, unit_number, size, plot_reg_no, plot_number, bedroom_type, mobile, email, nationality, developer, project, record_status, processed_timestamp
        FROM records{where_str}
        ORDER BY processed_timestamp DESC
        LIMIT ? OFFSET ?
    """
    cursor.execute(select_sql, params + [limit, offset])
    records = [dict(row) for row in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT community FROM records WHERE community IS NOT NULL AND community != '' ORDER BY community")
    communities = [row[0] for row in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT bedroom_type FROM records WHERE bedroom_type IS NOT NULL AND bedroom_type != '' ORDER BY bedroom_type")
    bedroom_types = [row[0] for row in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT source_file FROM records WHERE source_file IS NOT NULL AND source_file != '' ORDER BY source_file")
    source_files = [row[0] for row in cursor.fetchall()]

    conn.close()

    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1

    return {
        "records": records,
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "filter_options": {
            "communities": communities,
            "bedroom_types": bedroom_types,
            "source_files": source_files,
            "statuses": ["VALID", "DUPLICATE", "ERROR"]
        }
    }


@app.get("/api/records/{record_id}")
def get_single_record(record_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM records WHERE id = ?", (record_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Record not found")

    return dict(row)


@app.get("/api/column-mappings")
def get_column_mappings():
    return COLUMN_MAPPING_DATA


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
