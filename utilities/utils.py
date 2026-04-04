import re,os,uuid,shutil,logging,hashlib,traceback
from pathlib import Path
from uuid import UUID
from ulid import ULID 
from fastapi import UploadFile,Request,Depends
from fastapi.security import OAuth2PasswordBearer
from PIL import Image
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError,VerificationError
import pandas as pd
from jinja2 import Environment, FileSystemLoader
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from weasyprint import HTML
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select,exists,SQLModel,literal
from typing import Any,Type,TypeVar,Optional,Iterable, Union,Annotated
from markupsafe import Markup, escape

from services import set_current_user_id,set_current_user_role
from schemas.commonSchema import ErrorRes,WithoutData
from models.models import Users,UserSession
from core.db import get_db
from utilities.constant import REQUIRED_COLUMNS,LETTER_TEMPLATE_MAP

logger = logging.getLogger(__name__)

T = TypeVar("T")

env = Environment(loader=FileSystemLoader("templates"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login",auto_error=False)

STALE_SESSION_MINUTES = int(os.getenv("STALE_SESSION_MINUTES", "5"))


BASE_UPLOAD_DIR = Path("uploads")
IMAGE_DIR = BASE_UPLOAD_DIR / "images"
UPLOAD_DIR = "tmp_assets"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def safe(v, d="", *, is_num=False, dec=0):
    if v is None or pd.isna(v):
        return d

    s = str(v).strip()
    if s == "":
        return d

    if not is_num:
        return s

    # number=True => format with commas
    try:
        num = float(v)
        if dec == 0:
            return f"{int(round(num)):,}"
        return f"{num:,.{dec}f}"
    except (ValueError, TypeError):
        return s

ph = PasswordHasher(
    salt_len=32,
    hash_len=64,
    parallelism=4,
    time_cost=4,
    memory_cost=65536,
)

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

def normalize_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def hash_password(pwd: str) -> str:
    return ph.hash(pwd)

def verify_password(raw_pwd: str, hashed_pwd: str) -> bool:
    try:
        result = ph.verify(hashed_pwd, raw_pwd)
        return result
    except VerifyMismatchError:
        return False
    except VerificationError as e:
        return False
    except Exception as e:
        return False
    
def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
    

def create_token(data: dict, type: str, expires_delta: Optional[int] = None):
    if expires_delta is None:
        exp_str = (
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")
            if type == "access"
            else os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES")
        )
        try:
            expires_delta = int(exp_str)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid token expiration value: {exp_str}")

    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_delta)

    to_encode = data.copy()
    to_encode.update({"exp": expire, "type": type})

    encoded_jwt = jwt.encode(
        to_encode,
        os.getenv("SECRET_KEY"),
        algorithm=os.getenv("ALGORITHM", "HS256")
    )
    return encoded_jwt
    
class MyHTTPException(Exception):
    def __init__(self, status_code: int, content: dict):
        self.status_code = status_code
        self.content = content  

async def handle_request(func, *args, **kwargs):
    try:
        return await func(*args, **kwargs)
    except MyHTTPException as me:
        raise me
    except Exception as e:
        logger.error(f"Unhandled Exception in {func.__name__}: {str(e)}")
        logger.error("Traceback:\n" + traceback.format_exc())
        raise MyHTTPException(
            status_code=500,
            content=ErrorRes(
                status="error",
                message="Internal Server Error",
                error=str(e)
            )
        )
    
# def cleanup_files(paths: list[str]):
#     for path in paths:
#         try:
#             if os.path.exists(path):
#                 os.remove(path)
#         except Exception:
#             pass
  
def cleanup_files(paths: Iterable[Union[str, None]]) -> None:
    """
    Safely removes files or directories.
    - Ignores None values
    - Handles files & directories
    - Never raises
    """
    for path in paths:
        if not path or not isinstance(path, str):
            continue

        try:
            if os.path.isfile(path):
                os.remove(path)

            elif os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)

        except Exception as exc:
            logger.warning(
                "Cleanup failed for path=%s error=%s",
                path,
                exc,
            )
            
def is_empty(v):
    if v is None:
        return True
    s = str(v).strip()
    return s == "" or s.lower() in {"na", "n/a", "none", "-", "null"}

