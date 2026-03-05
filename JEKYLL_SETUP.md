# Markdown-to-HTML Rendering Setup

## What Was Configured

Your Jekyll site is now configured to automatically render all `.md` files as HTML on GitHub Pages.

### Files Created/Updated:

1. **`docs/_config.yml`** - Updated Jekyll configuration
   - Added `baseurl: /sam_gov` - ensures correct URLs on GitHub Pages
   - Added `permalink: /:path/` - converts .md files to directory indexes
   - Added plugins: jekyll-seo-tag, jekyll-sitemap
   - Set markdown processor to kramdown with GitHub Flavored Markdown

2. **`docs/Gemfile`** - New Ruby dependencies file
   - Specifies `github-pages` gem (includes all GitHub Pages dependencies)
   - Additional plugins for SEO and sitemap generation

3. **`.github/workflows/build-jekyll.yml`** - New GitHub Actions workflow
   - Automatically builds Jekyll site on every push to `main`
   - Deploys to GitHub Pages using official deployment action
   - Converts `.md` files to `.html` during build

4. **`docs/DEPLOYMENT.md`** - Updated deployment documentation

## How It Works

### Before (Raw Markdown)
```
Source:  docs/opportunities/{ID}/index.md
URL:     https://mgifford.github.io/sam_gov/opportunities/{ID}/index.md
Result:  Raw markdown text displayed in browser
```

### After (Rendered HTML)
```
Source:  docs/opportunities/{ID}/index.md
Build:   Jekyll processes .md → generates HTML
Output:  docs/_site/opportunities/{ID}/index.html
URL:     https://mgifford.github.io/sam_gov/opportunities/{ID}/
Result:  Formatted HTML page with styling
```

## Next Steps

### Step 1: GitHub Pages Configuration
1. Go to your GitHub repository **Settings** → **Pages**
2. Under **Source**, select **GitHub Actions** (not "Deploy from a branch")
3. Click **Save**

### Step 2: Commit and Push
```bash
git add docs/_config.yml docs/Gemfile docs/DEPLOYMENT.md .github/workflows/build-jekyll.yml
git commit -m "Configure Jekyll for markdown rendering"
git push origin main
```

### Step 3: Monitor Workflow
1. Go to repository **Actions** tab
2. Watch for "Build and Deploy Jekyll Site" workflow
3. Wait for green checkmark (1-2 minutes)

### Step 4: Verify Rendering
Visit an opportunity page (without `.md` extension):
```
https://mgifford.github.io/sam_gov/opportunities/{notice_id}/
```

Should show **formatted HTML**, not raw markdown.

## Key Permissions Needed

The GitHub Actions workflow requires:
- `pages: write` - to deploy to Pages
- `id-token: write` - for OIDC authentication
- `contents: read` - to read the repository

These are automatically configured in `.github/workflows/build-jekyll.yml`

## Local Testing (Optional)

To test the Jekyll build locally before pushing:

```bash
cd docs
bundle install
bundle exec jekyll serve --baseurl="/sam_gov"
```

Visit `http://localhost:4000/sam_gov/opportunities/`

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Still seeing raw `.md` file | Access directory URL (no `.md`): `/opportunities/ID/` not `/opportunities/ID/index.md` |
| 404 errors on opportunity pages | Check that workflow completed successfully in Actions tab |
| Styling looks broken | Ensure `baseurl: /sam_gov` is correct in `_config.yml` |
| Pages not updating | Wait 1-2 minutes after push, then hard refresh browser (Cmd+Shift+R) |

## Processing Workflow

When you run `scripts/process_today.py`:

1. ✅ Generates `docs/opportunities/*/index.md` with Jekyll front matter
2. ✅ Markdown files have proper layout: `layout: default`
3. ✅ On push, GitHub Actions builds the site
4. ✅ Jekyll converts all `.md` → `.html`
5. ✅ Pages deployed to GitHub Pages

Each markdown page includes:
```yaml
---
layout: default
title: Opportunity Title
agency: Agency Name
notice_type: Solicitation
---
```

This tells Jekyll to:
- Use the `_layouts/default.html` template
- Pass variables to the page template
- Generate HTML from the markdown content
