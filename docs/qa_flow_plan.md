# QA 통합 테스트 플랜 (사용자 Flow + API/프론트 결합)

버전: v1.0
최종 수정일: 2026-02-26
작성자: QA

## 1. 목적
- Myllm 프로젝트를 AI코웍 사업전문 도움 LLM로 리팩토링한 후, API/프론트 통합 동작이 실제 사용자 이용 흐름에서 문제없이 동작하는지 검증
- 특히 `RuleSet 기반 분류/튜닝`, `성장지원 파이프라인`, `PDF 출력`, `영속 저장`, `파일 업로드 deduplication`, `프론트 UX 흐름`이 실사용 환경에서 반복 사용 가능한지 확인
- 단순 기능 동작뿐 아니라, 사용자 가설 기반 재현 가능한 실패 시나리오까지 검증

## 2. 전제 조건
- 백엔드: `GET /health` 통과
- DB(SQLite/PostgreSQL), Redis, 프론트-백 API 라우팅 정상
- 테스트 계정: `super_admin` 1개, `standard_user` 1개
- 기본 RuleSet(`company-growth-default`) 및 관련 파일/산출물 템플릿 존재

---

## 3. 테스트 대상 페르소나

### 3.1 페르소나 A: 초기기업 대표 (Startup Founder)
- 역할: 사업 계획 초안 생성/분류를 빠르게 얻고, 결과를 공유
- 주요 가설
  - 최소한의 입력만으로도 분류/분석 파이프라인이 즉시 동작한다
  - 규칙 기반 분류 결과가 직관적으로 이해 가능해야 한다

### 3.2 페르소나 B: 사업지원 실무자 (Business Support Officer)
- 역할: 기존 사업계획 문서를 반영해 보완점과 매칭 결과를 빠르게 확인
- 주요 가설
  - 기존 텍스트 기반 재구성 모드에서 결과 품질이 유지된다
  - 파일 업로드/중복 처리에서 오탐 없이 문서가 반영된다

### 3.3 페르로나 C: 정책사업 운영 매니저 (Program PM)
- 역할: 업무 마감 상황에서 빠르게 반복 실행하고 산출물을 추출/배포
- 주요 가설
  - 반복 실행해도 캐시/DB 저장 결과가 안정적으로 유지된다
  - HTML/MD/PDF 산출물을 바로 공유 가능한 형식으로 획득한다

### 3.4 페르소나 D: Super Admin (Rule 관리자)
- 역할: 규칙셋을 편집/복제/활성화하고 현장 운영 반영 속도를 판단
- 주요 가설
  - RuleSet 수정/preview/activate가 실제 분류 파이프라인에 반영된다
  - 규칙 버전 관리와 롤백이 사용 가능한 방식으로 동작한다

---

## 4. 테스트 범위(기능 + 호출 방식)

### 4.1 API 호출 범위
1. 인증
2. 프로젝트 조회/생성
3. 파일 업로드 (단건/폴더/배치)
4. Admin RuleSet 관리 (생성/수정/복제/활성화/미리보기)
5. 성장지원 E2E 실행 및 결과 조회
6. 아티팩트 조회(HTML/Markdown/PDF)
7. 최신 결과 재조회(서버 재시작 조건 포함)

### 4.2 프론트 플로우
- 로그인 → 프로젝트 진입 → 채팅/업로드 → 규칙/파이프라인 실행 → 결과 확인 → 산출물 열람/다운로드

---

## 5. 6단계 통합 테스트 시나리오 (API 중심)

> 각 단계는 2인 1차 검증: (1) 기대 값 검증, (2) 오류/경계값 검증을 병행

### Step 1. 사전 인증 및 접근권한
- API 호출
  - `POST /api/v1/auth/login` (환경에 맞는 로그인 엔드포인트)
  - 토큰 획득 및 Authorization 전파
- 기대
  - 200, 토큰 발급
  - 이후 보호된 API 접근 가능
- 실패 포인트
  - 토큰 누락시 401/403
  - admin 권한 API 접근 실패

### Step 2. 프로젝트 생성/조회 및 컨텍스트 준비
- API 호출
  - `GET /api/v1/projects/`
  - (필요 시) `POST /api/v1/projects`
- 기대
  - 프로젝트 생성 시 고유 project_id 생성
  - tenant 분리 확인
- 실패 포인트
  - 기존 프로젝트와 충돌
  - 기본 에이전트/스레드 생성 누락

### Step 3. 문서 업로드 및 dedupe 검증
- API 호출
  - `POST /api/v1/files/upload`
  - `POST /api/v1/files/upload-folder`
  - `POST /api/v1/files/upload-batch`
