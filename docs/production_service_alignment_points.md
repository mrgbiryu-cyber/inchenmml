# Production Service Alignment Points

작성일: 2026-02-27  
목적: 서버 배포 전에 백엔드 정합성/안전성/운영성 기준을 1회 점검 가능한 문서로 정리

참고:
- `SERVER_DEPLOY_PLAN.md`
- `docs/DEPLOYMENT_GUIDE.md`
- `docs/qa_step5_e2e_env_setup_guide.md`

---

## 1) P0 (최우선 정리 필요 항목)

### 1-1. 외부 DB/캐시 서버 연동 규칙
- PostgreSQL, Redis, Neo4j는 별도 서버(또는 별도 인프라)에서 운영하고 앱은 연결만 수행
- `DATABASE_URL`, `REDIS_URL`, `NEO4J_URI`는 로컬 루프백(`127.0.0.1`, `localhost`) 금지
- `DATABASE_URL` 포맷은 `postgresql+asyncpg://...` 사용
- TLS/SSL, 보안그룹, DNS/호스트 정책을 사전 점검

### 1-2. 운영 시작 가드
- `ENVIRONMENT=production`에서 SQLite fallback 금지
- `STARTUP_WITHOUT_REDIS=false`
- `STARTUP_WITHOUT_POSTGRES=false`
- DB 연결 실패 시 서버 기동 실패 처리
- DB URL 미존재/형식오류는 즉시 종료

### 1-3. DB 정합성 사전 점검
- PostgreSQL 핵심 테이블 존재/PK/FK/UNIQUE/인덱스 점검
  - `users`, `user_projects`, `messages`, `threads`, `drafts`, `growth_runs`, `growth_artifacts`, `cost_logs`
- Neo4j 핵심 라벨/관계 점검(예: Project, AgentRole, Knowledge Graph)
- 최소권한 운영 계정 정책 및 migration 상태 점검

### 1-4. 헬스체크 강화
- `/health`는 `redis`, `postgresql`, `neo4j` 컴포넌트 상태 포함
- 상태값: `healthy` / `degraded` / `unhealthy`
- 타임아웃 기준(권장): redis 300ms, postgres 500ms, neo4j 700ms
- 외부 시스템 연동 실패 구간은 명확한 degraded/unhealthy 구분

### 1-5. 배포 산출물 정리
- 배포 패키지에서 `*.md`, `docs/`, `doc/`, 테스트/진단 스크립트(`scripts/test_*`, `scripts/check_*`, `scripts/debug_*` 등), 캐시 산출물 제외
- `.dockerignore` 신설/보강, `.gitignore` 보강 (`pytest-cache-*/` 포함)
- `.env`/개인키는 저장소/이미지에 포함하지 않음

---

## 2) P1 (중요 반영)

### 2-1. 시크릿 및 네트워크
- Vault/Secrets Manager/CI Secret으로 민감정보 주입
- `REDIS_URL`, `NEO4J_URI`, `DATABASE_URL`의 DNS/포맷 선검증
- CORS는 allowlist 기반 (`allow_origin_regex` 제거 권장)

### 2-2. 배포 전 자동검증
- `scripts/verify_prod_integration.py` 실행
- Redis ping -> Postgres 쿼리 -> Neo4j connectivity 순차 점검
- Step 1~3 핵심 플로우(register/token/projects) 점검

### 2-3. 권한/기능 정합
- `super_admin`, `tenant_admin`, `standard_user` 권한 시나리오 점검
- `orchestration.py` 중복 헬스 체크 정책 정리(단일 기준으로 통일)
- Neo4j debug 출력은 구조화 로그로 통일

---

## 3) P2 (운영 안정화)

### 3-1. 오류/관측성
- 4xx/5xx 응답에 공통 포맷 적용 (`error_code`, `message`, `detail`, `trace_id`)
- 민감정보 마스킹(토큰/비밀번호/키)

### 3-2. 장애 대응
- Neo4j/Redis/DB 불안정 상태에서 degraded/unhealthy 반환 정책 고정
- 외부 알림/대시보드 경보 임계치와 재시도 정책 문서화
- 이미지 태그 롤백 전략 사전 준비(1회 배포 실패시 즉시 롤백 가능)

---

## 4) Backend 변경사항 후보 (파일 단위)

### 4-1. `backend/app/core/config.py`
- `STARTUP_WITHOUT_POSTGRES` 미존재인지 점검 후 추가 필요
- 기본값으로 localhost 기반 URL/비밀번호 하드코딩 제거
- 필수 시크릿(`JWT_SECRET_KEY`, `JOB_SIGNING_*`, DB/Neo4j 자격증명) 강제 주입 정책 정리

