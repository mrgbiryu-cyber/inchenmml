# 리팩토링 E2E TODO + 무컨펌 실행계획 (One-File Master)

## 0. 문서 목적
- 특허 초안 기반 리팩토링을 엔드투엔드로 한 번에 진행하기 위한 실행 기준 문서
- 중간 컨펌 없이 단계별로 자동 진행하고, 내일 한 번에 검수할 수 있도록 산출물 중심으로 설계

## 1. 실행 원칙
- 원칙 1: 단계 순차 실행, 사용자 중간 컨펌 없이 진행
- 원칙 2: 각 단계는 완료조건(DoD) 충족 시에만 다음 단계로 이동
- 원칙 3: 모든 단계는 코드 + 테스트 + 문서 산출물을 남김
- 원칙 4: 막히는 항목은 우회 구현 후 `Known Issues`에 기록하고 전체 플로우 우선 완성
- 원칙 5: 판정 로직은 `RuleSet`이 결정, LLM은 설명/보조 제안만 수행

## 2. 범위 (이번 배치)
- 백엔드: RuleSet 엔진, 에이전트 실제화, 파일 인입 파이프라인, API 확장
- 프론트: 관리자 Rule 튜닝 UI, 실행/결과 화면 리팩토링, 문서 출력 UX
- 출력: HTML/Markdown/PDF
- 테스트: 단위/통합/회귀/부하

## 3. 무컨펌 순차 실행 TODO

### Step 1. RuleSet 도메인 모델 고정
- 작업
  - `RuleSet`, `RuleCondition`, `RuleAction`, `RuleEvalResult` 스키마 추가
  - `CompanyProfile` 필드 확장 및 정규화
- 대상 파일
  - `backend/app/models/schemas.py`
  - `backend/app/models/company.py`
- 완료조건
  - 스키마 import 에러 없음
  - 샘플 payload 검증 통과
- 산출물
  - 모델 변경 코드
  - 샘플 JSON 3종

### Step 2. RuleSet 엔진 구현
- 작업
  - 조건 연산자(`eq/gt/gte/lt/lte/in/exists`) 구현
  - 점수 계산(`weighted_sum`, `cutoff`, `fallback`) 구현
  - 판정 함수 `classify_company_type`, `classify_growth_stage` 구현
- 대상 파일
  - `backend/app/services/rules/engine.py` (신규)
  - `backend/app/services/rules/__init__.py` (신규)
- 완료조건
  - 규칙 10케이스 판정 테스트 통과
  - `reason_codes`, `confidence`, `ruleset_version` 반환
- 산출물
  - 엔진 코드
  - 테스트 로그

### Step 3. RuleSet 저장소/버전관리
- 작업
  - 활성 RuleSet 조회/변경/복제 기능 구현
  - 기본 RuleSet v1 시드
- 대상 파일
  - `backend/app/services/rules/repository.py` (신규)
  - `backend/data/rulesets/ruleset_v1.json` (신규)
- 완료조건
  - 활성화/복제 API에서 버전 반영 확인
- 산출물
  - 버전 파일
  - 시드 RuleSet

### Step 4. 관리자 Rule API 구현
- 작업
  - RuleSet CRUD/Activate/Clone/Preview API 추가
- 대상 파일
  - `backend/app/api/v1/admin.py`
- 완료조건
  - API 테스트 통과
  - 권한 체크(super admin) 적용
- 산출물
  - API 엔드포인트 코드
  - API 테스트 리포트

### Step 5. 분류/단계 에이전트 실구현
- 작업
  - `classification_agent`에서 RuleSet 엔진 호출
  - LLM 설명 생성(결정값 불변)
- 대상 파일
  - `backend/app/services/agents/classification_agent.py`
- 완료조건
  - 동일 입력에 동일 결정값 보장
  - 설명 생성 실패 시에도 결정값 반환
- 산출물
  - 분류 결과 JSON 샘플

### Step 6. 사업계획서 생성/재구성 엔진 실구현
- 작업
  - 신규/기존 사업자 분기 처리
  - 정책 기준 대비 누락/중복/미흡 진단
  - 템플릿 렌더링 가능한 구조화 산출물 생성
- 대상 파일
  - `backend/app/services/agents/business_plan_agent.py`
  - `backend/app/services/templates/` (신규)
- 완료조건
  - 두 경로(생성/재구성) 모두 정상 동작
