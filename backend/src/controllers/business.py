from fastapi import HTTPException
from sqlalchemy import func
from src.models.entities import Shipment,Sample,Study,Publication
from src.services.business import dump
def ensure_shipment(s,i):
 if not s.get(Shipment,i):raise HTTPException(404,'班次不存在')
def get_shipment(s,i):
 row=s.get(Shipment,i)
 if not row:raise HTTPException(404,'班次不存在')
 return row
def study_rows(s,zone):
 ids=[r.id for r in s.query(Shipment).filter_by(zone=zone).all()]
 rows=[]
 for r in s.query(Sample).filter(Sample.shipment_id.in_(ids)).all():
  d=dump(r);d.pop('detail',None);d.pop('calc_error',None);rows.append(d)
 return rows
def ensure_study(s,i):
 row=s.get(Study,i)
 if not row:raise HTTPException(404,'研究不存在')
 return row
def pending_block_count(s):
 return s.query(Sample).filter(Sample.calc_state.in_(['pending','failed'])).count()
def current_pub_version(s):
 return s.query(func.max(Publication.version)).scalar()
