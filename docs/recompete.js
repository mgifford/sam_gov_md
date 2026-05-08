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

const PARACHARTS_IMPORT_URLS = [
  "https://cdn.jsdelivr.net/npm/@fizz/paracharts@0.40.0/dist/paracharts.js",
  "https://cdn.jsdelivr.net/gh/fizzstudio/ParaCharts@main/dist/paracharts.js",
]

async function loadParaChartsLibrary() {
  if (customElements.get("para-chart")) {
    return true
  }

  for (const url of PARACHARTS_IMPORT_URLS) {
    try {
      await import(url)
      if (customElements.get("para-chart")) {
        return true
      }
    } catch (_error) {
      // Keep trying alternative URLs.
    }
  }
  return false
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

function renderAgencyBars(rows) {
  const container = document.getElementById("agencyBars")
  if (!rows.length) {
    container.innerHTML = '<p class="empty">No recompete rows available.</p>'
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

function renderQuarterTable(rows) {
  const container = document.getElementById("quarterTable")
  if (!rows.length) {
    container.innerHTML = '<p class="empty">No quarter data available.</p>'
    return
  }

  const total = rows.reduce((sum, row) => sum + row.count, 0)
  const body = rows
    .map((row) => {
      const share = total ? Math.round((row.count / total) * 100) : 0
      return `<tr><td>${row.quarter}</td><td>${row.count}</td><td>${share}%</td></tr>`
    })
    .join("")

  container.innerHTML = `
    <table>
      <thead>
        <tr><th>Quarter</th><th>Count</th><th>Share</th></tr>
      </thead>
      <tbody>${body}</tbody>
    </table>
  `
}

function renderRowsTable(rows) {
  const container = document.getElementById("rowsTable")
  if (!rows.length) {
    container.innerHTML = '<p class="empty">No sample rows available.</p>'
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

function renderParachartsFallback(specs, reason) {
  const mount = document.getElementById("parachartsMount")
  const status = document.getElementById("paraStatus")
  const manifests = specs?.manifests || []
  setText("paraStatus", reason)

  if (!manifests.length) {
    mount.innerHTML = '<p class="empty">No chart manifests available yet.</p>'
    return
  }

  const rows = manifests
    .map((item) => {
      const chartType = item.manifest?.type || "unknown"
      const categoryCount = (item.manifest?.categories || []).length
      return `<tr><td>${item.title}</td><td>${chartType}</td><td>${categoryCount}</td></tr>`
    })
    .join("")

  mount.innerHTML = `
    <p class="sub" style="margin-top:0;">ParaCharts script could not be loaded in this environment, so this fallback summarizes the generated manifests.</p>
    <table>
      <thead><tr><th>Manifest</th><th>Type</th><th>Categories</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `
}

function renderParacharts(specs) {
  const mount = document.getElementById("parachartsMount")
  const manifests = specs?.manifests || []

  if (!manifests.length) {
    setText("paraStatus", "Loaded ParaCharts specs, but no manifests are populated yet.")
    mount.innerHTML = '<p class="empty">No chart manifests available yet.</p>'
    return
  }

  setText("paraStatus", `Loaded ${manifests.length} ParaCharts manifests.`)
  mount.innerHTML = ""

  manifests.forEach((entry) => {
    const host = document.createElement("article")
    host.className = "chart-host"

    const title = document.createElement("h3")
    title.className = "chart-title"
    title.textContent = entry.title || entry.id || "ParaChart"
    host.appendChild(title)

    const desc = document.createElement("p")
    desc.className = "chart-desc"
    desc.textContent = entry.description || ""
    host.appendChild(desc)

    const element = document.createElement("para-chart")
    const manifest = entry.manifest || {}
    element.setAttribute("manifestType", "content")
    element.setAttribute("manifest", JSON.stringify(manifest))
    if (manifest.type) {
      element.setAttribute("type", manifest.type)
    }
    element.setAttribute("description", entry.description || entry.title || "")
    host.appendChild(element)

    mount.appendChild(host)
  })
}

async function main() {
  try {
    const [rows, specs] = await Promise.all([
      loadJson("data/recompetes.json"),
      loadJson("data/recompetes_paracharts_specs.json"),
    ])
    setText("info", `Loaded ${rows.length} recompete rows from docs/data/recompetes.json`)

    renderTopCards(rows)
    renderAgencyBars(groupByAgency(rows))
    renderQuarterTable(groupByQuarter(rows))
    renderRowsTable(rows)

    const hasParaCharts = await loadParaChartsLibrary()
    if (hasParaCharts) {
      renderParacharts(specs)
    } else {
      renderParachartsFallback(
        specs,
        "ParaCharts library could not be loaded from public CDN; showing manifest fallback.",
      )
    }
  } catch (error) {
    setText("info", `Failed to load recompete data: ${error.message}`)
    setText("countTotal", "0")
    setText("totalValue", "$0")
    setText("setAsideCount", "0")
    setText("agencyCount", "0")
    setText("paraStatus", "Failed to load ParaCharts specs.")
    document.getElementById("agencyBars").innerHTML = '<p class="empty">Run the recompete pipeline to generate docs/data/recompetes.json.</p>'
    document.getElementById("quarterTable").innerHTML = '<p class="empty">No quarter data available.</p>'
    document.getElementById("rowsTable").innerHTML = '<p class="empty">No rows available.</p>'
    document.getElementById("parachartsMount").innerHTML = '<p class="empty">No ParaCharts data available.</p>'
  }
}

main()
