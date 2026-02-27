# Step 5 운영 모드 실행 가이드 (실서비스 환경)

## 1. 실행 목적
`refactor_followup` 기반 리팩토링 후, 운영 환경(`production`)에서 Step 1~3(사전 인증/프로젝트 확보/기본 API) 검증을 위한 가이드입니다.

## 2. 실서비스 필수 환경변수 (별도 DB 서버 기준)

### Backend
- `ENVIRONMENT=production`
- `DEBUG=false`
- `PORT=8002`
- `HOST=0.0.0.0`
- `DATABASE_URL=postgresql+asyncpg://<db_user>:<db_password>@<db_host>:5432/<db_name>`
- `REDIS_URL=redis://<redis_host>:6379/0`
- `NEO4J_URI=bolt://<neo4j_host>:7687`
- `NEO4J_USER=<neo4j_user>`
- `NEO4J_PASSWORD=<neo4j_password>`
- `JWT_SECRET_KEY=<your-long-random>`
- `JOB_SIGNING_PRIVATE_KEY`, `JOB_SIGNING_PUBLIC_KEY`
- `STARTUP_WITHOUT_REDIS` (운영본권장: `false`; 로컬 스모크 한시적 허용: `true`)

### Frontend
- `NEXT_PUBLIC_API_URL=http://<backend-host>:8002/api/v1`
- (선택) `NEXT_PUBLIC_APP_NAME`, 분석키 설정

> 참고: 기존 `.env`의 `NEO4J_URL`은 하위 호환을 위해 현재 코드에서 읽도록 되어 있습니다. 운영에서는 신규 `NEO4J_URI` 사용을 권장합니다.

- 운영 전제: DATABASE/Redis/Neo4j는 각기 분리된 전용 서버로 운영(기본 포트 충돌 회피)
- `STARTUP_WITHOUT_REDIS=true`는 로컬 QA 스모크용 보조 플래그입니다. 운영 스테이징/프로덕션에서는 `false`를 강제하세요.

## 3. 운영 실행 전 사전 점검 (권장)

※ 운영 환경(실서비스)에서 `DATABASE_URL`을 `postgresql+asyncpg`로 사용할 경우:
- 백엔드 Python 런타임에 `asyncpg`가 반드시 설치되어 있어야 함
- 미설치 시 `backend` 기동/`init_db` 단계에서 시작 실패 가능성 있음

```powershell
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
$env:NEO4J_URI = "bolt://127.0.0.1:7687"
$env:NEO4J_USER = "neo4j"
$env:NEO4J_PASSWORD = "<pw>"
$env:PYTHONPATH = "D:\\project\\productllm\\backend"

python -c "import asyncio, os, redis.asyncio as redis\nfrom neo4j import AsyncGraphDatabase\n\nasync def main():\n    try:\n        rc = redis.from_url(os.environ['REDIS_URL'])\n        await rc.ping()\n        print('REDIS_OK')\n    except Exception as e:\n        print(f'REDIS_FAIL: {e.__class__.__name__}: {e}')\n\n    try:\n        d = AsyncGraphDatabase.driver(os.environ['NEO4J_URI'], auth=(os.environ['NEO4J_USER'], os.environ['NEO4J_PASSWORD']))\n        async with d.session() as s:\n            r = await s.run('RETURN 1 AS x')\n            v = await r.single()\n            print(f'NEO4J_OK: {v["x"]}')\n    except Exception as e:\n        print(f'NEO4J_FAIL: {e.__class__.__name__}: {e}')\n\nasyncio.run(main())" 
```

## 4. Step 1~3 실행 순서 (운영 모드)

### 4.1 Step 1: 백엔드 기동

```powershell
$env:PYTHONPATH = "D:\\project\\productllm\\backend"
$env:ENVIRONMENT = "production"
$env:DEBUG = "false"
$env:LOG_LEVEL = "INFO"
$env:DATABASE_URL = "postgresql+asyncpg://svc:***@db.internal:5432/prod_buja_core"
$env:REDIS_URL = "redis://redis.internal:6379/0"
$env:NEO4J_URI = "bolt://neo4j.internal:7687"
$env:NEO4J_USER = "neo4j"
$env:NEO4J_PASSWORD = "***"

cd D:\\project\\productllm\\backend
uvicorn app.main:app --host 0.0.0.0 --port 8002
```

기대 결과: `INFO` 레벨로 시작 로그 + `/health` 응답 가능

### 4.2 Step 2: 사전 인증 토큰 확보

```powershell
# 회원 등록(운영에서 이미 계정 존재 시 생략 가능)
Invoke-RestMethod "http://<host>:8002/api/v1/auth/register?username=admin&password=TempPass123!" -Method Post

# 토큰 획득
$login = @{ username="admin"; password="TempPass123!" } | ConvertTo-Json
$tokenResp = Invoke-RestMethod "http://<host>:8002/api/v1/auth/token" -Method Post -ContentType "application/json" -Body $login
$tokenResp.access_token
```

기대 결과: `access_token` 발급

### 4.3 Step 3: 프로젝트 ID 확보

```powershell
$headers = @{ Authorization = "Bearer $($tokenResp.access_token)" }
Invoke-RestMethod "http://<host>:8002/api/v1/projects/" -Method Get -Headers $headers

$body = @{ name = "Prod Test Project" } | ConvertTo-Json
$created = Invoke-RestMethod "http://<host>:8002/api/v1/projects/" -Method Post -Headers $headers -ContentType "application/json" -Body $body
$created.id
```

기대 결과: 프로젝트 목록 또는 생성 응답에서 `id` 획득

## 5. 실행 결과 기록(로그 업데이트용 템플릿)

- 실행 항목: Step 1~3 (운영 모드)
- 수행일시: `YYYY-MM-DD HH:mm`
- 결과: `PASS` / `BLOCKED`
- 근거:
  - Redis 연결: PASS/BLOCKED + 에러 메시지
  - Neo4j 연결: PASS/BLOCKED + 에러 메시지
  - `/api/v1/auth/token`: PASS/BLOCKED
  - 프로젝트 ID 추출: PASS/BLOCKED

## 6. 운영 모드 패치 참고(이번 리팩토링 분기 적용)
- `backend/app/core/config.py`: `NEO4J_URL` 호환 읽기 추가
- `backend/app/core/database.py`: 기본 Postgres placeholder만 sqlite fallback 처리로 정리
- `backend/requirements.txt`: `asyncpg`, `aiosqlite`, `sqlalchemy` 등록

