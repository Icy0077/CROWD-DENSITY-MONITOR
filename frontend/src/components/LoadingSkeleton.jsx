export function SkeletonBlock({ width, height = 20, style }) {
  return (
    <div
      className="skeleton-block"
      style={{ width, height, ...style }}
      aria-hidden="true"
    />
  )
}

export function SkeletonCard() {
  return (
    <div className="card skeleton-card" aria-hidden="true">
      <SkeletonBlock width="40%" height={14} />
      <SkeletonBlock width="60%" height={36} style={{ marginTop: 16 }} />
      <SkeletonBlock width="80%" height={12} style={{ marginTop: 12 }} />
    </div>
  )
}

export function SkeletonChartPanel() {
  return (
    <div className="card skeleton-card" aria-hidden="true" style={{ minHeight: 300 }}>
      <SkeletonBlock width="30%" height={14} />
      <SkeletonBlock width="50%" height={28} style={{ marginTop: 16 }} />
      <SkeletonBlock width="100%" height={160} style={{ marginTop: 20, borderRadius: 8 }} />
    </div>
  )
}
