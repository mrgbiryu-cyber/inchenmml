# 특허 초안 기반 리팩토링 코딩 계획서 v1

## 0) 목표
- 기준 문서: `docs/patent_summary_draft.md`
- 목표: 기존 목업/TODO 중심 구현을 실제 동작 가능한 E2E 시스템으로 전환
- 기간: 1주(7일) 내 MVP 완료

## 1) 구현 대상 (모듈 1~7)
1. 이용자 유형 자동 판별 모듈
2. 성장단계 분류 엔진
3. 사업계획서 생성/재구성 엔진
4. AI 코웍 분석/설계 엔진
5. 인증/IP 매칭 엔진
6. 성장 로드맵 자동 생성 모듈
7. 협업 인터페이스/출력 모듈

## 2) 현재 코드 기준 주요 갭
- `backend/app/services/agents/*`: 목업 HTML 반환 + TODO 중심
- 도메인 기준/임계치/점수 산식 미정
- 정책/인증/RFP 지식베이스 스키마/수집 파이프라인 미구현
- 문서 업로드 파이프라인(다중 포맷) 미구현
- 다운로드 문서가 목업 HTML 수준

## 3) 아키텍처 리팩토링 방향
- `Rules First + LLM Assist`
- `Agent Output = Structured JSON` (중간 산출물을 전부 JSON으로 통일)
- `Template Rendering` (최종 문서는 템플릿 렌더링으로 생성)
- `Versioned Knowledge Base` (정책/인증/IP 기준 데이터 버전 관리)
- `Versioned RuleSet + Admin Tuning UI` (임계치/가중치/매핑을 운영자가 학습형으로 조정)
- `Deterministic Decision, LLM Explanation` (판정은 규칙, LLM은 설명/보조 제안)

## 4) 상세 WBS

### Phase 1. RuleSet 설계 + 관리자 튜닝 UI (Day 1)
- 파일
  - `backend/app/models/company.py`
  - `backend/app/models/schemas.py`
  - `backend/app/services/rules/` (신규)
  - `backend/app/api/v1/admin.py` (확장)
  - `frontend/src/app/(admin)/admin/rules/page.tsx` (신규)
- 작업
  - `CompanyProfile` 확장: 판정에 필요한 입력 필드 정규화
  - RuleSet 스키마 정의: `company_type_rules`, `growth_stage_rules`, `matching_rules`, `weights`, `cutoffs`, `fallback_policy`
  - RuleSet 버전 체계: `ruleset_id`, `version`, `status(draft/active/archived)`, `effective_from`, `author`
  - 규칙 평가 결과 스키마(`score`, `reason_codes`, `confidence`, `ruleset_version`) 정의
  - Admin Rule UI 1차: 규칙 목록/버전복제/편집/활성화/롤백
  - 판정 근거 로그 조회 UI: 어떤 룰이 매칭되어 어떤 점수가 나왔는지 표시
- 산출물
  - RuleSet CRUD API + 활성화 API
  - 규칙 엔진 단위 테스트(경계값 포함)
  - 샘플 RuleSet v1 + 샘플 판정 케이스 JSON
  - 관리자 튜닝 UI 시연 가능 상태

#### Day 1 실행 체크리스트 (세부 TODO)

1. 백엔드 모델/스키마
- [ ] `backend/app/models/schemas.py`에 `RuleSet`, `RuleCondition`, `RuleAction`, `RuleEvalResult` 추가
- [ ] `backend/app/models/company.py`에 분류/단계 판정용 필드 확장
- [ ] `ruleset_version`, `ruleset_id`, `confidence`, `reason_codes` 공통 응답 필드 정의

2. 규칙 엔진 서비스
- [ ] `backend/app/services/rules/engine.py` 생성
- [ ] 조건 연산자 구현: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `in`, `exists`
- [ ] 점수 계산기 구현: `weighted_sum`, `hard_cutoff`, `fallback_policy`
- [ ] 결정 함수 분리: `classify_company_type()`, `classify_growth_stage()`
- [ ] 평가 로그 구조화: `matched_rules[]`, `unmatched_rules[]`, `trace_id`

