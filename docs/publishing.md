# Publishing to PyPI

This project uses **Trusted Publishing (OIDC)** — no API tokens needed.
GitHub Actions authenticates directly with PyPI via identity token.

---

## One-time setup (do this once)

### 1. Create accounts

- [pypi.org](https://pypi.org/account/register/) — production
- [test.pypi.org](https://test.pypi.org/account/register/) — staging

### 2. Configure Trusted Publisher on TestPyPI

Go to: https://test.pypi.org/manage/account/publishing/

Click **"Add a new pending publisher"** and fill in:

| Field | Value |
|---|---|
| PyPI Project Name | `arch-review` |
| Owner | `juliopessan` |
| Repository name | `arch-review-assistant` |
| Workflow filename | `publish.yml` |
| Environment name | `testpypi` |

### 3. Configure Trusted Publisher on PyPI

Go to: https://pypi.org/manage/account/publishing/

Same fields, but:

| Field | Value |
|---|---|
| Environment name | `pypi` |

### 4. Create GitHub Environments

In your repo: **Settings → Environments → New environment**

Create two environments:
- `testpypi`
- `pypi` — add a **required reviewer** (yourself) for extra safety

---

## How to release

```bash
# 1. Update version in pyproject.toml and src/arch_review/__init__.py
# 2. Update CHANGELOG.md
# 3. Commit
git add pyproject.toml src/arch_review/__init__.py CHANGELOG.md
git commit -m "chore: bump version to vX.Y.Z"
git push

# 4. Tag and push — this triggers the publish workflow
git tag v0.2.0
git push origin v0.2.0
```

GitHub Actions will:
1. Build the wheel and sdist
2. Publish to TestPyPI first
3. Then publish to PyPI (requires manual approval if you added a reviewer)

---

## Verify the release

```bash
# Test from TestPyPI first
pip install --index-url https://test.pypi.org/simple/ arch-review

# Then from PyPI
pip install arch-review
arch-review --version
```
