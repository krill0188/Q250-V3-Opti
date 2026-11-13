# SpecKit 입문 가이드: 왜 SpecKit인가?

> **초보 개발자도 인프라를 체계적으로 구축할 수 있게 해주는 "설계도 우선" 개발 프레임워크**

---

## 🎯 **SpecKit이란?**

**SpecKit** = **Spec**ification (명세서) + **Kit** (도구상자)

> **"코드보다 설계를 먼저, 실행은 나중에"**

SpecKit은 **설계 문서(스펙)**를 중심으로 개발 전체 라이프사이클을 관리하는 **프로젝트 관리 + 개발 방법론 + 도구체인**이 통합된 프레임워크입니다.

---

## 🤔 **왜 SpecKit인가? (핵심 장점 7가지)**

| # | 장점 | 설명 | 초보자 혜택 |
|---|------|------|-------------|
| **1** | **설계 우선(Design-First)** | 코드 작성 전 `tasks.md`에 전체 작업 분해 | "어디서부터 시작할까?" 고민 해결 |
| **2** | **단일 진실 소스(SSOT)** | `tasks.md` 하나로 설계·작업·진행률·의존성 통합 | 문서·코드·이슈 동기화 불필요 |
| **3** | **자동화된 추적성** | 작업 ID(T-01~)로 Git 커밋·PR·테스트·문서 자동 연결 | "이 코드가 무슨 태스크지?" 해결 |
| **4** | **의존성 그래프 시각화** | `tasks.md` → Mermaid 그래프 자동 생성 | 복잡한 의존성 한눈에 파악 |
| **5** | **병렬 작업 최적화** | 독립 태스크 그룹(Group A/B/C/D) 자동 식별 | 팀 협업 시 누가 뭘 할지 바로 분배 |
| **6** | **마일스톤·릴리즈 자동화** | Phase·Week·Tag·Release 연동 | "언제 릴리즈하지?" 고민 해결 |
| **7** | **AI 협업 최적화** | LLM이 `tasks.md` 읽고 코드 생성·리뷰·리팩토링 | AI 비서처럼 24시간 페어 프로그래밍 |

---

## 🏗️ **SpecKit 핵심 구성요소 (3대 축)**

```
┌─────────────────────────────────────────────────────────────┐
│                    SpecKit 삼각형                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│    📋 SPEC (tasks.md)      🔧 TOOLS (자동화)      👥 TEAM   │
│    ─────────────────       ───────────────       ────────   │
│    • 작업 분해 (T-01~)      • Git Hooks          • 역할 분담 │
│    • 의존성 그래프          • CI/CD Pipeline     • 리뷰 문화 │
│    • 마일스톤/릴리즈        • Auto Doc Gen       • 페어 프로그래밍│
│    • 마일스톤/릴리즈        • AI Agent 연동       • 지식 공유   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 **SpecKit 프로젝트 표준 구조**

```
project-root/
├── .specs/
│   └── tasks.md          # 🎯 단일 진실 소스 (단일 진실 소스)
├── .github/
│   └── workflows/        # CI/CD 파이프라인
├── docs/                 # 문서 (자동 생성 포함)
├── src/                  # 소스 코드
├── tests/                # 테스트 코드
├── scripts/              # 자동화 스크립트
├── Dockerfile            # 개발 환경 컨테이너
├── docker-compose.yml    # 멀티 컨테이너 오케스트레이션
├── check_env.sh          # 환경 검증 스크립트
└── README.md             # 프로젝트 개요
```

---

## 📝 **tasks.md 핵심 문법 (5분 마스터)**

### 1. **Phase & Task 정의**
```markdown
## Phase 1: 인프라 구축 (T-01 ~ T-10)