3. RuleSet 저장/버전
- [ ] `backend/app/services/rules/repository.py` 생성 (초기: 파일/DB 어댑터 인터페이스)
- [ ] 기본 RuleSet v1 시드 파일 생성: `backend/data/rulesets/ruleset_v1.json`
- [ ] 활성 버전 조회 함수 구현: `get_active_ruleset()`
- [ ] 버전 전환 함수 구현: `activate_ruleset(version)`

4. 관리자 API
- [ ] `backend/app/api/v1/admin.py`에 RuleSet 엔드포인트 추가
- [ ] `GET /api/v1/admin/rulesets`
- [ ] `POST /api/v1/admin/rulesets` (신규 버전 생성)
- [ ] `PATCH /api/v1/admin/rulesets/{id}` (초안 편집)
- [ ] `POST /api/v1/admin/rulesets/{id}/activate`
- [ ] `POST /api/v1/admin/rulesets/{id}/clone`
- [ ] `GET /api/v1/admin/rulesets/{id}/preview` (샘플 입력 판정 미리보기)

5. 프론트 관리자 UI
- [ ] `frontend/src/app/(admin)/admin/rules/page.tsx` 생성
- [ ] 규칙 버전 목록 테이블(상태: draft/active/archived)
- [ ] RuleSet JSON 에디터(유효성 검사 포함)
- [ ] 활성화/복제/롤백 버튼 및 확인 모달
- [ ] 미리보기 패널(샘플 프로필 입력 -> 판정 결과/근거 표시)

6. 검증/테스트
- [ ] 단위 테스트: `backend/tests/test_rules_engine.py`
- [ ] API 테스트: `backend/tests/test_admin_rulesets_api.py`
- [ ] 샘플 10케이스 분류 기대값 검증
- [ ] 경계값 테스트(업력 0/1, 매출 0/임계치, 고용 0/임계치)

7. 완료 조건 (Day 1)
- [ ] 관리자가 UI에서 RuleSet 초안 생성/수정/활성화 가능
- [ ] 활성 RuleSet으로 분류/단계 판정이 일관되게 동작
- [ ] 판정 결과에 `confidence`, `reason_codes`, `ruleset_version`가 포함
- [ ] 테스트 통과 + 데모 시나리오 3개 재현

### Phase 2. 정책/인증/IP 지식베이스 구축 (Day 1~2)
- 파일
  - `backend/app/services/knowledge/` (신규)
  - `backend/data/policy_kb/` (신규)
- 작업
  - 정책/인증/RFP 기준 스키마 설계(`requirement`, `eligibility`, `evidence`, `weight`)
  - 초기 KB 적재 스크립트
  - KB 조회 서비스/캐시 레이어
- 산출물
  - KB 로더 + 조회 API
  - 기준 데이터 버전(`kb_version`)

### Phase 3. 에이전트 실제화 (Day 2~4)
- 파일
  - `backend/app/services/agents/classification_agent.py`
  - `backend/app/services/agents/business_plan_agent.py`
  - `backend/app/services/agents/matching_agent.py`
  - `backend/app/services/agents/roadmap_agent.py`
  - `backend/app/services/agents/design_agent.py` (신규)
- 작업
  - 분류/단계: 규칙 엔진 호출 + LLM 설명 생성
  - 사업계획서 생성/재구성: 입력 유형 분기(예비창업/기존사업)
  - 매칭: 인증/IP 적합도 점수화 + 갭 분석
  - 로드맵: 연차별 액션아이템 + 선행조건 + KPI
  - 산출물 포맷 통일(JSON)
- 산출물
  - 각 모듈별 통합 테스트
  - 실패/재시도/폴백 로직

### Phase 4. 문서 인입 파이프라인 (Day 3~5)
- 파일
  - `backend/app/api/v1/files.py`
  - `backend/app/services/document_ingest/` (신규)
- 작업
  - 업로드 엔드포인트 확장(단일/묶음/폴더)
  - 포맷별 추출기 어댑터(`pdf`, `docx`, `hwp`, `hwpx`, `ppt`, `pptx`, `txt`, `excel`)
  - 추출 텍스트 정규화/섹션화
