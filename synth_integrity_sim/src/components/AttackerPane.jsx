import { IdentityWorkshop } from './IdentityWorkshop'
import { AttackControls } from './AttackControls'

export function AttackerPane({
  sourceMode,
  noiseEnabled,
  livenessState,
  onInjectPayload,
  onDisableInjection,
  onNoiseToggle,
  onResetStageA,
}) {
  return (
    <section className="flex h-full min-h-0 flex-col overflow-hidden border-t border-slate-800 bg-attacker-bg p-4 text-slate-100 lg:border-r lg:border-t-0">
      <div className="mb-2 flex shrink-0 items-center justify-between">
        <h2 className="text-base font-semibold text-attacker-accent">Attacker Dashboard</h2>
        <span className="rounded-md border border-attacker-border bg-slate-950/30 px-2.5 py-1 text-xs text-slate-300">
          Stage {livenessState.stage}
        </span>
      </div>
      <div className="grid min-h-0 flex-1 grid-rows-[auto_1fr] gap-2">
        <AttackControls
          sourceMode={sourceMode}
          noiseEnabled={noiseEnabled}
          onNoiseToggle={onNoiseToggle}
          onDisableInjection={onDisableInjection}
          onResetStageA={onResetStageA}
        />
        <IdentityWorkshop sourceMode={sourceMode} onInjectPayload={onInjectPayload} />
      </div>
    </section>
  )
}
