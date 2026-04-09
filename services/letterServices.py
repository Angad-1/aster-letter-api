# import io, zipfile
# from sqlalchemy.ext.asyncio import AsyncSession
# from fastapi import HTTPException
# from fastapi.responses import StreamingResponse
# from concurrent.futures import ProcessPoolExecutor
# from multiprocessing import cpu_count
# from threading import Semaphore
# from functools import partial
# import json
# from typing import List
# from schemas.letterSchema import UploadExcel
# from utilities.utils import save_signatures,save_and_optimize_image,generate_single_pdf,read_excel,cleanup_files


# MAX_PARALLEL_JOBS = 3
# PDF_WORKERS = max(cpu_count() - 2, 1)

# JOB_SEMAPHORE = Semaphore(MAX_PARALLEL_JOBS)


# async def upload_excel(db: AsyncSession, body: UploadExcel):
#     if not JOB_SEMAPHORE.acquire(blocking=False):
#         raise HTTPException(429, "server busy")

#     header_path = footer_path = None
#     signature_paths = {}

#     # ---- parse signatures json ----
#     signature_map = json.loads(body.signatures)

#     # ---- save signature images ----
#     signature_paths = save_signatures(
#         signature_map,
#         body.signature_files
#     )

#     try:
#         header_path = save_and_optimize_image(body.header)
#         footer_path = save_and_optimize_image(body.footer)

#         meta = {
#             "header_path": header_path,
#             "footer_path": footer_path,
#             "signatures": signature_paths, 
#         }

#         employees = read_excel(body.file)

#         func = partial(generate_single_pdf, meta=meta)

#         with ProcessPoolExecutor(max_workers=PDF_WORKERS) as executor:
#             results = list(executor.map(func, employees))

#         zip_buffer = io.BytesIO()
#         with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
#             for letter_type, filename, pdf_bytes in results:
#                 zipf.writestr(f"{letter_type}/{filename}", pdf_bytes)

#         zip_buffer.seek(0)

#         # ✅ schedule deletion AFTER response
#         body.background_tasks.add_task(
#             cleanup_files,
#             [header_path, footer_path,*signature_paths.values()]
#         )

#         return StreamingResponse(
#             zip_buffer,
#             media_type="application/zip",
#             headers={
#                 "Content-Disposition": "attachment; filename=letters.zip"
#             }
#         )

#     finally:
#         JOB_SEMAPHORE.release()

import logging

logging.basicConfig(level=logging.WARNING, force=True)

# Silence noisy libraries
for name in ["fontTools", "fontTools.subset", "fontTools.ttLib", "weasyprint"]:
    logger = logging.getLogger(name)
    logger.setLevel(logging.ERROR)
    logger.propagate = False
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    
import io,gc
import json
import zipfile
from pathlib import Path
import asyncio
from dataclasses import dataclass, field
from typing import List
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import cpu_count
from functools import partial

from utilities.utils import (
    save_signatures,
    save_and_optimize_image,
    generate_single_pdf,
    read_excel,
    cleanup_files,
)

BASE_DIR = Path(__file__).resolve().parent.parent  # go up from services/
ASSETS_DIR = BASE_DIR / "assets"

# =========================
# CONFIG
# =========================
MAX_QUEUE_SIZE = 3
PDF_WORKERS = max(cpu_count() - 2, 1)
PDF_CHUNK_SIZE = 4      

job_queue: asyncio.Queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
process_pool = ProcessPoolExecutor(max_workers=PDF_WORKERS)
cpu_semaphore = asyncio.Semaphore(PDF_WORKERS)

# =========================
# JOB CONTEXT
# =========================
@dataclass
class JobContext:
    body: object
    future: asyncio.Future
    cancelled: bool = False
    temp_files: List[str] = field(default_factory=list)

    def cleanup(self) -> None:
        cleanup_files(self.temp_files)
        self.temp_files.clear()


# =========================
# WORKER LOOP
# =========================
async def worker():
    loop = asyncio.get_running_loop()

    while True:
        ctx: JobContext = await job_queue.get()

        try:
            if ctx.cancelled:
                raise asyncio.CancelledError()
            
            async with cpu_semaphore:
                zip_buffer, temp_files = await loop.run_in_executor(
                    process_pool,
                    process_excel_sync,
                    ctx.body
                )
            # extend temp_files for cleanup
            ctx.temp_files.extend(temp_files)

            # ✅ set bytes directly, not BytesIO
            ctx.future.set_result(zip_buffer)
            # zip_buffer.close()

        except asyncio.CancelledError:
            ctx.future.cancel()

        except Exception as e:
            ctx.future.set_exception(e)

        finally:
            ctx.cleanup()
            # gc.collect()
            job_queue.task_done()

# =========================
# CPU WORK (SYNC)
# =========================

def generate_pdf_for_employee(emp, meta):
    letter_type, filename, pdf_bytes = generate_single_pdf(emp, meta)
    return letter_type, filename, pdf_bytes

def process_excel_sync(body):
    """
    body is UploadExcel
    """

    temp_files: list[str] = []

    # ✅ body.signatures is already a dict (parsed in route)
    signature_paths = save_signatures(
        body.signatures,
        body.signature_files
    )

    header_path = save_and_optimize_image(body.header)
    footer_path = save_and_optimize_image(body.footer)

    temp_files.extend(
        p for p in (
            header_path,
            footer_path,
            *signature_paths.values(),
        )
        if p
    )

    meta = {
        "header_path": header_path,
        "footer_path": footer_path,
        "signatures": signature_paths,
        "assets_dir": str(ASSETS_DIR), 
    }
    # print ("Meta prepared, starting to read Excel and generate PDFs...",signature_paths, flush=True)
    # print ("body sign...",body.signatures, flush=True)

    employees = read_excel(body.file)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Create a top-level picklable function using partial
        pdf_worker = partial(generate_pdf_for_employee, meta=meta)

        # Use ProcessPoolExecutor safely
        with ProcessPoolExecutor(max_workers=PDF_WORKERS) as pool:
            results = list(pool.map(pdf_worker, employees))

        for letter_type, filename, pdf_bytes in results:
            zipf.writestr(f"{letter_type}/{filename}", pdf_bytes)

        # 🔥 CHUNKING = MAGIC
        # for i in range(0, len(employees), PDF_CHUNK_SIZE):
        #     batch = employees[i:i + PDF_CHUNK_SIZE]

        #     for emp in batch:
        #         letter_type, filename, pdf = generate_single_pdf(emp, meta)
        #         zipf.writestr(f"{letter_type}/{filename}", pdf)


        # for emp in employees:
        #     letter_type, filename, pdf_bytes = generate_single_pdf(emp, meta)
        #     zipf.writestr(f"{letter_type}/{filename}", pdf_bytes)

    # zip_buffer.seek(0)

    return zip_buffer, temp_files

# =========================
# PUBLIC API
# =========================
async def enqueue_job(body):
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    ctx = JobContext(body=body, future=future)

    await job_queue.put(ctx)

    try:
        return await future
    except asyncio.CancelledError:
        ctx.cancelled = True
        ctx.cleanup()
        raise
