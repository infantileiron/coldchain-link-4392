import os,time,json,logging
from pathlib import Path
import redis
from src.config.database import Session
from src.models.entities import Study,Sample
from src.services.analysis import analyze
from src.services.recalc import run_recalc
r=redis.Redis.from_url(os.environ['REDIS_URL'])
with Session() as recovery:
 for pending in recovery.query(Study).filter(Study.state.in_(['queued','running'])).all():
  pending.state='queued';r.rpush('studies',pending.id)
 recovery.commit()
 if recovery.query(Sample).filter_by(calc_state='pending').count():r.rpush('recalc',1)
while True:
 Path('/tmp/heartbeat').touch()
 try:
  item=r.blpop(['studies','recalc'],timeout=3)
  if not item:continue
  queue=item[0].decode() if isinstance(item[0],bytes) else item[0]
  if queue=='recalc':
   with Session() as s:
    summary=run_recalc(s)
    if summary.get('published'):
     Path(f"/artifacts/pub-{summary['published']}.json").write_text(json.dumps(summary,ensure_ascii=False))
    if summary.get('stale') or summary.get('published'):
     if s.query(Sample).filter_by(calc_state='pending').count():r.rpush('recalc',1)
   continue
  with Session() as s:
   row=s.get(Study,int(item[1]))
   if not row or row.state!='queued':continue
   snapshot=row.result['snapshot'];row.state='running';s.commit()
   try:
    row.result={**analyze(snapshot,row.feature),'snapshot':snapshot,'pub_version':row.result.get('pub_version')};row.state='done'
    Path('/artifacts/'+str(row.id)+'.json').write_text(json.dumps(row.result,ensure_ascii=False))
   except Exception as e:row.state='failed';row.error=str(e)
   s.commit()
 except Exception:logging.exception('worker');time.sleep(2)
