# Deploy & Submission Checklist

## 1. Build & Push Docker Image

```bash
# From project root (not ./src)
docker buildx build --platform linux/amd64 -f src/Dockerfile -t rmoraes4/rinha-api-python3:latest . --push
```

- [ ] Image pushed to `docker.io/rmoraes4/rinha-api-python3:latest`

---

## 2. Update submission branch infra files

```bash
git checkout submission

# Edit docker-compose.yml / nginx.conf / info.json as needed

git add docker-compose.yml nginx.conf info.json
git commit -m "chore: update infra files"
git push origin submission
```

- [ ] `docker-compose.yml` — image name matches Docker Hub tag
- [ ] `info.json` — source-code-repo URL is correct
- [ ] `nginx.conf` — present at repo root

---

## 3. Pre-push checklist

| Item | Check |
|---|---|
| Total CPU ≤ 1.00 (lb + api1 + api2) | [ ] |
| Total RAM ≤ 350MB | [ ] |
| Port 9999 exposed on lb | [ ] |
| `platform: linux/amd64` on all services | [ ] |
| Network driver is `bridge` | [ ] |
| No `network_mode: host` or `privileged` | [ ] |
| At least 1 LB + 2 API services | [ ] |
| Repo is **public** on GitHub | [ ] |
| Branches `main` and `submission` pushed | [ ] |
| `docker-compose.yml` + `info.json` at root of `submission` | [ ] |

---

## 4. Open PR to official repo

```bash
cd ~/personal/projetos/rinha-de-backend/rinha-de-backend-2026

# Sync fork with upstream
git checkout main
git pull origin main

# Create branch and update participants file
git checkout -b chore/add-mpraes-<project>
# Edit participants/mpraes.json — add new { "id": "...", "repo": "..." } entry

git add participants/mpraes.json
git commit -m "participants: add <project> submission for mpraes"
git push fork chore/add-mpraes-<project>

# Open PR against upstream
gh pr create \
  --repo zanfranceschi/rinha-de-backend-2026 \
  --head mpraes:chore/add-mpraes-<project> \
  --base main \
  --title "participants: add <project> submission for mpraes" \
  --body "## Summary
Add submission entry to \`participants/mpraes.json\`.

## Changes
- Add \`<project>\` → https://github.com/mpraes/<project>

## Submission checklist
- [x] Total across services respects the limit of 1 CPU and 350MB RAM
- [x] Backend exposes port 9999
- [x] Images are linux/amd64
- [x] Network mode is bridge
- [x] Does not use \`network_mode: host\` nor \`privileged\`
- [x] Has at least 1 load balancer + 2 APIs
- [x] Repository is public and contains branches \`main\` and \`submission\`
- [x] Branch \`submission\` contains \`docker-compose.yml\` and \`info.json\` at repo root"
```

- [ ] PR opened at `github.com/zanfranceschi/rinha-de-backend-2026/pulls`

---

## 5. Retrigger CI after fixing participant repos

The smoke test runs on PR push, not when you push to participant repos.  
If you fix the `submission` branch after opening the PR, force a rerun with an empty commit:

```bash
cd ~/personal/projetos/rinha-de-backend/rinha-de-backend-2026
git checkout chore/add-mpraes-<project>
git commit --allow-empty -m "ci: retrigger smoke tests"
git push fork chore/add-mpraes-<project>
```

- [ ] All smoke tests green on the PR

---

## Common Errors

| Error | Cause | Fix |
|---|---|---|
| `"daemon" directive is duplicate` | `daemon off;` in `nginx.conf` — the official nginx image sets this internally | Remove `daemon off;` from `nginx.conf` |
| `open Dockerfile: no such file or directory` | `submission` branch has `build: .` but no `Dockerfile` committed | Add `Dockerfile` to the `submission` branch |
| `failed to compute cache key: "/resources": not found` | Docker build context is `./src` but `resources/` is at project root | Build from project root: `docker buildx build -f src/Dockerfile .` |
| YAML anchor `!reset` not supported | `build: !reset null` is not standard Docker Compose | Replace with two explicit service blocks instead of using anchors |
| Smoke test re-runs but still fails | Remote participant repo was fixed after the PR was already running | Push an empty commit to the PR branch (see step 5) |