- 산출물
  - HTML/Markdown 아티팩트

### Step 7. 인증/IP 매칭 엔진 실구현
- 작업
  - KB 기준 점수 계산
  - 갭/필요증빙/우선순위 산출
- 대상 파일
  - `backend/app/services/agents/matching_agent.py`
  - `backend/app/services/knowledge/` (신규)
- 완료조건
  - 상위 추천 Top-N 및 근거 반환
- 산출물
  - 매칭 결과 JSON

### Step 8. 성장 로드맵 엔진 실구현
- 작업
  - 연차별 목표/실행과제/선행조건 생성
  - 사업계획 -> 인증/IP -> R&D -> 투자 흐름 연결
- 대상 파일
  - `backend/app/services/agents/roadmap_agent.py`
- 완료조건
  - 3개 샘플 케이스 연차 로드맵 생성
- 산출물
  - 로드맵 HTML/Markdown

### Step 9. 파일 인입 파이프라인 구축
- 작업
  - 업로드 API 확장(단일/배치)
  - 포맷 어댑터(`pdf/docx/hwp/hwpx/ppt/pptx/txt/excel`)
- 대상 파일
  - `backend/app/api/v1/files.py`
  - `backend/app/services/document_ingest/` (신규)
- 완료조건
  - 지원 포맷별 텍스트 추출 성공
  - 실패 리포트 반환
- 산출물
  - 인입 테스트 결과

### Step 10. 오케스트레이션/API 통합
- 작업
  - 실행 파이프라인을 모듈 1~7 순으로 연결
  - 결과 아티팩트 조회/다운로드 API 연결
- 대상 파일
  - `backend/app/services/orchestration_service.py`
  - `backend/app/api/v1/projects.py`
- 완료조건
  - API 한 번 호출로 E2E 결과 생성
- 산출물
  - 실행 로그 샘플

### Step 11. 관리자 Rule 튜닝 UI
- 작업
  - RuleSet 목록/편집/복제/활성화
  - 판정 미리보기(샘플 입력 -> 결과/근거)
- 대상 파일
  - `frontend/src/app/(admin)/admin/rules/page.tsx` (신규)
- 완료조건
  - UI에서 RuleSet 운영 사이클 완결
- 산출물
  - UI 동작 캡처 기준 코드

### Step 12. 사용자 실행/결과 UI
- 작업
  - 입력(텍스트+파일) 화면 정비
  - 결과(사업계획/매칭/로드맵) 브라우저 뷰 + 다운로드
- 대상 파일
  - `frontend/src/app/projects/[projectId]/execute/page.tsx`
  - `frontend/src/components/workflow/*`
- 완료조건
  - 사용자 E2E 플로우 완료
- 산출물
  - 결과 화면 코드

### Step 13. 테스트/배포 문서화
- 작업
  - 단위/통합/회귀/부하 테스트 실행
  - 릴리즈 노트, Known Issues, 롤백 가이드 작성
- 대상 파일
  - `backend/tests/*`
  - `docs/refactor_release_notes_v1.md` (신규)
  - `docs/refactor_known_issues_v1.md` (신규)
- 완료조건
  - 테스트 결과와 배포 문서 존재
- 산출물
  - 최종 검수 패키지

## 4. 내일 검수용 산출물 패키지
- 코드 변경: 백엔드/프론트 전체 반영
- 문서 3종
  - `docs/refactor_release_notes_v1.md`
  - `docs/refactor_known_issues_v1.md`
  - `docs/refactor_validation_report_v1.md` (테스트/성능/KPI)
- 샘플 결과물
  - 사업계획서 2종(생성/재구성)
  - 인증/IP 매칭 리포트 2종
  - 성장 로드맵 2종

## 5. 자동 진행 중 예외 처리 규칙
- 치명 blocker(의존성/런타임 크래시)는 우회 구현 후 TODO 주석 + Known Issues 기록
- 비치명 blocker(일부 포맷 파싱 실패)는 기능 플래그로 격리하고 다음 단계 진행
- 보안/정책 강화 요청은 범위 외로 분리 기록

## 6. 최종 완료 정의
- RuleSet 기반 판정 + 관리자 튜닝 UI 동작
- 모듈 1~7 E2E 실행 가능
- HTML/Markdown/PDF 출력 가능
- 테스트 리포트 및 릴리즈 문서 완료
