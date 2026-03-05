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

function normalizeRecord(raw) {
  return {
    NoticeId: raw.NoticeId || '',
    Type: raw.Type || '',
    Title: raw.Title || '',
    Agency: raw.Agency || raw['Department/Ind.Agency'] || '',
    PostedDate: raw.PostedDate || '',
    Link: raw.Link || '',
    AdditionalInfoLink: raw.AdditionalInfoLink || raw['AdditionalInfoLink'] || '',
    matches: raw.matches || [],
  }
}

function isPdfLink(link) {
  const value = (link || '').toLowerCase()
  return value.includes('.pdf') || value.includes('rfq')
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
    const dept = row.department || ''
    const isDod = dept.toLowerCase().includes('defense')
    return `
      <tr>
        <td><button type="button" class="dept-filter" data-dept="${dept}" style="background:none;border:none;color:#0969da;cursor:pointer;padding:0;text-align:left;${isDod ? 'font-weight:700;' : ''}">${dept}</button>${isDod ? ' <span style="font-size:12px;color:#59636e;">(DoD)</span>' : ''}</td>
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
    <p class="sub" style="margin-top:10px;"><button type="button" id="showAllDepts" style="background:none;border:none;color:#0969da;cursor:pointer;padding:0;">Show all departments</button></p>
  `
}

function renderAwardedCompanies(awardHistory) {
  const container = document.getElementById('awardedCompanies')
  if (!awardHistory || !awardHistory.top_companies || !awardHistory.top_companies.length) {
    container.innerHTML = '<p class="empty">No awarded company data available.</p>'
    return
  }

  const leaders = awardHistory.top_companies.slice(0, 12).map((row) => `
    <tr>
      <td>${row.company}</td>
      <td>${row.awarded}</td>
    </tr>
  `)

  const months = (awardHistory.monthly || []).slice(0, 6).map((row) => `
    <tr>
      <td>${row.month}</td>
      <td>${row.awarded}</td>
      <td>${row.unique_companies}</td>
    </tr>
  `)

  container.innerHTML = `
    <p class="sub" style="margin-top: 0;">Top companies receiving awards and recent monthly award activity.</p>
    <div style="display:grid;grid-template-columns:2fr 1fr;gap:12px;">
      <div>
        <table>
          <thead>
            <tr><th>Company</th><th>Awarded</th></tr>
          </thead>
          <tbody>${leaders.join('')}</tbody>
        </table>
      </div>
      <div>
        <table>
          <thead>
            <tr><th>Month</th><th>Awarded</th><th>Companies</th></tr>
          </thead>
          <tbody>${months.join('')}</tbody>
        </table>
      </div>
    </div>
  `
}

function renderTable(records, heading = '') {
  const container = document.getElementById('recordsTable')
  if (!records.length) {
    container.innerHTML = '<p class="empty">No matching records for this date.</p>'
    return
  }

  const rows = records.slice(0, 20).map((record) => {
    const terms = (record.matches || []).slice(0, 3).map((m) => `${m.term}(${m.count})`).join(', ')
    const markdownLink = record.NoticeId
      ? `<a href="opportunities/${record.NoticeId}/index.md" target="_blank" rel="noreferrer">Markdown</a>`
      : ''
    const pdfLink = isPdfLink(record.AdditionalInfoLink)
      ? `<a href="${record.AdditionalInfoLink}" target="_blank" rel="noreferrer">PDF</a>`
      : ''
    const samLink = record.Link
      ? `<a href="${record.Link}" target="_blank" rel="noreferrer">SAM.gov</a>`
      : ''
    const posted = (record.PostedDate || '').slice(0, 10)
    return `
      <tr>
        <td>${record.Type || ''}</td>
        <td>${record.Title || ''}</td>
        <td>${record.Agency || ''}</td>
        <td>${posted}</td>
        <td>${terms}</td>
        <td>${[markdownLink, pdfLink, samLink].filter(Boolean).join(' · ')}</td>
      </tr>
    `
  })

  container.innerHTML = `
    ${heading ? `<p class="sub" style="margin-top:0;">${heading}</p>` : ''}
    <table>
      <thead>
        <tr>
          <th>Type</th>
          <th>Title</th>
          <th>Agency</th>
          <th>Posted</th>
          <th>Terms</th>
          <th>Links (Markdown first)</th>
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
    const [summary, relationships, allRecordsRaw] = await Promise.all([
      loadJson('data/today_summary.json'),
      loadJson('data/today_relationships.json'),
      loadJson('data/today_records.json'),
    ])

    const allRecords = (allRecordsRaw || []).map((row) => normalizeRecord(row))
    const matchedRecords = (summary.top_matching_records || []).map((row) => normalizeRecord(row))

    const msg = summary.used_fallback_latest
      ? `Requested ${summary.requested_date}, no records found. Showing latest available date: ${summary.effective_date}.`
      : `Showing records published on ${summary.effective_date}.`
    setText('dateInfo', msg)
    setText('total', String(summary.records_total || 0))
    setText('opps', String(summary.opportunities_total || 0))
    setText('wins', String(summary.awarded_total || summary.wins_total || 0))
    setText('departments', String(summary.departments_total || 0))

    const popularTerms = (summary.top_terms || []).slice(0, 3).map(([term]) => term)
    setText('topTerm', popularTerms.length ? popularTerms.join(', ') : 'None')

    renderTypeBreakdown(summary.type_breakdown || [], summary.records_total || 0)
    renderDepartmentTable(summary.department_breakdown || [])
    renderAwardedCompanies(summary.award_company_history || {})
    renderTerms(summary.top_terms || [])
    renderTable(matchedRecords.length ? matchedRecords : allRecords, 'Showing highest-signal records (by tracked terms).')
    renderGraph(relationships)

    containerHandlers(allRecords, summary.department_breakdown || [])
  } catch (error) {
    setText('dateInfo', `Failed to load dashboard data: ${error.message}`)
  }
}

function containerHandlers(allRecords) {
  const table = document.getElementById('departmentTable')
  if (!table) return

  table.addEventListener('click', (event) => {
    const deptButton = event.target.closest('.dept-filter')
    if (deptButton) {
      const department = deptButton.getAttribute('data-dept') || ''
      const filtered = allRecords.filter((row) => (row.Agency || '') === department)
      renderTable(filtered, `Department filter: ${department}`)
      return
    }

    const resetButton = event.target.closest('#showAllDepts')
    if (resetButton) {
      renderTable(allRecords, 'Showing all records for this publication date.')
    }
  })
}

main()