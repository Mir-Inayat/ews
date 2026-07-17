"""FastAPI application for the Enterprise Annual Report Extraction Framework.

Endpoints
---------
- ``POST /extract/full``               — full 9-layer extraction pipeline (taxonomy, tables, validation)
- ``POST /extract``                    — legacy VLM-only financial statement extraction as JSON
- ``POST /extract/excel``              — legacy VLM-only extraction as Excel download
- ``POST /extract/zip``                — legacy VLM-only extraction as ZIP (JSON + Excel)
- ``GET  /``                           — web UI for upload + download
- ``GET  /health``                     — health check

Run::

    uvicorn app:app --reload --port 8080
"""

import asyncio
import io
import json
import logging
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Query, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

import sys as _sys
_graph_root = str(Path(__file__).resolve().parent.parent)
if _graph_root not in _sys.path:
    _sys.path.insert(0, _graph_root)

from sources.annual_report.vlm_extractor import vlm_extract_all
from sources.annual_report.excel_builder import build_excel
from sources.annual_report.extraction_pipeline import run_full_extraction

# Database auto-save
import sys as _sys
_db_root = str(Path(__file__).resolve().parent.parent.parent / "db")
if _db_root not in _sys.path:
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
try:
    from db import get_db
except ImportError:
    get_db = None

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

# ===================================================================
# App setup
# ===================================================================

app = FastAPI(
    title="Annual Report Extraction Framework",
    description=(
        "Enterprise-grade 9-layer extraction pipeline for Indian annual reports. "
        "Extracts all meaningful information, maps to 17-category taxonomy, "
        "detects and reconstructs financial tables with VLM fallback. "
        "Powered by Groq LLM + pdfplumber + SQLite master data layer."
    ),
    version="2.0.0",
)


# ===================================================================
# Helpers
# ===================================================================

async def _save_upload(tmp_dir: Path, upload: UploadFile) -> Path:
    """Persist an uploaded file to tmp_dir and return the path."""
    dest = tmp_dir / (upload.filename or "report.pdf")
    with open(dest, "wb") as f:
        content = await upload.read()
        f.write(content)
    return dest


def _auto_save_to_db(result: dict[str, Any]) -> None:
    """Persist extraction result to the local database if available."""
    if not get_db:
        return
    try:
        db = get_db()
        entry = db.save(result)
        logger.info(
            "Auto-saved to db: company=%s fy=%s id=%s",
            entry.get("company"), entry.get("financial_year"), entry.get("id"),
        )
    except Exception:
        logger.warning("Auto-save to db failed", exc_info=True)


# ===================================================================
# Endpoints
# ===================================================================

@app.post("/extract", summary="Extract all financial statements as JSON")
async def extract_all(
    file: UploadFile = File(...),
    dpi: int = Query(150, description="Image resolution in DPI for VLM"),
) -> JSONResponse:
    """Extract standalone and consolidated statements into structured JSON using the VLM pipeline."""
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp_dir = Path(tmp_str)
        pdf_path = await _save_upload(tmp_dir, file)
        
        # Run extraction in thread pool to avoid blocking async loop
        result = await asyncio.to_thread(
            vlm_extract_all,
            pdf_path=pdf_path,
            dpi=dpi
        )
        
        # Save to DB asynchronously (fire and forget via thread)
        asyncio.create_task(asyncio.to_thread(_auto_save_to_db, result))
        
        return JSONResponse(content=result)


@app.post("/extract/excel", summary="Extract all financial statements as Excel")
async def extract_excel(
    file: UploadFile = File(...),
    dpi: int = Query(150, description="Image resolution in DPI for VLM"),
) -> StreamingResponse:
    """Extract statements and return an Excel file directly."""
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp_dir = Path(tmp_str)
        pdf_path = await _save_upload(tmp_dir, file)
        
        # Run extraction
        result = await asyncio.to_thread(
            vlm_extract_all,
            pdf_path=pdf_path,
            dpi=dpi
        )
        
        # Save to DB
        asyncio.create_task(asyncio.to_thread(_auto_save_to_db, result))
        
        # Build Excel
        excel_bytes = build_excel(result)
        
        # Determine filename
        out_name = f"{pdf_path.stem}_vlm_output.xlsx"
        
        return StreamingResponse(
            io.BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{out_name}"'}
        )


