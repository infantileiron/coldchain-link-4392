import {state} from '../stores/session.js';
import {esc,fmt} from '../utils/html.js';
import {table} from '../components/common/table.js';
import {field} from '../components/common/fields.js';
import {CALC_LABELS,BATCH_LABELS} from '../constants/enums.js';
export function example(){
 let pts=[],t0=new Date('2026-11-14T07:55:00Z').getTime();
 for(let i=0;i<27;i++){
  let off=i*5;
  if(off>=70&&off<95)continue;
  let temp=2.5+((i*37)%10-5)/10;
  if(off>=40&&off<65)temp=5.6;
  if(off>=100&&off<115)temp=6.3;
  pts.push({ts:new Date(t0+off*60000).toISOString(),temp});
 }
 return pts;
}
function detail(s){
 if(s.calc_state==='pending')return `<p class=notice>样本 ${esc(s.code)} 待重算：日志或班次已变更，全部算完后一起发布。</p>`;
 if(s.calc_state==='failed')return `<p class=notice>样本 ${esc(s.code)} 计算失败：${esc(s.calc_error)}。修正日志或班次后点击“重算待发布样本”。</p>`;
 let d=s.detail;
 if(!d)return '<p class=notice>尚无计算明细。</p>';
 return `<h3>${esc(s.code)} · 探头 ${esc(d.probe)} 修订 ${d.revision} · 发布 v${s.pub_version}</h3>
 <p>阈值 ${d.threshold}°C · 缺测间隔 ${d.max_gap_minutes} 分钟 · 读数 ${d.points_used} 个 · 计算于 ${fmt(d.computed_at)}</p>
 <div class=metrics><div><strong>${d.over_minutes}</strong>超温分钟</div><div><strong>${d.segments}</strong>连续超温段</div><div><strong>${d.measured_minutes}</strong>实测分钟</div><div><strong>${d.gap_minutes}</strong>缺测分钟</div></div>
 <p>运输窗口 ${fmt(d.window.start)} → ${fmt(d.window.end)} 共 ${d.window.total_minutes} 分钟 ＝ 实测 ${d.measured_minutes} ＋ 缺测 ${d.gap_minutes}</p>
 <h3>逐段超温</h3>${table(['开始','结束','时长分钟','峰值 °C'],d.over_segments.map(x=>[fmt(x.start),fmt(x.end),x.minutes,x.peak]))}
 <h3>缺测时段（不计入正常）</h3>${table(['开始','结束','时长分钟'],d.gaps.map(x=>[fmt(x.start),fmt(x.end),x.minutes]))}`;
}
export function render(){
 let auto=state.samples.filter(x=>x.source==='auto');
 let sel=state.calcSample;
 return `<div class=split><section class=panel>
 <h2>探头与发布</h2>
 <div class=metrics>${state.probes.map(p=>`<div><strong>${esc(p.code)}</strong>修订 ${p.current_rev} · ${p.points} 个读数</div>`).join('')}<div><strong>${state.pubs.length?'v'+state.pubs[0].version:'—'}</strong>当前发布版本</div></div>
 <h2>自动样本核对</h2>
 ${auto.map(x=>`<button class=study data-calc=${x.id}>${esc(x.code)} · ${CALC_LABELS[x.calc_state]||'待重算'}</button>`).join('')||'<p>尚无探头样本。为班次登记探头与运输起止后，样本改由温度日志计算。</p>'}
 ${sel?detail(sel):''}
 <h2>导入批次</h2>
 ${table(['时间','探头','修订','结果','点数','说明'],state.logs.map(b=>[fmt(b.received),b.probe,b.revision,BATCH_LABELS[b.state]||b.state,b.points_count,b.note]))}
 </section><aside class=side>
 <h2>导入温度日志</h2>
 <form id=logs>
 ${field('探头编号','probe','text','required placeholder="P-01"')}
 ${field('修订号','revision','number','min=0 required')}
 <label>温度点 JSON（ts / temp 数组）<textarea name=points rows=8 required placeholder='[{"ts":"2026-11-14T08:00:00Z","temp":2.6}]'></textarea></label>
 <input type=file id=logfile accept=".json,.txt">
 <button class=primary>校验并导入</button>
 </form>
 <p><button id=logdemo type=button>填充示例修订</button></p>
 <h2>重算与发布</h2>
 <p>较低修订自动忽略；同号温度分歧整批拒收。更正后相关班次样本标为待重算，全部算完才一起发布；失败保留旧版。</p>
 <p><button id=recalc type=button>重算待发布样本</button> <button id=refresh type=button>刷新</button></p>
 </aside></div>`}
