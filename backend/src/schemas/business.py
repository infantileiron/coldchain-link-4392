from pydantic import BaseModel,Field,field_validator
from typing import Optional,Literal
from datetime import datetime
def _strip(v):
 if isinstance(v,str):v=v.strip()
 return v or None
class Login(BaseModel):
 email:str;password:str
class ShipmentInput(BaseModel):
 code:str=Field(min_length=1,max_length=60);route:str=Field(min_length=1,max_length=60);zone:Literal['冷藏','冷冻','常温对照'];driver:str=Field(min_length=1,max_length=60)
 probe:Optional[str]=Field(default=None,max_length=60);depart_at:Optional[datetime]=None;arrive_at:Optional[datetime]=None
 threshold:Optional[float]=Field(default=None,ge=-80,le=80);max_gap:Optional[int]=Field(default=None,ge=1,le=240)
 @field_validator('probe')
 @classmethod
 def strip_probe(cls,v):return _strip(v)
class SampleInput(BaseModel):
 shipment_id:int;code:str=Field(min_length=1,max_length=60);exposure:Optional[float]=Field(default=None,ge=0,le=1440);excursions:Optional[int]=Field(default=None,ge=0,le=100);loss:Optional[float]=Field(default=None,ge=0,le=100)
class LogPoint(BaseModel):
 ts:datetime;temp:float=Field(ge=-80,le=80)
class LogBatchInput(BaseModel):
 probe:str=Field(min_length=1,max_length=60);revision:int=Field(ge=0,le=1000000);points:list[LogPoint]=Field(min_length=1,max_length=20000)
 @field_validator('probe')
 @classmethod
 def strip_probe(cls,v):return _strip(v)
class StudyInput(BaseModel):
 name:str=Field(min_length=1,max_length=100);zone:Literal['冷藏','冷冻','常温对照'];feature:Literal['exposure','excursions']='exposure'
class RecommendationInput(BaseModel):
 study_id:int;note:str=Field(min_length=10,max_length=2000);owner:str=Field(min_length=1,max_length=60)
