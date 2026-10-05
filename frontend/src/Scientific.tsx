import type { ReactNode } from 'react'

export function SignalStatus({ status }: { status: string }) {
  const icons: Record<string, string> = { DETECTED: '△', 'NOT DETECTED': '○', 'INSUFFICIENT DATA': '◌', UNAVAILABLE: '⊘' }
  if (!icons[status]) return <span>{status}</span>
  return <span className={`signal-status ${status.toLowerCase().replaceAll(' ', '-')}`} aria-label={`Scientific status: ${status}`}><span aria-hidden="true">{icons[status]}</span><span>{status}</span></span>
}
export function Evidence({ measured, result, evidence, may, cannot }: { measured: string; result: ReactNode; evidence: ReactNode; may: string; cannot: string }) {
  return <section className="evidence-frame" aria-label="Evidence frame"><dl><dt>Measured</dt><dd>{measured}</dd><dt>Result</dt><dd>{result}</dd><dt>Evidence</dt><dd>{evidence}</dd><dt>May conclude</dt><dd>{may}</dd><dt>Cannot conclude</dt><dd>{cannot}</dd></dl></section>
}
