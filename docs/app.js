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
    Awardee: raw.Awardee || '',
    AwardAmount: raw['Award$'] || '',
    PrimaryContactFullname: raw.PrimaryContactFullname || '',
    PrimaryContactEmail: raw.PrimaryContactEmail || '',
    PrimaryContactPhone: raw.PrimaryContactPhone || '',
    matches: raw.matches || [],
  }
}

function isPdfLink(link) {
  const value = (link || '').toLowerCase()
  return value.includes('.pdf') || value.includes('rfq')
}

/**
 * Returns a background color style string for a given notice type.
 * Colors are chosen to be distinct, accessible, and easy to scan at a glance.
 */
function getTypeStyle(type) {
  const t = (type || '').toLowerCase()
  if (t.includes('special notice'))                   return 'background-color:#f3e8ff;' // lavender
  if (t.includes('sources sought'))                   return 'background-color:#fef3c7;' // amber
  if (t.includes('solicitation'))                     return 'background-color:#dbeafe;' // blue
  if (t.includes('award notice'))                     return 'background-color:#dcfce7;' // green
  if (t.includes('presolicitation'))                  return 'background-color:#ffedd5;' // orange
  if (t.includes('justification'))                    return 'background-color:#f1f5f9;' // slate
  if (t.includes('sale of surplus'))                  return 'background-color:#fce7f3;' // pink
  return 'background-color:#f9fafb;'                                                     // fallback
}

const TYPE_LEGEND = [
  { label: 'Special Notice',                 style: 'background-color:#f3e8ff;' },
  { label: 'Sources Sought',                 style: 'background-color:#fef3c7;' },
  { label: 'Solicitation / Combined',        style: 'background-color:#dbeafe;' },
  { label: 'Award Notice',                   style: 'background-color:#dcfce7;' },
  { label: 'Presolicitation',                style: 'background-color:#ffedd5;' },
  { label: 'Justification',                  style: 'background-color:#f1f5f9;' },
  { label: 'Sale of Surplus Property',       style: 'background-color:#fce7f3;' },
  { label: 'Other',                          style: 'background-color:#f9fafb;' },
]

