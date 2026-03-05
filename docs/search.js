async function loadJson(path) {
  const response = await fetch(path)
  if (!response.ok) {
    throw new Error(`Failed to load ${path}: ${response.status}`)
  }
  return response.json()
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
    Description: raw.Description || '',
    Awardee: raw.Awardee || '',
    matches: raw.matches || [],
  }
}

function calculateScore(query, record) {
  const queryTerms = query.toLowerCase().split(/\s+/).filter(t => t.length > 0)
  let score = 0
  let matchedTerms = []

  const title = (record.Title || '').toLowerCase()
  const agency = (record.Agency || '').toLowerCase()
  const description = (record.Description || '').toLowerCase()
  const terms = (record.matches || []).map(m => m.term.toLowerCase())

  queryTerms.forEach(qterm => {
    // Title matches (high weight)
    if (title.includes(qterm)) {
      score += 100 * (title.match(new RegExp(qterm, 'g')) || []).length
      matchedTerms.push(`Title`)
    }

    // Agency matches (medium weight)
    if (agency.includes(qterm)) {
      score += 50 * (agency.match(new RegExp(qterm, 'g')) || []).length
      matchedTerms.push(`Agency`)
    }

    // Description matches (medium weight)
    if (description.includes(qterm)) {
      score += 30 * (description.match(new RegExp(qterm, 'g')) || []).length
      matchedTerms.push(`Description`)
    }

    // Term matches (high weight - these are your tracked terms)
    terms.forEach(t => {
      if (t.includes(qterm)) {
        score += 75
        matchedTerms.push(`Term: ${record.matches.find(m => m.term.toLowerCase() === t)?.term}`)
      }
    })
  })

  return {
    score,
    matchedTerms: [...new Set(matchedTerms)],
  }
}

function displayResults(results, query) {
  const resultsContainer = document.getElementById('search-results')
  const statsContainer = document.getElementById('search-stats')

  if (results.length === 0) {
    resultsContainer.innerHTML = '<li class="empty">No results found. Try different keywords.</li>'
    statsContainer.textContent = `No results for "${query}"`
    return
  }

  statsContainer.textContent = `Found ${results.length} result${results.length !== 1 ? 's' : ''} for "${query}"`
  resultsContainer.innerHTML = ''

  results.slice(0, 50).forEach((record, idx) => {
    const li = document.createElement('li')
    li.className = 'result-item'

    const posted = (record.PostedDate || '').slice(0, 10)
    const excerpt = (record.Description || '').slice(0, 150) + (record.Description?.length > 150 ? '...' : '')

    const markdownLink = record.NoticeId
      ? `<a href="opportunities/${record.NoticeId}/index.md" target="_blank" rel="noreferrer">Markdown</a>`
      : ''
    const samLink = record.Link
      ? `<a href="${record.Link}" target="_blank" rel="noreferrer">SAM.gov</a>`
      : ''

    li.innerHTML = `
      <div class="result-title">
        <a href="${record.Link || '#'}" target="_blank" rel="noreferrer">${record.Title || 'Untitled'}</a>
      </div>
      <div class="result-meta">
        <span><strong>Agency:</strong> ${record.Agency || 'Unknown'}</span>
        <span><strong>Type:</strong> ${record.Type || 'Unknown'}</span>
        <span><strong>Posted:</strong> ${posted}</span>
      </div>
      ${excerpt ? `<div class="result-excerpt">${excerpt}</div>` : ''}
      <div class="result-links">
        ${markdownLink}
        ${samLink}
      </div>
    `
    resultsContainer.appendChild(li)
  })

  if (results.length > 50) {
    const moreInfo = document.createElement('li')
    moreInfo.className = 'empty'
    moreInfo.textContent = `Showing 50 of ${results.length} results`
    resultsContainer.appendChild(moreInfo)
  }
}

async function main() {
  try {
    const records = await loadJson('data/today_records.json')
    const allRecords = (records || []).map(normalizeRecord)

    const searchInput = document.getElementById('search-input')

    function performSearch(query) {
      if (!query.trim()) {
        document.getElementById('search-results').innerHTML = ''
        document.getElementById('search-stats').textContent = ''
        return
      }

      const scored = allRecords
        .map((record) => ({
          ...record,
          score: calculateScore(query, record).score,
        }))
        .filter((record) => record.score > 0)
        .sort((a, b) => b.score - a.score)

      displayResults(scored, query)
    }

    searchInput.addEventListener('input', (event) => {
      performSearch(event.target.value)
    })

    // Trigger search if there's a query parameter
    const params = new URLSearchParams(window.location.search)
    const q = params.get('q')
    if (q) {
      searchInput.value = q
      performSearch(q)
    }
  } catch (error) {
    document.getElementById('search-results').innerHTML =
      '<li class="empty">Error loading search data: ' + error.message + '</li>'
  }
}

main()
