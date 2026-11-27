# Project Context

**Project:** q250-v3-opti
**Goal:** Q250-V3-Opti: Jetson Orin TensorRT INT8 + CUDA Kernel Optimization with 5 tasks T-01 through T-05 with DoD criteria
**Status:** active

## Stop Condition

The project should stop when: All T-01 through T-05 DoD verified on Jetson Orin target
If the stop condition appears to be met, the leader should raise a motion for the team to vote on whether to stop.

**Heartbeat Member:** leader (woken every 10 min)

## Kanban Summary

- Triage: 0 | Todo: 16 | Ready (queued): 0 | Running: 2 | Blocked: 18 | In review: 0 | Done: 30

**Todo tasks:**
- `t_2ee30393` assignee=developer — Implement calibration improvements: CLI args (--calib_batche
- `t_239faff6` assignee=developer — Build and validate CUDA kernels (libtrajectory_kernels.so) o
- `t_e79e2d72` assignee=researcher — Run TensorRT INT8 calibration validation (entropy vs percent
- `t_4db858cf` assignee=devops — Verify CI/build pipeline integration with cloud GPU environm
- `t_7e37d686` assignee=tester — Design and implement CUDA/TensorRT test fixtures and benchma
- ... +11 more

**Running tasks:**
- `t_a8822365` assignee=reviewer — Validate INT8 calibration algorithm correctness (entropy vs 
- `t_404560c4` assignee=developer — Execute Track B gates on Jetson Orin: DLA engine build, nati

**Blocked tasks:**
- `t_e422abdb` assignee=developer — [Developer] Jetson Orin에서 CUDA 커널 빌드 및 검증
- `t_030f0a53` assignee=devops — [DevOps] CI Lint/Format 수정 및 Jetson 빌드 환경 검증 스크립트 준비
- `t_40ece852` assignee=researcher — [Researcher] TensorRT INT8 캘리브레이션 전략 검증 및 Jetson Orin 베스트 프랙
- `t_72c75ff8` assignee=tester — [Tester] CUDA/TensorRT 검증 테스트 설계 및 테스트 픽스처 준비
- `t_fe13bd88` assignee=researcher — Validate TensorRT INT8 calibration strategy with agreed spec
- ... +13 more

**Last heartbeat:** 2026-11-27T04:20:18.412626+00:00

## Recent Decisions

- `[t_3456f063]` ✅ Jetson Orin target access blocker - how to proceed with T-01
- `[t_3e0445d2]` ✅ Coordinate Jetson Orin target validation execution
- `[t_4f744038]` ✅ Coordinate final Jetson Orin target validation for T-01~T-05

## Workflow

1. Check your assigned tasks with `agora_project_status` or `hermes kanban list`.
2. Use `kanban show <task_id>` to read task details.
3. **Developer:** after completing a task, if your team has a `reviewer`,
   use `kanban_request_review(task_id, summary="...")` to submit for code
   review (summary describes what was implemented + how it was verified).
   The reviewer is auto-spawned. If the reviewer requests changes, fix the
   findings and re-submit. If no `reviewer` on team, use `kanban complete`.
4. **Reviewer:** approve with `kanban complete`; reject with
   `kanban_request_changes(task_id, reason="concrete findings")` — the
   task routes back to the implementer automatically.
5. **All other roles:** use `kanban complete <task_id>` when done.
6. If blocked, use `kanban block <task_id>` with a clear explanation.
7. For design decisions that need team input, use `agora_raise_motion`.
8. **Never** use Python, terminal, or direct DB calls to manage tasks/motions.
   Always use agora tools (`agora_raise_motion`, `agora_create_task`, etc.).
