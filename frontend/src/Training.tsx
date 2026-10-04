import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { models, request, type Metric, type Project, type BaselineResults } from './api/projects'

const stages = [['VALIDATING', 'Checking data'], ['SPLITTING', 'Splitting data'], ['CROSS_VALIDATING', 'Running 5-fold CV'], ['TRAINING', 'Fitting final model'], ['EVALUATING', 'Evaluating held-out reference'], ['CALIBRATION', 'Checking calibration'], ['IMPORTANCE', 'Measuring feature reliance'], ['PERSISTING', 'Saving baseline'], ['COMPLETE', 'Done']]
const value = (n: number | undefined | null) => n == null ? 'Unavailable' : n.toFixed(4)
const title = (key: string) => key.replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase())
function Reading({ metric }: { metric: Metric }) { return <>{metric.value == null ? `Unavailable — ${metric.reason}` : value(metric.value)}</> }

export function DiscardReview({ p, checked, onChange }: { p: Project; checked: boolean; onChange: (checked: boolean) => void }) {
  return p.baseline?.results ? <label className="notice discard-review"><input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} /> I understand that changing this dependency discards the draft training results. The new configuration must be trained before establishment.</label> : null
}

export function TrainAction({ p }: { p: Project }) {
  const client = useQueryClient()
  const [discard, setDiscard] = useState(false)
  const [now, setNow] = useState(Date.now())
  const active = ['QUEUED', 'RUNNING'].includes(p.job?.state ?? '')
  useEffect(() => { if (!active) return; const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer) }, [active])
  const train = useMutation({ mutationFn: () => request<Project>(`/projects/${p.id}/train?discard_results=${discard}`, { method: 'POST' }), onSuccess: result => client.setQueryData(['project', p.id], result) })
  const current = stages.findIndex(([key]) => key === p.job?.stage)
  return <section aria-label="Baseline training"><DiscardReview p={p} checked={discard} onChange={setDiscard} />
    <button disabled={active || train.isPending || !p.confirmation?.training_available || Boolean(p.baseline?.results) && !discard} onClick={() => train.mutate()}>Train baseline</button>
    {train.isError && <p className="notice error" role="alert">{train.error.message}</p>}
    {p.job?.job_type === 'BASELINE_TRAIN' && <><p role="status" className="notice">{p.job.state === 'QUEUED' ? 'Waiting for worker' : p.job.state === 'FAILED' ? 'Training needs attention' : stages[current]?.[1] ?? 'Starting worker'}{active && p.job.started_at ? ` · ${Math.max(0, Math.floor((now - Date.parse(p.job.started_at)) / 1000))} seconds elapsed` : ''}</p>
      <ol className="training-stages">{stages.map(([key, label], i) => <li key={key} aria-current={i === current ? 'step' : undefined}>{label} <small>{i < current || p.job?.state === 'SUCCEEDED' ? 'Complete' : i === current && active ? 'In progress' : 'Not started'}</small></li>)}</ol></>}
    {p.job?.state === 'FAILED' && <p role="alert" className="notice error">{p.job.error_message}</p>}
    {p.baseline?.results && <Link className="button" to={`/projects/${p.id}/setup/results`}>Review baseline results</Link>}
  </section>
}

function Metrics({ data }: { data: BaselineResults }) {
  return <div className="table-scroll"><table><caption>Held-out Baseline Reference · n = {data.heldout_count}</caption><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>{Object.entries(data.metrics.metrics).map(([name, metric]) => <tr key={name}><th scope="row">{title(name)}{name === 'brier' && <small>Probabilistic prediction quality</small>}</th><td><Reading metric={metric} /></td></tr>)}</tbody></table></div>
}

