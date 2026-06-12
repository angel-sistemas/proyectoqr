import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'telematica-qr-2026')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'postgresql://postgres:1997@localhost:5432/inventario_qr'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'static/img/equipos'
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY', '')
    GOOGLE_SEARCH_ENGINE_ID = os.environ.get('GOOGLE_SEARCH_ENGINE_ID', '')