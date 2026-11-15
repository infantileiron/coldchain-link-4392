import {state} from '/workspace/frontend/src/stores/session.js';
import * as logs from '/workspace/frontend/src/pages/logs.js';
import * as ships from '/workspace/frontend/src/pages/shipments.js';
import * as samples from '/workspace/frontend/src/pages/samples.js';
import * as studies from '/workspace/frontend/src/pages/studies.js';
import * as recs from '/workspace/frontend/src/pages/recommendations.js';

state.user = {email: 'analyst@demo.local', role: 'analyst'};
state.ships = [{id: 1, code: 'T-01', route: '线路 01', zone: '冷藏', driver: '王某', probe: 'P-01',
  depart_at: '2026-11-14T08:00:00', arrive_at: '2026-11-14T10:00:00', threshold: null, max_gap: null}];
state.samples = [
  {id: 1, code: 'T-01-S', source: 'auto', calc_state: 'published', pub_version: 1, exposure: 25, excursions: 2, loss: 3.4,
   detail: {probe: 'P-01', revision: 1, threshold: 4, max_gap_minutes: 10, points_used: 20, computed_at: '2026-11-14T10:05:00',
     window: {start: '2026-11-14T08:00:00', end: '2026-11-14T10:00:00', total_minutes: 120},
     over_minutes: 25, segments: 2, measured_minutes: 95, gap_minutes: 25,
     over_segments: [{start: '2026-11-14T08:35:00', end: '2026-11-14T08:50:00', minutes: 15, peak: 6}],
     gaps: [{start: '2026-11-14T09:05:00', end: '2026-11-14T09:30:00', minutes: 25}]}},
  {id: 2, code: 'M-01-S', source: 'manual', calc_state: null, pub_version: null, exposure: 30, excursions: 2, loss: 2.2, detail: null},
  {id: 3, code: 'P-01-S', source: 'auto', calc_state: 'pending', pub_version: null, exposure: null, excursions: null, loss: 1.0, detail: null}];
state.probes = [{id: 1, code: 'P-01', current_rev: 2, points: 22}];
state.logs = [{id: 1, probe: 'P-01', revision: 2, state: 'applied', points_count: 22, note: '修订 2 替换修订 1', received: '2026-11-14T11:00:00'}];
state.pubs = [{id: 1, version: 1, gen: 1, sample_count: 1, created: '2026-11-14T10:06:00'}];
state.studies = [{id: 1, name: '研究', state: 'done', result: {pearson: 0.5, spearman: 0.4, n: 3, excluded: 0, total: 3,
  pearson_p: 0.01, spearman_p: 0.02, points: [{x: 1, y: 2}], pub_version: 1, warning: 'w'}}];
state.recs = [];
state.selected = state.studies[0];
state.calcSample = state.samples[0];

const out = [logs.render(), ships.render(), samples.render(), studies.render(), recs.render()];
const need = ['修订 2 替换修订 1', '超温分钟', '缺测时段', '待重算', 'v1', '手填', 'datetime-local', '同一已发布版本', 'P-01'];
const all = out.join('');
const missing = need.filter(x => !all.includes(x));
if (missing.length) { console.log('MISSING', missing); process.exit(1); }
const ex = logs.example();
if (!Array.isArray(ex) || ex.length < 20 || !ex[0].ts || typeof ex[0].temp !== 'number') { console.log('EXAMPLE_BAD'); process.exit(1); }
state.calcSample = state.samples[2];
if (!logs.render().includes('待重算')) { console.log('PENDING_VIEW_BAD'); process.exit(1); }
console.log('FRONTEND_RENDER_OK');
