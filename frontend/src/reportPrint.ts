// One reviewed stylesheet for browser print and its onscreen preview.
export const reportPrintStyles = `
@page { margin: 15mm; }
  .topbar, .skip-link, .run-navigation, .report-controls, main > .eyebrow, main > .page-heading, main > .mode-banner { display: none !important; }
  body, main, .run-layout, .run-content, .reliability-report { width: auto; max-width: none; margin: 0; padding: 0; display: block; background: white; color: black; }
  .reliability-report { font-size: 10pt; line-height: 1.45; }
  .reliability-report section { margin: 1.2rem 0; }
  .reliability-report h2, .reliability-report h3, .reliability-report h4, .reliability-report caption { break-after: avoid; color: black; }
  .reliability-report table { min-width: 0; width: 100%; font-size: 9pt; border-collapse: collapse; }
  .reliability-report th, .reliability-report td { min-width: 0; border: 1px solid black; color: black; background: white; padding: .3rem; }
  .reliability-report tr, .report-evidence div { break-inside: avoid; }
  .reliability-report .table-scroll { overflow: visible; }
  .report-wide-table { display: none !important; }
  .print-table-alternative { display: block; }
  .print-table-alternative dl { border: 1px solid black; padding: .5rem; }
  .print-table-alternative dl div { display: grid; grid-template-columns: 40% 60%; }
  .print-table-alternative dt { font-weight: bold; }
  .print-table-alternative dt, .print-table-alternative dd { min-width: 0; overflow-wrap: anywhere; }
  .print-table-alternative dd { margin: 0; }
  .reliability-report a { color: black; text-decoration: underline; }
`