@app.get("/health", summary="Health Check")
async def health() -> dict[str, str]:
    """Check if the API is running."""
    return {
        "status": "ok",
        "engine": "hybrid_framework",
        "version": "2.0.0",
        "layers": "ingestion → sqlite → taxonomy → table_detect → vlm_fallback → validation",
    }


@app.post("/extract/zip", summary="Extract all and return ZIP of JSON and Excel")
async def extract_zip(
    file: UploadFile = File(...),
    dpi: int = Query(150, description="Image resolution in DPI for VLM"),
) -> StreamingResponse:
    """Extract statements and return a ZIP containing both JSON and Excel."""
    import zipfile
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp_dir = Path(tmp_str)
        pdf_path = await _save_upload(tmp_dir, file)
        
        # Run extraction
        result = await asyncio.to_thread(
            vlm_extract_all,
            pdf_path=pdf_path,
            dpi=dpi
        )
        
        # Save to DB
        asyncio.create_task(asyncio.to_thread(_auto_save_to_db, result))
        
        # Build Excel and JSON
        excel_bytes = build_excel(result)
        json_bytes = json.dumps(result, indent=2).encode('utf-8')
        
        # Create ZIP in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{pdf_path.stem}_extracted.json", json_bytes)
            zf.writestr(f"{pdf_path.stem}_extracted.xlsx", excel_bytes)
        
        zip_buffer.seek(0)
        out_name = f"{pdf_path.stem}_extracted.zip"
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{out_name}"'}
        )

