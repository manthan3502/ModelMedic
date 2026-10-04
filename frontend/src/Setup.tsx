import { useState } from 'react'
import { BaselineResultsView, Establish, TrainAction, DiscardReview } from './Training'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { models, request, saveConfig, type Classifier, type FeatureType, type Project, type Weighting } from './api/projects'

const steps = [ ['upload', 'Upload'], ['profile', 'Review data'], ['features', 'Target & features'], ['preprocessing', 'Preprocessing'], ['model', 'Model'], ['confirm', 'Confirm & train'], ['results', 'Baseline results'], ['establish', 'Establish baseline'] ]
const percent = (value: number) => `${(value * 100).toFixed(1)}%`

export function Setup() {
  const { id = '', step = 'upload' } = useParams()
  const query = useQuery({ queryKey: ['project', id], queryFn: () => request<Project>(`/projects/${id}`), refetchInterval: q => ['QUEUED', 'RUNNING'].includes(q.state.data?.job?.state ?? '') ? 1000 : false })
  if (query.isPending) return <p role="status">Loading project…</p>
  if (query.isError) return <div className="notice error" role="alert"><h1>Project unavailable</h1><p>{query.error.message}</p><button onClick={() => void query.refetch()}>Retry</button></div>
  const p = query.data
  const ready = p.dataset?.status === 'READY'
  const configured = Boolean(p.configuration.target_id)
  const completed: Record<string, boolean> = { upload: ready, profile: configured, features: configured, preprocessing: Boolean(p.configuration.classifier), model: Boolean(p.confirmation), confirm: Boolean(p.baseline?.results), results: Boolean(p.baseline?.results), establish: p.baseline?.status === "ESTABLISHED" }
  const available = (slug: string) => {
    if (['results', 'establish'].includes(slug)) return Boolean(p.baseline?.results)
    if (p.state !== 'DRAFT') return false
    return steps.some(([known]) => known === slug) && (slug === 'upload' || ready && (['profile', 'features'].includes(slug) || configured && (slug !== 'confirm' || Boolean(p.confirmation))))
  }
  return <><div className="page-heading"><div><p className="eyebrow">Baseline setup · {p.state}</p><h1>{p.name}</h1><p>{p.description}</p></div><Link to="/projects">All projects</Link></div>
    <div className="setup-layout"><aside className="stepper" aria-label="Baseline setup steps"><ol>{steps.map(([slug, title], i) => <li key={slug}>
      {available(slug) ? <Link to={`/projects/${id}/setup/${slug}`} aria-current={step === slug ? 'step' : undefined}><span className="mono">{i + 1}</span> {title} <small>{step === slug ? 'Current' : completed[slug] ? 'Complete' : 'Not started'}</small></Link>
        : <span><span className="mono">{i + 1}</span> {title}<small>{completed[slug] ? "Complete" : "Not started"}</small></span>}</li>)}</ol></aside>
      <div className="setup-content">{p.deletion_pending ? <div className="notice error" role="alert">Project deletion needs attention. Retry deletion from Upload.</div> : null}
        {!available(step) ? <div className="notice"><h2>{p.state === "BASELINE_READY" ? "Baseline is locked" : "Finish the preceding setup steps"}</h2><Link to={`/projects/${id}/setup/${p.state === "BASELINE_READY" ? "results" : "upload"}`}>{p.state === "BASELINE_READY" ? "Review frozen baseline" : "Go to Upload"}</Link></div>
          : step === 'results' ? <BaselineResultsView p={p} /> : step === 'establish' ? <Establish p={p} /> : step === 'upload' ? <Upload p={p} /> : step === 'profile' ? <Profile p={p} /> : step === 'features' ? <Features key={p.dataset?.id} p={p} />
            : step === 'preprocessing' ? <Preprocessing p={p} /> : step === 'model' ? <Model key={p.dataset?.id} p={p} /> : <Confirmation p={p} />}</div></div></>
}