function renderTypeLegend() {
  return `
    <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px;font-size:12px;">
      ${TYPE_LEGEND.map(item => `
        <span style="${item.style};border:1px solid #d0d7de;border-radius:4px;padding:2px 8px;">${item.label}</span>
      `).join('')}
    </div>
  `
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
    const button = document.createElement('button')
    button.type = 'button'
    button.className = 'term-filter'
    button.setAttribute('data-term', term)
    button.style.cssText = `
      background: none;
      border: none;
      color: #0369a1;
      cursor: pointer;
      text-align: left;
      padding: 4px 0;
      border-radius: 3px;
      font-size: 14px;
      font-family: inherit;
      transition: background-color 0.15s;
    `
    button.onmouseover = function() { this.style.backgroundColor = '#f0f0f0' }
    button.onmouseout = function() { this.style.backgroundColor = 'transparent' }
    button.textContent = `${term}: ${count}`
    li.appendChild(button)
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
        <td><button type="button" class="dept-filter" data-dept="${dept}" style="background:none;border:none;color:#0969da;cursor:pointer;text-align:left;padding:4px 0;border-radius:3px;font-size:14px;font-family:inherit;transition:background-color 0.15s;${isDod ? 'font-weight:700;' : ''}" onmouseover="this.style.backgroundColor='#f0f0f0'" onmouseout="this.style.backgroundColor='transparent'">${dept}</button>${isDod ? ' <span style="font-size:12px;color:#59636e;">(DoD)</span>' : ''}</td>
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
          <th>Awarded</th>
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
      <td><button type="button" class="company-filter" data-company="${row.company}" style="background:none;border:none;color:#0369a1;cursor:pointer;text-align:left;padding:4px 0;border-radius:3px;font-size:14px;font-family:inherit;transition:background-color 0.15s;" onmouseover="this.style.backgroundColor='#f0f0f0'" onmouseout="this.style.backgroundColor='transparent'">${row.company}</button></td>
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
    <p class="sub" style="margin-top: 0;">Top companies receiving awards and recent monthly award activity. Click a company to view its contracts.</p>
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
    const terms = (record.matches || []).slice(0, 2).map((m) => `${m.term}(${m.count})`).join(', ')
    const awardee = (record.Awardee || '').trim()
    const awardAmount = record.AwardAmount || ''
    const posted = (record.PostedDate || '').slice(0, 10)
    const markdownLink = record.NoticeId
      ? `<a href="opportunities/${record.NoticeId}/" title="View full opportunity">View</a>`
      : ''
    const samLink = record.Link
      ? `<a href="${record.Link}" target="_blank" rel="noreferrer" title="Open on SAM.gov">SAM.gov ↗</a>`
      : ''
    const rowStyle = getTypeStyle(record.Type)

    return `
      <tr style="${rowStyle}">
        <td style="width:80px;">${record.Type || ''}</td>
        <td style="width:280px; white-space:normal;">${record.Title || ''}</td>
        <td style="width:100px;">${record.Agency || ''}</td>
        <td style="width:80px;">${posted}</td>
        <td style="width:120px; color:#0369a1; font-weight:500;">${terms || '—'}</td>
        <td style="width:120px;">${awardee || '—'}</td>
        <td style="width:80px;">${awardAmount ? '$' + awardAmount : '—'}</td>
        <td style="width:100px; white-space:nowrap;">${[markdownLink, samLink].filter(Boolean).join(' | ')}</td>
      </tr>
    `
  })

  container.innerHTML = `
    ${heading ? `<p class="sub" style="margin-top:0;">${heading}</p>` : ''}
    ${renderTypeLegend()}
    <div style="overflow-x: auto; border: 1px solid #d8dee4; border-radius: 6px;">
      <table style="margin:0;">
        <thead>
          <tr style="background-color: #f6f8fa;">
            <th style="width:80px;">Type</th>
            <th style="width:280px;">Title</th>
            <th style="width:100px;">Agency</th>
            <th style="width:80px;">Posted</th>
            <th style="width:120px; color:#0369a1;">Tracked Terms</th>
            <th style="width:120px;">Awardee</th>
            <th style="width:80px;">Award $</th>
            <th style="width:100px;">Links</th>
          </tr>
        </thead>
        <tbody>${rows.join('')}</tbody>
      </table>
    </div>
  `
}

function renderDepartmentForecast(forecastData) {
  const container = document.getElementById('departmentForecast')
  if (!forecastData || !forecastData.departments_by_opportunity_volume) {
    container.innerHTML = '<p class="empty">No forecasting data available.</p>'
    return
  }

  const depts = (forecastData.departments_by_opportunity_volume || []).slice(0, 10)
  const rows = depts.map(
    (dept) => `
      <tr>
        <td style="font-weight: 500;">${dept.department}</td>
        <td style="text-align: right;">${dept.open_opportunities}</td>
        <td style="text-align: right;">${dept.awarded}</td>
        <td style="text-align: right;">${dept.win_rate_percent}%</td>
        <td style="text-align: right; color: #059669;">$${(dept.estimated_monthly_value / 1000000).toFixed(1)}M</td>
      </tr>
    `
  ).join('')

  container.innerHTML = `
    <table style="width: 100%; overflow-x: auto;">
      <thead style="background: #f6f8fa;">
        <tr>
          <th>Department</th>
          <th style="text-align: right;">Open Opps</th>
          <th style="text-align: right;">Awards</th>
          <th style="text-align: right;">Win Rate</th>
          <th style="text-align: right;">Est. Value</th>
        </tr>
      </thead>
      <tbody>
        ${rows}
      </tbody>
    </table>
  `
}

