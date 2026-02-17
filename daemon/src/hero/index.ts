// daemon/src/hero/index.ts
// Hero modules: stances, not classes. The agent shifts fluidly.
//
// One loop, many postures. The agent wears the stance,
// not the other way around.

export { STANCES, getStance, filterTools } from "./stance"
export type { StanceConfig } from "./stance"

export { detectShift, applyShift } from "./shift"
export type { StanceTransition } from "./shift"

export { SessionTracker } from "./session"

export { dream } from "./dream"
export type { DreamResult, DreamPhase, DreamStep } from "./dream"

export { speak, AUDIENCES } from "./speak"
export type { SpeakResult, KeyShift } from "./speak"