function Upload({ p }: { p: Project }) {
  const client = useQueryClient()
  const navigate = useNavigate()
  const [discard, setDiscard] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const active = ['QUEUED', 'RUNNING'].includes(p.job?.state ?? '')
  const stageLabels: Record<string, string> = { READING_FILE: 'Reading file', CHECKING_COLUMNS: 'Checking columns', BUILDING_TYPED_COPY: 'Building typed copy', EXECUTING: 'Reading file' }
  const upload = useMutation({ mutationFn: () => request<Project>(`/projects/${p.id}/baseline?discard_results=${discard}`, { method: 'POST', headers: { 'Content-Type': 'text/csv' }, body: file }), onSuccess: value => { client.setQueryData(['project', p.id], value); void client.invalidateQueries({ queryKey: ['projects'] }) } })
  const deletion = useMutation({ mutationFn: () => request<void>(`/projects/${p.id}`, { method: 'DELETE' }), onSuccess: () => { void client.invalidateQueries({ queryKey: ['projects'] }); navigate('/projects') } })
  return <><h2>Upload Baseline CSV</h2><p>Choose a UTF-8 CSV with one header row and one observation per row. Only empty or whitespace-only cells count as missing.</p>
    <p>Computational limits: {p.limits.upload_max_bytes.toLocaleString()} bytes, {p.limits.max_rows.toLocaleString()} rows, {p.limits.max_columns} columns.</p>
    <p className="notice">Files stay in private application storage. Do not upload sensitive personal data to shared deployments.</p>
    <form className="panel" onSubmit={e => { e.preventDefault(); upload.mutate() }}><div className="dropzone" onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); if (!active) setFile(e.dataTransfer.files[0] ?? null) }}>
      <label htmlFor="baseline-file">Drop a CSV here or choose a file</label><input id="baseline-file" type="file" accept=".csv,text/csv" disabled={active || p.deletion_pending} onChange={e => setFile(e.target.files?.[0] ?? null)} /></div>
      {file && <p>{file.name} · {file.size.toLocaleString()} bytes</p>}{p.dataset && <p>Uploading again replaces the draft dataset selection and clears its configuration. Stored draft imports are removed when the project is deleted.</p>}
      <DiscardReview p={p} checked={discard} onChange={setDiscard} /><button disabled={Boolean(p.baseline?.results) && !discard || !file || active || upload.isPending || p.deletion_pending}>{upload.isPending ? 'Uploading…' : 'Upload and validate'}</button></form>
    {upload.isError && <p className="notice error" role="alert">{upload.error.message}</p>}
    {active && <p className="notice" role="status">Validating baseline: {p.job?.state === 'QUEUED' ? 'Waiting for worker' : stageLabels[p.job?.stage ?? ''] ?? 'Validation in progress'}.</p>}
    {p.job?.state === 'FAILED' && <p className="notice error" role="alert">Validation job could not finish. {p.job.error_message} Re-upload the CSV to retry.</p>}
    {p.dataset?.validation_report?.errors.length ? <div className="notice error" role="alert"><h3>Dataset needs attention</h3><ul>{p.dataset.validation_report.errors.map(e => <li key={e}>{e}</li>)}</ul></div> : null}
    {p.dataset?.status === 'READY' && <div className="notice"><h3>Dataset validated</h3><p>Canonical Parquet and dataset profile are ready. No rows were deleted.</p><Link className="button" to={`/projects/${p.id}/setup/profile`}>Review dataset profile</Link></div>}
    <div className="delete-draft"><button className="secondary" disabled={active || deletion.isPending} onClick={() => setConfirmDelete(true)}>Delete draft project</button>
      {confirmDelete && <div className="notice"><p>This removes the draft project and its stored datasets.</p><button onClick={() => deletion.mutate()} disabled={deletion.isPending}>Confirm deletion</button> <button className="secondary" onClick={() => setConfirmDelete(false)}>Keep project</button></div>}
      {deletion.isError && <p role="alert">{deletion.error.message}</p>}</div></>
}

