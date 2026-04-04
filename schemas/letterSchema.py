from fastapi import Request, BackgroundTasks, UploadFile, File, Form
from typing import List, Dict
import json

class UploadExcel:
    def __init__(
        self,
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        header: UploadFile = File(...),
        footer: UploadFile = File(...),
        signatures: str = Form(...),
        signature_files: List[UploadFile] = File(...)
    ):
        self.background_tasks = background_tasks
        self.file = file
        self.header = header
        self.footer = footer
        self.signatures: Dict[str, str] = json.loads(signatures)
        self.signature_files = signature_files
