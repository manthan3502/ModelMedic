import { MutationNotice, ErrorState } from './Workspace'
import { useRuntime } from './runtime'
import { reportPrintStyles } from './reportPrint'
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { request } from './api/projects'
import type { ReportData, ReportTable, SliceAnalysis, SliceRow, SlicesData, TrendsData } from './api/diagnostics'

const metricName = (s: string) => ({ brier: 'Brier Score · probability quality', log_loss: 'Log Loss', ks: 'KS statistic', js: 'Jensen–Shannon distance', missing_percent: 'Missing %', class_share: 'Predicted class share', roc_auc: 'ROC-AUC', macro_ovr_roc_auc: 'Macro OvR ROC-AUC', average_precision: 'Average Precision' })[s as 'brier'] ?? s.replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase())
const number = (n: number | null | undefined) => n == null ? 'Unavailable' : Math.abs(n) > 0 && Math.abs(n) < .0001 ? n.toExponential(3) : n.toFixed(4)
const sliceName = (r: SliceRow) => r.is_overall ? 'All rows' : r.slice_value == null ? 'Missing value (null)' : JSON.stringify(r.slice_value)

export function SliceResults({ analysis }: { analysis: SliceAnalysis }) {
  const [metric, setMetric] = useState('balanced_accuracy')
  const keys = Object.keys(analysis.rows[0]?.metrics ?? {})
  const selected = keys.includes(metric) ? metric : keys[0]
  const all = analysis.rows.find(r => r.is_overall)?.metrics[selected]?.value
  const slices = analysis.rows.filter(r => !r.is_overall)
  const max = selected === 'log_loss' ? Math.max(1, ...slices.map(r => r.metrics[selected]?.value ?? 0), all ?? 0) : selected === 'brier' && Object.keys(analysis.rows[0]?.class_support ?? {}).length > 2 ? 2 : 1
  return <section aria-label={`Saved slices for ${analysis.feature_name}`}><h3>{analysis.feature_name}</h3><p>{analysis.limitation}</p><p>Methodology {analysis.methodology_version} · Created result {analysis.published_at}. Categories keep their raw spellings; missing values are a separate group.</p>
    <label htmlFor="slice-metric">Metric for dot plot</label><select id="slice-metric" value={selected ?? ''} onChange={e => setMetric(e.target.value)}>{keys.map(k => <option key={k} value={k}>{metricName(k)}</option>)}</select>
    <div className="plot-scroll"><svg className="slice-plot" viewBox={`0 0 760 ${80 + slices.length * 34}`} role="img" aria-label={`One metric: ${metricName(selected ?? '')}. All rows reference and slice sample sizes. Insufficient slices omitted from plot and retained in table.`}>
      <text x="300" y="18">0</text><text x="700" y="18">{number(max)}</text>
      {all != null && <><line x1={310 + 390 * all / max} x2={310 + 390 * all / max} y1="28" y2={55 + slices.length * 34} stroke="var(--baseline)" strokeDasharray="4 4" /><text x="300" y={75 + slices.length * 34}>All rows: {number(all)}</text></>}
      {slices.filter(r => r.row_count >= 30 && r.metrics[selected]?.value != null).map(r => { const i = slices.indexOf(r), v = r.metrics[selected].value!; return <g key={r.slice_key}><text x="8" y={45 + i * 34}>{sliceName(r).slice(0, 32)} · n={r.row_count}</text><circle cx={310 + 390 * v / max} cy={40 + i * 34} r="5" tabIndex={0} role="img" aria-label={`${sliceName(r)}: ${metricName(selected)} ${number(v)}, n=${r.row_count}`} fill="var(--current)" /><text x={Math.min(705, 325 + 390 * v / max)} y={45 + i * 34}>{number(v)}</text></g> })}
    </svg></div>
    <div className="table-scroll"><table><caption>All rows and raw-category slices · category order, no performance ranking</caption><thead><tr><th scope="col">Slice</th><th scope="col">n</th><th scope="col">Class support</th>{keys.map(k => <th scope="col" key={k}>{metricName(k)}</th>)}<th scope="col">Availability / reason</th></tr></thead><tbody>{analysis.rows.map(r => <tr key={r.slice_key}><th scope="row">{sliceName(r)}</th><td className="numeric">{r.row_count}</td><td>{Object.entries(r.class_support).map(([c, n]) => `${c}: ${n}`).join(' · ')}</td>{keys.map(k => <td className="numeric" key={k}>{r.row_count < 30 ? 'Unavailable' : number(r.metrics[k]?.value)}{r.metrics[k]?.reason && <small>{r.metrics[k].reason}</small>}{r.metrics[k]?.note && <small>{r.metrics[k].note}</small>}</td>)}<td>{r.status}{r.reason && <p>{r.reason}</p>}</td></tr>)}</tbody></table></div>
  </section>
}