function Profile({ p }: { p: Project }) {
  const data = p.dataset!.profile!
  return <><h2>Dataset Profile</h2><p>ModelMedic does not silently clean or delete your data. It shows what it found so you can decide what belongs in the model.</p>
    <dl className="summary-strip"><div><dt>Rows</dt><dd>{data.row_count.toLocaleString()}</dd></div><div><dt>Columns</dt><dd>{data.column_count}</dd></div><div><dt>Duplicate rows</dt><dd>{data.duplicate_rows}</dd></div><div><dt>Numeric / categorical</dt><dd>{data.columns.filter(c => c.inferred_type === 'numeric').length} / {data.columns.filter(c => c.inferred_type === 'categorical').length}</dd></div></dl>
    {data.duplicate_rows > 0 && <p className="notice">Duplicate rows are retained. Review the source to decide whether they represent repeated observations.</p>}
    <section className="notice" aria-label="Validation warnings"><h3>Review before configuring</h3><ul>{data.columns.filter(c => c.flags.length).map(c => <li key={c.feature_id}><b>{c.name}</b>: {c.flags.join(' ')}</li>)}</ul>{!data.columns.some(c => c.flags.length) && <p>No column warnings found.</p>}</section>
    <div className="table-scroll"><table><caption>Column profile</caption><thead><tr><th>Feature</th><th>Inferred type</th><th>Missing</th><th>Distinct</th><th>Sample values</th><th>Flags</th><th>Target eligibility</th></tr></thead><tbody>{data.columns.map(c => <tr key={c.feature_id}><th scope="row">{c.name}</th><td>{c.inferred_type}</td><td>{percent(c.missing_count / data.row_count)}</td><td>{c.distinct_count}</td><td>{c.samples.join(' · ')}</td><td>{c.flags.join(' ') || 'None'}</td><td>{c.target.eligible ? 'Eligible' : c.target.reasons.join(' ')}</td></tr>)}</tbody></table></div>
    <div className="table-scroll"><table><caption>First 10 rows · missing cells shown as —</caption><thead><tr>{data.columns.map(c => <th key={c.feature_id}>{c.name}</th>)}</tr></thead><tbody>{data.preview.map((row, i) => <tr key={i}>{row.map((v, j) => <td key={j}>{v ?? '—'}</td>)}</tr>)}</tbody></table></div>
    <p className="mono hash">{p.dataset!.canonical_schema_version} · SHA-256 {p.dataset!.canonical_sha256}</p><Link className="button" to={`/projects/${p.id}/setup/features`}>Select target and configure features</Link></>
}

function ClassCounts({ p, targetId }: { p: Project; targetId?: string }) {
  const target = p.dataset?.profile?.columns.find(c => c.feature_id === (targetId ?? p.configuration.target_id))?.target
  const counts = target?.classes ?? []
  return <>{target?.class_balance_note && <p className="notice">{target.class_balance_note}</p>}<div className="table-scroll"><table><caption>Target class distribution</caption><thead><tr><th>Class</th><th>Rows</th><th>Proportion</th></tr></thead><tbody>{counts.map(c => <tr key={c.label}><th scope="row">{c.label}</th><td>{c.count}</td><td>{percent(c.proportion)}</td></tr>)}</tbody></table></div></>
}