- 기대
  - 신규: `status=queued` 또는 `saved_only`
  - 동일 해시: `status=skipped`, reason=duplicate
- 실패 포인트
  - 프로젝트별 분리 미반영 중복탐지
  - 파서 미지원 확장자 400 처리 이상

### Step 4. 관리자 규칙셋 관리/미리보기
- API 호출
  - `GET /api/v1/admin/rulesets?ruleset_id=company-growth-default`
  - `POST /api/v1/admin/rulesets/{id}/{version}/preview`
  - `POST /api/v1/admin/rulesets/{id}/{version}/clone`
  - `POST /api/v1/admin/rulesets/{id}/{version}/activate`
- 기대
  - preview: trace/company_type/growth_stage/신뢰도/원인코드 반환
  - 활성화 후 실제 `run`에서 해당 버전 반영
- 실패 포인트
  - clone/activate 충돌
  - version 정렬 및 선택 규칙 오류

### Step 5. 성장지원 E2E 실행 및 산출물 생성
- API 호출
  - `POST /api/v1/projects/{project_id}/growth-support/run` with `{profile, input_text}`
  - `GET /api/v1/projects/{project_id}/growth-support/latest`
  - `GET /api/v1/projects/{project_id}/artifacts/business_plan?format=html`
  - `GET /api/v1/projects/{project_id}/artifacts/matching?format=html`
  - `GET /api/v1/projects/{project_id}/artifacts/roadmap?format=html`
  - `GET /api/v1/projects/{project_id}/artifacts/business_plan?format=markdown`
  - `GET /api/v1/projects/{project_id}/artifacts/business_plan?format=pdf`
- 기대
  - run 결과에 classification/business_plan/matching/roadmap 포함
  - latest 응답 일관성
  - 각 형식의 content-type/바디 정상
- 실패 포인트
  - classification/ruleset 버전 미반영
  - PDF 생성 시 500/빈바디

### Step 6. 재시작/재조회 복구성(영속성)
- API 호출
  - 실행 후 앱 재시작(또는 캐시 클리어 시뮬레이션)
  - `GET /api/v1/projects/{project_id}/growth-support/latest`
  - `GET /api/v1/projects/{project_id}/artifacts/{artifact_type}?format=html`
- 기대
  - cache miss 상황에서도 DB에서 최신 결과 복구
  - 최신 run 기준으로 일관된 결과 제공
- 실패 포인트
  - cache-only 의존으로 404 발생
  - 오래된 run를 반환

---

## 6. 사용자 플로우 기반 프론트 테스트 시나리오

### F1. 초기기업 대표 플로우
- 로그인 → 프로젝트 선택 → 실행 페이지 진입
- profile 입력(JSON) 실행 → business_plan HTML/Md/PDF 순차 조회
- 기대
  - 에러 메시지 없이 4개 단계 완료
- 검증 포인트
  - 실행 버튼 비활성 상태 전이
  - 결과 snapshot 일관성

### F2. 실무자 플로우(기존 문서 반영)
- 파일 업로드(단건/배치) → 업로드 결과 표시
- input_text(기존 초안) 입력 후 run 재실행
- matching/roadmap 결과에서 gaps/recommendation 가시성 확인
- 기대
  - 기존 텍스트 기반 재구성 플래그 반영

### F3. 정책사업 매니저 플로우(반복 실행)
- 연속 3회 run 연타
- 매 회 latest/artifact 호출
- 기대
  - 요청당 결과 갱신, 최신 기준 일관성

### F4. 규칙 관리자 플로우
- RuleSet 편집(버전 선택/복제/활성화)
- preview와 실제 실행 결과의 분류 값 비교
- 기대
  - 변경 직후 분류 및 산출물 반영

---

## 7. 테스트 케이스 목록(우선순위)

### P0 (필수)
- P0-01: 인증+권한 테스트
- P0-02: growth-support/run → latest → artifacts(html/markdown/pdf) end-to-end
- P0-03: pdf 산출물 다운로드 헤더/바디 확인
- P0-04: 서버 재시작 후 latest 조회 성공

### P1 (중요)
- P1-01: 규칙셋 preview/activate 후 즉시 분류 반영
- P1-02: upload-batch 중복 파일 스킵
- P1-03: 업로드/실행 권한 분리(tenant/project_id)
- P1-04: admin UI에서 RuleSet JSON 저장/클론 실패 케이스 처리
- 상태: 완료 처리(백엔드/프론트 정렬·파싱 정합성 반영 완료)

### P2 (권장)
- P2-01: 확장자별 파서 동작(지원/미지원)
- P2-02: 프론트에서 3개 artifact 버튼 동시 동작
- P2-03: 대용량 파일 업로드 실패 메시지 및 fallback 동작
- P2-01-확장: fallback 정책 최소 신뢰도/폴백 반영(`cutoffs`, `fallback_policy`)