function Performance({ data }: { data: BaselineResults }) {
  const maximum = Math.max(1, ...data.metrics.confusion_matrix.flat())
  return <><h3>Held-out Baseline Reference — official baseline</h3><Metrics data={data} />
    <div className="table-scroll"><table><caption>Class metrics · frozen class order</caption><thead><tr><th>Class</th><th>Precision</th><th>Recall</th><th>F1</th><th>Support</th></tr></thead><tbody>{data.metrics.per_class.map(c => <tr key={c.class}><th scope="row">{c.class}</th><td><Reading metric={c.precision} /></td><td><Reading metric={c.recall} /></td><td><Reading metric={c.f1} /></td><td>{c.support}</td></tr>)}</tbody></table></div>
    <div className="table-scroll"><table><caption>Confusion matrix · rows = actual, columns = predicted</caption><thead><tr><th>Actual / predicted</th>{data.class_order.map(c => <th key={c}>{c}</th>)}</tr></thead><tbody>{data.metrics.confusion_matrix.map((row, i) => <tr key={data.class_order[i]}><th scope="row">{data.class_order[i]}</th>{row.map((n, j) => <td key={j} style={{ background: `rgba(73,87,123,${0.05 + 0.3 * n / maximum})` }}>{n}</td>)}</tr>)}</tbody></table></div>
    <section className="cv-diagnostics"><h3>Development CV — diagnostics only</h3><p>Five stratified folds within the Development Set. Each fold fits its own preprocessing and model. These results do not select or tune a model.</p>
      {Object.entries(data.cv).map(([name, summary]) => <div className="cv-row" key={name}><h4>{title(name)}</h4>{summary.reason ? <p>Unavailable — {summary.reason}</p> : <><svg viewBox="0 0 500 58" role="img" aria-label={`${title(name)} five fold values: ${summary.values.map(value).join(', ')}`}><line x1="20" x2="480" y1="26" y2="26" stroke="#c6cad4" />{summary.values.map((n, i) => <circle key={i} cx={20 + 460 * ((n ?? 0) - (summary.min ?? 0)) / ((summary.max ?? 1) - (summary.min ?? 0) || 1)} cy={18 + i * 4} r="4" fill="#49577b"><title>Fold {i + 1}: {value(n)}</title></circle>)}</svg><p>Mean {value(summary.mean)} · SD {value(summary.sd)} · min–max {value(summary.min)}–{value(summary.max)}</p><p className="mono">{summary.values.map((n, i) => `Fold ${i + 1}: ${value(n)}`).join(' · ')}</p></>}</div>)}
    </section></>
}

function Calibration({ data }: { data: BaselineResults }) {
  const [selected, setSelected] = useState(data.calibration.classes[0].class)
  const curve = data.calibration.classes.find(c => c.class === selected)!
  return <><h3>Reliability diagram</h3><p>Held-out observations only · n = {data.calibration.support} · {data.calibration.requested_bins} requested quantile bins. Tied boundaries are combined and empty bins omitted.</p>
    <label htmlFor="calibration-class">{data.class_order.length === 2 ? 'Positive class' : 'One-vs-rest class'}</label><select id="calibration-class" value={selected} onChange={e => setSelected(e.target.value)}>{data.calibration.classes.map(c => <option key={c.class}>{c.class}</option>)}</select>
    <p>{curve.positive_count} positive · {curve.non_positive_count} non-positive</p>{data.calibration.warning && <p className="notice">{data.calibration.warning}</p>}
    {curve.reason ? <p className="notice">{curve.reason}</p> : <><svg className="reliability" viewBox="0 0 480 330" role="img" aria-label={`Reliability diagram for ${selected}; exact bin values in the following table`}><line x1="55" y1="275" x2="440" y2="25" stroke="#9ca3b4" strokeDasharray="5 5" /><path d="M55 25 V275 H440" fill="none" stroke="#647084" /><text x="55" y="295">0</text><text x="430" y="295">1</text><text x="35" y="32">1</text><text x="185" y="322">Mean predicted probability</text><text transform="translate(16 205) rotate(-90)">Observed event rate</text><polyline points={curve.bins.map(b => `${55 + 385 * b.mean_probability},${275 - 250 * b.observed_rate}`).join(' ')} fill="none" stroke="#49577b" strokeWidth="2" />{curve.bins.map((b, i) => <circle key={i} cx={55 + 385 * b.mean_probability} cy={275 - 250 * b.observed_rate} r="5" fill="#49577b"><title>n = {b.count}</title></circle>)}</svg>
    <div className="table-scroll"><table><caption>Reliability bins · every observation counted once</caption><thead><tr><th>Bin</th><th>Mean probability</th><th>Observed rate</th><th>n</th></tr></thead><tbody>{curve.bins.map((b, i) => <tr key={i}><th scope="row">{i + 1}</th><td>{value(b.mean_probability)}</td><td>{value(b.observed_rate)}</td><td>{b.count}</td></tr>)}</tbody></table></div></>}
    <p>Brier Score — probabilistic prediction quality: <Reading metric={data.metrics.metrics.brier} /></p><p>Log Loss: <Reading metric={data.metrics.metrics.log_loss} /></p><p>No recalibration is performed.</p></>
}

function Reliance({ data }: { data: BaselineResults }) {
  const low = Math.min(0, ...data.importance.map(v => v.mean - v.sd))
  const high = Math.max(0, ...data.importance.map(v => v.mean + v.sd))
  const x = (n: number) => 20 + 460 * (n - low) / (high - low || 1)
  return <><h3>Model reliance estimate — not causal importance.</h3><p>Held-out raw project features through the full frozen pipeline. Balanced accuracy · 10 repeats · seed 42. Whiskers show ±1 SD across permutations, not confidence intervals.</p>
    {data.importance.map(v => <div className="cv-row" key={v.feature}><h4>{v.feature}</h4><svg viewBox="0 0 500 48" role="img" aria-label={`${v.feature}: mean ${value(v.mean)}, SD ${value(v.sd)}`}><line x1={x(0)} x2={x(0)} y1="0" y2="48" stroke="#929bad" strokeDasharray="3 3" /><line x1={x(v.mean - v.sd)} x2={x(v.mean + v.sd)} y1="24" y2="24" stroke="#49577b" strokeWidth="2" /><circle cx={x(v.mean)} cy="24" r="5" fill="#49577b" /></svg><p>Mean {value(v.mean)} · SD {value(v.sd)}</p></div>)}<p>Axis {value(low)} to {value(high)} · dashed line = zero. Negative importance values are retained.</p></>
}

