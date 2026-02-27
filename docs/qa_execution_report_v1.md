# QA 통합 검수 보고서 v1.0

- 작성일: 2026-02-26
- 작성자: QA
- 대상 문서: `docs/refactor_requirements_v1.md`, `docs/refactor_coding_plan_v1.md`, `docs/refactor_e2e_todo_master.md`, `docs/refactor_execution_report_step1_to_5.md`, `docs/qa_flow_plan.md`
- 산출 기준: 리팩토링 완료 여부 + API/프론트 통합 동작 + 사용자 Flow 기반 테스트 설계 반영도

## 1) QA 결과 요약
- `Step 1~4`(PDF 렌더러 연결, 영속 저장, E2E 테스트 케이스 추가)는 코드 단위로 반영됨.
- `Step 2`(hwp/hwpx 전용 파서)는 사용자 요청에 따라 미도입 상태로 유지되어 있음.
- 자동화 테스트는 통과했으며, P0 3건 및 P1 2건은 해결되었고 현재는 P2 계열 보완 항목이 잔여임.

## 2) 자동화 테스트 실행 이력
- 실행 명령:
  - `pytest -q backend/tests/test_rules_engine.py backend/tests/test_rules_repository.py backend/tests/test_growth_support_service.py backend/tests/test_growth_support_api_integration.py`
  - `pytest -q backend/tests/test_e2e_frontend_like_flows.py`
- 결과:
  - `7 passed` (규칙/저장소/서비스/API 기반 핵심 기능)
  - `8 passed` (프런트 유사 E2E/API 사용자 플로우)
  - `2 passed` (Admin ruleset API 예외/경계값 케이스)
- 총계: `12 passed` (현재 기준)
- 참고: `backend/tests/test_document_parser_service.py` 추가 실행 시 총 `13 passed` 확인됨.
- 경고: Pydantic deprecation 및 timezone/캐시 경고 다수(기능 실패와 직접 연계 없음)

## 3) 통합 플로우 상태 (실행 모의/사전 점검 기반)
- Step 1 인증: API 호출 패턴 정상, 실행 예시 수행 완료
- Step 2 프로젝트 조회/생성: 라우트 존재 및 실측 호출 완료
  - `health`/`register`/`token`/`projects` 기본 시퀀스(운영 모드 2026-02-27 PASS)
- Step 3 업로드 및 dedupe: 코드상 동작 가능하나 dedupe 정확도 이슈 존재 (아래 P0)
- Step 4 RuleSet 관리(복제/활성화/preview): UI/API 구현 존재, 버전 정렬·활성 선택 관련 보완 필요
- Step 5 성장지원 실행 및 artifact: API+서비스 흐름 존재, PDF 제공도 구현됨
- Step 6 재기동/재조회 복구성: DB 기반 저장/조회 경로 존재

## 4) 기능 충족도 점검(요구사항 Mapping)

### PASS
- `Growth Support 영속 저장`(`backend/app/core/database.py:118`, `backend/app/core/database.py:325`, `backend/app/core/database.py:351`, `backend/app/services/growth_support_service.py:68`, `backend/app/services/growth_support_service.py:75`)
- `PDF 렌더링`(`backend/app/services/templates/pdf_renderer.py:4`, `backend/app/services/growth_support_service.py:87`, `backend/app/api/v1/projects.py:714`)
- `Artifact html/markdown/pdf 엔드포인트`(`backend/app/api/v1/projects.py:714`)
- `관리자 RuleSet UI`(`frontend/src/app/(admin)/admin/rules/page.tsx`)
- `RuleSet API CRUD/clone/activate/preview`(`backend/app/api/v1/admin.py`)
- `통합 테스트 케이스 문서화`(`docs/refactor_e2e_api_front_test_cases.md`, `docs/qa_flow_plan.md`)

