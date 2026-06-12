from fastapi import Depends, FastAPI, HTTPException

from app.auth import get_current_user_id
from app.db import get_report
from app.schemas import ReportOut

app = FastAPI()


@app.get("/reports/{report_id}")
def show_report(report_id: int, user_id: int = Depends(get_current_user_id)) -> ReportOut:
    row = get_report(report_id)
    if row is None:
        raise HTTPException(status_code=404)
    if row[1] != user_id:
        raise HTTPException(status_code=403)
    return ReportOut(id=row[0], body=row[2])
