# Accessibility Commitment (ACCESSIBILITY.md)

## 1. Our Commitment

We believe accessibility is a subset of quality. This project—which actively tracks federal government contracts that require **Section 508**, **WCAG**, **VPAT**, and **OpenACR** compliance—holds itself to the same standards it helps users find. We commit to **WCAG 2.2 AA** conformance for all user-facing pages in the GitHub Pages dashboard (`docs/`) and to accessibility-aware patterns throughout all HTML templates and documentation.

We track our progress publicly to remain accountable to contributors and users.

## 2. Scope

This commitment covers:

| Component | Description |
| :--- | :--- |
| **Dashboard** (`docs/index.html`) | Main SAM.gov opportunities & awarded contracts view |
| **Search** (`docs/search.html`) | Full-text search across tracked opportunities |
| **Trends** (`docs/trends.html`) | Historical department activity and sparkline charts |
| **Opportunity pages** (`docs/opportunities/`) | Jekyll-generated detail pages for individual records |
| **Documentation** (`README.md`, `*.md`) | All project documentation in the repository root |

Scripts and data-pipeline tooling (`scripts/`) are not user-facing interfaces, but we encourage accessible practices (e.g., meaningful CLI output, screen-reader-friendly terminal messages) where practical.

## 3. Real-Time Health Metrics