### BLOCKER / CRITICAL
- `P0-01` 사용자 플로우 하드코딩 포트 버그 [FIXED: 2026-02-26]
  - 근거: `frontend/src/app/projects/[projectId]/execute/page.tsx:55`에서 artifact URL이 `:8002`로 고정되어 있어 비표준 배포/리버스프록시 환경에서 깨질 가능성 큼.
  - 영향: 산출물 버튼 클릭 시 환경 의존 404/연결 오류.

- `P0-02` 프로젝트 범위 dedupe 신뢰성 저하 [FIXED: 2026-02-26]
  - 근거: `backend/app/api/v1/files.py:102`, `backend/app/api/v1/files.py:207`의 JSON 문자열 탐색 방식은 해시 충돌/포맷 변화/중복성 판단 오탐 가능.
  - 영향: 서로 다른 프로젝트 간 중복 파일을 동일 파일로 오판하거나, 동일 파일이어도 미탐지될 수 있음.

- `P0-03` RuleSet reason_code 정확성 손상 [FIXED: 2026-02-26]
  - 근거: `backend/app/services/rules/engine.py:63`~`backend/app/services/rules/engine.py:66`에서 `reason_codes`가 전역 누적되어 마지막 값이 `matched_rules` reason으로 재사용됨.
  - 영향: 규칙 추적(trace)의 감사성/설명력 저하, 관리자 튜닝 검증 불일치.

### HIGH
- `P1-01` 규칙 버전 정렬 로직이 문자열 정렬
  - 근거: `backend/app/services/rules/repository.py:26`의 `sorted(items, key=lambda x: x.version)`
  - 영향: `v1.10`/`v1.2` 정렬 불일치로 active/preview 선택 이력 꼬임 가능.
  - 상태: [FIXED: 2026-02-26]

- `P1-02` 파일 파서 확장자 커버리지 미일치
  - 근거: 파서가 `.xlsx`, `.xls`만 처리(`backend/app/services/document_parser_service.py:44`)하고 `.excel`은 미지원(`backend/app/services/document_parser_service.py:72`)
  - 영향: 요구 스펙 `excel` 입력과 실제 동작 불일치.
  - 상태: [FIXED: 2026-02-26]

### REMAINING HIGH
- `P2-01` fallback 정책 반영 일부 축소
  - 근거: `backend/app/services/rules/engine.py`의 임계치/전략 반영이 제한적이었으나 현재 `cutoffs.minimum_confidence`와 `fallback_on_low_confidence` 반영 완료.
  - 상태: [FIXED: 2026-02-26]

### MEDIUM
- `P2-02` 프론트 페르소나 흐름에서 결과 동기화 검증 미실행
  - 근거: `docs/qa_flow_plan.md`에 설계 존재 (`F1~F4`), API Flow 레벨 검증은 완료되었으나 실제 브라우저 자동화 실행 기록은 미부재
  - 영향: 사용자 체감 이슈(버튼 상태, 에러 메시지, 반복 실행 UI 안정성) 미확인

- `P2-03` 파일 업로드 확장자/실패 메시지 일관성
  - 근거: 업로드 경로에서 지원 불가 파일은 400 처리되며, API 테스트에서는 코드-prefix 메시지와 reason/unsupported 처리 일관성 보강
  - 영향: 운영 사용자 오해 소지

- `P2-04` Admin ruleset API 예외 응답 정합성
  - 근거: 중복 생성/버전 mismatch/미존재 버전 케이스의 실패 응답이 일관되지 않을 수 있음
  - 영향: 운영 운영에서 조치 판단 실패/지연
  - 상태: [FIXED: 2026-02-26]

## 5) 사용자 Flow + 프론트 QA 설계 실행 계획(다음 단계)
- 기준 1: QA Flow 파일 기준 6단계 API 시퀀스(`docs/qa_flow_plan.md`)와 페르소나 F1~F4 실행
- 기준 2: 아래 3개 환경에서 반복 실행
  1) 브라우저 localhost
  2) localhost가 아닌 내부 호스트(예: Tailscale 도메인)
  3) 인증 권한 분기(super_admin, standard_user)
