# E2E API/프론트 통합 테스트 케이스

## 목적
- Growth Support API와 실행 UI의 연결 검증
- 관리자 RuleSet 튜닝과 실행 결과 반영 검증

## 사전조건
- 백엔드 서버 실행 (`:8002`)
- 프론트 서버 실행
- 관리자 계정 로그인

## 케이스

### TC-01 RuleSet 활성화 반영
1. `/admin/rules` 진입
2. `v1` 복제 -> `v1.1` 생성
3. 특정 룰 점수 수정 후 저장
4. `Activate` 실행
5. `/projects/{id}/execute`에서 동일 입력으로 파이프라인 실행

기대결과
- 결과 JSON에 `ruleset_version: v1.1` 반영
- `reason_codes` 변화 확인 가능

### TC-02 Growth Pipeline Run
1. `/projects/{id}/execute` 진입
2. Company Profile JSON 입력
3. `Run Growth Pipeline` 클릭

기대결과
- 상태가 `DONE`으로 전환
- 결과 스냅샷에 `classification/business_plan/matching/roadmap` 포함

### TC-03 Artifact HTML/Markdown/PDF
1. 실행 완료 후 Artifact 버튼 클릭
2. `BusinessPlan HTML`, `BusinessPlan MD`, `BusinessPlan PDF` 순차 확인

기대결과
- HTML: 브라우저 렌더링
- Markdown: 텍스트 응답
- PDF: `application/pdf` 다운로드 또는 새 탭 표시

### TC-04 Batch Upload 연동
1. `/api/v1/files/upload-batch`로 동일 파일 포함 배치 업로드

기대결과
- 중복 파일은 `skipped`
- 신규 파일은 `queued`

### TC-05 최신 실행 결과 조회
1. `/api/v1/projects/{id}/growth-support/latest` 호출

기대결과
- 마지막 실행 결과(JSON)가 반환
- 서버 재시작 이후에도 DB 저장 결과 조회 가능

## 6단계 사용자 페르소나 플로우(E2E) 통합 체크

### F-01 초기기업 대표
1. `/projects/{id}/execute`에 유효한 `profile`/`input_text` 입력
2. `Run` 실행 요청 호출(동일 API)
3. `growth-support/latest` 조회
4. `artifacts`(HTML/Markdown/PDF) 연속 조회

검증 포인트
- 1회 실행에서 4개 결과 항목이 모두 생성되는지
- 버튼 클릭 흐름에서 연속 실패 없이 1회 완료되는지

### F-02 사업지원 실무자(재구성 사용)
1. 파일 업로드 `POST /api/v1/files/upload` (지원 포맷)
2. 기존 초안 텍스트로 재실행
3. Matching/roadmap 결과의 gap/recommendation 확인

검증 포인트
- 기존 입력을 반영한 재구성 모드로 결과 필드가 채워지는지
- 업로드 결과 메시지와 파이프라인 결과가 일치하는지

### F-03 정책사업 운영 매니저(반복 실행)
1. 동일 프로젝트에서 연속 2회 이상 run 호출
2. 호출 직후 latest 조회
3. 결과 항목 title/version 갱신 확인

검증 포인트
- 캐시/DB에서 최신 결과가 조회되는지
- 연속 실행이 서로 다른 결과 ID/시간대로 분기되는지

### F-04 규칙 관리자
1. `GET /api/v1/admin/rulesets` 조회
2. clone + activate 수행
3. `/api/v1/admin/rulesets/{id}/{version}/preview` 확인
4. 동일 프로젝트 run 호출

검증 포인트
- 활성 ruleset 변경 후 런타임 분류 `ruleset_version`이 최신으로 반영되는지