---

## 8. Pass/Fail 정의

### Pass 기준
- Step별 상태코드가 명세 범위 내이며, 핵심 필드가 비어있지 않음
- 사용자 플로우에서 각 화면/버튼 동작이 1회 이상 실패 없이 완료
- PDF/HTML/Markdown 산출물이 실제 응답으로 반환
- 규칙 변경 후 1회 실행으로 검증 가능

### Fail 기준
- 규칙 반영 불일치(버전/결과/trace mismatch)
- cache miss/재시작 시 데이터 복구 실패
- 프론트 하드코딩 포트/호스트로 인해 환경별 링크 실패
- dedupe가 프로젝트 경계를 무시

---

## 9. 실행 로그 템플릿

각 테스트 케이스 종료 시 아래 포맷으로 기록
- 테스트명:
- 수행자:
- 시간:
- 입력/요청:
- 기대결과:
- 실제결과:
- 상태(PASS/FAIL):
- 실패시 재현 스텝:
- 개선 우선순위:

---

## 10. 오픈 이슈 및 리스크 트래킹
- 프론트 아티팩트 링크가 현재 환경 포트/호스트에 고정되지 않고 동작해야 함
- dedupe 로직은 프로젝트 스코프 필터 강화 필요
- Rule trace reason_code 및 버전 정렬 정합성은 관리용 지표 정확도에 영향
- Step 7 fallback 정책 적용(최소 신뢰도, 폴백 정책) 실사용 검증 필요

## 11. 다음 액션
- QA 수행 후 실패 케이스 기준으로 `docs/qa_execution_log_YYYY-MM-DD.md` 생성
- API 실패율/재시도율/산출물 생성 시간 지표 대시보드화

## 12. 실행 결과 요약 (2026-02-26)
- 기본 판정: 리팩토링 골격 완료 및 테스트 프레임워크 구성은 충족됨. 초기 P0 3건은 모두 선해결되어 현재 P1/P2 단계 검증 필요
- 통합 테스트 결과: `pytest -q backend/tests/test_rules_engine.py backend/tests/test_rules_repository.py backend/tests/test_growth_support_service.py backend/tests/test_growth_support_api_integration.py`
- 테스트 결과 요약: `5 passed`
- 참조:
  - 정적 QA 세부 결과: `docs/qa_execution_report_v1.md`
  - 상세 테스트 시나리오: `docs/qa_flow_plan.md`(F1~F4)
- 최초 발견 P0:
  - `frontend/src/app/projects/[projectId]/execute/page.tsx:55` artifact 링크의 포트 하드코딩
  - `backend/app/api/v1/files.py:102`, `backend/app/api/v1/files.py:207` dedupe JSON LIKE 조건 정확도
- 최초 확인 P1/P2:
  - `backend/app/services/rules/engine.py:66` reason_code 누적 공유
  - `backend/app/services/rules/repository.py:26` 버전 정렬 문자열 비교
  - `backend/app/services/document_parser_service.py:44` `.excel` 미지원
- 상태 업데이트:
  - P0-01~P0-03 모두 코드로 선해결 완료
  - P1은 정렬/파서/폴백 정책 반영을 통해 보완 완료
- 다음 실행: `docs/qa_execution_log_2026-02-26.md` 템플릿 생성 후 실제 사용자 시나리오 1회차 실행 예정

## 13. Persona UI E2E 자동화 추가(추가 실행 항목)

- 테스트 위치: `frontend/e2e/persona-flow.spec.ts`
- 실행 커맨드: `cmd /c "cd /d D:\\project\\productllm\\frontend && npx playwright test"` (또는 `npm run test:e2e:persona`)
- 전제 환경:
  - 프론트엔드: `http://127.0.0.1:3000`
  - 백엔드: `http://127.0.0.1:8002`
  - 환경변수:
    - `E2E_PROJECT_ID`
    - `E2E_AUTH_TOKEN`
    - `E2E_FRONTEND_URL` (선택)
    - `E2E_AUTH_USERNAME` (선택)
- 커버 시나리오:
  - F-01 Founder: profile/input 입력 → 실행 → status DONE → artifact 버튼 3×3 열림 확인
  - F-02 Support officer: profile/input 반영 실행
  - F-03 Program manager: 연속 실행 후 run-count 증가 확인
  - F-04 admin 계정 기반 관리자 규칙 변경 반영 여부는 기존 backend API 테스트(`test_admin_ruleset_activation_reflects_runtime_classification`)와 연동 확인
- 결과 처리: 실행 성공/실패는 `docs/qa_execution_log_2026-02-26.md`에 항목 추가 필요
