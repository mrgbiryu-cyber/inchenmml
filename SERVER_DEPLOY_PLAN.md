# 서버 배포(릴리스) 파일 정리 계획

작성일: 2026-02-27  
대상 경로: `D:\project\productllm`

## 1) 목표
- 배포 서버에 올리기 전에 소스와 실행 산출물을 분리해 추적 가능하고 안전한 배포 상태를 만든다.
- 민감정보 및 임시 산출물을 제외하고, 운영에 필요한 파일만 패키징한다.
- 배포/운영/점검이 반복되어도 같은 기준으로 동작하도록 표준화한다.

## 2) 현재 상태 요약 (루트 레벨)
- `backend`, `frontend` 코드/구성은 존재.
- `docker`, `scripts`, `shared`, `tools`, `data` 등 역할 구분된 디렉터리 존재.
- 루트에는 임시 산출물/로그/캐시/중간물성 파일이 다수 존재: `pytest-cache-*`, `backend/logs`, `backend/.next`, `frontend/test-results`, `backend_prod.log`, `startup_prod_*`.
- 문서 파일이 여러 개 존재해 운영 기준 문서 통합이 필요.

## 3) 파일 분류 기준
- `A-운영(필수)` : 서버에서 실행에 필요한 코드/설정/의존성.
- `B-개발(권장)` : 개발/검증/수정용 도구 및 가이드.
- `C-임시/산출물` : 실행 로그, 캐시, 테스트 결과, 중간 산출물.
- `D-민감정보` : 실제 시크릿(`.env`, API 키, 인증서 키 등).

## 4) 배포용 폴더 표준 (권장)
```
/D:\
  productllm/
    backend/
    frontend/
    docker/
    shared/
    tools/
    scripts/
    data/                # 운영 데이터/시드(필요 시)
    docs/
    deploy/
      release/
      env/
      scripts/
```

운영에 직접 필요 없는 폴더는 배포 시 제외한다.

## 5) 정리 실행 계획 (파일 정리)
### 5-1. `.env` 및 시크릿 분리
1. 루트 `.env`, `backend/.env`, `frontend/.env.local`를 즉시 점검.
2. 배포 템플릿만 남김:
   - `.env.example`(기존/신규)로 값 이름만 보존하고 실제 값 제거.
3. 실제 값은 서버 비밀관리 방식으로 이전:
   - Docker Secret, GitHub Actions Secret, 서버 환경변수, 또는 Vault.

### 5-2. 로그/캐시/임시 파일 정리 (`C`)
1. 루트/서비스 하위에서 임시 산출물 분리:
   - `pytest-cache-*`
   - `*.log` (예: `backend_prod.log`, `startup_prod_out.log` 등)
   - `.next`, `test-results`
   - `__pycache__`
2. 가능하면 삭제 대상은 `.gitignore` 보강 후, 배포 패키지 빌드 스크립트에서 제외 처리.
3. 운영 로그는 실행 디렉터리 하위 `backend/logs/`, `data/logs/` 같은 영속 위치로 통일.

### 5-3. 스크립트 분리
1. 배포 관련 스크립트는 `deploy/scripts/`로 통합:
   - 배포 시작/종료
   - health check
   - DB/Redis/Neo4j 초기 점검
2. 일회성 진단/디버깅 스크립트는 `scripts/diagnosis/`로 묶고 `README`에 용도 명시.
3. 운영 전용 스크립트는 `deploy/release/`로 이동 후 버전 태깅 대상 관리.

### 5-4. 문서 정리 (`B`)
1. `docs/`, `doc/` 병합 대상 지정:
 - 운영 가이드: 배포/운영/장애 복구 관련 문서 1개 폴더 통합.
 - 설계/개발 기록은 별도 `docs/notes/`로 보관.
2. 루트의 `README` 계열 중 중복 내용을 정리해 `docs/`로 이동, 루트 `README.md`는 진입점만 남김.

## 6) 배포 단계 체크리스트 (권장 순서)
### 6-1. 사전 준비
- [ ] Node, Python, docker 설치 확인
- [ ] 포트/도메인/SSL 정책 확정
- [ ] 외부 의존성(예: Redis/DB/Neo4j) 접속정보 정리
- [ ] 배포용 환경변수 키 목록 확정

### 6-2. 패키징
- [ ] 운영 브랜치/커밋 고정
- [ ] 임시/캐시/로그 삭제 후 클린 빌드
- [ ] `frontend` 정적 빌드 산출물 검증
- [ ] `backend` 의존성 잠금 파일 점검(`requirements.txt`, `package-lock.json`)

### 6-3. 서버 반영
- [ ] `docker-compose` 네트워크/볼륨/재시작 정책 확인
- [ ] `.env`는 런타임 주입 방식으로 주입
- [ ] 헬스체크 엔드포인트/의존성 연결 테스트
- [ ] 정적 자산, API, WS/WebSocket 연결 동작 확인

### 6-4. 배포 후 정리
- [ ] `health_check` 실행 로그 저장
- [ ] 롤백 지점(`git tag`, 도커 이미지 태그) 기록
- [ ] 임시 산출물 생성 주기와 보관기간 설정

## 7) `.gitignore` 권장 항목 추가
- `*.log`
- `.next/`
- `node_modules/`
- `pytest-cache-*`
- `__pycache__/`
- `backend/*.log`
- `frontend/test-results/`
- `*.err`

## 8) 즉시 실행 가능 액션
1. `deploy/` 폴더 생성:
   - `deploy/release`, `deploy/scripts`, `deploy/env`
2. `.gitignore`에 `C-임시/산출물` 패턴 반영.
3. `docs/`에 배포 기준 문서(`SYSTEM_OVERVIEW`, `QUICKSTART`, `RESTART`, `README`) 링크맵 작성.
4. `deploy/scripts/deploy.sh` 또는 `deploy/scripts/deploy.ps1` 추가:
   - 클린 빌드
   - 이미지 빌드/업
   - health check
   - 실패 시 롤백

## 9) 운영 판단 규칙 (승인 기준)
- `A-운영`만 서버로 복사/빌드 대상.
- `B-개발`은 운영 패키지에 포함하지 않아도 됨.
- `C-임시`는 배포 이전에 반드시 제거.
- `D-민감`은 절대 코드 저장소에 실값 저장 금지.

## 10) 다음 단계 권장
- 1) 먼저 `deploy/` 기준 폴더 구조만 세팅
- 2) `.gitignore` 정리 후, 클린 빌드가 통과되는지 확인
- 3) 실제 운영 서버 한 번 드라이런(실배포 없이 이미지 빌드+헬스체크) 수행