export function Slices({ runId }: { runId: string }) {
  const runtime = useRuntime()
  const client = useQueryClient(), [feature, setFeature] = useState('')
  const query = useQuery({ queryKey: ['slices', runId], queryFn: () => request<SlicesData>(`/runs/${runId}/slices`), refetchInterval: q => q.state.data?.analyses?.some(a => a.status === 'PENDING' && a.job?.state !== 'FAILED') ? 700 : false })
  const create = useMutation({ mutationFn: (featureId: string) => request<SliceAnalysis>(`/runs/${runId}/slices`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ feature_id: featureId }) }), onSuccess: () => { void client.invalidateQueries({ queryKey: ['slices', runId] }) } })
  if (query.isPending) return <p role="status">Loading saved slice analyses…</p>
  if (query.isError) return <ErrorState error={query.error} retry={() => void query.refetch()} />
  const data = query.data
  if (data.status === 'UNAVAILABLE') return <><h2>Slices</h2><p>{data.reason}</p></>
  const selected = data.eligible_features.some(f => f.feature_id === feature) ? feature : data.eligible_features[0]?.feature_id ?? ''
  const analysis = data.analyses.find(a => a.feature_id === selected)
  return <><h2>Slices</h2><p className="notice">{data.limitation}</p><p>Only categorical model features included in the frozen schema are eligible. At least 30 labeled rows per slice are required. Product guardrail — not a universal statistical law.</p>
    <label htmlFor="slice-feature">Categorical model feature</label><select id="slice-feature" value={selected} onChange={e => setFeature(e.target.value)} disabled={!data.eligible_features.length}>{data.eligible_features.map(f => <option key={f.feature_id} value={f.feature_id}>{f.name}</option>)}</select>
    {!data.eligible_features.length && <p>No included categorical features are eligible.</p>}
    <MutationNotice /><button disabled={!runtime || runtime.read_only || !selected || create.isPending || Boolean(analysis)} onClick={() => create.mutate(selected)}>Analyze Slices</button>{create.isError && <ErrorState error={create.error} />}
    <h3>Previously analyzed features</h3><ul>{data.analyses.map(a => <li key={a.id}><button className="secondary" onClick={() => setFeature(a.feature_id)}>{a.feature_name} · {a.status}</button></li>)}</ul>
    {analysis?.status === 'READY' ? <SliceResults analysis={analysis} /> : analysis?.job?.state === 'FAILED' ? <ErrorState error={new Error(`Slice job could not finish. ${analysis.job.error_message ?? ""} The saved run remains unchanged. Inspect the worker and create a new monitoring run in Full Mode to repeat the workflow.`)} /> : analysis ? <p role="status">Slice analysis {analysis.job?.state}: {analysis.job?.stage}. No results appear until they are saved together.</p> : <p>Select an eligible feature and explicitly analyze its slices.</p>}</>
}

export function TrendChart({ data }: { data: TrendsData }) {
  const max = data.signal === 'missing_percent' ? 100 : data.signal === 'brier' && data.class_order.length > 2 ? 2 : data.signal === 'log_loss' ? Math.max(1, ...data.points.map(p => p.value ?? 0), data.reference?.value ?? 0) : 1
  const x = (i: number) => 125 + i * 530 / Math.max(1, data.points.length - 1), y = (v: number) => 235 - 195 * v / max
  return <><div className="plot-scroll"><svg className="trend-chart" viewBox="0 0 760 320" role="img" aria-label={`${metricName(data.signal)} across monitoring dates. Separate observed points; unavailable runs remain gaps. Square Mode A; circle Mode B. No interpolation.`}>
    <path d="M55 35 V235 H700" fill="none" stroke="#647084" /><text x="10" y="45">{number(max)}</text><text x="35" y="240">0</text>
    {data.reference?.value != null && <g><circle cx="72" cy={y(data.reference.value)} r="5" fill="var(--baseline)" /><text x="55" y="265">Baseline</text><text x="55" y="290">n={data.reference.n}</text></g>}
    {data.points.map((p, i) => <g key={p.run_id}><text x={x(i)} y="265" textAnchor="middle" fontSize="10">{p.monitoring_date}</text>{p.value == null ? <text x={x(i)} y="290" textAnchor="middle" fontSize="10">Unavailable</text> : p.mode === 'A' ? <rect x={x(i) - 5} y={y(p.value) - 5} width="10" height="10" fill="#647084" tabIndex={0} role="img" aria-label={`${p.name}, Mode A: ${number(p.value)}, n=${p.n}`} /> : <circle cx={x(i)} cy={y(p.value)} r="5" fill="var(--current)" tabIndex={0} role="img" aria-label={`${p.name}, Mode B: ${number(p.value)}, n=${p.n}`} />}</g>)}
  </svg></div><p>□ Mode A · ○ Mode B. Markers represent saved observations; no line connects unavailable points. Exact values and support follow.</p></>
}