### 4-2. `backend/app/core/database.py`
- production에서 SQLite fallback 로직은 제거 또는 운영 모드에서 즉시 실패 처리
- `DATABASE_URL` 형식/`asyncpg` 검증 보강

### 4-3. `backend/app/main.py`
- `allow_origin_regex` 사용 제거 후 `CORS_ORIGINS` whitelist 적용
- `/health`에 redis/postgres/neo4j 컴포넌트 상태 반영
- `/health`에서 데이터 적재(`save_to_db`) 같은 테스트성 쓰기 제거
- `STARTUP_WITHOUT_POSTGRES` 반영

### 4-4. `backend/app/api/v1/orchestration.py`
- 중복 `/health` 처리 정책 정리(단일 기준 엔드포인트 유지)

### 4-5. `backend/app/core/neo4j_client.py`
- `print(...)` 기반 디버그 제거 후 structured logger로 교체
- 연결 실패/타임아웃 시 반환 상태와 에러 코드 일관화

### 4-6. `docker/docker-compose.yml`
- Neo4j/Postgres 비밀번호 하드코딩 제거
- 운영 환경에서는 외부 DB/캐시 연결을 기본 모드로 유지

### 4-7. `scripts/verify_prod_integration.py`
- 등록/토큰/프로젝트 흐름 + DB read-after-write 검증 추가
- Redis/PG/Neo4j 각각의 쓰기·조회 일치성 검증 항목 통합

---

## 5) DB 읽기/적재 검증 항목 (핵심 질문 반영)

### 5-1. 읽기(Read) 경로
- PostgreSQL 읽기: 메시지/성장 실행 결과/초안 조회 API 및 쿼리 경로 점검
- Redis 읽기: ping/publish/subscribe 경로, TTL 정책 점검
- Neo4j 읽기: `get_project`, `list_projects`, `query_knowledge`, `get_knowledge_graph` 경로 점검

### 5-2. 적재(Write) 경로
- PostgreSQL 적재: 메시지 저장, 성장 결과/아티팩트 저장 함수
- Redis 적재: 큐/세션/임시 캐시 적재와 만료 정책
- Neo4j 적재: 프로젝트 생성/그래프 생성 흐름

### 5-3. 일치성 점검
- 생성 직후 즉시 조회되는지 read-after-write로 검증
- 실패 시 재시도/ dead-letter 전략 문서화
- 백업/복구 루틴 확인(예: PostgreSQL dump, Neo4j export, Redis BGSAVE)

---

## 6) 크로스체크 코멘트(코드 반영 필요 체크리스트)

- [C1] `main.py`의 `allow_origin_regex` → whitelist 전환
- [C2] `config.py`에 `STARTUP_WITHOUT_POSTGRES` 추가/확인
- [C3] `database.py`에서 production SQLite fallback 차단
- [C4] `neo4j_client.py` debug print 제거 및 구조화 로깅 적용
- [C5] `.dockerignore` 생성 및 산출물 제외 규칙 반영
- [C6] `.gitignore`에 `pytest-cache-*/` 추가
- [C7] `docker-compose.yml` 시크릿 하드코딩 제거
- [C8] 백업/롤백 항목(C10~C12)의 실행 스크립트 정식 배치

---

## 7) 실행 체크리스트

### 사전
- [ ] `ENVIRONMENT=production`, `STARTUP_WITHOUT_REDIS=false`, `STARTUP_WITHOUT_POSTGRES=false`
- [ ] `.dockerignore`/`.gitignore` 정리 반영
- [ ] CORS whitelist 값 점검

### 자동
- [ ] `python -c "import asyncpg; print(asyncpg.__version__)"`
- [ ] `GET /health` 컴포넌트 상태/지연시간 확인
- [ ] `python scripts/verify_prod_integration.py --url http://localhost:8000`
- [ ] DB read-after-write 통합 검사 실행

### 운영
- [ ] 권한별 API 시나리오 검증(super_admin/tenant_admin/standard_user)
- [ ] 4xx/5xx 응답 스키마 및 민감정보 마스킹 검증
- [ ] 배포 이미지에 문서/테스트 산출물 미포함 확인
- [ ] 롤백/복구 스크립트 및 백업 점검(C10~C11)

---

## 8) 완료 보고서 + 라인 단위 검증 (2026-02-27)

### 8-1. 반영 증거 (직접 확인)

> 검증 방법: codex 제시 라인을 직접 열람하여 실제 코드 확인  
> `✅ 확인` = 해당 라인에서 코드 직접 확인 / `⚠` = 부분 반영

