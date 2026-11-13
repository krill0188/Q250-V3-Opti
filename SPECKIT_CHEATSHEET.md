# SpecKit Quick Reference Card (치트시트)

> **개발 중 언제든 꺼내보는 1페이지 요약**

---

## 📋 tasks.md 핵심 문법

```markdown
### T-XX: 태스크 제목
- **설명**: 한 줄 요약
- **산출물**: `경로/파일명.ext`
- **의존성**: T-XX, T-YY
- **DoD**: 검증 가능한 완료 조건 (자동 테스트 통과 등)
- **예상**: N일
```

### 의존성 체인
```markdown
T-01 → T-02 → T-03
```

### 병렬 그룹
```markdown
| 그룹 | 작업 | 비고 |
|------|------|------|
| Group A | T-11~T-20 | 병렬 가능 |
```

### 마일스톤
```markdown
| 마일스톤 | 목표 | 완료 기준 |
|----------|------|-----------|
| M1 | Week 2 | T-10 완료 |
```

---

## 🏷️ 태스크 ID 체계

| 접두사 | 의미 | 예시 |
|--------|------|------|
| **T-** | 일반 태스크 | T-01, T-42 |
| **M-** | 마일스톤 | M1, M2 |
| **G-** | 그룹 | Group A, Group B |

---

## ✅ DoD (Definition of Done) 템플릿

| 레벨 | 예시 |
|------|------|
| **코드** | `colcon build` 성공, 정적 분석 통과 |
| **테스트** | 단위 테스트 100% 통과, 커버리지 ≥ 80% |
| **문서** | README 업데이트, API 문서 자동 생성 |
| **배포** | Docker 이미지 빌드·푸시 성공 |
| **릴리즈** | `gh release create vX.Y.Z` 완료 |

---

## 🔄 Git 커밋 메시지 규칙 (Conventional Commits)

```
<type>(<scope>): <subject>

<body>

<footer>
```

| Type | 용도 | 예시 |
|------|------|------|
| `feat` | 새 기능 | `feat(bridge): add MAVLink proxy` |
| `fix` | 버그 수정 | `fix(voice): handle VAD timeout` |
| `refactor` | 리팩토링 | `refactor(bridge): simplify coordinator` |
| `docs` | 문서만 | `docs: update API reference` |
| `test` | 테스트 추가 | `test(bridge): add integration test` |
| `chore` | 빌드/설정 | `chore: update dependencies` |
| `perf` | 성능 개선 | `perf(optimizer): reduce solve time` |

**자동 생성**: `git commit -m "feat(bridge): add Silvus proxy"` → GitHub Actions가 tasks.md 진행률 업데이트

---

## 🌿 Git 브랜치 전략

```
main (보호됨)
  ├── develop
  │   ├── feature/T-XX-태스크명
  │   ├── fix/T-XX-버그명
  │   └── refactor/모듈명
  └── release/vX.Y.Z (태그)
```

**보호 규칙**: main/develop 직접 푸시 금지 → PR 필수 + CI 통과 + 리뷰 1명 이상

---

## 🤖 AI 협업 프롬프트 템플릿

```markdown
# AI에게 주는 프롬프트 템플릿

내 .specs/tasks.md를 읽고 T-XX 태스크를 구현해줘.

## 컨텍스트
- 의존 태스크: T-XX, T-YY (이미 완료)
- 관련 파일: src/모듈/파일.py
- 코드 스타일: 기존 src/모듈/ 스타일 따라줘

## 요구사항
1. 요구사항 1
2. 요구사항 3

## DoD
- 단위 테스트 100% 통과
- 정적 분석 통과 (ruff, mypy)
- 기존 테스트 깨지지 않음

## 산출물
- 구현 코드
- 단위 테스트
- 필요시 문서 업데이트
```

---

## 🔧 유용한 별칭 (alias)

```bash
# ~/.bashrc 또는 ~/.zshrc에 추가

# SpecKit 프로젝트 이동
alias sp="cd ~/projectm/Q250-V3-Opti"

# tasks.md 보기
alias tasks="cat .specs/tasks.md | head -100"

# 현재 태스크 상태
alias task-status="grep -E '^### T-' .specs/tasks.md | tail -5"

# 현재 Phase 진행률
alias phase-progress="python3 scripts/phase_progress.py"

# Git 커밋 (컨벤션 자동)
alias gc='git commit -m'
alias gca='git commit -am'

# Docker 개발 환경
alias dcup='docker compose up -d'
alias dcdn='docker compose down'
alias dexec='docker exec -it q250-dev bash'

# 테스트
alias pytest='python -m pytest -v'
alias pytest-cov='python -m pytest --cov=src --cov-report=term-missing'
```

---

## 🚨 트러블슈팅 빠른 해결

| 증상 | 원인 | 해결 |
|------|------|------|
| `colcon build` 실패 | 의존성 누락 | `rosdep install --from-paths src --ignore-src -r -y` |
| GitHub Actions 실패 | 권한 부족 | Repository Settings → Actions → General → Workflow permissions: Read/Write |
| Docker 빌드 느림 | 캐시 무효화 | `docker compose build --no-cache` |
| GPU 인식 안됨 | 드라이버/컨테이너 | `docker run --gpus all ...` + `nvidia-smi` 확인 |
| MAVLink 메시지 미인식 | mavgen 미실행 | `python -m pymavlink.tools.mavgen ...` 재실행 |

---

## 📱 유용한 링크 모음

| 분류 | 링크 |
|------|------|
| **SpecKit 템플릿** | https://github.com/speckit/template |
| **Mermaid 문법** | https://mermaid.js.org/syntax/flowchart.html |
| **GitHub Actions** | https://docs.github.com/en/actions |
| **Conventional Commits** | https://www.conventionalcommits.org/ |
| **ROS 2 Humble** | https://docs.ros.org/en/humble/ |
| **PX4 Developer Guide** | https://docs.px4.io/main/en/ |
| **Docker Compose** | https://docs.docker.com/compose/ |

---

## 🎯 일일 체크리스트

```
[ ] 아침: tasks.md 확인 → 오늘 할 T-XX 선택
[ ] 오전: 구현 + 단위 테스트 작성
[ ] 점심: 커밋 + 푸시 (CI 자동 실행)
[ ] 오후: 코드 리뷰 + PR 생성
[ ] 저녁: PR 머지 → 다음 T-XX 선택 → tasks.md 업데이트
[ ] 금요일: 주간 회고 + 다음 주 계획 → tasks.md 업데이트
```

---

## 📌 핵심 원칙 3가지

1. **작게 쪼개라** - 1일 이상 걸리는 태스크는 분할
2. **DoD는 테스트로** - "수동 확인" → "자동 테스트 통과"
3. **AI를 써라** - 단순 구현·테스트·문서화는 AI에게 위임

---

*이 치트시트를 프린트해 모니터 옆에 붙여두세요!* 📌