- 산출물
  - 포맷별 파서 결과 검증 테스트
  - 실패 파일 리포트

### Phase 5. API/오케스트레이션 정비 (Day 4~5)
- 파일
  - `backend/app/api/v1/projects.py`
  - `backend/app/services/orchestration_service.py`
- 작업
  - 프로젝트 실행 결과를 단계별 구조화 응답으로 노출
  - 실행 상태/로그/아티팩트 조회 API 분리
  - 다운로드 API를 실제 렌더링 결과 기반으로 전환
- 산출물
  - API 계약 문서 초안
  - 회귀 테스트

### Phase 6. 프론트 UI 리팩토링 (Day 5~6)
- 파일
  - `frontend/src/app/projects/[projectId]/execute/page.tsx`
  - `frontend/src/components/workflow/*`
  - `frontend/src/components/*` (업로드/문서뷰어 신규)
- 작업
  - 입력: 텍스트 + 파일/폴더 업로드 UX
  - 출력: 계획서/매칭표/로드맵 브라우저 뷰 + PDF 다운로드
  - 협업: 전문가 수정 코멘트 반영 영역
- 산출물
  - E2E 사용자 플로우 동작

### Phase 7. 검증/릴리즈 (Day 6~7)
- 작업
  - KPI 측정 스크립트(일치율/수용률/누락률)
  - 단위/통합/회귀/부하 테스트 실행
  - 저녁 점검 배포 + 롤백 절차 문서화
- 산출물
  - 테스트 리포트
  - 릴리즈 노트

## 5) API 변경안 (초안)
- `POST /api/v1/projects/{id}/classify`
- `POST /api/v1/projects/{id}/business-plan/generate`
- `POST /api/v1/projects/{id}/business-plan/reconstruct`
- `POST /api/v1/projects/{id}/matching/score`
- `POST /api/v1/projects/{id}/roadmap/generate`
- `GET /api/v1/projects/{id}/artifacts/{artifact_type}`
- `POST /api/v1/files/upload-batch`

## 6) 데이터 모델 변경안 (초안)
- `CompanyProfile` 확장 필드
  - `industry_code`, `founding_date`, `last_fiscal_year_revenue`, `employment_trend`, `ip_assets`, `cert_status`, `document_sources`
- `AssessmentResult`
  - `company_type`, `growth_stage`, `confidence`, `reasons[]`
- `MatchingResult`
  - `items[] {category, name, score, gaps[], required_evidence[]}`
- `RoadmapResult`
  - `yearly_plan[] {year, goals[], actions[], dependencies[], deliverables[]}`
- `ArtifactMeta`
  - `artifact_id`, `artifact_type`, `format`, `template_id`, `version`

## 7) 테스트 전략
- 단위
  - 규칙 엔진 경계값 테스트
  - 점수 산식 테스트
  - 문서 파서 포맷별 테스트
- 통합
  - 분류 -> 계획서 -> 매칭 -> 로드맵 연쇄 검증
  - API 계약 테스트
- 회귀
  - 기존 프로젝트 생성/조회/실행 플로우
- 부하
  - 동시 업로드/동시 실행 시나리오

## 8) 리스크 및 대응
- 리스크: 1주 내 전 포맷 파서 품질 확보 난이도 높음
- 대응: 파서 어댑터 우선순위 적용(`pdf/docx/txt` 우선), 나머지는 베타 플래그
- 리스크: 도메인 임계치 부정확
- 대응: 규칙 버전 관리 + 설명가능성 로그 + 운영자 조정 포인트 제공

## 9) 비차단 추가 확인 사항
- API 하위호환 정책(기존 응답 필드 유지 범위)
- KPI 수치 목표값(예: 일치율 80% 이상 등)
- 파일 업로드 용량/개수 제한

## 10) 완료 정의 (이번 스프린트)
- 모듈 1~7 전체 E2E 동작
- 텍스트+파일 입력, 브라우저 출력, PDF 다운로드 동작
- 단위/통합/회귀/부하 테스트 리포트 생성
- 저녁 점검 배포 절차 문서 포함