- 기준 3: 실패 로그는 `docs/qa_execution_log_2026-02-26.md`에 즉시 기록

## 6) 수정 상태(업데이트)
- `P0-01` 하드코딩 포트: 수정 완료 (`frontend/src/app/projects/[projectId]/execute/page.tsx:55`)
- `P0-02` 프로젝트 범위 dedupe: 수정 완료 (`backend/app/api/v1/files.py`의 `check_duplicate_file` 적용)
- `P0-03` reason_code 추적 정합성: 수정 완료 (`backend/app/services/rules/engine.py` per-rule 처리로 변경)
- `P1-01` 규칙 버전 정렬: 보강 완료 (`backend/app/services/rules/repository.py`, `frontend/src/app/(admin)/admin/rules/page.tsx`)
- `P1-02` `.excel` 파서 지원: 보강 완료 (`backend/app/services/document_parser_service.py`)
- `P2-01` fallback 정책: `minimum_confidence`/`fallback_on_low_confidence` 반영 완료 (`backend/app/services/rules/engine.py`)
- `P2-02` 업로드 오류 메시지 일관성: 지원 확장자 선필터 반영 (`backend/app/api/v1/files.py`)
- `P2-04` Admin API 예외 응답 정합성: 경계값 처리 및 HTTP status/detail 정합성 반영 (`backend/app/api/v1/admin.py`, `backend/tests/test_e2e_frontend_like_flows.py`)
- 잔여 우선순위: 브라우저 기반 Persona F1~F4 실행 스크립트 및 권한/재시작 시나리오까지 확장 (`P2-02`~`P2-03`)

## 7) 결론
- Refactor 핵심 골격은 유지되며, 운영 반영 전 `P0` 및 `P1` 핵심 이슈는 선해결 완료.
- 다음 단계 우선순위: `P2` 사용자 흐름 검증 강화 및 권한 분리 케이스 기반 QA 재실행.

## 8) Step1~4 실행 순차 결과 반영
- Step 1(PDF 렌더러): `backend/app/services/templates/pdf_renderer.py` 연동 및 `format=pdf` API 응답 확인 완료
- Step 3(영속 저장): `GrowthRunModel`/`GrowthArtifactModel` 저장 및 재조회 경로 확인 완료
- Step 4(E2E API/프론트 플로우): `backend/tests/test_e2e_frontend_like_flows.py`에 persona 기반 8개 케이스 통과

## 8) 즉시 QA 리포트 결과 기록 시작 템플릿
- 테스트명:
- 수행자:
- 시간:
- 입력/요청:
- 기대결과:
- 실제결과:
- 상태(PASS/FAIL):
- 실패시 재현 스텝:
- 개선 우선순위:

## 9) Step5: Persona UI 자동화 하네스(진행)
- 새 산출물:
  - `frontend/e2e/persona-flow.spec.ts`
  - `frontend/playwright.config.ts`
  - `frontend/package.json` (`test:e2e:persona`)
- 반영 내역:
  - 실행 페이지에 E2E 식별자(`data-testid`) 추가: 상태/버튼/입력
  - Persona별 run/status/artifact 흐름 자동 검증용 스크립트 기본형 생성
  - 실행 순차 가이드: `docs/qa_flow_plan.md` 13항으로 통합
- 현재 상태:
  - 코드/시나리오 작성 완료
  - 운영 실행은 Playwright 설치 및 환경변수(`E2E_PROJECT_ID`, `E2E_AUTH_TOKEN`) 주입 후 진행 예정

## 10) Step5 진행 상태 업데이트
- `frontend/package.json`에 `test:e2e:persona` 명령을 `npx playwright test`로 보정
- `@playwright/test` 런타임 의존성은 추가 완료
- `docs/qa_execution_log_2026-02-26.md`에 실행 권한/패키지 페치 차단 이슈 기록 (`EACCES`)
- 잔여 과제: CI/로컬에서 `npm install` 후 `npm run test:e2e:persona` 통과 확인
