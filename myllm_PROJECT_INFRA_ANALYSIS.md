# 📊 Project Infrastructure Analysis

목적:
이 프로젝트를 Proxmox 기반 서버에 배치하기 위한 리소스 산정을 수행한다.

---

## 1️⃣ 기본 정보

- **프로젝트명**: BUJA Core Platform (Server-Centric Hybrid AI Platform)
- **주요 목적**: AI 에이전트 작업 오케스트레이션, 클라우드 및 온프레미스 워커를 통한 LLM 프롬프트/작업 스케줄링 및 처리
- **현재 개발 단계**: 개발 진행중 / 사내 베타 (Mock DB 혼용, 로컬 개발 환경 구성 위주)
- **예상 사용자 수 (초기 / 6개월 후)**: 
  - 초기: 10~50명 (어드민, 핵심 개발/사용자)
  - 6개월 후: 100~500명 규모 (작업 큐 및 분산 워커에 따른 시스템 확장이 필요한 시점)

---

## 2️⃣ 기술 스택 분석

1. **사용 언어**: Python 3.10+ (Backend/Worker), TypeScript/Node.js (Frontend)
2. **프레임워크**: FastAPI (Backend), Next.js 14 App Router (Frontend)
3. **실행 방식**: 멀티 프로세스 / 워커 구조
   - FastAPI (Uvicorn 구동)
   - Next.js SSR 서버
   - Local Agent Hub (독립적인 Long Polling Worker 프로세스)
4. **Docker 사용 여부**: Yes (docker-compose 환경 제공)
5. **docker-compose 구성 여부**: Yes (Redis, Neo4j, PostgreSQL 포함)
6. **DB 종류**: 
   - RDBMS: PostgreSQL 16 (로컬 개발용으로 SQLite 병용)
   - Graph DB: Neo4j 5.16 (지식 메타데이터 관리)
   - Queue/State: Redis 7.2
7. **캐시 사용 여부 (Redis 등)**: Yes (Job Queue, 상태 캐싱 등에 Redis 활용)
8. **외부 API 의존성**: OpenRouter, OpenAI 플랫폼 API 연동 (경우에 따라 로컬 Ollama 사용)
9. **GPU 필요 여부**: Yes (Worker가 Ollama 등을 통한 Local LLM 모델 실행 시 강력한 GPU/VRAM 필수)

---

## 3️⃣ 실행 구조 분석

1. **API 서버 여부**: Yes (FastAPI가 메인 API 서버 역할을 수행)
2. **WebSocket 사용 여부**: 명시적이지 않으나, Worker가 30초 간격으로 `GET /pending` Long Polling을 수행함
3. **백그라운드 작업 존재 여부**: Yes (`knowledge_worker` 등 백그라운드 태스크 구동)
4. **스케줄러 사용 여부 (cron, Celery, Bull 등)**: Yes (요구사항에 Celery 옵셔널 기재, 기본적으로 Redis 큐 기반 워커 실행)
5. **실시간 처리 여부**: 부분적 실시간 (Frontend에서 스트리밍 로그 및 작업 상태 실시간 모니터링)
6. **대량 반복 루프 존재 여부**: Worker의 Heartbeat 및 Long Polling 무한 루프
7. **영상/이미지 인코딩 여부**: No (주로 Text/LLM 데이터 파싱 및 Graph 처리)

---

## 4️⃣ 리소스 소비 성향 분석

**분류: Memory 집약적 & CPU/GPU 집약적**

**이유**:
1. **Memory 집약적**: 
   - **Neo4j**는 자바 기반의 Graph DB로, 기본 `Initial Heap 512M / Max Heap 2G`가 설정되어 있으며 데이터와 쿼리가 복잡해질수록 막대한 메모리를 점유합니다.
   - **Next.js** SSR 환경 역시 컴파일과 요청 처리에 의외의 메모리를 소모합니다.
2. **CPU/GPU 집약적**:
   - `local_agent_hub` 워커가 온프레미스로 **Ollama** 등 로컬 LLM을 실행할 경우, 토큰 추론 마다 강력한 CPU, 가급적 전용 GPU가 필요합니다. 병목의 핵심입니다.

---

## 5️⃣ 데이터 특성

1. **파일 업로드 기능**: Worker가 로컬 파일 시스템에서 생성/읽기/수정(Create/Read/Update) 작업을 직접 수행함 (Jailbreak 등 보안 요주의)
2. **로그 발생량 추정**: High (LLM 요청/응답 페이로드, 30초 단위 Polling 로그, Redis Job 로그 등)
3. **데이터 증가 속도**: 빠름 (대화 내역, Draft/Shadow Mining 데이터, Neo4j 노드 엣지가 트랜잭션마다 증가함)
4. **백업 중요도**: High (Neo4j 지식 그래프 및 RDB 유저/잡 데이터 무결성 보존 필요)
5. **개인정보 저장 여부**: Tenant ID, 권한(Role), 비밀번호(Bcrypt), JWT Auth 기반이므로 유출 민감도 높음

