# SBOM and Software Risk Register

This document tracks software components used in this repository to support legal, licensing, and security risk management.

## Scope
- Repository: `mgifford/sam_gov_md`
- Primary language/runtime: Python (`>=3.12`)
- Build/test/deploy surface: local CLI scripts + GitHub Actions workflows + GitHub Pages

## First-party project metadata

| Component | Version source | Current value | License |
|---|---|---|---|
| `sam-gov-md` project | `pyproject.toml` | `0.1.0` | AGPL-3.0-or-later (`LICENSE`) |
| Python runtime | `pyproject.toml` (`requires-python`) | `>=3.12` | PSF |

## Direct Python dependencies (application + tooling)

Source: `pyproject.toml` (`[project].dependencies`)

| Package | Declared version | License status | Notes |
|---|---|---|---|
| beautifulsoup4 | `>=4.14.3` | Review on upgrade | HTML parsing |
| lxml | `>=6.1.1` | Review on upgrade | XML parsing |
| playwright | `>=1.60.0` | Review on upgrade | Browser automation |
| pdfplumber | `>=0.11.8` | Review on upgrade | PDF extraction |
| python-docx | `>=1.2.0` | Review on upgrade | DOCX processing |
| pyyaml | `>=6.0.1` | Review on upgrade | YAML config loading |
| requests | `>=2.31.0` | Review on upgrade | HTTP client |
| pytest | `>=9.0.3` | Review on upgrade | Test framework |

## GitHub Actions software supply chain

Source: `.github/workflows/*.yml`

| Action | Version | Purpose |
|---|---|---|
| actions/checkout | `v6` | Source checkout |
| actions/setup-python | `v6` | Python runtime setup |
| astral-sh/setup-uv | `v8` | uv setup |
| actions/github-script | `v8` | Issue automation |
| actions/configure-pages | `v6` | Pages build config |
| actions/jekyll-build-pages | `v1` | Jekyll build |
| actions/upload-pages-artifact | `v4` | Upload Pages artifact |
| actions/deploy-pages | `v5` | Deploy GitHub Pages |
| github/accessibility-scanner | `v2` | Accessibility scans |

## Version-control and licensing control process

1. **Dependency change trigger**: when `pyproject.toml`, `uv.lock`, or workflow `uses:` lines change.
2. **Version lock update**: regenerate lockfile with `uv lock` and commit `uv.lock`.
3. **License review**:
   - Confirm compatibility with AGPL-3.0-or-later for newly introduced dependencies/actions.
   - Record review results by updating this file’s tables.
4. **Security review**:
   - Check advisories for newly added dependencies.
   - Prefer pinned major versions for Actions and upgrade intentionally.
5. **Audit cadence**: review this file at least monthly and during dependency upgrades.

## Authoritative machine-readable sources
- Python dependencies + constraints: `pyproject.toml`
- Resolved Python dependency graph: `uv.lock`
- CI/CD action dependencies: `.github/workflows/*.yml`
