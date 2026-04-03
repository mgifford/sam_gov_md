async function loadJson(path) {
  const response = await fetch(path)
  if (!response.ok) throw new Error(`Failed to load ${path}: ${response.status}`)
  return response.json()
}

function normalizeRecord(raw) {
  return {
    NoticeId: raw.NoticeId || '',
    SolNumber: raw['Sol#'] || '',
    Type: raw.Type || '',
    Title: raw.Title || '',
    Agency: raw.Agency || raw['Department/Ind.Agency'] || '',
    PostedDate: raw.PostedDate || '',
    ResponseDeadLine: raw.ResponseDeadLine || '',
    Link: raw.Link || '',
    AdditionalInfoLink: raw.AdditionalInfoLink || '',
    Description: raw.Description || '',
    Awardee: raw.Awardee || '',
    AwardAmount: raw['Award$'] || '',
    SetAside: raw.SetAside || '',
    matches: raw.matches || [],
    first_seen_date: raw.first_seen_date || '',
    seen_count: raw.seen_count || 1,
    version_count: raw.version_count || 1,
    has_pdf_content: raw.has_pdf_content || false,
    pdf_text: raw.pdf_text || '',
  }
}

function getRecordDate(record) {
  return (record.first_seen_date || record.PostedDate || '').slice(0, 10)
}

function getDeadlineBadge(deadline) {
  if (!deadline) return ''
  const dl = new Date(deadline)
  if (isNaN(dl)) return ''
  const diffDays = Math.ceil((dl - Date.now()) / 86400000)
  if (diffDays < 0)  return '<span class="deadline-badge deadline-expired">Closed</span>'
  if (diffDays <= 7) return `<span class="deadline-badge deadline-urgent" title="Response deadline">${diffDays}d left</span>`
  if (diffDays <= 30) return `<span class="deadline-badge deadline-soon" title="Response deadline">${diffDays}d left</span>`
  return `<span class="deadline-badge deadline-ok" title="Response deadline">${diffDays}d left</span>`
}

/**
 * Returns a background color style string for a given notice type.
 */
function getTypeStyle(type) {
  const t = (type || '').toLowerCase()
  if (t.includes('special notice'))  return 'background-color:#f3e8ff;'
  if (t.includes('sources sought'))  return 'background-color:#fef3c7;'
  if (t.includes('solicitation'))    return 'background-color:#dbeafe;'
  if (t.includes('award notice'))    return 'background-color:#dcfce7;'
  if (t.includes('presolicitation')) return 'background-color:#ffedd5;'
  if (t.includes('justification'))   return 'background-color:#f1f5f9;'
  if (t.includes('sale of surplus')) return 'background-color:#fce7f3;'
  return 'background-color:#f9fafb;'
}

function calculateScore(query, record) {
  const queryTerms = query.toLowerCase().split(/\s+/).filter(t => t.length > 0)
  let score = 0
  queryTerms.forEach(qterm => {
    if (record.Title.toLowerCase().includes(qterm)) score += 100
    if (record.Agency.toLowerCase().includes(qterm)) score  += 50
    if (record.Description.toLowerCase().includes(qterm)) score += 30
    if (record.matches.some(m => m.term.toLowerCase().includes(qterm))) score += 75
    if (record.pdf_text && record.pdf_text.toLowerCase().includes(qterm)) score += 20
  })
  return { score }
}

