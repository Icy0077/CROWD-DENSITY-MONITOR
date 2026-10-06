function figureCount(value) {
  const count = Number(value)
  return Number.isFinite(count) ? Math.min(6, Math.max(0, Math.round(count))) : 0
}

function People({ value, direction }) {
  return (
    <span className={`flow-people flow-people-${direction}`} aria-hidden="true">
      {Array.from({ length: figureCount(value) }, (_, index) => (
        <i className="person-figure" key={index}><b /></i>
      ))}
    </span>
  )
}

export default function FlowIllustration({ inflow, outflow }) {
  return (
    <div className="flow-illustration" aria-label="Conceptual flow from entry, through the space, to exit">
      <div className="flow-station">
        <span>IN</span>
        <People value={inflow} direction="in" />
        <em>↓</em>
      </div>
      <div className="flow-space">
        <i aria-hidden="true" />
        <span>SPACE</span>
      </div>
      <div className="flow-station">
        <em>↓</em>
        <People value={outflow} direction="out" />
        <span>OUT</span>
      </div>
    </div>
  )
}
