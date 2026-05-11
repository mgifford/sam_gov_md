async function loadJson(path) {
  const response = await fetch(path)
  if (!response.ok) {
    throw new Error(`Failed to load ${path}: ${response.status}`)
  }
  return response.json()
}

function setText(id, value) {
  const node = document.getElementById(id)
  if (node) node.textContent = value
}

function money(value) {
  if (!Number.isFinite(value)) return "$0"
  if (value >= 1000000000) return `$${(value / 1000000000).toFixed(1)}B`
  if (value >= 1000000) return `$${(value / 1000000).toFixed(1)}M`
  if (value >= 1000) return `$${(value / 1000).toFixed(0)}K`
  return `$${value.toFixed(0)}`
}

function groupByAgency(rows) {
  const map = new Map()
  rows.forEach((row) => {
    const agency = row.agency || "Unknown"
    const prior = map.get(agency) || { agency, count: 0, value: 0 }
    prior.count += 1
    prior.value += Number(row.value || 0)
    map.set(agency, prior)
  })
  return [...map.values()].sort((a, b) => b.value - a.value)
}

function groupByQuarter(rows) {
  const order = ["Q1", "Q2", "Q3", "Q4"]
  const base = { Q1: 0, Q2: 0, Q3: 0, Q4: 0 }
  rows.forEach((row) => {
    const q = row.expiry_quarter || "Q1"
    base[q] = (base[q] || 0) + 1
  })
  return order.map((quarter) => ({ quarter, count: base[quarter] || 0 }))
}

function renderQuarterChart(quarterRows) {
  const container = document.getElementById("quarterChart")
  if (!container) return

  const maxCount = Math.max(...quarterRows.map((r) => r.count), 1)
  const W = 480
  const H = 200
  const pad = { top: 24, right: 20, bottom: 40, left: 40 }
  const chartW = W - pad.left - pad.right
  const chartH = H - pad.top - pad.bottom
  const slotW = chartW / quarterRows.length
  const barW = Math.floor(slotW * 0.55)

  const bars = quarterRows
    .map((row, i) => {
      const barH = Math.max(row.count > 0 ? 2 : 0, Math.round((row.count / maxCount) * chartH))
      const x = pad.left + i * slotW + (slotW - barW) / 2
      const y = pad.top + chartH - barH
      const labelY = H - pad.bottom + 16
      const countY = y - 5
      return `
        <rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW}" height="${barH}" fill="#0ea5e9" rx="3"/>
        <text x="${(x + barW / 2).toFixed(1)}" y="${labelY}" text-anchor="middle" font-size="13" fill="#334155">${row.quarter}</text>
        ${row.count > 0 ? `<text x="${(x + barW / 2).toFixed(1)}" y="${countY.toFixed(1)}" text-anchor="middle" font-size="11" fill="#59636e">${row.count}</text>` : ""}
      `
    })
    .join("")

  const titleId = "quarter-chart-title"
  container.innerHTML = `
    <svg width="100%" viewBox="0 0 ${W} ${H}" role="img" aria-labelledby="${titleId}" style="max-width:520px; display:block;">
      <title id="${titleId}">Expiry Quarter Distribution: contracts expiring each quarter</title>
      <line x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${pad.top + chartH}" stroke="#d0d7de" stroke-width="1"/>
      <line x1="${pad.left}" y1="${pad.top + chartH}" x2="${W - pad.right}" y2="${pad.top + chartH}" stroke="#d0d7de" stroke-width="1"/>
      ${bars}
    </svg>
    <table style="margin-top:12px; max-width:320px; font-size:13px;">
      <thead><tr><th>Quarter</th><th>Count</th><th>Share</th></tr></thead>
      <tbody>
        ${quarterRows
          .map((row) => {
            const total = quarterRows.reduce((s, r) => s + r.count, 0)
            const share = total ? Math.round((row.count / total) * 100) : 0
            return `<tr><td>${row.quarter}</td><td>${row.count}</td><td>${share}%</td></tr>`
          })
          .join("")}
      </tbody>
    </table>
  `
}