---

## 6️⃣ 장애 민감도 평가

**장애 발생 시 리스크 등급: High**

**이유**:
1. 백엔드와 Redis 중 하나라도 다운되면 워커(LLM 작업자)들이 일감을 가져가지 못해 전체 파이프라인이 정지(SPOF)됩니다.
2. Neo4j 연결이 불안정할 경우 Agent의 컨텍스트 파악이나 정보 기록이 실패하게 되어 AI 응답 품질에 치명적인 영향을 미칩니다.
3. Long Polling 방식이므로 서버 재시작 시 워커들이 일시적으로 재연결폭주(Thundering Herd)를 유발할 수 있습니다.

---

## 7️⃣ 확장 시뮬레이션

| 동시 사용자 | CPU 리소스 추정 | RAM 추정 | 비고 |
| --- | --- | --- | --- |
| **1명** | 2~4 vCPU | 8GB | 로컬 LLM 사용시 추가 GPU VRAM 8GB+ 필요 |
| **10명** | 4~8 vCPU | 16GB | Neo4j Heap RAM 증설 및 Redis IO 증가 대응 |
| **100명** | 16+ vCPU | 32GB+ | Worker 분산, API 서버 다중화, DB 별도 VM 격리 필수 |

---

## 8️⃣ 최종 인프라 권장안

| 인프라 요구 항목 | 권장 사양 / 설정 |
| --- | --- |
| **추천 vCPU 범위** | 8 Core ~ 16 Core 기조 (워커 포함 통합 운영 시) |
| **추천 RAM 범위** | 16GB ~ 32GB (Neo4j, Redis, LLM 구동 포함) |
| **디스크 권장 용량** | 200GB SSD 이상 (Neo4j DB, Docker 이미지, LLM 가중치 파일 저장) |
| **분리 VM 필요 여부** | **Yes** (API/DB 코어 VM과 Local LLM Worker VM 분리 강력 권장) |
| **스케줄 실행 권장 여부** | Yes (비동기 태스크/Redis 기반 분산 처리 구조 유지) |
| **GPU 필요 여부** | **Yes** (로컬 Ollama 구동 시 Nvidia GPU Pass-through 필요) |
| **명시적 Reverse Proxy** | **Yes** (Nginx/Traefik - 포트 통합, SSL 터미네이션, WebSocket/Polling 타임아웃 튜닝) |
| **Rate Limit 지정** | **Yes** (LLM API 크레딧 고갈/비용 폭탄 및 자원 남용 방지 목적) |

---

## 9️⃣ 위험 요소 및 인프라 리스크

해당 프로젝트를 서버에 올릴 경우 식별되는 5가지 잠재적 인프라 리스크:

1. **OOM (Out Of Memory) 리스크**: Neo4j JVM Heap 메모리와 로컬 Agent Hub(Ollama) 사용 메모리가 충돌하여 호스트나 컨테이너가 뻗을 가능성.
2. **Long Polling Connection 고갈 리스크**: 워커 수가 늘어날 경우 백엔드(FastAPI)의 비동기 커넥션 스레드/파일 디스크립터 한도에 도달하여 병목 발생. (웹소켓이나 Redis Pub/Sub 도입 고려 필요)
3. **무한 재실행 / 데드락 충돌**: Worker의 파일 오퍼레이션(Read/Write) 중 충돌이나 토큰 초과 시 무한 Retry 상태에 빠져 CPU가 지속적으로 점유될 가능성.
4. **보안 유출 (Jailbreak)**: Worker가 로컬 파일에 직접 접근하므로(보안 룰존재하나), 프롬프트 인젝션을 통해 악의적인 사용자가 호스트(Proxmox)의 민감한 파일 경로에 접근할 위험이 존재함. VM Isolation 필수.
5. **데이터 디스크 I/O 포화 리스크**: Neo4j의 대량 노드 조회 및 RDB(Postgres), Redis 영속성(AOF) 기록이 동시에 발생하면 Proxmox 스토리지 I/O(IOWait)가 급증하여 시스템 전반적인 지연 발생.

---

## 🔟 최종 등급

- **등급**: **Tier 4 (격리 필수)**

**선정 이유**:
이 프로젝트는 단순한 CRUD 기반 웹 애플리케이션(Tier 1/2)을 넘어서, **Graph DB(Neo4j)와 비동기 LLM Agent(로컬 구동 포함)**를 결합하여 운영되는 고도화된 시스템입니다. 
메모리 점유 폭이 크고, 에이전트의 로컬 시스템 파일 접근 기능(FS Operator)이 포함되어 있으므로 **보안적 관점에서도, 자원 할당 관점에서도 다른 서비스와 분리하여 격리된 전용 VM 환경(Tier 4)에 배포**하는 것이 필수적입니다.
