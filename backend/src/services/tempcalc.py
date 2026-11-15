from datetime import timedelta
def _minutes(a,b):return round((b-a).total_seconds()/60,2)
def compute_window(points,start,end,threshold,max_gap_minutes):
 '''按读数保持语义计算运输窗口内的超温与缺测。
 points: [(ts,temp)] 任意顺序；读数保持到下一时刻，但单条读数最多覆盖 max_gap_minutes 分钟。
 返回超温分钟、连续超温段、缺测时段；缺测单列，不计入正常也不计入超温。'''
 if end<=start:raise ValueError('运输结束必须晚于开始')
 hold=timedelta(minutes=max_gap_minutes)
 pts=sorted(points)
 covered=[]
 for i,(ts,temp) in enumerate(pts):
  limit=ts+hold
  nxt=pts[i+1][0] if i+1<len(pts) else None
  ce=min(limit,nxt) if nxt else limit
  cs2,ce2=max(ts,start),min(ce,end)
  if cs2<ce2:covered.append((cs2,ce2,temp))
 gaps=[];cursor=start
 for cs,ce,_ in covered:
  if cs>cursor:gaps.append((cursor,cs))
  if ce>cursor:cursor=ce
 if cursor<end:gaps.append((cursor,end))
 segments=[];cur=None
 for cs,ce,temp in covered:
  if temp>threshold:
   if cur and cur[1]==cs:cur[1]=ce;cur[2]=max(cur[2],temp)
   else:
    if cur:segments.append(cur)
    cur=[cs,ce,temp]
  elif cur:segments.append(cur);cur=None
 if cur:segments.append(cur)
 seg_list=[{'start':s.isoformat(),'end':e.isoformat(),'minutes':_minutes(s,e),'peak':round(p,2)} for s,e,p in segments]
 gap_list=[{'start':s.isoformat(),'end':e.isoformat(),'minutes':_minutes(s,e)} for s,e in gaps]
 total=_minutes(start,end)
 gap_min=round(sum(g['minutes'] for g in gap_list),2)
 over_min=round(sum(x['minutes'] for x in seg_list),2)
 return {'window':{'start':start.isoformat(),'end':end.isoformat(),'total_minutes':total},
 'threshold':threshold,'max_gap_minutes':max_gap_minutes,
 'over_minutes':over_min,'segments':len(seg_list),
 'measured_minutes':round(total-gap_min,2),'gap_minutes':gap_min,
 'over_segments':seg_list,'gaps':gap_list,'points_used':len(pts)}