export function BaselineResultsView({ p }: { p: Project }) {
  const [tab, setTab] = useState('Summary')
  const data = p.baseline!.results!
  return <><h2>Baseline Results</h2><div className="reference-ribbon"><strong>Official baseline = Held-out Baseline Reference</strong><span>Development CV = diagnostics only</span></div>
    {data.warnings.map(w => <p key={w} className="notice">{w}</p>)}<div className="result-tabs" aria-label="Baseline result sections">{['Summary', 'Performance', 'Calibration', 'Model reliance', 'Data reference'].map(t => <button className="secondary" key={t} aria-pressed={tab === t} onClick={() => setTab(t)}>{t}</button>)}</div>
    {tab === 'Summary' && <><h3>{models.find(m => m.value === p.configuration.classifier)?.name} · {p.configuration.weighting} weighting</h3><p>Target: {String(data.manifest.target)} · Positive class: {p.configuration.positive_class ?? 'Not applicable (multiclass)'}</p><dl className="summary-strip"><div><dt>Development Set</dt><dd>{data.development_count}</dd></div><div><dt>Held-out reference</dt><dd>{data.heldout_count}</dd></div><div><dt>Seed</dt><dd>42</dd></div></dl><p>{Object.entries(data.heldout_class_counts).map(([c, n]) => `${c}: ${n} held-out observations`).join(' · ')}</p><Metrics data={data} /></>}
    {tab === 'Performance' && <Performance data={data} />}{tab === 'Calibration' && <Calibration data={data} />}{tab === 'Model reliance' && <Reliance data={data} />}
    {tab === 'Data reference' && <><h3>Frozen schema and reproducibility</h3><div className="table-scroll"><table><caption>Features before preprocessing</caption><thead><tr><th>Feature</th><th>Type</th><th>Missing baseline rows</th></tr></thead><tbody>{data.features.map(f => <tr key={f.feature_id}><th>{f.name}</th><td>{f.frozen_type}</td><td>{f.missing_count}</td></tr>)}</tbody></table></div><div className="table-scroll"><table><caption>Class counts · frozen probability order</caption><thead><tr><th>Class</th><th>Full baseline</th><th>Development</th><th>Held-out</th></tr></thead><tbody>{data.class_order.map(c => <tr key={c}><th>{c}</th><td>{data.class_counts[c]}</td><td>{data.development_class_counts[c]}</td><td>{data.heldout_class_counts[c]}</td></tr>)}</tbody></table></div><p>Stable row IDs, split membership, held-out predictions and probabilities are persisted with this snapshot. Scientific outputs are stored, not recomputed when viewed.</p><dl className="confirmation panel">{Object.entries(data.manifest).map(([key, v]) => <div key={key}><dt>{title(key)}</dt><dd className="hash">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</dd></div>)}</dl></>}
    {p.state === 'DRAFT' ? <Link className="button" to={`/projects/${p.id}/setup/establish`}>Review and establish baseline</Link> : <p className="notice">Baseline established. Its model, settings and reference are frozen. Create a new project for a different baseline. Open the project to create monitoring runs.</p>}
  </>
}

export function Establish({ p }: { p: Project }) {
  const client = useQueryClient()
  const navigate = useNavigate()
  const establish = useMutation({ mutationFn: () => request<Project>(`/projects/${p.id}/establish`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ snapshot_id: p.baseline!.id }) }), onSuccess: result => { client.setQueryData(['project', p.id], result); void client.invalidateQueries({ queryKey: ['projects'] }); navigate(`/projects/${p.id}/setup/results`) } })
  return <><h2>Establish Baseline</h2><div className="establish-review"><section className="panel"><h3>This becomes frozen</h3><ul><li>Model and weighting</li><li>Preprocessing</li><li>Features and types</li><li>Target and positive class</li><li>Class order and baseline reference</li></ul></section><section className="panel"><h3>You can still do</h3><p>Inspect the baseline results.</p><p>Create monitoring runs and inspect their history against this same baseline.</p></section></div><p className="notice">Locking keeps later comparisons fair because every new run is evaluated against the same model, preprocessing and reference.</p>{establish.isError && <p role="alert" className="notice error">{establish.error.message}</p>}<button disabled={p.state !== 'DRAFT' || establish.isPending} onClick={() => establish.mutate()}>Establish baseline</button></>
}