function Features({ p }: { p: Project }) {
  const columns = p.dataset!.profile!.columns
  const [discard, setDiscard] = useState(false)
  const [targetId, setTargetId] = useState(p.configuration.target_id ?? '')
  const [positive, setPositive] = useState(p.configuration.positive_class ?? '')
  const [features, setFeatures] = useState(p.configuration.features ?? columns.filter(c => c.allowed_types.length > 0).map(c => ({ feature_id: c.feature_id, type: c.inferred_type })))
  const target = columns.find(c => c.feature_id === targetId)
  const selected = features.filter(f => f.feature_id !== targetId)
  const encoded = selected.reduce((n, f) => n + (f.type === 'numeric' ? 1 : columns.find(c => c.feature_id === f.feature_id)!.distinct_count + 1), 0)
  const navigate = useNavigate()
  const client = useQueryClient()
  const save = useMutation({ mutationFn: () => saveConfig(p.id, { dataset_id: p.dataset!.id, target_id: targetId, positive_class: target?.target.classes.length === 2 ? positive : null, features: selected, classifier: null, weighting: null }, discard), onSuccess: value => { client.setQueryData(['project', p.id], value); navigate(`/projects/${p.id}/setup/preprocessing`) } })
  const positiveRequired = target?.target.classes.length === 2
  return <><h2>Target & Features</h2><form onSubmit={e => { e.preventDefault(); save.mutate() }}><label htmlFor="target">Target</label><select id="target" value={targetId} required onChange={e => { setTargetId(e.target.value); setPositive('') }}><option value="">Select target</option>{columns.map(c => <option key={c.feature_id} value={c.feature_id} disabled={!c.target.eligible}>{c.name}{!c.target.eligible ? ' — ineligible' : ''}</option>)}</select>
    <p>Choose the outcome you want to predict. Target eligibility and class support are shown in the dataset profile.</p>
    {target && <ClassCounts p={p} targetId={targetId} />}{positiveRequired && <><label htmlFor="positive">Binary positive class (required)</label><select id="positive" value={positive} required onChange={e => setPositive(e.target.value)}><option value="">Select positive class</option>{target.target.classes.map(c => <option key={c.label} value={c.label}>{c.label}</option>)}</select><p>Which outcome are you trying to catch? Precision, recall, F1 and false positives/negatives use this class as the event of interest.</p></>}
    <h3>Model inputs</h3><p>Unsupported features are excluded with a reason. Review identifiers and constants before choosing inputs.</p>
    <div className="table-scroll"><table><thead><tr><th>Include</th><th>Feature</th><th>Type</th><th>Flags / reason</th></tr></thead><tbody>{columns.filter(c => c.feature_id !== targetId).map(c => {
      const chosen = selected.find(f => f.feature_id === c.feature_id)
      return <tr key={c.feature_id}><td><input aria-label={`Include ${c.name}`} type="checkbox" disabled={!c.allowed_types.length} checked={Boolean(chosen)} onChange={e => setFeatures(e.target.checked ? [...features.filter(f => f.feature_id !== c.feature_id), { feature_id: c.feature_id, type: c.inferred_type }] : features.filter(f => f.feature_id !== c.feature_id))} /></td><th scope="row">{c.name}</th><td><select aria-label={`Type for ${c.name}`} disabled={!chosen || !c.allowed_types.length} value={chosen?.type ?? c.inferred_type} onChange={e => setFeatures(features.map(f => f.feature_id === c.feature_id ? { ...f, type: e.target.value as FeatureType } : f))}>{(c.allowed_types.length ? c.allowed_types : [c.inferred_type]).map(t => <option key={t} value={t}>{t === 'numeric' ? 'Numeric' : 'Categorical'}</option>)}</select></td><td>{c.flags.join(' ') || 'Supported'}</td></tr>
    })}</tbody></table></div>
    <div className="sticky-summary"><p>{selected.length} / {p.limits.max_features} included · {selected.filter(f => f.type === 'numeric').length} numeric · {selected.filter(f => f.type === 'categorical').length} categorical · ~{encoded} encoded columns / {p.limits.max_encoded_columns.toLocaleString()} computational limit (including categorical missing buckets)</p>
      {save.isError && <p role="alert" className="notice error">{save.error.message}</p>}<DiscardReview p={p} checked={discard} onChange={setDiscard} /><button disabled={Boolean(p.baseline?.results) && !discard || !target || !selected.length || positiveRequired && !positive || save.isPending}>Review preprocessing</button></div></form></>
}

