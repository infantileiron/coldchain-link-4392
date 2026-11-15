import os,logging
from contextlib import asynccontextmanager
from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from src.config.database import Base,engine
from src.models import entities
from src.routes.api import router
from src.middlewares.request import RequestId,SecurityHeaders
NEW_COLUMNS={
 'shipments':[('probe','VARCHAR(60)'),('depart_at','DATETIME'),('arrive_at','DATETIME'),('threshold','FLOAT'),('max_gap','INT')],
 'samples':[('source',"VARCHAR(10) DEFAULT 'manual'"),('calc_state','VARCHAR(10)'),('pub_version','INT'),('detail','JSON'),('calc_error','TEXT')],
}
def ensure_columns():
 '''为既有库补齐新增列（create_all 不修改已存在的表），保证原手填样本可用。'''
 if engine.dialect.name!='mysql':return
 with engine.begin() as c:
  for table,cols in NEW_COLUMNS.items():
   existing={r[0] for r in c.execute(text(f'SHOW COLUMNS FROM {table}'))}
   for name,ddl in cols:
    if name not in existing:c.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'))
@asynccontextmanager
async def lifespan(app):
 Base.metadata.create_all(engine)
 try:ensure_columns()
 except Exception:logging.exception('ensure columns failed')
 if os.getenv('SEED_DEMO')=='true':
  try:
   from scripts.seed_demo import seed
   seed()
  except Exception:logging.exception('seed failed')
 yield
app=FastAPI(title='冷链温控与损耗关联',lifespan=lifespan)
app.add_middleware(RequestId);app.add_middleware(SecurityHeaders)
app.include_router(router)
@app.get('/health')
def health():
 from sqlalchemy import text
 import redis
 with engine.connect() as c:c.execute(text('SELECT 1'))
 redis.Redis.from_url(os.environ['REDIS_URL']).ping()
 return {'status':'ok'}
@app.exception_handler(Exception)
async def errors(request:Request,exc:Exception):
 logging.exception('request failed');return JSONResponse(status_code=500,content={'detail':'服务暂时异常，请稍后重试'})
