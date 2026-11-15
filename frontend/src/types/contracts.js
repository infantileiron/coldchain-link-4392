/** @typedef {{id:number,code:string,route:string,zone:string,driver:string,probe:?string,depart_at:?string,arrive_at:?string,threshold:?number,max_gap:?number}} Shipment */
/** @typedef {{id:number,code:string,source:'manual'|'auto',calc_state:?string,pub_version:?number,exposure:?number,excursions:?number,loss:?number,detail:?object}} Sample */
/** @typedef {{id:number,state:'queued'|'running'|'done'|'failed',result:object}} Study */
/** @typedef {{id:number,code:string,current_rev:number,points:number}} Probe */
/** @typedef {{id:number,probe:string,revision:number,state:'applied'|'ignored'|'rejected',points_count:number,note:string,received:string}} TempBatch */
/** @typedef {{id:number,version:number,gen:number,sample_count:number,created:string}} Publication */