| 항목 | 파일:라인 | 상태 | 확인된 실제 코드 |
|------|-----------|------|----------------|
| `STARTUP_WITHOUT_POSTGRES` 추가 | `config.py:37` | ✅ | `STARTUP_WITHOUT_POSTGRES: bool = False` |
| `STRICT_DB_MODE` 추가 | `config.py:38` | ✅ | `STRICT_DB_MODE: bool = False` |
| health timeout 설정 | `config.py:100~102` | ✅ | `HEALTH_REDIS_TIMEOUT_MS`, `HEALTH_POSTGRES_TIMEOUT_MS`, `HEALTH_NEO4J_TIMEOUT_MS` |
| production SQLite fallback 차단 | `database.py:200~201` | ✅ | `if IS_PRODUCTION and selected_url.startswith("sqlite"): raise RuntimeError(...)` |
| production loopback DB 차단 | `database.py:197~198` | ✅ | `if IS_PRODUCTION and ("localhost" in ...): raise RuntimeError(...)` |
| `postgresql+asyncpg://` 강제 검증 | `database.py:184,194` | ✅ | `must use postgresql+asyncpg://` / asyncpg 설치 확인 |
| CORS allowlist 적용 | `main.py:211` | ✅ | `allow_origins=_parse_cors_origins(settings.CORS_ORIGINS)` |
| `allow_origin_regex` 제거 | `main.py` | ✅ | 파일 전체에 `allow_origin_regex` 없음 |
| `/health` PG 점검 추가 | `main.py:270` | ✅ | `async def _check_postgresql(...)` + `SELECT 1` |
| `/health` Neo4j 점검 추가 | `main.py:281` | ✅ | `async def _check_neo4j(...)` + `verify_connectivity()` |
| `/health` 복합 엔드포인트 | `main.py:297` | ✅ | `@app.get("/health")` composite health |
| `save_to_db` 제거 | `main.py` | ✅ | 파일 전체에 `save_to_db` 없음 |
| `STARTUP_WITHOUT_REDIS` 가드 | `main.py:74` | ✅ | `allow_startup_without_redis = bool(settings.STARTUP_WITHOUT_REDIS)` |
| 운영 loopback Redis/Neo4j 차단 | `main.py:77,79` | ✅ | `_is_loopback_endpoint` 체크 + `RuntimeError` |
| 중복 `/health` 제거 | `orchestration.py` | ✅ | 파일 전체에 `@router.get("/health")` 없음 (WebSocket만 존재) |
| `neo4j_client.py` structlog 전환 | `neo4j_client.py:6,9` | ✅ | `from structlog import get_logger` / `logger = get_logger(__name__)` |
| `pytest-cache-*/` → `.gitignore` | `.gitignore:72` | ✅ | `pytest-cache-*/` 확인 |
| `.dockerignore` 신규 생성 | 루트 | ✅ | 36줄, docs/md/env/tests/scripts/cache 제외 완성 |
| compose 시크릿 env 치환 | `docker-compose.yml:33,34,58` | ✅ | `${NEO4J_PASSWORD:-change_me_in_env}`, `${POSTGRES_PASSWORD:-change_me_in_env}` |
| config 기본값(localhost/기본 비밀번호) 제거 | `config.py:35,39,43,44` | ✅ | `REDIS_URL/NEO4J_*`를 `Optional` + `None`으로 변경 |
| 전역 에러 스키마 핸들러 | `main.py:166,174,186,196` | ✅ | trace-id 미들웨어 + HTTP/Validation/Unhandled 예외 핸들러 |
| DLQ/재시도 정책 | `job_manager.py:81,408,409,424` | ✅ | 실패 시 재큐잉, 최대 재시도 초과 시 DLQ 이동 |
| `verify_prod_integration.py` Redis/Neo4j write-read | `verify_prod_integration.py:64,65,151,173` | ✅ | Redis set/get, Neo4j create/read/delete(옵션 인자 기반) |
| `verify_prod_integration.py` 신규 | `scripts/` | ✅ | health + register/token/projects create + read-after-write |
| `backup.ps1` 신규 | `deploy/scripts/` | ✅ | 40줄, pg_dump/BGSAVE/neo4j cypher export |

### 8-2. 부분 반영 (⚠)

| 항목 | 상태 | 잔여 사항 |
|------|------|-----------|
| `verify_prod_integration.py` Redis/Neo4j write-read | ⚠ | direct check는 옵션 인자(`--redis-url`, `--neo4j-*`) 제공 시에만 실행 |

### 8-3. 미반영 (❌)

| 항목 | 상태 | 비고 |
|------|------|------|
| 없음 | - | 코드 반영 항목 기준 미반영 없음 |

### 8-3. 요약

- ✅ 완료: 24건
- ⚠ 부분 반영: 1건
- ❌ 미반영: 0건

### 8-4. 후속 작업

- [ ] CI에서 `verify_prod_integration.py` 실행 시 `--redis-url`, `--neo4j-uri`, `--neo4j-user`, `--neo4j-password` 주입