| Metric | Status / Value |
| :--- | :--- |
| **Open A11y Issues** | [View open accessibility issues](https://github.com/mgifford/sam_gov_md/labels/accessibility) |
| **Target Standard** | WCAG 2.2 Level AA |
| **Automated Testing** | Active — axe-core via `github/accessibility-scanner` (`.github/workflows/a11y-scan.yml`) |
| **Browser Support** | Last 2 major versions of Chrome, Firefox, Safari |
| **Known Gaps** | See §8 below |

## 4. Contributor Requirements (The Guardrails)

When contributing to the GitHub Pages dashboard or documentation, please follow these guidelines:

### HTML & Templates

- Use **semantic HTML elements** (`<header>`, `<main>`, `<nav>`, `<section>`, `<article>`, `<footer>`, `<table>`, etc.).
- Every `<img>` must have a meaningful `alt` attribute (or `alt=""` for purely decorative images).
- Every form control (e.g., the search input) must have a visible, associated `<label>`.
- Interactive elements (links, buttons) must be keyboard reachable and have focus styles.
- Tables must include `<th scope="col|row">` headers for data tables.
- Do not rely on color alone to convey information (contrast ratio ≥ 4.5:1 for text, ≥ 3:1 for UI components).

### JavaScript & Dynamic Content

- When JavaScript updates the DOM (e.g., dashboard panels loaded via `app.js`), ensure:
  - New content is inserted in the correct DOM order.
  - Live regions (`aria-live`) or focus management are used for important status updates.
  - Loading states (e.g., the initial `-` placeholders) are meaningful to assistive technologies.
- Do not trap keyboard focus.

### SVG & Data Visualisations

- SVG-based relationship graphs (`#graph` section) must include a `<title>` element as the first child of the `<svg>` for screen reader support; use `aria-labelledby` pointing to that `<title>` id, or `aria-label` when an inline title is not practical.
- Provide a text-based fallback or summary table when SVG data is non-trivial.
- Sparkline charts in `trends.html` should include accessible labels and a data table alternative.

### Inclusive Language

- Use person-centered, respectful language in all documentation and user-visible strings.
- Avoid jargon that excludes non-specialist audiences where a plain-language alternative exists.

## 5. Automated Check Coverage

Accessibility scanning is integrated into CI via a dedicated GitHub Actions workflow (`.github/workflows/a11y-scan.yml`):

- **axe-core** HTML audits via [`github/accessibility-scanner`](https://github.com/github/accessibility-scanner) on `index.html`, `search.html`, and `trends.html` (published GitHub Pages URLs).
- Runs **monthly** (1st of every month) and on every **push to `docs/`**, plus on demand via `workflow_dispatch`.
- Findings are filed automatically as **GitHub Issues** labelled for triage; GitHub Copilot can be assigned to suggest fixes when available.
- Screenshots of failing pages are attached to each issue for context.

### Prerequisites for the a11y workflow

The `github/accessibility-scanner` action requires a fine-grained Personal Access Token (PAT) stored as a repository secret named `GH_TOKEN` with the following permissions on this repository:

| Permission | Level |
| :--- | :--- |
| `actions` | write |
| `contents` | write |
| `issues` | write |
| `pull-requests` | write |
| `metadata` | read |

The built-in `GITHUB_TOKEN` cannot be used because the action needs to open issues and (optionally) request AI-powered fixes via GitHub Copilot.

Contributors can also run axe-core locally against the development server:

```bash
# Run axe-cli against the local server (install once: npm install -g axe-cli)
python -m http.server 8000 --directory docs &
axe http://localhost:8000 http://localhost:8000/search.html http://localhost:8000/trends.html
```

## 6. Browser & Assistive Technology Testing

### Browser Support

The dashboard targets the **last 2 major versions** of:

- **Chrome / Chromium** (including Edge)
- **Firefox**
- **Safari / WebKit** (macOS and iOS)

### Assistive Technology Testing

Contributors are encouraged to test the dashboard with:

| Tool | Platform |
| :--- | :--- |
| NVDA + Firefox | Windows |
| JAWS + Chrome | Windows |
| VoiceOver + Safari | macOS / iOS |
| TalkBack + Chrome | Android |
| Keyboard-only navigation | All platforms |
| Browser zoom (200 %) | All platforms |

At minimum, verify that:

1. All dashboard panels are reachable by keyboard.
2. Screen readers announce dynamic content correctly (counts, table data, match results).
3. The search input is labelled and results are announced.
4. The relationship graph (`#graph`) has an accessible description or text alternative.

## 7. Section 508 Alignment

This project specifically helps users discover federal contracts that require **Section 508** compliance. We align the dashboard with Section 508 Technical Standards (which incorporate WCAG 2.1 AA as of 2018 and are being updated to WCAG 2.2). Specific areas of focus:

- **1194.22 (Web-based intranet and internet information and applications)** — applies to the GitHub Pages dashboard.
- **Operable UI** — all interactive components are keyboard operable without a mouse.
- **Perceivable content** — text alternatives for non-text content; captions/transcripts for any time-based media added in future.

## 8. Known Limitations

The dashboard is a living project with areas that have not yet been fully audited:

| Area | Gap | Priority |
| :--- | :--- | :--- |
| `#graph` SVG | No accessible title or text alternative | High |
| Sparkline charts (`trends.html`) | No data table fallback | High |
| Dynamic panel content (`app.js`) | No `aria-live` announcements on load | Medium |
| Search results (`search.js`) | Result count not announced to screen readers | Medium |
| Color contrast (dark labels) | `.label` and `.sub` text not yet contrast-checked | Medium |
| Mobile/touch targets | Touch target size not systematically checked | Low |

Contributions that address these gaps are very welcome — see §10.

## 9. Reporting an Accessibility Issue

If you encounter an accessibility barrier on the dashboard or in documentation, please open a GitHub Issue using the label **`accessibility`**:

- **URL:** [https://github.com/mgifford/sam_gov_md/issues/new](https://github.com/mgifford/sam_gov_md/issues/new)

When reporting, please include:

- The page URL or file path affected.
- A description of the barrier (what you expected vs. what happened).
- The assistive technology and browser/OS you were using, if applicable.
- A screenshot or screen recording if helpful.

### Severity Taxonomy

| Level | Description |
| :--- | :--- |
| **Critical** | Prevents a user from accessing core functionality (e.g., entire dashboard panel unreachable by keyboard or screen reader) |
| **High** | Significant barrier that degrades the experience without a workaround |
| **Medium** | Partial barrier; a workaround exists but is not obvious |
| **Low** | Minor improvement, visual polish, or plain-language enhancement |

## 10. Continuous Improvement

We regularly review and update:

- Dashboard HTML for semantic correctness and ARIA usage.
- `config/terms.yml` — ensuring accessibility-related search terms (Section 508, WCAG, VPAT, OpenACR, AT, assistive technology) remain current with federal procurement vocabulary.
- Documentation language for inclusivity and clarity.
- Automated tooling recommendations as the ecosystem evolves.

Contributions that improve accessibility are always welcome. See the [Contributing section in README.md](./README.md#contributing) for how to submit a pull request.

## 11. Getting Help

| Need | Where to go |
| :--- | :--- |
| Report a bug or gap | [Open an issue](https://github.com/mgifford/sam_gov_md/issues/new?labels=accessibility) |
| Ask a question | [GitHub Discussions](https://github.com/mgifford/sam_gov_md/discussions) (if enabled) or open an issue |
| Request an accommodation | Open an issue with the `accessibility-accommodation` label |
| Contribute a fix | See [README.md → Contributing](./README.md#contributing) |

---

*Last updated: 2026-03-14*
