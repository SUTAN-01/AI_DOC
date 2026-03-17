from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from app.api_deps import get_current_user
from app.docs_service import build_vector_db, get_status, list_doc_files, save_upload


router = APIRouter(prefix='/docs', tags=['docs'])


@router.get('/files')
def files(_current = Depends(get_current_user)):
    return list_doc_files()


@router.get('/status')
def status(_current = Depends(get_current_user)):
    return get_status().to_dict()


@router.post('/upload')
def upload(file: UploadFile = File(...), _current = Depends(get_current_user)):
    try:
        path = save_upload(file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {'ok': True, 'path': path}


@router.post('/build')
def build(background: BackgroundTasks, _current = Depends(get_current_user)):
    st = get_status()
    if st.state == 'running':
        raise HTTPException(status_code=409, detail='Build already running')
    background.add_task(build_vector_db)
    return {'ok': True}
