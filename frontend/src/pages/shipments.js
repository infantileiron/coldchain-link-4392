import {state} from '../stores/session.js';
import {fmt} from '../utils/html.js';
import {table} from '../components/common/table.js';
import {field,select} from '../components/common/fields.js';
import {ZONES} from '../constants/enums.js';
export function render(){return `<div class=split><section class=panel><h2>${state.ships.length} 班次的运输背景</h2>${table(['班次号','配送线路','温区','驾驶员','探头','运输开始','运输结束','阈值 °C','缺测间隔'],state.ships.map(s=>[s.code,s.route,s.zone,s.driver,s.probe||'—',fmt(s.depart_at),fmt(s.arrive_at),s.threshold??'默认',s.max_gap??'默认']))}</section><aside class=side><h2>录入运输班次</h2><p>先建立班次，再录入温控与货损样本。登记探头与运输起止后，该班次样本改由温度日志计算。</p><form id=ship>${field('班次编号','code','text','required')}${field('配送线路','route','text','required')}${select('温区','zone',ZONES.map(z=>[z,z]))}${field('驾驶员','driver','text','required')}${field('探头编号（可空）','probe','text','placeholder="P-01"')}${field('运输开始','depart_at','datetime-local')}${field('运输结束','arrive_at','datetime-local')}${field('超温阈值 °C（可空，按温区默认）','threshold','number','step=0.5 min=-80 max=80')}${field('缺测间隔分钟（可空，默认 10）','max_gap','number','min=1 max=240')}<button class=primary>保存班次</button></form></aside></div>`}