### T-01: ROS2 워크스페이스 설정
- **설명**: ROS2 Humble 워크스페이스 구성
- **산출물**: `ros2_ws/src/q250_msgs/msg/*.msg`
- **의존성**: 없음
- **DoD**: `colcon build` 성공
- **예상**: 1일
```

### 2. **의존성 체인** (자동 그래프 생성)
```markdown
T-01 → T-02 → T-03 → T-04
```

### 3. **병렬 그룹** (자동 스케줄링)
```markdown
| 그룹 | 작업 | 비고 |
|------|------|------|
| Group A | T-11~T-20 (음성), T-21~T-30 (Non-GPS) | 병렬 가능 |
```

### 4. **마일스톤**
```markdown
| 마일스톤 | 목표 | 완료 기준 |
|----------|------|-----------|
| M1: 인프라 | Week 2 | T-10 완료 |
```

---

## 🚀 **빠른 시작: 10분 만에 SpecKit 프로젝트 생성**

```bash
# 1. 템플릿 클론 (또는 수동 생성)
git clone https://github.com/your-org/speckit-template.git my-project
cd my-project

# 2. 초기 tasks.md 생성 (템플릿 복사)
cp templates/tasks.md .specs/tasks.md

# 3. Git Hooks 설치 (자동 커밋 메시지 포맷)
./scripts/install-git-hooks.sh

# 4. CI/CD 파이프라인 활성화
git push origin main  # GitHub Actions 자동 실행

# 5. 첫 태스크 시작
# .specs/tasks.md에서 T-01 선택 → 구현 → 커밋 → T-02로 이동
```

---

## 🤖 **AI 협업: SpecKit + LLM = 슈퍼파워**

```markdown
# AI에게 이렇게 요청하세요:

"내 .specs/tasks.md를 읽고 T-05 태스크를 구현해줘.
의존성(T-03, T-04)은 이미 완료됐어.
코드 스타일은 기존 src/bridge/ 스타일 따라줘."
```

**AI가 자동으로 수행하는 것들:**
- ✅ `tasks.md` 읽고 컨텍스트 파악
- ✅ 의존 태스크 코드 분석
- ✅ 코드 생성 + 테스트 작성
- ✅ 커밋 메시지 자동 생성 (`feat: T-05 ...`)
- ✅ PR 생성 + 자기 리뷰
- ✅ `tasks.md` 진행률 업데이트

---

## 📊 **SpecKit 도입 전 vs 후 비교**

| 항목 | 도입 전 | 도입 후 |
|------|---------|---------|
| **작업 착수 시간** | 30분~2시간 (고민) | **5분** (tasks.md 보고 바로 시작) |
| **진행률 파악** | 매번 회의/슬랙 확인 | **실시간** (tasks.md + GitHub Projects) |
| **릴리즈 준비** | 1~2주 (문서 정리) | **1일** (자동 CHANGELOG + Tag) |
| **신입 온보딩** | 2~4주 | **1일** (tasks.md만 읽으면 됨) |
| **버그 원인 추적** | 수시간~수일 | **분 단위** (Task ID → Commit → Test) |
| **팀 확장성** | 어려움 (구두 전수) | **즉시** (tasks.md 공유만으로) |

---

## 🛠️ **추천 도구체인 (SpecKit 스택)**

| 영역 | 추천 도구 | 비고 |
|------|-----------|------|
| **버전 관리** | Git + GitHub | 필수 |
| **이슈/프로젝트** | GitHub Projects + Tasks.md | 양방향 동기화 |
| **CI/CD** | GitHub Actions | 무료, 강력 |
| **컨테이너** | Docker + Docker Compose | 환경 통일 |
| **문서** | Markdown + Mermaid | Git에서 바로 렌더링 |
| **다이어그램** | Mermaid + Excalidraw | tasks.md에 임베드 가능 |
| **AI 비서** | GitHub Copilot / Claude / GPT | tasks.md 컨텍스트 주입 |
| **모니터링** | GitHub Insights + 커스텀 대시보드 | 실시간 진행률 |

---

## 🎓 **학습 로드맵 (초보자 → 숙련자)**

| 단계 | 기간 | 학습 내용 | 산출물 |
|------|------|-----------|--------|
| **1주차** | SpecKit 기초 | tasks.md 작성, Git Hooks, CI/CD | 첫 Phase 완료 |
| **2주차** | 실전 적용 | 실제 프로젝트에 Phase 1~2 적용 | Phase 1~2 완료 |
| **3주차** | AI 협업 | LLM에게 tasks.md 주고 코드 생성 | AI 페어 프로그래밍 체득 |
| **4주차** | 고급 운영 | 병렬 그룹, 의존성 그래프, 릴리즈 자동화 | 팀 리드 가능 |

---

## 💡 **초보자를 위한 팁 10가지**

| # | 팁 | 이유 |
|---|-----|------|
| 1 | **작게 쪼개라** | T-01은 "환경 구축"이 아닌 "Docker 설치", "ROS2 설치"로 분리 |
| 2 | **DoD를 구체적으로** | "빌드 성공" → "`colcon build` 성공, 테스트 100% 통과" |
| 3 | **의존성은 과감히** | 순환 의존 없으면 최대한 연결 (병렬화 방해 안 됨) |
| 4 | **DoD는 테스트로** | "수동 확인" → "자동 테스트 통과" |
| 5 | **주간 리뷰** | 매주 금요일 tasks.md 리뷰 + 다음 주 계획 |
| 6 | **AI에게 맡겨라** | 단순 구현·테스트·문서화는 AI에게 |
| 7 | **작업은 작게** | 1일 이상 걸리는 태스크는 분할 |
| 8 | **문서는 코드와 함께** | README·API 문서는 코드 옆에서 자동 생성 |
| 9 | **릴리즈는 자동으로** | `gh release create` + 자동 CHANGELOG |
| 10 | **회고하라** | Phase 끝날 때마다 "무엇이 작동했나/안했나" 기록 |

---

## 🚀 **지금 바로 시작하세요!**

```bash
# 1. 이 가이드 저장
curl -o SPECKIT_GUIDE.md https://raw.githubusercontent.com/your-org/speckit-guide/main/SPECKIT_GUIDE.md