def build_annexure_rows(values: list[dict]) -> Markup:
    """
    values: list of {label, current, new, show_if_any=True/False}
    Skips a row if both current and new are empty.
    """
    rows_html = []
    for item in values:
        label = item["label"]
        cur = item.get("current")
        new = item.get("new")

        if is_empty(cur) and is_empty(new):
            continue

        rows_html.append(f"""
          <tr style="border: 1px solid #000;">
            <td style="border: 1px solid #000; padding: 10px;white-space: nowrap;">{escape(label)}</td>
            <td style="border: 1px solid #000; padding: 10px; text-align:right;">{escape("" if is_empty(cur) else cur)}</td>
            <td style="border: 1px solid #000; padding: 10px; text-align:right;">{escape("" if is_empty(new) else new)}</td>
          </tr>
        """.strip())
    return Markup("\n".join(rows_html))

def format_date(value):
    if not value:
        return ""

    dt = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(dt):
        return ""

    day = dt.day

    if 11 <= day <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")

    return f"{day}{suffix} {dt.strftime('%b %Y')}"

def generate_pdf(emp,meta):
    """
    emp: dict from read_excel()
    meta: dict of header & footer()
    Chooses template based on Letter type
    """
    letter_type = emp.get("Letter type")
    # print("Letter type:", repr(letter_type), flush=True)
    # print("Template name:", repr(template_name), flush=True)
    template_name = LETTER_TEMPLATE_MAP.get(letter_type)
    # print("Template name:", template_name)
    if not template_name:
        raise ValueError(f"Unsupported Letter type: {letter_type}")

    template = env.get_template(template_name)
    ASSETS_DIR = Path(meta["assets_dir"])
    css_path = (ASSETS_DIR / "css/common.css").as_uri()
        
    
    annexure_items = [
        {"label": "Basic Salary",              "current": safe(emp.get("Current Basic Salary"), is_num=True),                  "new": safe(emp.get("New Basic Salary"), is_num=True)},
        {"label": "HRA",                       "current": safe(emp.get("Current HRA"), is_num=True),                           "new": safe(emp.get("New HRA"), is_num=True)},
        {"label": "Other Allowance",           "current": safe(emp.get("Current Other Allowances"), is_num=True),              "new": safe(emp.get("New Other Allowances"), is_num=True)},
        {"label": "Individual Allowance",      "current": safe(emp.get("Current Individual Allowances"), is_num=True),         "new": safe(emp.get("New Individual Allowances"), is_num=True)},
        {"label": "Fixed Salary (A)",          "current": safe(emp.get("Current Fixed Salary (A)"), is_num=True),              "new": safe(emp.get("New Fixed Salary (A,)"), is_num=True)},
        {"label": "Travel & Mobile Allowance (B)", "current": safe(emp.get("Current Travel & Mobile Allowance (B)"), is_num=True), "new": safe(emp.get("New Travel & Mobile Allowance (B)"), is_num=True)},
        {"label": "Total Compensation",        "current": safe(emp.get("Current Total Gross Salary (TGS) (A) + (B)"), is_num=True), "new": safe(emp.get("New Total Gross Salary (TGS) (A) + (B)"), is_num=True)},
    ]

    html = template.render(

        # ---------- META ----------
        date=datetime.today().strftime("%d %B %Y"),
        letter_type=letter_type,

        # ---------- EMPLOYEE ----------
        name=safe(emp.get("Name")),
        employee_code=safe(emp.get("E Code")),
        designation=safe(emp.get("Designation")),
        new_designation=safe(emp.get("New Designation")),
        band=safe(emp.get("Band")),
        new_role_band=safe(emp.get("New Role Band")),
        vertical=safe(emp.get("Vertical")),
        business_unit=safe(emp.get("Business Unit")),
        department=safe(emp.get("Department")),

        # ---------- PERFORMANCE ----------
        performance_year=safe(emp.get("Performance year")),
        rating_label=safe(emp.get("Rating Label")),
        promotion=safe(emp.get("Promotion")),

        # ---------- CURRENT SALARY ----------
        currency=safe(emp.get("Currency", "AED")),
        current_basic=safe(emp.get("Current Basic Salary")),
        current_hra=safe(emp.get("Current HRA")),
        current_fixed=safe(emp.get("Current Fixed Salary (A)")),
        current_tgs=safe(emp.get("Current Total Gross Salary (TGS) (A) + (B)")),

        # ---------- NEW SALARY ----------
        new_basic=safe(emp.get("New Basic Salary")),
        new_hra=safe(emp.get("New HRA")),
        new_fixed=safe(emp.get("New Fixed Salary (A,)")),
        new_tgs=safe(emp.get("New Total Gross Salary (TGS) (A) + (B)")),

        # ---------- ALLOWANCES ----------
        org_allowance=safe(emp.get("Organizational Allowance")),
        aed_per_month=safe(emp.get("AED Per Month"), is_num=True),
        cur_other_allowance=safe(emp.get("Current Other Allowances")),
        cur_individual_allowance=safe(emp.get("Current Individual Allowances")),
        cur_vehicle_allowance=safe(emp.get("Current Vehicle Allowance")),
        cur_telephone_allowance=safe(emp.get("Current Telephone Allowance")),
        cur_travel_allowance=safe(emp.get("Current Travel & Mobile Allowance (B)")),
        new_other_allowance=safe(emp.get("New Other Allowances")),
        new_individual_allowance=safe(emp.get("New Individual Allowances")),
        new_vehicle_allowance=safe(emp.get("New Vehicle Allowance")),
        new_telephone_allowance=safe(emp.get("New Telephone Allowance")),
        new_travel_allowance=safe(emp.get("New Travel & Mobile Allowance (B)")),

        # ---------- DATES ----------
        new_salary_effective_date=format_date(emp.get("New salary effective date")),
        new_salary_effective_year=safe(emp.get("New salary effective Year")),
        next_review_date=format_date(emp.get("Next Review Date")),
        pip_duration=safe(emp.get("PIP Duration")),
        pip_effective_date=format_date(emp.get("PIP Effective Date")),

        # ---------- SIGNATORY ----------
        signatory_name=safe(emp.get("Signatory Name")),
        signatory_designation=safe(emp.get("Signatory Designation")),

        # ---------- TEMPLATE META ----------
        header_path=meta["header_path"],
        footer_path=meta["footer_path"],
        signature_path=meta.get("signatures", {}).get(emp.get("Signatory Name")),
        annexure_rows = build_annexure_rows(annexure_items),
        css_path=css_path,
    )

    return HTML(string=html, base_url=os.getcwd()).write_pdf()

