from fastapi.responses import FileResponse
from pathlib import Path
from fastapi import APIRouter
from utilities.utils import MyHTTPException
from schemas.commonSchema import WithoutData

UPLOAD_DIR = Path("uploads/images")

router = APIRouter(prefix="/media")

@router.get("/getMedia/{file_id}")
async def get_file(file_id: str):
    try:
        # ✅ Check if directory exists
        if not UPLOAD_DIR.exists() or not UPLOAD_DIR.is_dir():
            raise MyHTTPException(
                status_code=500,
                content=WithoutData(
                    status="error",
                    message="Media not available"
                )
            )

        # ✅ Find file
        files = list(UPLOAD_DIR.glob(f"{file_id}.*"))

        if not files:
            raise MyHTTPException(
                status_code=404,
                content=WithoutData(
                    status="error",
                    message="Media not found"
                )
            )

        return FileResponse(files[0])

    except MyHTTPException:
        raise

    except Exception as e:
        raise MyHTTPException(
            status_code=500,
            content=WithoutData(
                status="error",
                message="Internal Server Error",
                error=str(e)
            )
        )