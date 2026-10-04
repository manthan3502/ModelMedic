import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Projects, CreateProject } from './Projects'
import { Setup } from './Setup'

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
      : location.pathname === '/methodology' ? 'Methodology' : location.pathname.startsWith('/projects/') ? 'Baseline setup' : 'Page not found'
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
        <Route path="/projects/new" element={<CreateProject />} />
        <Route path="/projects/:id/setup/:step" element={<Setup />} />
        <Route path="/methodology" element={<Methodology />} />
        <Route path="*" element={<div className="prose"><h1>Page not found</h1><p>This address is not part of the workspace.</p><Link to="/projects">Back to Projects</Link></div>} />
      </Routes>
    </main>
  </>
}