def generate_single_pdf(emp, meta):
    letter_type = emp.get("Letter type", "UNKNOWN")
    emp_code = emp.get("E Code", "EMP")

    filename = f"{emp_code}.pdf"
    pdf_bytes = generate_pdf(emp, meta)

    return letter_type, filename, pdf_bytes

def save_signatures(signature_map: dict,signature_files: list) -> dict:
    """
    Returns:
    {
      "John Doe": "/path/to/john.png",
      "Jane Smith": "/path/to/jane.jpg"
    }
    """
    os.makedirs("tmp_assets/signatures", exist_ok=True)

    # filename → UploadFile
    file_lookup = {f.filename: f for f in signature_files}
    result = {}

    for name, filename in signature_map.items():
        upload = file_lookup.get(filename)
        if not upload:
            continue
        ext = Path(filename).suffix or ".png"
        path = os.path.join("tmp_assets/signatures", f"{uuid.uuid4().hex}{ext}")
        with open(path, "wb") as buffer:
            buffer.write(upload.file.read())
        result[name] = path
    return result

def normalize_column(col: str) -> str:
    """
    Normalize column names:
    - strip leading/trailing spaces
    - replace multiple spaces with single space
    """
    col = col.strip()
    col = re.sub(r"\s+", " ", col)
    return col

def read_excel(upload_file):
    df = pd.read_excel(upload_file.file)

    df.columns = [normalize_column(c) for c in df.columns]

    normalized_required = {normalize_column(c) for c in REQUIRED_COLUMNS}
    missing_columns = normalized_required - set(df.columns)
    if missing_columns:
        raise ValueError(
            f"Missing columns in uploaded file: {', '.join(sorted(missing_columns))}"
        )

    df = df.dropna(how="all")

    if "Letter type" in df.columns:
        df = df[df["Letter type"].notna()]
        df["Letter type"] = df["Letter type"].astype(str).str.strip()
        df = df[df["Letter type"] != ""]

    # print("Filtered DF shape:", df.shape, flush=True)
    # print(df["Letter type"].tolist(), flush=True)

    return df.to_dict(orient="records")

def save_and_optimize_image(upload, max_width=1000):
    ALLOWED_EXT = {".png", ".jpg", ".jpeg"}
    MAX_MB = 2
    UPLOAD_DIR = "tmp_assets"
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    ext = os.path.splitext(upload.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        raise MyHTTPException(400, "only png, jpg, jpeg allowed")

    upload.file.seek(0, os.SEEK_END)
    if upload.file.tell() / (1024 * 1024) > MAX_MB:
        raise MyHTTPException(400, "image too large")
    upload.file.seek(0)

    out_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}.png")

    img = Image.open(upload.file).convert("RGB")

    if img.width > max_width:
        ratio = max_width / img.width
        img = img.resize(
            (max_width, int(img.height * ratio)),
            Image.LANCZOS
        )

    img.save(out_path, "PNG",optimize=True)
    upload.file.seek(0)

    return out_path