function renderAgencyBars(rows) {
  const container = document.getElementById("agencyBars")
  if (!rows.length) {
    container.innerHTML = '<p class="empty">No recompete rows available. Run <code>scripts/build_recompete_risk.py</code> to populate this dashboard.</p>'
    return
  }

  const top = rows.slice(0, 12)
  const maxValue = Math.max(...top.map((row) => row.value), 1)

  const html = top
    .map((row) => {
      const width = Math.max(2, Math.round((row.value / maxValue) * 100))
      return `
        <div class="bar-row">
          <div class="bar-label">${row.agency}</div>
          <div class="bar-track"><div class="bar-fill" style="width:${width}%"></div></div>
          <div style="text-align:right; font-size:12px; color:#334155;">${money(row.value)}</div>
        </div>
      `
    })
    .join("")

  container.innerHTML = `<div class="bar-wrap">${html}</div>`
}

function renderRowsTable(rows) {
  const container = document.getElementById("rowsTable")
  if (!rows.length) {
    container.innerHTML = '<p class="empty">No recompete rows available. Run <code>scripts/build_recompete_risk.py</code> to populate this dashboard.</p>'
    return
  }

  const body = rows
    .slice(0, 20)
    .map((row) => {
      const diff = Number(row.benchmark_diff || 0)
      return `
        <tr>
          <td>${row.agency || "Unknown"}</td>
          <td>${money(Number(row.value || 0))}</td>
          <td>${row.expiry_quarter || "Q1"}</td>
          <td>${row.set_aside_status || "Unknown"}</td>
          <td>${row.rule_of_two_signal || "unknown"}</td>
          <td>${diff.toFixed(1)}%</td>
        </tr>
      `
    })
    .join("")

  container.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Agency</th>
          <th>Value</th>
          <th>Expiry Quarter</th>
          <th>Set-Aside</th>
          <th>Rule-of-Two Signal</th>
          <th>Benchmark Diff</th>
        </tr>
      </thead>
      <tbody>${body}</tbody>
    </table>
  `
}

function renderTopCards(rows) {
  const total = rows.length
  const totalValue = rows.reduce((sum, row) => sum + Number(row.value || 0), 0)
  const agencies = new Set(rows.map((row) => row.agency || "Unknown"))
  const setAsides = rows.filter((row) => {
    const text = String(row.set_aside_status || "").toLowerCase()
    return text.includes("small") && (text.includes("set aside") || text.includes("set-aside"))
  })

  setText("countTotal", String(total))
  setText("totalValue", money(totalValue))
  setText("setAsideCount", String(setAsides.length))
  setText("agencyCount", String(agencies.size))
}

async function main() {
  try {
    const rows = await loadJson("data/recompetes.json")
    const count = Array.isArray(rows) ? rows.length : 0
    setText(
      "info",
      count > 0
        ? `Loaded ${count} recompete rows from docs/data/recompetes.json`
        : "No recompete data yet — run scripts/build_recompete_risk.py to populate this dashboard.",
    )

    renderTopCards(rows)
    renderQuarterChart(groupByQuarter(rows))
    renderAgencyBars(groupByAgency(rows))
    renderRowsTable(rows)
  } catch (error) {
    setText("info", `Failed to load recompete data: ${error.message}`)
    setText("countTotal", "0")
    setText("totalValue", "$0")
    setText("setAsideCount", "0")
    setText("agencyCount", "0")
    document.getElementById("quarterChart").innerHTML = '<p class="empty">Could not load recompete data.</p>'
    document.getElementById("agencyBars").innerHTML = '<p class="empty">Could not load recompete data.</p>'
    document.getElementById("rowsTable").innerHTML = '<p class="empty">Could not load recompete data.</p>'
  }
}

main()