function TrendSignals({ metadata, projectId }: { metadata: TrendsData; projectId: string }) {
  const [group, setGroup] = useState('confidence'), [signal, setSignal] = useState('median'), [feature, setFeature] = useState(''), [classLabel, setClassLabel] = useState('')
  const features = metadata.features.filter(f => signal === 'ks' ? f.type === 'numeric' : signal === 'js' ? f.type === 'categorical' : true)
  const selectedFeature = features.some(f => f.feature_id === feature) ? feature : features[0]?.feature_id ?? ''
  const selectedClass = metadata.class_order.includes(classLabel) ? classLabel : metadata.class_order[0]
  const params = new URLSearchParams({ group, signal })
  if (group === 'data') params.set('feature_id', selectedFeature)
  if (group === 'predictions') params.set('class_label', selectedClass)
  const query = useQuery({ queryKey: ['trend-signal', projectId, params.toString()], queryFn: () => request<TrendsData>(`/projects/${projectId}/trends?${params}`), enabled: group !== 'data' || Boolean(selectedFeature) })
  return <><h2>Trends</h2><p>One stored signal at a time, ordered by Monitoring Date, Creation Timestamp and Run ID. This is a factual history, without an overall reliability trend.</p>
    <div className="data-filters"><label>Signal group<select value={group} onChange={e => { setGroup(e.target.value); setSignal(metadata.options[e.target.value][0]) }}>{Object.keys(metadata.options).map(g => <option key={g} value={g}>{g === 'probability' ? 'Probability quality' : metricName(g)}</option>)}</select></label><label>Signal<select value={signal} onChange={e => setSignal(e.target.value)}>{metadata.options[group].map(s => <option key={s} value={s}>{metricName(s)}</option>)}</select></label>
    {group === 'data' && <label>Frozen model feature<select value={selectedFeature} onChange={e => setFeature(e.target.value)}>{features.map(f => <option key={f.feature_id} value={f.feature_id}>{f.name} · {f.type}</option>)}</select></label>}
    {group === 'predictions' && <label>Frozen class<select value={selectedClass} onChange={e => setClassLabel(e.target.value)}>{metadata.class_order.map(c => <option key={c}>{c}</option>)}</select></label>}</div>
    {query.isPending ? <p role="status">Loading selected stored signal…</p> : query.isError ? <ErrorState error={query.error} retry={() => void query.refetch()} /> : <>{query.data.warning && <p className="notice">{query.data.warning}</p>}<p>{query.data.limitation}</p>{query.data.reference ? <p>{query.data.reference.label}: {number(query.data.reference.value)} · n={query.data.reference.n ?? 'Unavailable'} {query.data.reference.reason}</p> : <p>{group === 'data' && ['ks', 'js'].includes(signal) ? 'No baseline self-comparison point is created for KS/JS.' : 'Baseline reference unavailable until stored monitoring observations exist.'}</p>}<TrendChart data={query.data} /><div className="table-scroll"><table><caption>{metricName(signal)} · stored values; unavailable runs remain gaps</caption><thead><tr><th scope="col">Run</th><th scope="col">Monitoring date</th><th scope="col">Mode</th><th scope="col">Value</th><th scope="col">n / support</th><th scope="col">Status / reason</th><th scope="col">Adjusted p</th></tr></thead><tbody>{query.data.points.map(p => <tr key={p.run_id}><th scope="row"><Link to={`/runs/${p.run_id}/overview`}>{p.name}</Link></th><td>{p.monitoring_date}</td><td>{p.mode ?? 'Pending'}</td><td className="numeric">{number(p.value)}</td><td className="numeric">{p.n ?? 'Unavailable'}</td><td>{p.status}{p.reason && <p>{p.reason}</p>}</td><td className="numeric">{number(p.adjusted_p)}</td></tr>)}</tbody></table></div></>}</>
}
export function Trends({ projectId }: { projectId: string }) {
  const query = useQuery({ queryKey: ['trend-metadata', projectId], queryFn: () => request<TrendsData>(`/projects/${projectId}/trends`) })
  return query.isPending ? <p role="status">Loading monitoring history…</p> : query.isError ? <ErrorState error={query.error} retry={() => void query.refetch()} /> : <TrendSignals metadata={query.data} projectId={projectId} />
}

