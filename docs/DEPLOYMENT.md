# GitHub Pages Deployment

## Automatic Jekyll Build (Recommended)

GitHub Actions now automatically builds and deploys your Jekyll site to GitHub Pages.

**Workflow:** `.github/workflows/build-jekyll.yml`

This workflow:
1. Triggers on any push to `main` branch (changes to `docs/` folder)
2. Builds the Jekyll site using GitHub's official Jekyll action
3. Deploys to GitHub Pages

**The markdown files in `docs/opportunities/*/index.md` will be automatically converted to HTML.**

## GitHub Pages Configuration

If automatic deployment hasn't been set up yet:

1. Go to the repository **Settings** → **Pages**
2. Under **Source**, select **GitHub Actions**
3. Click **Save**

## URL Structure

Your opportunity markdown files will be accessible at:

```
https://mgifford.github.io/sam_gov/opportunities/{notice_id}/
```

Jekyll automatically converts `index.md` → `index.html` during the build process.

## Local Testing

To test locally:

```bash
cd docs
bundle install
bundle exec jekyll serve
```

Then visit: `http://localhost:4000/sam_gov/opportunities/`

## Data Refresh Workflow

After processing new data:

```bash
python scripts/process_today.py --target-date YYYY-MM-DD --fallback-latest
git add docs/
git commit -m "Update opportunities"
git push origin main
```

GitHub Actions will automatically rebuild and deploy.

## Troubleshooting

**Issue:** Still seeing raw markdown

**Solutions:**
1. Access directory URL (not `.md` file): `https://example.com/sam_gov/opportunities/ID/`
2. Verify GitHub Pages Source is set to **GitHub Actions**
3. Check the Actions tab to see if workflow completed successfully
4. Wait 1-2 minutes for deployment to complete
5. Clear browser cache
