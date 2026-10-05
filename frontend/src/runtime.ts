import { createContext, useContext } from 'react'
export const demoExplanation = 'This action is disabled in the public portfolio demo. Run ModelMedic locally to upload your own data.'
export type Runtime = { deployment_mode: 'FULL_MODE' | 'DEMO_MODE'; read_only: boolean }
// Isolated page components can be tested in Full Mode; the app always supplies
// a fail-closed runtime context obtained from the server.
export const RuntimeContext = createContext<Runtime | null>({ deployment_mode: 'FULL_MODE', read_only: false })
export const useRuntime = () => useContext(RuntimeContext)