function Preprocessing({ p }: { p: Project }) {
  const summary = p.preprocessing!
  return <><h2>Preprocessing Review</h2><ol className="pipeline">{summary.steps.map(s => <li key={s}>{s}</li>)}</ol><div className="panel"><h3>Numeric features</h3><p>{summary.numeric}</p><h3>Categorical features</h3><p>{summary.categorical}</p></div><p className="notice">{summary.learning}</p><p className="notice">{summary.frozen}</p><p>{p.baseline?.results ? "These are the preprocessing rules used for this trained draft." : "These deterministic rules are a review only. No imputers, encoders or scalers have been fitted."}</p><Link className="button" to={`/projects/${p.id}/setup/model`}>Select classifier and weighting</Link></>
}

function Model({ p }: { p: Project }) {
  const [discard, setDiscard] = useState(false)
  const [classifier, setClassifier] = useState<Classifier | ''>(p.configuration.classifier ?? '')
  const [weighting, setWeighting] = useState<Weighting | ''>(p.configuration.weighting ?? '')
  const navigate = useNavigate()
  const client = useQueryClient()
  const save = useMutation({ mutationFn: () => saveConfig(p.id, { dataset_id: p.dataset!.id, target_id: p.configuration.target_id!, positive_class: p.configuration.positive_class ?? null, features: p.configuration.features!, classifier: classifier as Classifier, weighting: weighting as Weighting }, discard), onSuccess: value => { client.setQueryData(['project', p.id], value); navigate(`/projects/${p.id}/setup/confirm`) } })
  return <><h2>Model & Weighting</h2><form onSubmit={e => { e.preventDefault(); save.mutate() }}><fieldset><legend>Classifier</legend><div className="model-options">{models.map(m => <label className="model-option" key={m.value}><span><input name="classifier" type="radio" value={m.value} checked={classifier === m.value} onChange={() => setClassifier(m.value)} required /> <b>{m.name}</b></span><p>{m.description}</p><p>{m.tradeoff}</p></label>)}</div></fieldset>
    <fieldset><legend>Class weighting</legend>{(['standard', 'balanced'] as const).map(w => <label className="radio-label" key={w}><input name="weighting" type="radio" checked={weighting === w} onChange={() => setWeighting(w)} required /> {w === 'standard' ? 'Standard' : 'Balanced'}</label>)}<p>Standard treats observations equally. Balanced accounts for class frequencies during fitting. No model is recommended from these counts.</p></fieldset><ClassCounts p={p} />
    {save.isError && <p role="alert" className="notice error">{save.error.message}</p>}<DiscardReview p={p} checked={discard} onChange={setDiscard} /><button disabled={Boolean(p.baseline?.results) && !discard || !classifier || !weighting || save.isPending}>Review and train</button></form></>
}

function Confirmation({ p }: { p: Project }) {
  const config = p.configuration
  const confirmation = p.confirmation!
  const columns = p.dataset!.profile!.columns
  return <><h2>Training Confirmation</h2><p>Training uses this configuration. Review it before starting.</p><dl className="confirmation panel"><dt>Target</dt><dd>{columns.find(c => c.feature_id === config.target_id)?.name}</dd><dt>Positive class</dt><dd>{config.positive_class ?? 'Not applicable (multiclass)'}</dd><dt>Classifier</dt><dd>{models.find(m => m.value === config.classifier)?.name}</dd><dt>Weighting</dt><dd>{config.weighting === 'balanced' ? 'Balanced' : 'Standard'}</dd><dt>Inputs</dt><dd>{config.features?.map(f => `${columns.find(c => c.feature_id === f.feature_id)?.name} (${f.type})`).join(', ')}</dd><dt>Encoded columns estimate</dt><dd>{config.encoded_columns}</dd><dt>Split</dt><dd>{confirmation.split}</dd><dt>Development diagnostics</dt><dd>{confirmation.cv}</dd><dt>Random seed</dt><dd>{confirmation.seed}</dd></dl>
    <p className="notice">{confirmation.guardrail}</p><TrainAction p={p} /></>
}