function displayResults(results, query) {
  const resultsContainer = document.getElementById('search-results')
  const statsContainer = document.getElementById('search-stats')

  if (results.length === 0) {
    resultsContainer.innerHTML = '<li class="empty">No results found. Try different keywords or filters.</li>'
    statsContainer.textContent = query ? `No results for "${query}"` : 'No results match your filters'
    return
  }

  statsContainer.textContent = `Found ${results.length} result${results.length !== 1 ? 's' : ''}`
  resultsContainer.innerHTML = ''

  results.slice(0, 100).forEach(record => {
    const li = document.createElement('li')
    li.className = 'result-item'
    li.style.cssText = getTypeStyle(record.Type)
    const posted = (record.PostedDate || '').slice(0, 10)
    const excerpt = (record.Description || '').slice(0, 180) + (record.Description?.length > 180 ? '...' : '')
    const statusBadge = record.Awardee ? '<span class="result-badge badge-awarded">Awarded</span>' : '<span class="result-badge badge-opportunity">Open</span>'
    const typeBadge = record.Type ? `<span class="result-badge badge-type">${record.Type}</span>` : ''
    const pdfBadge = record.has_pdf_content ? '<span class="result-badge badge-pdf">📄 Docs Extracted</span>' : ''
    const deadlineBadge = getDeadlineBadge(record.ResponseDeadLine)
    const versionBadge = record.version_count > 1 ? `<span class="version-badge" title="${record.version_count} versions of this solicitation">v${record.version_count}</span>` : ''
    const noticeId = record.SolNumber ? `<span class="notice-id" title="SAM.gov Notice ID">📋 ${record.SolNumber}</span>` : ''
    const seenNote = record.seen_count > 5 ? `<span title="Seen across ${record.seen_count} daily snapshots — long-running or IDIQ">👁 ${record.seen_count}×</span>` : ''
    const matchedTerms = record.matches.length > 0 ? `<div class="result-meta"><span><strong>Tracked Terms:</strong> ${record.matches.map(m => m.term).join(', ')}</span></div>` : ''
    const detailLink = record.NoticeId ? `<a href="opportunities/${record.NoticeId}/" title="View opportunity details and extracted documents">Details</a>` : ''
    const docsLink = record.AdditionalInfoLink ? `<a href="${record.AdditionalInfoLink}" target="_blank" rel="noopener" title="Additional documents / solicitation">📎 Documents</a>` : ''

    li.innerHTML = `
      <div class="result-title">${statusBadge}${typeBadge}${pdfBadge}${deadlineBadge} <a href="${record.Link || '#'}" target="_blank">${record.Title || 'Untitled'}</a>${versionBadge}</div>
      <div class="result-meta">
        <span><strong>Agency:</strong> ${record.Agency || 'Unknown'}</span>
        <span><strong>Posted:</strong> ${posted}</span>
        ${noticeId}
        ${seenNote}
        ${detailLink ? `<span>${detailLink}</span>` : ''}
        ${docsLink ? `<span>${docsLink}</span>` : ''}
      </div>
      ${matchedTerms}
      <div class="result-excerpt">${excerpt}</div>
    `
    resultsContainer.appendChild(li)
  })
}

