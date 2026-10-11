import os
from celery import Celery

celery = Celery("worker", broker=os.environ["REDIS_URL"], backend=os.environ["REDIS_URL"])
