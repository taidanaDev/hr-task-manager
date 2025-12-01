import os

class Config: 
    SECRET_KEY = os.environ.get('SECRET_KEY')
    DATABASE_URL = os.environ.get('DATABASE_URL')
    MAX_WORKLOAD = os.environ.get('MAX_WORKLOAD')

    try:
        MAX_WORKLOAD = int(MAX_WORKLOAD)
    except (TypeError, ValueError):
        MAX_WORKLOAD = 3