function renderContractOfficers(officersData) {
  const container = document.getElementById('contractOfficers')
  if (!officersData || !officersData.top_officers) {
    container.innerHTML = '<p class="empty">No contract officer data available.</p>'
    return
  }

  // Filter out generic/system entries and show top real officers
  const officers = (officersData.top_officers || [])
    .filter((o) => o.opportunities >= 5 && o.email && !o.email.includes('listing') && !o.email.includes('dibbs'))
    .slice(0, 15)

  if (!officers.length) {
    container.innerHTML = '<p class="empty">No individual officers found with significant activity.</p>'
    return
  }

  const rows = officers.map(
    (officer) => `
      <tr>
        <td>
          <div style="font-weight: 500;">${officer.name}</div>
          <div style="font-size: 12px; color: #59636e;">${officer.email || 'N/A'}</div>
        </td>
        <td style="text-align: right;">${officer.opportunities}</td>
        <td style="text-align: right; color: #059669; font-weight: 500;">${officer.awards}</td>
        <td style="text-align: right; font-size: 14px;">$${(officer.total_award_value / 1000000).toFixed(1)}M</td>
        <td style="text-align: center; font-size: 12px; color: #59636e;">${officer.departments.slice(0, 2).join(' / ')}</td>
      </tr>
    `
  ).join('')

  container.innerHTML = `
    <table style="width: 100%;">
      <thead style="background: #f6f8fa;">
        <tr>
          <th>Officer Name</th>
          <th style="text-align: right;">Opps</th>
          <th style="text-align: right;">Awards</th>
          <th style="text-align: right;">Value</th>
          <th style="text-align: center;">Agencies</th>
        </tr>
      </thead>
      <tbody>
        ${rows}
      </tbody>
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
    const [summary, relationships, allRecordsRaw, departmentForecast, contractOfficers] = await Promise.all([
      loadJson('data/today_summary.json'),
      loadJson('data/today_relationships.json'),
      loadJson('data/today_records.json'),
      loadJson('data/department_forecast.json').catch(() => null),
      loadJson('data/contract_officers.json').catch(() => null),
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
    if (departmentForecast) {
      renderDepartmentForecast(departmentForecast)
    }
    if (contractOfficers) {
      renderContractOfficers(contractOfficers)
    }
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
  const termsList = document.getElementById('terms')
  if (!table) return

  // Department filter handler
  table.addEventListener('click', (event) => {
    const deptButton = event.target.closest('.dept-filter')
    if (deptButton) {
      event.preventDefault()
      const department = deptButton.getAttribute('data-dept') || ''
      if (!department) return
      
      const filtered = allRecords.filter((row) => (row.Agency || '') === department)
      renderTable(filtered, `Department filter: ${department} (${filtered.length} matches)`)
      
      // Scroll to results and add visual feedback
      const recordsTable = document.getElementById('recordsTable')
      if (recordsTable) {
        recordsTable.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
      return
    }

    const resetButton = event.target.closest('#showAllDepts')
    if (resetButton) {
      event.preventDefault()
      renderTable(allRecords, 'Showing all records for this publication date.')
      
      // Scroll to results
      const recordsTable = document.getElementById('recordsTable')
      if (recordsTable) {
        recordsTable.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    }
  })

  // Term filter handler
  if (termsList) {
    termsList.addEventListener('click', (event) => {
      const termButton = event.target.closest('.term-filter')
      if (termButton) {
        event.preventDefault()
        const term = termButton.getAttribute('data-term') || ''
        if (!term) return
        
        // Filter records that have matches for this term
        const filtered = allRecords.filter((row) => {
          return (row.matches || []).some((m) => m.term.toLowerCase() === term.toLowerCase())
        })
        
        renderTable(filtered, `Term filter: "${term}" (${filtered.length} matching opportunities)`)
        
        // Scroll to results
        const recordsTable = document.getElementById('recordsTable')
        if (recordsTable) {
          recordsTable.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }
      }
    })
  }

  // Company filter handler
  const awardedCompaniesContainer = document.getElementById('awardedCompanies')
  if (awardedCompaniesContainer) {
    awardedCompaniesContainer.addEventListener('click', (event) => {
      const companyButton = event.target.closest('.company-filter')
      if (companyButton) {
        event.preventDefault()
        const company = companyButton.getAttribute('data-company') || ''
        if (!company) return
        
        // Filter records by awarded company (Awardee field)
        const filtered = allRecords.filter((row) => {
          const awardee = row.Awardee || row.awardee || ''
          return awardee.toLowerCase() === company.toLowerCase()
        })
        
        renderTable(filtered, `Awarded Company filter: "${company}" (${filtered.length} contracts awarded)`)
        
        // Scroll to results
        const recordsTable = document.getElementById('recordsTable')
        if (recordsTable) {
          recordsTable.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }
      }
    })
  }
}

main()