# 2. 내 프로젝트에 적용
mkdir my-project && cd my-project
mkdir -p .specs src tests docs scripts .github/workflows

# 3. tasks.md 템플릿 다운로드
curl -o .specs/tasks.md https://raw.githubusercontent.com/your-org/speckit-template/main/.specs/tasks.md

# 4. 첫 태스크 작성하고 커밋
git init
git add .specs/tasks.md
git commit -m "feat: T-01 프로젝트 초기화"
git remote add origin https://github.com/your-org/my-project.git
git push -u origin main

# 5. GitHub Actions 확인 → 첫 Phase 시작!
```

---

## 📚 **참고 자료**

| 자료 | 링크 |
|------|------|
| **SpecKit 공식 템플릿** | https://github.com/speckit/template |
| **tasks.md 완전 가이드** | https://github.com/speckit/guide |
| **Mermaid 다이어그램 치트시트** | https://mermaid.js.org/syntax/flowchart.html |
| **GitHub Actions 완전정복** | https://docs.github.com/en/actions |
| **Conventional Commits** | https://www.conventionalcommits.org/ |

---

## 🎉 **마무리: SpecKit으로 얻는 것**

> **"혼란스러운 개발에서 체계적인 제품 개발로"**

| Before SpecKit | After SpecKit |
|----------------|---------------|
| 😰 "뭐부터 하지?" | 😎 "T-01부터 시작" |
| 😰 "진행률 모르겠어" | 😎 "M2: 60% 완료" |
| 😰 "릴리즈 언제?" | 😎 "Week 4 금요일 v1.0" |
| 😰 "버그 어디서 났지?" | 😎 "T-23 커밋에서 발생" |
| 😰 "신입 교육 2주" | 😎 "tasks.md 읽고 1일" |

---

## 🤝 **다음 단계**

1. **오늘**: 위 가이드대로 프로젝트 생성 + T-01 작성
2. **이번 주**: Phase 1 완료 (인프라 구축)
3. **이번 달**: Phase 1~2 완료 (핵심 기능 골격)
4. **분기 말**: v1.0 릴리즈

---

**질문이나 막히는 부분이 있으면 언제든 물어보세요!** 🤝

> *SpecKit은 도구가 아니라 **생각하는 방식**입니다. 오늘부터 "설계 먼저, 코드 나중"을 실천해보세요.*

---

*문서 버전: 1.0 | 작성일: 2024 | 대상: SpecKit 입문자*