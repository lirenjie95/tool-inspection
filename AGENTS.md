# AGENTS.md

## 分支约定 / Branching Convention

- 主分支固定为 `master`，受分支保护，所有变更必须通过 PR 合入。
  The main branch is always `master`. It is protected; all changes must go through a PR.
- 开发/集成分支固定为 `slave`。新功能或修复从 `slave` 检出分支，PR 一律以 `slave` 为 base。
  The development/integration branch is always `slave`. Branch off `slave` for features and fixes, and target `slave` as the PR base.
- 发布时通过 `slave` → `master` 的 PR 合入，CI 通过并合并后在 `master` 上打 tag（`vX.Y.Z`）。
  To release, merge `slave` into `master` via PR; after CI passes and the merge completes, tag `master` (`vX.Y.Z`).

## 测试与检查 / Tests & Checks

- 运行测试 / Run tests: `python -m pytest tests/`
- Lint: `flake8 client/ server/ scripts/ tests/ --max-line-length=250 --extend-ignore=E402`
- CI（`.github/workflows/ci-cd.yml`）只在 `master` 的 push 和 PR 上运行（`slave` 不触发）；合入 `master` 前必须通过。
  CI runs only on pushes and PRs to `master` (`slave` does not trigger CI); it must pass before merging into `master`.
