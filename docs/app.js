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

function renderTerms(topTerms) {
  const list = document.getElementById('terms')
  list.innerHTML = ''
  if (!topTerms.length) {
    list.innerHTML = '<li class="empty">No term matches found for this date.</li>'
    return
  }

  topTerms.slice(0, 12).forEach(([term, count]) => {
    const li = document.createElement('li')
    li.textContent = `${term}: ${count}`
    list.appendChild(li)
  })
}

function renderTypeBreakdown(typeBreakdown, total) {
  const container = document.getElementById('typeBreakdown')
  if (!typeBreakdown.length) {
    container.innerHTML = '<p class="empty">No notice type data for this date.</p>'
    return
  }

  const rows = typeBreakdown.slice(0, 12).map(([kind, count]) => {
    const pct = total > 0 ? Math.round((count / total) * 100) : 0
    return `
      <tr>
        <td>${kind}</td>
        <td>${count}</td>
        <td>${pct}%</td>
      </tr>
    `
  })

  container.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Type</th>
          <th>Count</th>
          <th>Share</th>
        </tr>
      </thead>
      <tbody>${rows.join('')}</tbody>
    </table>
  `
}

function renderDepartmentTable(departments) {
  const container = document.getElementById('departmentTable')
  if (!departments.length) {
    container.innerHTML = '<p class="empty">No department-level data for this date.</p>'
    return
  }

  const rows = departments.slice(0, 25).map((row) => {
    return `
      <tr>
        <td>${row.department || ''}</td>
        <td>${row.total || 0}</td>
        <td>${row.opportunities || 0}</td>
        <td>${row.wins || 0}</td>
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
        </tr>
      </thead>
      <tbody>${rows.join('')}</tbody>
    </table>
  `
}

function renderTable(records) {
  const container = document.getElementById('recordsTable')
  if (!records.length) {
    container.innerHTML = '<p class="empty">No matching records for this date.</p>'
    return
  }

  const rows = records.slice(0, 20).map((record) => {
    const terms = (record.matches || []).slice(0, 3).map((m) => `${m.term}(${m.count})`).join(', ')
    const link = record.Link
      ? `<a href="${record.Link}" target="_blank" rel="noreferrer">View</a>`
      : ''
    return `
      <tr>
        <td>${record.Type || ''}</td>
        <td>${record.Title || ''}</td>
        <td>${record.Agency || ''}</td>
        <td>${terms}</td>
        <td>${link}</td>
      </tr>
    `
  })

  container.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Type</th>
          <th>Title</th>
          <th>Agency</th>
          <th>Terms</th>
          <th>Link</th>
        </tr>
      </thead>
      <tbody>${rows.join('')}</tbody>
    </table>
  `
}

function renderGraph(graphData) {
  const container = document.getElementById('graph')
  const nodes = (graphData.nodes || []).slice(0, 45)
  const validNodeIds = new Set(nodes.map((n) => n.id))
  const edges = (graphData.edges || []).filter((e) => validNodeIds.has(e.source) && validNodeIds.has(e.target)).slice(0, 80)

  if (!nodes.length || !edges.length) {
    container.innerHTML = '<p class="empty">No relationship graph data for this date.</p>'
    return
  }

  const width = 1000
  const laneY = { agency: 80, type: 220, naics: 360 }

  const byGroup = { agency: [], type: [], naics: [] }
  nodes.forEach((node) => {
    const group = node.group || 'type'
    if (byGroup[group]) byGroup[group].push(node)
  })

  const positions = {}
  Object.entries(byGroup).forEach(([group, groupNodes]) => {
    const gap = width / Math.max(groupNodes.length + 1, 2)
    groupNodes.forEach((node, index) => {
      positions[node.id] = {
        x: Math.round((index + 1) * gap),
        y: laneY[group],
      }
    })
  })

  const edgeLines = edges.map((edge) => {
    const from = positions[edge.source]
    const to = positions[edge.target]
    if (!from || !to) return ''
    const strokeWidth = Math.min(6, 1 + Math.log2((edge.weight || 1) + 1))
    return `<line x1="${from.x}" y1="${from.y}" x2="${to.x}" y2="${to.y}" stroke="#8c959f" stroke-opacity="0.45" stroke-width="${strokeWidth}" />`
  }).join('')

  const nodeCircles = nodes.map((node) => {
    const pos = positions[node.id]
    if (!pos) return ''
    const color = node.group === 'agency' ? '#0969da' : node.group === 'type' ? '#1a7f37' : '#bf8700'
    const label = node.label.length > 28 ? `${node.label.slice(0, 28)}...` : node.label
    return `
      <circle cx="${pos.x}" cy="${pos.y}" r="7" fill="${color}" />
      <text x="${pos.x + 10}" y="${pos.y + 4}" fill="#1f2328">${label}</text>
    `
  }).join('')

  container.innerHTML = `
    <svg width="1000" height="430" viewBox="0 0 1000 430" role="img" aria-label="Agency to type to NAICS relationship graph">
      <text x="10" y="25" fill="#57606a">Agency</text>
      <text x="10" y="165" fill="#57606a">Notice Type</text>
      <text x="10" y="305" fill="#57606a">NAICS</text>
      ${edgeLines}
      ${nodeCircles}
    </svg>
  `
}

async function main() {
  try {
    const [summary, relationships] = await Promise.all([
      loadJson('data/today_summary.json'),
      loadJson('data/today_relationships.json'),
    ])

    const msg = summary.used_fallback_latest
      ? `Requested ${summary.requested_date}, no records found. Showing latest available date: ${summary.effective_date}.`
      : `Showing records published on ${summary.effective_date}.`
    setText('dateInfo', msg)
    setText('total', String(summary.records_total || 0))
    setText('opps', String(summary.opportunities_total || 0))
    setText('wins', String(summary.wins_total || 0))
    setText('departments', String(summary.departments_total || 0))

    const topTerm = (summary.top_terms && summary.top_terms[0] && summary.top_terms[0][0]) || 'None'
    setText('topTerm', topTerm)

    renderTypeBreakdown(summary.type_breakdown || [], summary.records_total || 0)
    renderDepartmentTable(summary.department_breakdown || [])
    renderTerms(summary.top_terms || [])
    renderTable(summary.top_matching_records || [])
    renderGraph(relationships)
  } catch (error) {
    setText('dateInfo', `Failed to load dashboard data: ${error.message}`)
  }
}

main()