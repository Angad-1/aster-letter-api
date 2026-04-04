import asyncio,io
from fastapi import APIRouter, Depends,Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from core.db import get_db
from schemas.letterSchema import UploadExcel
from schemas.activitySchema import LogActivity
from services.letterServices import enqueue_job
from services.activityServices import log_activity
from services import get_current_user_id
from schemas.commonSchema import WithoutData,ErrorRes
from utilities.utils import handle_request,MyHTTPException,get_client_ip
from utilities.constant import ActivityType,ActivityModule,ActivityMessage,ActivityStatus

router = APIRouter(prefix="/letter")

def zip_stream_generator(zip_buffer: io.BytesIO):
    try:
        zip_buffer.seek(0)
        yield from zip_buffer
    finally:
        zip_buffer.close()

@router.post("/generateLetter",response_model=None)
async def upload_excel(
    req:Request,
    body: UploadExcel=Depends(),
    db: AsyncSession = Depends(get_db)
):
    try:
        zip_buffer = await enqueue_job(body)

        await log_activity(
            db=db,
            body=LogActivity(
                user_id=get_current_user_id(),
                type=ActivityType.LETTER_GENERATED,
                module=ActivityModule.LETTER,
                message=ActivityMessage.LETTER_GENERATED,
                status=ActivityStatus.SUCCESS,
                ip=get_client_ip(req),
            )
        )
        # stream response directly
        response = StreamingResponse(
            zip_stream_generator(zip_buffer),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=letters.zip"}
        )
        

        return response

    except asyncio.CancelledError:
        raise MyHTTPException(status_code=499, content=WithoutData(status="error", message="Client cancelled the process"))

    except Exception as e:
        raise MyHTTPException(status_code=500, content=ErrorRes(status="error", message="Internal Server Error",error=str(e)))
