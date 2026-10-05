import { createContext, useContext } from 'react'

export type Interpretation = { may: string; cannot: string }
export const PresentationContext = createContext<Record<string, Interpretation> | null>(null)
export function useInterpretation(section: string): Interpretation {
  return useContext(PresentationContext)?.[section] ?? { may: 'The reviewed interpretation is unavailable. No additional scientific conclusion is shown.', cannot: 'Inspect the saved evidence and retry loading the reviewed interpretation.' }
}