async function main() {
  try {
    const records = await loadJson('data/all_opportunities.json')
    const allRecords = records.map(normalizeRecord)

    // Update header with total record count
    const headerDesc = document.querySelector('header p')
    if (headerDesc) {
      const uniqueDates = new Set(allRecords.map(r => getRecordDate(r)).filter(Boolean))
      headerDesc.textContent = `Search across ${allRecords.length.toLocaleString()} opportunities tracked over ${uniqueDates.size} days. Filters by title, agency, description, and tracked terms.`
    }

    const deptFilter = document.getElementById('filter-department')
    const uniqueDepartments = [...new Set(allRecords.map(r => r.Agency))].filter(Boolean).sort()
    uniqueDepartments.forEach(dept => {
      const option = document.createElement('option')
      option.value = dept
      option.textContent = dept
      deptFilter.appendChild(option)
    })

    const termFilter = document.getElementById('filter-term')
    const uniqueTerms = [...new Set(allRecords.flatMap(r => r.matches.map(m => m.term)))].filter(Boolean).sort()
    uniqueTerms.forEach(term => {
      const option = document.createElement('option')
      option.value = term
      option.textContent = term
      termFilter.appendChild(option)
    })

    const setAsideFilter = document.getElementById('filter-setaside')
    const uniqueSetAsides = [...new Set(allRecords.map(r => r.SetAside))].filter(Boolean).sort()
    uniqueSetAsides.forEach(sa => {
      const option = document.createElement('option')
      option.value = sa
      option.textContent = sa
      setAsideFilter.appendChild(option)
    })

    const searchInput = document.getElementById('search-input')
    const statusFilter = document.getElementById('filter-status')
    const dateFromFilter = document.getElementById('filter-date-from')
    const clearFiltersBtn = document.getElementById('clear-filters')
    const activeFiltersContainer = document.getElementById('active-filters')

    // Exact-date filter set via URL parameter ?date=YYYY-MM-DD
    let exactDate = ''

    function updateUrl() {
      const params = new URLSearchParams()
      if (searchInput.value.trim()) params.set('q', searchInput.value.trim())
      if (deptFilter.value) params.set('dept', deptFilter.value)
      if (statusFilter.value) params.set('status', statusFilter.value)
      if (termFilter.value) params.set('term', termFilter.value)
      if (setAsideFilter.value) params.set('setaside', setAsideFilter.value)
      if (exactDate) params.set('date', exactDate)
      else if (dateFromFilter.value) params.set('from', dateFromFilter.value)
      const qs = params.toString()
      history.replaceState(null, '', qs ? `${window.location.pathname}?${qs}` : window.location.pathname)
    }

    function getActiveFilters() {
      const filters = []
      if (searchInput.value.trim()) filters.push({ type: 'keyword', label: `Keyword: "${searchInput.value}"` })
      if (deptFilter.value) filters.push({ type: 'department', label: `Dept: ${deptFilter.value.slice(0, 30)}` })
      if (statusFilter.value) filters.push({ type: 'status', label: statusFilter.value === 'open' ? 'Open Opportunities' : 'Awarded Contracts' })
      if (termFilter.value) filters.push({ type: 'term', label: `Term: ${termFilter.value}` })
      if (setAsideFilter.value) filters.push({ type: 'setaside', label: `Set-Aside: ${setAsideFilter.value}` })
      if (exactDate) filters.push({ type: 'exactDate', label: `Date: ${exactDate}` })
      else if (dateFromFilter.value) filters.push({ type: 'date', label: `After: ${dateFromFilter.value}` })
      return filters
    }

    function renderActiveFilters() {
      const filters = getActiveFilters()
      activeFiltersContainer.innerHTML = ''
      if (filters.length === 0) return
      filters.forEach(filter => {
        const chip = document.createElement('div')
        chip.className = 'filter-chip'
        chip.innerHTML = `${filter.label} <button data-filter="${filter.type}">×</button>`
        chip.querySelector('button').addEventListener('click', () => {
          if (filter.type === 'keyword') searchInput.value = ''
          else if (filter.type === 'department') deptFilter.value = ''
          else if (filter.type === 'status') statusFilter.value = ''
          else if (filter.type === 'term') termFilter.value = ''
          else if (filter.type === 'setaside') setAsideFilter.value = ''
          else if (filter.type === 'date') dateFromFilter.value = ''
          else if (filter.type === 'exactDate') exactDate = ''
          performSearch()
        })
        activeFiltersContainer.appendChild(chip)
      })
    }

    function applyFilters(records) {
      let filtered = [...records]
      if (deptFilter.value) filtered = filtered.filter(r => r.Agency === deptFilter.value)
      if (statusFilter.value === 'open') filtered = filtered.filter(r => !r.Awardee || r.Awardee.trim() === '')
      else if (statusFilter.value === 'awarded') filtered = filtered.filter(r => r.Awardee && r.Awardee.trim() !== '')
      if (termFilter.value) filtered = filtered.filter(r => r.matches.some(m => m.term === termFilter.value))
      if (setAsideFilter.value) filtered = filtered.filter(r => r.SetAside === setAsideFilter.value)
      if (exactDate) {
        filtered = filtered.filter(r => getRecordDate(r) === exactDate)
      } else if (dateFromFilter.value) {
        const fromDate = new Date(dateFromFilter.value)
        filtered = filtered.filter(r => new Date(r.PostedDate) >= fromDate)
      }
      return filtered
    }

    function performSearch() {
      const query = searchInput.value.trim()
      const filteredRecords = applyFilters(allRecords)
      renderActiveFilters()
      updateUrl()

      if (query === '' && getActiveFilters().length === 0) {
        document.getElementById('search-results').innerHTML = ''
        document.getElementById('search-stats').textContent = 'Enter keywords or select filters to search'
        return
      }

      let results = filteredRecords
      if (query) {
        results = filteredRecords.map(record => ({ ...record, score: calculateScore(query, record).score }))
          .filter(record => record.score > 0).sort((a, b) => b.score - a.score)
      }
      displayResults(results, query)
    }

    searchInput.addEventListener('input', performSearch)
    deptFilter.addEventListener('change', performSearch)
    statusFilter.addEventListener('change', performSearch)
    termFilter.addEventListener('change', performSearch)
    setAsideFilter.addEventListener('change', performSearch)
    dateFromFilter.addEventListener('change', performSearch)
    clearFiltersBtn.addEventListener('click', () => {
      searchInput.value = ''; deptFilter.value = ''; statusFilter.value = ''
      termFilter.value = ''; setAsideFilter.value = ''; dateFromFilter.value = ''
      exactDate = ''; performSearch()
    })

    const params = new URLSearchParams(window.location.search)
    if (params.get('q')) searchInput.value = params.get('q')
    if (params.get('dept')) deptFilter.value = params.get('dept')
    if (params.get('status')) statusFilter.value = params.get('status')
    if (params.get('term')) termFilter.value = params.get('term')
    if (params.get('setaside')) setAsideFilter.value = params.get('setaside')
    if (params.get('date')) exactDate = params.get('date')
    if (params.get('from')) dateFromFilter.value = params.get('from')
    if ([...params.keys()].length > 0) performSearch()
  } catch (error) {
    document.getElementById('search-results').innerHTML = '<li class="empty">Error: ' + error.message + '</li>'
  }
}

main()