const text = (v: unknown): string => v == null ? 'Unavailable' : Array.isArray(v) ? v.map(text).join(', ') : typeof v === 'object' ? Object.entries(v).map(([k, value]) => `${k.replaceAll('_', ' ')}: ${text(value)}`).join(' · ') : typeof v === 'number' ? Number.isInteger(v) ? String(v) : number(v) : String(v)
function StoredTable({ data }: { data: ReportTable }) {
  return <><div className={`table-scroll ${data.columns.length > 6 ? 'report-wide-table' : ''}`}><table><caption>{data.caption}</caption><thead><tr>{data.columns.map(c => <th scope="col" key={c}>{c}</th>)}</tr></thead><tbody>{data.rows.map((r, i) => <tr key={i}>{r.map((v, j) => j === 0 ? <th scope="row" key={j}>{text(v)}</th> : <td className={typeof v === "number" ? "numeric" : undefined} key={j}>{text(v)}</td>)}</tr>)}</tbody></table></div>{data.columns.length > 6 && <div className="print-table-alternative"><h4>{data.caption}</h4>{data.rows.map((r, i) => <dl key={i}>{data.columns.map((c, j) => <div key={c}><dt>{c}</dt><dd>{text(r[j])}</dd></div>)}</dl>)}</div>}</>
}
export function ReportView({ data }: { data: ReportData }) {
  const report = data.report
  const [preview, setPreview] = useState(false)
  return <article className="reliability-report"><style>{`${preview ? reportPrintStyles : `@media print { ${reportPrintStyles} }`} @media print { .print-preview-toolbar { display: none !important; } }`}</style>{preview && <div className="print-preview-toolbar"><p>Print layout preview · the same reviewed styles are used by browser print. Pagination depends on your browser and paper settings.</p><button className="print-return" onClick={() => setPreview(false)}>Return to report</button></div>}<div className="report-controls"><button onClick={() => window.print()}>Print / Save as PDF</button><button className="secondary" onClick={() => setPreview(true)}>Preview print layout</button><nav aria-label="Report sections">{report.sections.map(s => <a key={s.key} href={`#report-${s.key}`}>{s.title}</a>)}</nav></div><h2>Reliability Report</h2><p>Template {report.report_template_version} · Methodology {report.methodology_version} · Generated {report.generated_at}</p><p className="hash">Report code {report.code_version} · Run source code {report.source_code_version}</p>
    {report.sections.map(s => <section id={`report-${s.key}`} key={s.key}><h3>{s.title}</h3>{s.paragraphs.map((p, i) => <p key={i}>{p}</p>)}{s.findings.map((f, i) => <dl className="report-evidence" key={i}>{(['measured', 'result', 'evidence', 'may_conclude', 'cannot_conclude'] as const).map(k => <div key={k}><dt>{({ measured: 'Measured', result: 'Result', evidence: 'Evidence', may_conclude: 'May conclude', cannot_conclude: 'Cannot conclude' })[k as 'measured']}</dt><dd>{f[k]}</dd></div>)}</dl>)}{s.tables.map((t, i) => <StoredTable key={i} data={t} />)}{s.key === 'slices' && data.slice_analyses.map(a => <section key={a.id}><h4>Separate additive slice result · {a.feature_name}</h4><p>{a.limitation} · {a.methodology_version} · {a.published_at}</p><StoredTable data={{ caption: 'Saved slices · All rows reference and category order', columns: ['Slice', 'n', 'Class support', ...Object.keys(a.rows[0]?.metrics ?? {}).map(metricName), 'Availability / reason'], rows: a.rows.map(r => [sliceName(r), r.row_count, r.class_support, ...Object.keys(a.rows[0]?.metrics ?? {}).map(k => r.row_count < 30 ? 'Unavailable' : r.metrics[k]?.value == null ? `Unavailable — ${r.metrics[k]?.reason ?? 'No valid metric'}` : `${number(r.metrics[k].value)}${r.metrics[k].note ? ' · ' + r.metrics[k].note : ''}`), r.reason ?? r.status]) }} /></section>)}</section>)}<footer>{report.footer}</footer></article>
}
export function ReliabilityReport({ runId }: { runId: string }) {
  const query = useQuery({ queryKey: ['report', runId], queryFn: () => request<ReportData>(`/runs/${runId}/report`) })
  return query.isPending ? <p role="status">Loading stored report…</p> : query.isError ? <ErrorState error={query.error} retry={() => void query.refetch()} /> : <ReportView data={query.data} />
}
