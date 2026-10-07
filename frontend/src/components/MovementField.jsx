import { useEffect, useMemo, useRef, useState } from 'react'

const MOVEMENT_DURATION_MS = 1250
const MAX_VISIBLE_OCCUPANTS = 48
const MAX_FLOW_STICKMEN = 10

function numericCount(value) {
  const count = Number(value)
  return Number.isFinite(count) && count > 0 ? Math.floor(count) : 0
}

function personPosition(index, total) {
  const columns = Math.min(8, Math.max(3, Math.ceil(Math.sqrt(total))))
  const row = Math.floor(index / columns)
  const column = index % columns
  const rows = Math.max(1, Math.ceil(total / columns))
  return {
    left: `${18 + (column / Math.max(1, columns - 1)) * 64}%`,
    top: `${30 + (row / Math.max(1, rows - 1)) * 43}%`,
  }
}

function Stickman({ className = '', style, label }) {
  return <span className={`stick-person ${className}`} style={style} aria-label={label} aria-hidden="true"><i className="stick-head" /><i className="stick-body" /><i className="stick-arm stick-arm-left" /><i className="stick-arm stick-arm-right" /><i className="stick-leg stick-leg-left" /><i className="stick-leg stick-leg-right" /></span>
}

function FlowPeople({ count, direction }) {
  const visibleCount = Math.min(count, MAX_FLOW_STICKMEN)
  return <div className={`flow-people flow-people-${direction}`} aria-label={`${count} people ${direction === 'in' ? 'entering' : 'leaving'} in the latest interval`}>
    {Array.from({ length: visibleCount }, (_, index) => <Stickman key={`${direction}-${index}`} className="stick-flow" style={{ '--flow-index': index }} label={`${direction === 'in' ? 'Entering' : 'Leaving'} person`} />)}
    {count > MAX_FLOW_STICKMEN && <span className="flow-people-more">+{count - MAX_FLOW_STICKMEN}</span>}
  </div>
}

export default function MovementField({ occupancy, inflow, outflow, event }) {
  const [activeMovement, setActiveMovement] = useState(null)
  const [movementQueue, setMovementQueue] = useState([])
  const lastEventKey = useRef(event?.key ?? null)
  const insideCount = numericCount(occupancy)
  const visibleOccupants = Math.min(insideCount, MAX_VISIBLE_OCCUPANTS)

  const occupants = useMemo(() => Array.from({ length: visibleOccupants }, (_, index) => ({
    key: `occupant-${index}`,
    style: personPosition(index, visibleOccupants),
  })), [visibleOccupants])

  useEffect(() => {
    if (!event || !event.key || event.key === lastEventKey.current) return
    lastEventKey.current = event.key
    const nextMovements = [
      ...Array.from({ length: numericCount(event.inflow) }, (_, index) => ({ direction: 'in', index, key: `${event.key}-in-${index}` })),
      ...Array.from({ length: numericCount(event.outflow) }, (_, index) => ({ direction: 'out', index, key: `${event.key}-out-${index}` })),
    ]
    if (nextMovements.length) setMovementQueue((previous) => [...previous, ...nextMovements])
  }, [event])

  useEffect(() => {
    if (activeMovement || movementQueue.length === 0) return
    setActiveMovement(movementQueue[0])
    setMovementQueue((previous) => previous.slice(1))
  }, [activeMovement, movementQueue])

  useEffect(() => {
    if (!activeMovement) return undefined
    const timer = setTimeout(() => setActiveMovement(null), MOVEMENT_DURATION_MS)
    return () => clearTimeout(timer)
  }, [activeMovement])

  return <section className="movement-section" aria-labelledby="movement-title">
    <div className="section-rule-heading"><p className="eyebrow" id="movement-title">Live movement</p><h2>People moving through the monitored space</h2></div>
    <div className="movement-layout">
      <div className="flow-counter flow-in"><span>IN</span><div className="flow-count-line"><strong>{inflow ?? '—'}</strong><FlowPeople count={numericCount(inflow)} direction="in" /></div><small>latest interval</small></div>
      <div className="movement-diagram" aria-label={`Movement diagram showing ${insideCount} people inside, with ${numericCount(inflow)} entering and ${numericCount(outflow)} leaving in the latest interval`}>
        <span className="direction direction-in">IN <b>↓</b></span>
        <div className="flow-lines" aria-hidden="true"><i /><i /><i /><i /></div>
        <div className="monitored-space"><span>MONITORED</span><strong>SPACE</strong><small>{occupancy === null || occupancy === undefined ? 'occupancy unavailable' : `${insideCount} inside`}</small></div>
        {occupants.map((person) => <Stickman key={person.key} className="stick-inside" style={person.style} label="Person inside monitored space" />)}
        {activeMovement && <Stickman key={activeMovement.key} className={`stick-moving stick-moving-${activeMovement.direction}`} label={activeMovement.direction === 'in' ? 'Person entering monitored space' : 'Person leaving monitored space'} style={{ '--movement-delay': `${activeMovement.index * 90}ms` }} />}
        <span className="direction direction-out">OUT <b>↓</b></span>
      </div>
      <div className="flow-counter flow-out"><span>OUT</span><div className="flow-count-line"><strong>{outflow ?? '—'}</strong><FlowPeople count={numericCount(outflow)} direction="out" /></div><small>latest interval</small></div>
    </div>
    <p className="movement-note">Stickmen animate only when a new telemetry timestamp reports real movement.</p>
  </section>
}
