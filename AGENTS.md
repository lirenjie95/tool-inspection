# AGENTS.md

## 分支约定 / Branching Convention

- 主分支固定为 `master`，受分支保护，所有变更必须通过 PR 合入。
  The main branch is always `master`. It is protected; all changes must go through a PR.
- 开发分支固定为 `slave`。新开发从 `master` 检出 `slave` 分支；如果 `slave` 已被占用，则依次使用 `slave-asia`、`slave-africa`、`slave-north-america`、`slave-south-america`、`slave-antarctica`、`slave-europe`、`slave-oceania` 等 `slave` 加大洲名字的分支名。
  The development branch is always `slave`. Check out `slave` from `master` for new work; if `slave` is already taken, use continent-suffixed names in order, such as `slave-asia`, `slave-africa`, `slave-north-america`, `slave-south-america`, `slave-antarctica`, `slave-europe`, `slave-oceania`.
- 开发完毕后提 PR 到 `master`，CI 通过并合并后删除该 `slave` 分支。
  When development is done, open a PR targeting `master`; after CI passes and the merge completes, delete the `slave` branch.
- 是否打 tag 以及 tag 版本号（`vX.Y.Z`）根据本次修改的内容决定。
  Whether to tag and which version number (`vX.Y.Z`) to use is decided based on the changes made.

## 测试与检查 / Tests & Checks

- 运行测试 / Run tests: `python -m pytest tests/`
- Lint: `flake8 client/ server/ scripts/ tests/ --max-line-length=250 --extend-ignore=E402`
- CI（`.github/workflows/ci-cd.yml`）只在 `master` 的 push 和 PR 上运行（`slave` 不触发）；合入 `master` 前必须通过。
  CI runs only on pushes and PRs to `master` (`slave` does not trigger CI); it must pass before merging into `master`.