async def get_object_if_exists(
    db: AsyncSession,
    model: Type[T],
    id: uuid.UUID,
    tbn: str = "" #Table Name for generating message
) -> T:
    """
    Retrieves an object from the database table based on UUID.
    Raises an HTTP exception if the object does not exist.

    Args:
        db (AsyncSession): The database session.
        model (Type[T]): SQLAlchemy model class.
        id (UUID): The UUID of the object.
        not_found_message (str): Message for 404 error if not found.

    Returns:
        T: The found object.
    """
    stmt = select(model).where(model.id == id)
    result = await db.execute(stmt)
    obj = result.scalar_one_or_none()

    if not obj:
        raise MyHTTPException(
            status_code=404,
            content=WithoutData(status="error", message=f"${tbn} not found")
        )

    return obj


async def save_upload_file(upload_file: UploadFile,suffix:str)-> dict:
    """
    Save uploaded file into appropriate folder based on content type.
    Falls back to 'misc' if type is unknown.
    Returns relative path from BASE_UPLOAD_DIR.
    """
    if not upload_file:
        return None
    
    BASE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    content_type = upload_file.content_type or ""
    ext = Path(upload_file.filename).suffix.lower()

    if content_type.startswith("image/"):
        folder = IMAGE_DIR
        
    folder.mkdir(parents=True, exist_ok=True)
    file_name = f"{suffix}_{str(ULID())}{ext}"
    file_path = folder / file_name

    content = await upload_file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    print("📂 Saved file to:", file_path.resolve()) 
    return {
        "file_name": file_name,
        "file_type": ext.lstrip("."),  # without the dot
        "path": str(file_path.relative_to(BASE_UPLOAD_DIR).as_posix()),  # relative path
    }
    
def build_file_url(request: Request, path: str | None) -> str:
    if not path:
        return ""
    # # ensures "/images/.." formatting
    # if not path.startswith("/"):
    #     path = "/" + path
        
    file_id = Path(path).stem
    # return str(request.base_url).rstrip("/") + "/uploads" + path
    return f"{request.base_url}api/media/getMedia/{file_id}"


async def decode_token(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db)
):
    not_authenticated_exception = MyHTTPException(
        status_code=401,
        content={
            "status": "error",
            "code": 1001,
            "message": "Not authenticated",
        },
    )

    credentials_exception = MyHTTPException(
        status_code=401,
        content=dict(status="error", code=1002, message="Invalid token or expired"),
    )

    if token is None:
        raise not_authenticated_exception

    try:
        payload = jwt.decode(
            token,
            os.getenv("SECRET_KEY"),
            algorithms=[os.getenv("ALGORITHM", "HS256")]
        )

        user_id_raw = payload.get("id")
        role = payload.get("role")
        token_type = payload.get("type")
        session_id_raw = payload.get("session_id")

        if token_type != "access" or user_id_raw is None or session_id_raw is None:
            raise credentials_exception

        user_id = UUID(str(user_id_raw))
        session_id = UUID(str(session_id_raw))

    except (JWTError, ValueError, TypeError):
        raise credentials_exception

    user_stmt = select(Users).where(Users.id == user_id)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise credentials_exception

    session_stmt = select(UserSession).where(
        UserSession.id == session_id,
        UserSession.user_id == user_id
    )
    session_result = await db.execute(session_stmt)
    session = session_result.scalar_one_or_none()

    if not session:
        raise credentials_exception

    if session.revoked_at is not None:
        raise credentials_exception

    expires_at = normalize_utc(session.expires_at)
    now = normalize_utc(utcnow())

    if expires_at is None or expires_at <= now:
        raise credentials_exception

    session.last_seen_at = now
    await db.commit()

    set_current_user_id(user_id)
    set_current_user_role(role)

    return payload
def _safe_delete_file(path_str: str | None) -> None:
    """
    Deletes a file if it exists. Never throws to avoid breaking API response.
    Only deletes local filesystem paths.
    """
    if not path_str:
        return
    try:
        p = Path(BASE_UPLOAD_DIR / path_str)
        if p.exists() and p.is_file():
            p.unlink()
    except Exception:
        # log if you have logging; don't raise
        pass


def get_client_ip(request: Request) -> str:
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()

    x_real_ip = request.headers.get("x-real-ip")
    if x_real_ip:
        return x_real_ip

    return request.client.host

def file_stem(path: str | None) -> str | None:
    if not path:
        return None
    name = path.rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[0]

