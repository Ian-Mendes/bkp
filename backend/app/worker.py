# Fila Celery removida no MVP: e-mail roda em BackgroundTasks e o enriquecimento
# roda síncrono (NullProvider). Ao ligar um provider real (Apify), reintroduza a
# fila: descomente o app abaixo, recrie as tasks (o loop de enriquecimento está em
# `services.run_enrichment`, para reempacotar com retry) e os serviços
# `worker`/`beat`/`redis` no docker-compose.yml.
#
# import os
# from celery import Celery
#
# celery = Celery("worker", broker=os.environ["REDIS_URL"], backend=os.environ["REDIS_URL"])
