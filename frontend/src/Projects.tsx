import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { readReadiness } from './api/health'
import { models, request, type Project } from './api/projects'

export function Projects() {
  const service = useQuery({ queryKey: ['readiness'], queryFn: readReadiness, retry: false })
  const projects = useQuery({ queryKey: ['projects'], queryFn: () => request<Project[]>('/projects'), retry: false })
  return <>
    <div className="page-heading"><div><p className="eyebrow">ML reliability workspace</p><h1>Projects</h1>
      <p>One baseline. Every newer dataset. Evidence you can inspect.</p></div><Link className="button" to="/projects/new">New project</Link></div>
    {(service.isPending || projects.isPending) && <p className="notice" role="status">Connecting to the workspace service…</p>}
    {(service.isError || projects.isError) && <div className="notice error" role="alert"><strong>The workspace service is unavailable.</strong>
      <p>Check that the API and database are running, then retry.</p><button className="secondary" onClick={() => { void service.refetch(); void projects.refetch() }}>Retry connection</button></div>}
    <section className="project-list" aria-label="Project workspace"><div className="list-label">Project workspace <span className="mono">BASELINE / MONITORING</span></div>
      {Array.isArray(projects.data) && projects.data.length > 0 ? <div className="table-scroll"><table><thead><tr><th>Project name + description</th><th>State</th><th>Model</th><th>Target</th><th>Baseline established</th><th>Run count</th><th>Last activity</th></tr></thead>
        <tbody>{projects.data.map(p => <tr key={p.id}><td><Link to={p.baseline?.status === "ESTABLISHED" ? `/projects/${p.id}/overview` : `/projects/${p.id}/setup/${p.baseline?.results ? "results" : "upload"}`}>{p.name}</Link><p>{p.description}</p></td><td>{p.state}</td><td>{models.find(m => m.value === p.configuration.classifier)?.name ?? 'Not selected'}</td>
          <td>{p.dataset?.profile?.columns.find(c => c.feature_id === p.configuration.target_id)?.name ?? 'Not selected'}</td><td>{p.baseline?.established_at ? new Date(p.baseline.established_at).toLocaleString() : "Not established"}</td><td>{p.run_count ?? 0}</td><td>{new Date(p.updated_at).toLocaleString()}</td></tr>)}</tbody></table></div>
        : !projects.isError && !projects.isPending && <><div className="empty-state"><h2>No projects yet</h2><p>A project holds one baseline model and every newer dataset you compare against it.</p></div>
          <ol className="workflow" aria-label="Project workflow"><li><span className="step-number">01</span><div><h3>Establish a baseline</h3><p>Freeze a model and its reference data.</p></div></li><li><span className="step-number">02</span><div><h3>Check newer data</h3><p>Compare each dataset with that baseline.</p></div></li><li><span className="step-number">03</span><div><h3>Read the evidence</h3><p>Keep data change and performance distinct.</p></div></li></ol></>}
    </section><p className="footnote">Data drift alone does not prove model degradation.</p>
  </>
}

export function CreateProject() {
  const navigate = useNavigate()
  const client = useQueryClient()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const create = useMutation({ mutationFn: () => request<Project>('/projects', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, description }) }),
    onSuccess: p => { void client.invalidateQueries({ queryKey: ['projects'] }); navigate(`/projects/${p.id}/setup/upload`) } })
  return <><p className="eyebrow">New prediction problem</p><h1>Create Project</h1><div className="create-layout"><form className="panel" onSubmit={e => { e.preventDefault(); create.mutate() }}>
    <label htmlFor="project-name">Name</label><input id="project-name" value={name} onChange={e => setName(e.target.value)} required maxLength={200} autoComplete="off" />
    <label htmlFor="project-description">Description (optional)</label><textarea id="project-description" value={description} onChange={e => setDescription(e.target.value)} maxLength={2000} rows={3} />
    {create.isError && <p role="alert" className="notice error">{create.error.message}</p>}
    <button disabled={create.isPending || !name.trim()}>{create.isPending ? 'Creating project…' : 'Create project and upload baseline'}</button></form>
    <aside className="prose"><h2>One project, one prediction problem</h2><p>A ModelMedic project is one prediction problem: one target, one frozen baseline model and every later dataset compared against it.</p><p>Start with the dataset that will become your baseline reference.</p></aside></div></>
}
