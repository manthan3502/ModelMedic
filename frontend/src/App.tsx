import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { readReadiness } from './api/health'

function Projects() {
  const service = useQuery({ queryKey: ['readiness'], queryFn: readReadiness, retry: false })
  return <>
    <div className="page-heading">
      <div><p className="eyebrow">ML reliability workspace</p><h1>Projects</h1>
        <p>One baseline. Every newer dataset. Evidence you can inspect.</p></div>
      <div className="create-action"><button disabled aria-describedby="create-note">New project</button>
        <span id="create-note">Project setup arrives in the next milestone.</span></div>
    </div>
    {service.isPending && <p className="notice" role="status">Connecting to the workspace service…</p>}
    {service.isError && <div className="notice error" role="alert">
      <strong>The workspace service is unavailable.</strong>
      <p>This page hasn’t changed any data. Check that the API and database are running, then retry.</p>
      <button className="secondary" onClick={() => void service.refetch()}>Retry connection</button>
    </div>}
    <section className="project-list" aria-labelledby="empty-title">
      <div className="list-label">Project workspace <span className="mono">M0 / FOUNDATION</span></div>
      <div className="empty-state">
        <svg width="36" height="36" viewBox="0 0 36 36" fill="none" aria-hidden="true">
          <path d="M5 9h10l3 4h13v17H5V9Z" stroke="currentColor" strokeWidth="1.5" />
          <path d="M11 19h14M11 24h9" stroke="currentColor" strokeWidth="1.5" />
        </svg>
        <h2 id="empty-title">Your reliability workspace starts here</h2>
        <p>A project holds one baseline model and every newer dataset you compare against it.</p>
        <p className="foundation-note">The application foundation is in place. Project creation and dataset setup are not available yet.</p>
      </div>
      <ol className="workflow" aria-label="Planned project workflow">
        <li><span className="step-number">01</span><div><h3>Establish a baseline</h3><p>Freeze a model and its reference data.</p></div></li>
        <li><span className="step-number">02</span><div><h3>Check newer data</h3><p>Compare each dataset with that baseline.</p></div></li>
        <li><span className="step-number">03</span><div><h3>Read the evidence</h3><p>Keep data change and performance distinct.</p></div></li>
      </ol>
    </section>
    <p className="footnote">ModelMedic reports separate reliability signals. Data drift alone does not prove model degradation.</p>
  </>
}

function Methodology() {
  return <div className="prose"><p className="eyebrow">Reference</p><h1>Methodology</h1>
    <p className="lead">Evidence, not manufactured certainty.</p>
    <p>The methodology and glossary page will be added in a later milestone. The locked product and architecture specifications in the repository remain the source of truth.</p>
    <p>ModelMedic distinguishes changes in data, predictions, confidence and measured performance. Actual predictive performance requires ground-truth labels.</p>
    <Link to="/projects">Back to Projects</Link></div>
}

export function App() {
  const location = useLocation()
  const main = useRef<HTMLElement>(null)
  const previousPath = useRef(location.pathname)
  const [menuOpen, setMenuOpen] = useState(false)
  useEffect(() => {
    const title = location.pathname === '/projects' ? 'Projects'
      : location.pathname === '/methodology' ? 'Methodology' : 'Page not found'
    document.title = `${title} · ModelMedic`
    if (previousPath.current !== location.pathname) main.current?.focus()
    previousPath.current = location.pathname
    setMenuOpen(false)
  }, [location.pathname])

  return <>
    <a className="skip-link" href="#main-content">Skip to content</a>
    <header className="topbar"><div className="topbar-inner">
      <Link className="brand" to="/projects">ModelMedic<span className="brand-rule" aria-hidden="true" /></Link>
      <button className="menu-toggle secondary" aria-expanded={menuOpen} aria-controls="global-nav"
        onClick={() => setMenuOpen(!menuOpen)}>Menu</button>
      <nav id="global-nav" aria-label="Main navigation" className={menuOpen ? 'open' : ''}>
        <NavLink to="/projects">Projects</NavLink><NavLink to="/methodology">Methodology</NavLink>
      </nav>
    </div></header>
    <main id="main-content" ref={main} tabIndex={-1}>
      <Routes>
        <Route path="/" element={<Navigate to="/projects" replace />} />
        <Route path="/projects" element={<Projects />} />
        <Route path="/methodology" element={<Methodology />} />
        <Route path="*" element={<div className="prose"><h1>Page not found</h1><p>This address is not part of the workspace.</p><Link to="/projects">Back to Projects</Link></div>} />
      </Routes>
    </main>
  </>
}
