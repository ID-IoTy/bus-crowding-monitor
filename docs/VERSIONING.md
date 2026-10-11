# Versioning and integration

## Preserved baseline

`frontend` remains at `596f559085c134f471c79c26be38c877b0738751`, the initial three-bus demo. `frontend-v2` was created from that exact commit. `integration` was created from main commit `804bba0aea5ff4595c6b51cf92a172c92424ede3`.

To inspect the baseline without changing an existing checkout, clone the repository into a separate directory and check out `frontend`, or create a new branch from the baseline SHA. Follow the baseline's own frontend README. Dependencies are pinned by its lockfile; external map tiles/fonts still require their providers.

The planned `v0.1.0-demo` tag and "Initial frontend demo" release are pending, not created. Once available, create them targeting the exact baseline SHA (or the still-frozen `frontend` branch). Include launch instructions and a note that this is a frontend-only synthetic demo. Do not target main by default.

## Workflow

Current status: `frontend-v3-compact-bus` is the active standalone deliverable; earlier iterations are preserved. Integration is deferred by project decision; the sequence below is a future workflow, not completed work.

1. Commit v2 work on `frontend-v2`, preserving the baseline branch.
2. Open component PRs targeting `integration`, in order: frontend-v2, backend, Arduino.
3. Review differences and merge using merge commits. Resolve shared documentation semantically; never discard an entire colleague branch to resolve a conflict.
4. Develop integration adapters on a branch from integration and merge through a PR after tests.
5. Only promote integration to main after the supported end-to-end paths pass, recording any hardware limitations.
6. Publish `v0.2.0-integrated-demo` only after the milestone is actually verified. A repository merge alone does not establish runtime interoperability.

No force pushes, baseline tag movement, or deletion of colleagues' branches. Re-fetch branch heads immediately before merging/publishing to accommodate concurrent team changes. A PR is a proposed comparison; opening it does not modify its target.

## Visual variation

`frontend-v2-clean-map` starts from completed v2 commit `b08777bb03a81dfe018ef76447e188fb846bc7ee`. It contains presentation refinements only; `frontend-v2` remains recoverable unchanged. Integration is still deferred.

## Capacity iteration and recovery index

The active layout iteration is `frontend-v3-compact-bus`, based on map-contrast commit `8856db7ada86d43c44b358af71523d2a2ee7ae5c`. It removes the white route gap, compacts bus markers and compares predicted occupancy before/after the selected stop. Earlier branches remain unchanged.

| Iteration | Preserved branch | Exact starting or completed commit |
| --- | --- | --- |
| Initial three-bus demo | `frontend` | `596f559085c134f471c79c26be38c877b0738751` |
| Completed frontend v2 | `frontend-v2` | `b08777bb03a81dfe018ef76447e188fb846bc7ee` |
| Compact map, 75 total / 32 seated | `frontend-v2-clean-map` | `c478f111c6ebfa97e8433676e4563ed022e7a0d4` |
| Compact map, 70 total / 25 seated | `frontend-v2-capacity-70` | `536b3d0022264125434b4603406282776bee7395` |
| Stop-first passenger planner | `frontend-v3-journey` | `5dda674b54e005ec369ab3754fcc974fef028a58` |
| Passenger cards left, map right | `frontend-v3-side-map` | `31461bc1e824c7e96990e3e532b96840db537b58` |
| Logo-only shell, URL interface selection | `frontend-v3-minimal` | `e2c80029697bfc3b1f77d48610de00ef9250579a` |
| Desktop window fit and detail dialogs | `frontend-v3-desktop-fit` | `45783509036c1ae330c5e15bc7b9d4b02245aa57` |
| Inline selected bus and clean percentages | `frontend-v3-inline-bus` | `d63896fe6282903e142ec6a1bc19ec97916941dc` |
| Route contrast and line-only bus labels | `frontend-v3-map-contrast` | `8856db7ada86d43c44b358af71523d2a2ee7ae5c` |
| Compact markers and before/after percentages | `frontend-v3-compact-bus` | Starts at `8856db7ada86d43c44b358af71523d2a2ee7ae5c` |

For each future iteration, keep the last delivered branch frozen and create a new working branch from its verified head. Record the source SHA and the change here. Recover a previous iteration in a separate clone using `git switch --detach <exact-commit-sha>`, or create a new branch from that SHA. Use that iteration's lockfile and README; do not reset or force-push a shared branch. Integration remains deferred.

