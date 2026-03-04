async function loadJson(path) {
  const response = await fetch(path)
  if (!response.ok) {
    throw new Error(`Failed to load ${path}: ${response.status}`)
  }
  return response.json()
}

function setText(id, text) {
  const node = document.getElementById(id)
  if (node) node.textContent = text
}

function renderTopAgencies(topAgencies) {
  const container = document.getElementById('topAgencies')
  if (!topAgencies.length) {
    container.innerHTML = '<p class="empty">No top agencies data available.</p>'
    return
  }

  const rows = topAgencies.map((row) => {
    const winRate = row.total > 0 ? Math.round((row.wins / row.total) * 100) : 0
    return `
      <tr>
        <td>${row.agency}</td>
        <td>${row.total}</td>
        <td>${row.opportunities}</td>
        <td>${row.wins}</td>
        <td>${winRate}%</td>
        <td>${row.days_seen}</td>
      </tr>
    `
  })

  container.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Department</th>
          <th>Total</th>
          <th>Opportunities</th>
          <th>Wins</th>
          <th>Win Rate</th>
          <th>Days Seen</th>
        </tr>
      </thead>
      <tbody>${rows.join('')}</tbody>
    </table>
  `
}

function renderSparkline(values, width = 120, height = 30) {
  if (!values.length) return ''
  const max = Math.max(...values)
  const min = 0
  const range = max - min || 1
  const points = values
    .map(
      (v, i) => `${(i / (values.length - 1)) * width},${height - ((v - min) / range) * height}`
    )
    .join(' ')
  return `<svg class="sparkline" viewBox="0 0 ${width} ${height}">
    <polyline points="${points}" fill="none" stroke="#0969da" stroke-width="1.5" />
  </svg>`
}

function renderTrends(agencies, timeline) {
  const container = document.getElementById('trends')
  if (!timeline.length) {
    container.innerHTML = '<p class="empty">No trend timeline available.</p>'
    return
  }

  // Show only last 14 days
  const recentDates = timeline.slice(-14)
  const recentDateSet = new Set(recentDates)

  // Get agencies that appeared in recent days
  const activeAgencies = Object.entries(agencies)
    .map(([agency, sightings]) => {
      const recentSightings = sightings.filter((s) => recentDateSet.has(s.date))
      if (!recentSightings.length) return null
      const counts = recentSightings.map((s) => s.count)
      return { agency, sightings: recentSightings, sparkline: counts }
    })
    .filter(Boolean)
    .sort((a, b) => {
      const sumA = a.sightings.reduce((acc, s) => acc + s.count, 0)
      const sumB = b.sightings.reduce((acc, s) => acc + s.count, 0)
      return sumB - sumA
    })
    .slice(0, 20)

  const rows = activeAgencies.map((item) => {
    const latest = item.sightings[item.sightings.length - 1]
    const line = renderSparkline(item.sparkline)
    return `
      <tr>
        <td>${item.agency}</td>
        <td>${line}</td>
        <td>${latest.count}</td>
        <td>${latest.opportunities}</td>
        <td>${latest.wins}</td>
      </tr>
    `
  })

  container.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Department</th>
          <th>Trend (${recentDates[0]} to ${recentDates[recentDates.length - 1]})</th>
          <th>Latest Count</th>
          <th>Opportunities</th>
          <th>Wins</th>
        </tr>
      </thead>
      <tbody>${rows.join('')}</tbody>
    </table>
  `
}

async function main() {
  try {
    const trends = await loadJson('data/trends.json')

    const info = `Timeline spans ${trends.timeline.length} snapshot(s) from ${trends.timeline[0]} to ${trends.timeline[trends.timeline.length - 1]}`
    setText('info', info)

    renderTopAgencies(trends.top_agencies || [])
    renderTrends(trends.agencies || {}, trends.timeline || [])
  } catch (error) {
    setText('info', `Failed to load trends: ${error.message}`)
  }
}

main()