@app.post("/extract/full", summary="Full 9-layer extraction pipeline")
async def extract_full(
    file: UploadFile = File(...),
    dpi: int = Query(150, description="Image resolution in DPI for VLM"),
    use_llm_taxonomy: bool = Query(True, description="Use LLM for taxonomy classification"),
) -> StreamingResponse:
    """Run the full enterprise extraction pipeline and return a ZIP containing JSON and Excel.

    This endpoint runs all 9 layers:
      1. PDF Ingestion (pdfplumber)
      2. Master Data Layer (SQLite)
      3. Taxonomy Classification (Hybrid LLM + keyword/regex)
      4. Table Detection
      5/6. Extraction Strategy + VLM Workflow
      7. Financial Statement Engine
      8. Output Schema
      9. Validation

    Returns structured JSON with taxonomy mappings, text extractions,
    table extractions, and a validation/completeness report.
    """
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp_dir = Path(tmp_str)
        pdf_path = await _save_upload(tmp_dir, file)

        # Run the full pipeline in a thread pool
        result = await asyncio.to_thread(
            run_full_extraction,
            pdf_path=pdf_path,
            dpi=dpi,
            use_llm_taxonomy=use_llm_taxonomy,
        )

        # Save to DB asynchronously
        asyncio.create_task(asyncio.to_thread(_auto_save_to_db, result))

        # Build Excel from the result
        excel_bytes = build_excel(result)
        
        import zipfile
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zf:
            zf.writestr(f"{pdf_path.stem}_full_extraction.json", json.dumps(result, indent=2))
            zf.writestr(f"{pdf_path.stem}_full_extraction.xlsx", excel_bytes)
            
        zip_buffer.seek(0)
        out_name = f"{pdf_path.stem}_full_extraction.zip"
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{out_name}"'}
        )


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def web_ui():
    """Premium UI for uploading and extracting annual reports."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>EWS | Annual Report Extraction Framework</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary: #4F46E5;
                --primary-hover: #4338CA;
                --accent: #10B981;
                --bg-dark: #0F172A;
                --glass-bg: rgba(30, 41, 59, 0.7);
                --glass-border: rgba(255, 255, 255, 0.1);
                --text-main: #F8FAFC;
                --text-muted: #94A3B8;
            }
            body {
                margin: 0;
                padding: 0;
                font-family: 'Inter', sans-serif;
                background: linear-gradient(135deg, var(--bg-dark) 0%, #1E1B4B 100%);
                color: var(--text-main);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .container {
                width: 100%;
                max-width: 560px;
                padding: 20px;
            }
            .card {
                background: var(--glass-bg);
                backdrop-filter: blur(12px);
                border: 1px solid var(--glass-border);
                border-radius: 24px;
                padding: 40px;
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
                text-align: center;
                transition: transform 0.3s ease;
            }
            .card:hover {
                transform: translateY(-5px);
            }
            .badge {
                display: inline-block;
                padding: 4px 12px;
                border-radius: 9999px;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.5px;
                margin-bottom: 12px;
                background: rgba(16, 185, 129, 0.15);
                color: var(--accent);
                border: 1px solid rgba(16, 185, 129, 0.3);
            }
            h1 {
                margin: 0 0 10px 0;
                font-size: 28px;
                font-weight: 700;
                background: linear-gradient(to right, #818CF8, #C084FC);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            p {
                margin: 0 0 24px 0;
                color: var(--text-muted);
                font-size: 14px;
                line-height: 1.6;
            }
            .file-upload {
                position: relative;
                border: 2px dashed var(--glass-border);
                border-radius: 16px;
                padding: 40px 20px;
                cursor: pointer;
                transition: all 0.3s ease;
                margin-bottom: 16px;
            }
            .file-upload:hover, .file-upload.dragover {
                border-color: var(--primary);
                background: rgba(79, 70, 229, 0.05);
            }
            .file-upload input {
                position: absolute;
                top: 0; left: 0; width: 100%; height: 100%;
                opacity: 0; cursor: pointer;
            }
            .file-icon {
                font-size: 32px;
                margin-bottom: 10px;
            }
            .file-name {
                font-weight: 500;
                color: var(--primary);
            }
            .mode-toggle {
                display: flex;
                gap: 8px;
                margin-bottom: 16px;
                background: rgba(255,255,255,0.05);
                border-radius: 12px;
                padding: 4px;
            }
            .mode-btn {
                flex: 1;
                padding: 10px;
                border: none;
                border-radius: 10px;
                font-size: 13px;
                font-weight: 600;
                font-family: 'Inter', sans-serif;
                cursor: pointer;
                transition: all 0.2s ease;
                color: var(--text-muted);
                background: transparent;
            }
            .mode-btn.active {
                background: var(--primary);
                color: white;
                box-shadow: 0 2px 8px rgba(79, 70, 229, 0.4);
            }
            .mode-btn:hover:not(.active) {
                color: var(--text-main);
                background: rgba(255,255,255,0.05);
            }
            .btn {
                background: var(--primary);
                color: white;
                border: none;
                padding: 14px 24px;
                border-radius: 12px;
                font-size: 16px;
                font-weight: 600;
                width: 100%;
                cursor: pointer;
                transition: all 0.2s ease;
                box-shadow: 0 4px 6px -1px rgba(79, 70, 229, 0.4);
            }
            .btn:hover {
                background: var(--primary-hover);
                box-shadow: 0 10px 15px -3px rgba(79, 70, 229, 0.5);
                transform: scale(1.02);
            }
            .btn:disabled {
                background: #475569;
                cursor: not-allowed;
                transform: none;
                box-shadow: none;
            }
            .progress-container {
                display: none;
                margin-top: 24px;
                text-align: left;
            }
            .progress-bar {
                width: 100%;
                height: 8px;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                overflow: hidden;
                margin-bottom: 8px;
            }
            .progress-fill {
                height: 100%;
                width: 0%;
                background: linear-gradient(90deg, #818CF8, #C084FC);
                border-radius: 4px;
                transition: width 0.4s ease;
                animation: pulse 2s infinite;
            }
            .status-text {
                font-size: 13px;
                color: var(--text-muted);
                display: flex;
                justify-content: space-between;
            }
            .mode-desc {
                font-size: 12px;
                color: var(--text-muted);
                margin-bottom: 16px;
                min-height: 18px;
                opacity: 0.7;
            }
            @keyframes pulse {
                0% { opacity: 1; }
                50% { opacity: 0.7; }
                100% { opacity: 1; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card">
                <div class="badge">ENTERPRISE FRAMEWORK v2.0</div>
                <h1>Annual Report Extractor</h1>
                <p>Upload an Annual Report PDF to extract all sections into a structured taxonomy, detect financial tables, and reconstruct them using VLM fallback. Powered by a 9-layer hybrid pipeline.</p>

                <form id="uploadForm">
                    <div class="file-upload" id="dropZone">
                        <input type="file" id="pdfFile" accept=".pdf" required onchange="updateFileName(this)">
                        <div class="file-icon">📄</div>
                        <div id="fileLabel">Drag & drop your PDF here or click to browse</div>
                    </div>

                    <div class="mode-toggle">
                        <button type="button" class="mode-btn active" id="modeFullBtn" onclick="setMode('full')">Full Pipeline</button>
                        <button type="button" class="mode-btn" id="modeLegacyBtn" onclick="setMode('legacy')">Financial Tables Only</button>
                    </div>
                    <div class="mode-desc" id="modeDesc">9-layer extraction: Ingestion → SQLite → Taxonomy → Table Detection → VLM → Validation</div>

                    <button type="button" class="btn" id="submitBtn" onclick="startExtraction()">Extract Report</button>

                    <div class="progress-container" id="progressContainer">
                        <div class="progress-bar">
                            <div class="progress-fill" id="progressFill"></div>
                        </div>
                        <div class="status-text">
                            <span id="statusMsg">Initializing Pipeline...</span>
                            <span id="timeElapsed">00:00</span>
                        </div>
                    </div>
                </form>
            </div>
        </div>

        <script>
            let timerInterval;
            let currentMode = 'full';  // 'full' or 'legacy'

            function setMode(mode) {
                currentMode = mode;
                document.getElementById('modeFullBtn').classList.toggle('active', mode === 'full');
                document.getElementById('modeLegacyBtn').classList.toggle('active', mode === 'legacy');
                if (mode === 'full') {
                    document.getElementById('modeDesc').innerText = '9-layer extraction: Ingestion → SQLite → Taxonomy → Table Detection → VLM → Validation';
                    document.getElementById('submitBtn').innerText = 'Extract Report';
                } else {
                    document.getElementById('modeDesc').innerText = 'VLM-only: Extracts Balance Sheet, P&L, Cash Flow as ZIP (JSON + Excel)';
                    document.getElementById('submitBtn').innerText = 'Extract & Download ZIP';
                }
            }

            function updateFileName(input) {
                const label = document.getElementById('fileLabel');
                if (input.files.length > 0) {
                    label.innerHTML = `<span class="file-name">${input.files[0].name}</span>`;
                } else {
                    label.innerHTML = "Drag & drop your PDF here or click to browse";
                }
            }

            function updateTimer(startTime) {
                const elapsed = document.getElementById('timeElapsed');
                const now = new Date();
                const diff = Math.floor((now - startTime) / 1000);
                const m = String(Math.floor(diff / 60)).padStart(2, '0');
                const s = String(diff % 60).padStart(2, '0');
                elapsed.innerText = `${m}:${s}`;
            }

            async function startExtraction() {
                const fileInput = document.getElementById('pdfFile');
                if (!fileInput.files[0]) {
                    alert("Please select a PDF file first.");
                    return;
                }

                const btn = document.getElementById('submitBtn');
                const progContainer = document.getElementById('progressContainer');
                const progFill = document.getElementById('progressFill');
                const statusMsg = document.getElementById('statusMsg');

                btn.disabled = true;
                btn.innerText = "Processing...";
                progContainer.style.display = 'block';

                let progress = 0;
                progFill.style.width = '0%';

                const isFullMode = currentMode === 'full';

                const simInterval = setInterval(() => {
                    if (progress < 85) {
                        progress += Math.random() * 2;
                        progFill.style.width = progress + '%';

                        if (isFullMode) {
                            if (progress < 10) statusMsg.innerText = "Layer 1: Ingesting PDF pages...";
                            else if (progress < 20) statusMsg.innerText = "Layer 2: Building SQLite Master Data...";
                            else if (progress < 35) statusMsg.innerText = "Layer 3: Classifying pages into taxonomy (LLM)...";
                            else if (progress < 45) statusMsg.innerText = "Layer 4: Detecting structured tables...";
                            else if (progress < 70) statusMsg.innerText = "Layer 5-7: Extracting financial tables (VLM)...";
                            else statusMsg.innerText = "Layer 9: Running validation checks...";
                        } else {
                            if (progress < 30) statusMsg.innerText = "Parsing PDF & Running Discovery...";
                            else if (progress < 60) statusMsg.innerText = "Calling VLM on pages (this takes a while)...";
                            else statusMsg.innerText = "Structuring JSON & Building Excel...";
                        }
                    }
                }, 1000);

                const startTime = new Date();
                timerInterval = setInterval(() => updateTimer(startTime), 1000);

                const formData = new FormData();
                formData.append('file', fileInput.files[0]);

                try {
                    let response;
                    if (isFullMode) {
                        response = await fetch('/extract/full', { method: 'POST', body: formData });
                    } else {
                        response = await fetch('/extract/zip', { method: 'POST', body: formData });
                    }
                    if (!response.ok) throw new Error("Extraction failed: " + await response.text());

                    clearInterval(simInterval);
                    progFill.style.width = '100%';
                    statusMsg.innerText = "Done! Processing result...";

                    if (isFullMode || !isFullMode) {
                        // Both modes now return a ZIP file
                        const blob = await response.blob();
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        let filename = isFullMode ? 'full_extraction.zip' : 'extracted_financial_data.zip';
                        const disposition = response.headers.get('content-disposition');
                        if (disposition && disposition.indexOf('filename=') !== -1) {
                            const matches = /filename="([^"]+)"/.exec(disposition);
                            if (matches != null && matches[1]) filename = matches[1];
                        }
                        a.download = filename;
                        document.body.appendChild(a);
                        a.click();
                        window.URL.revokeObjectURL(url);
                        a.remove();
                        statusMsg.innerText = "Done! Downloading ZIP with JSON and Excel...";
                    }


                    setTimeout(() => {
                        progContainer.style.display = 'none';
                        btn.disabled = false;
                        btn.innerText = isFullMode ? 'Extract Report' : 'Extract & Download ZIP';
                        clearInterval(timerInterval);
                    }, 3000);

                } catch (err) {
                    clearInterval(simInterval);
                    clearInterval(timerInterval);
                    statusMsg.innerText = "Error occurred.";
                    statusMsg.style.color = "#ef4444";
                    alert(err);
                    btn.disabled = false;
                    btn.innerText = "Try Again";
                }
            }

            // Drag and drop effects
            const dropZone = document.getElementById('dropZone');
            dropZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                dropZone.classList.add('dragover');
            });
            dropZone.addEventListener('dragleave', (e) => {
                e.preventDefault();
                dropZone.classList.remove('dragover');
            });
            dropZone.addEventListener('drop', (e) => {
                e.preventDefault();
                dropZone.classList.remove('dragover');
                if (e.dataTransfer.files.length) {
                    document.getElementById('pdfFile').files = e.dataTransfer.files;
                    updateFileName(document.getElementById('pdfFile'));
                }
            });
        </script>
    </body>
    </html>
    """
