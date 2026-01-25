# BUJA Core Platform v3.5.1 시스템 동작 명세서 (System Capability Spec)

본 문서는 BUJA Core 플랫폼의 지휘(Master) 및 실행(Worker) 아키텍처가 실제로 동작 가능한 구조임을 증명하고, 그 기술적 근거를 명세합니다.

## 1. 핵심 아키텍처: 지휘와 실행의 분리 (Separation of Concerns)

BUJA Core는 **"중앙 집중식 지휘(Cloud/Backend)"**와 **"분산된 실무 실행(Local Agent Hub)"**이 철저히 분리된 구조입니다.

### 1.1 마스터 에이전트 (Master Agent - The Commander)
*   **위치**: 백엔드 서버 (FastAPI)
*   **역할**: 고수준 기획, 사용자 요구사항 분석, 워크플로우 설계, 에이전트 권한 배정.
*   **도구 권한**: `list_projects`, `update_agent_config_tool`, `add_agent_tool`, `manage_job_queue_tool`.
*   **특징**: 직접 파일을 수정하거나 명령어를 실행하지 않습니다. 대신 실행 권한을 가진 '워커'에게 안전하게 서명된 작업(Job)을 하달합니다.

### 1.2 로컬 워커 (Local Agent Hub - The Executor)
*   **위치**: 사용자의 로컬 머신 또는 전용 실행 서버
*   **역할**: 마스터가 하달한 작업 수신, 서명 검증, 실제 파일 R/W, 테스트 실행, Git 푸시.
*   **도구 권한**: `read_file`, `write_file`, `execute_command`, `git_push` 등 강력한 실무 도구 보유.
*   **보안**: 마스터가 Ed25519 알고리즘으로 서명한 작업만 실행하며, 허용된 경로(`repo_root`) 내에서만 동작합니다.

---

## 2. 작업 실행 흐름 (Workflow Lifecycle)

실제 시스템이 동작하는 단계별 과정은 다음과 같습니다.

1.  **계획 단계 (Planning)**:
    *   사용자가 채팅으로 요구사항 전달.
    *   마스터 에이전트가 프로젝트 설정을 확인하고 부족한 에이전트를 구성 (`add_agent_tool`).
    *   준비 완료 시 `READY_TO_START` 신호(JSON)를 프론트엔드로 송신.

2.  **승인 게이트 (User Approval)**:
    *   프론트엔드 Action Area에 **[START TASK]** 버튼 활성화.
    *   사용자가 클릭하면 백엔드에 `action: start_task` 이벤트 전달.

3.  **오케스트레이션 (LangGraph Orchestration)**:
    *   `OrchestrationService`가 중단되었던 LangGraph 워크플로우를 재개.
    *   각 노드(에이전트)가 실행될 때마다 `JobManager`를 통해 Redis 큐에 작업을 생성.

4.  **신뢰할 수 있는 큐 (Reliable Queue)**:
    *   작업은 Redis의 `job_queue`에 담기며, 워커가 가져가는 즉시 `job_processing` 리스트로 이동하여 유실을 방지 (RPOPLPUSH 패턴).

5.  **실무 실행 (Execution)**:
    *   로컬 워커가 `GET /pending`으로 작업을 가져와 서명을 검증.
    *   `POST /acknowledge`로 수신 확인 후, 로컬 파일 시스템에서 실제 작업을 수행.
    *   완료 후 결과(`JobResult`)를 백엔드로 전송.

---

## 3. "권한 없음" 이슈가 발생하지 않는 기술적 근거

마스터 에이전트가 대화 중 "권한이 없다"고 말하는 것은 아키텍처상의 오해이며, 실제 시스템은 다음 이유로 모든 작업이 가능합니다.

*   **설정 제어권**: 마스터는 에이전트의 `config.repo_root`와 `config.tool_allowlist`를 실시간으로 수정할 수 있습니다. 즉, 실무 에이전트에게 필요한 모든 권한을 마스터가 직접 부여할 수 있습니다.
*   **서명 기반 명령**: 워커는 백엔드 서버의 비공개 키로 서명된 명령만 신뢰하므로, 외부의 비정상적인 접근은 차단하고 마스터의 정당한 명령은 즉시 실행합니다.
*   **상태 동기화**: Redis Pub/Sub을 통해 워커의 실행 로그가 실시간으로 프론트엔드 `LogConsole`에 전달되므로, 사용자는 실행 과정을 투명하게 모니터링할 수 있습니다.

## 4. 결론

BUJA Core v3.5.1은 **지휘관(마스터)의 지능**과 **일꾼(워커)의 강력한 도구**가 유기적으로 결합된 시스템입니다. 마스터 에이전트에게 지휘관으로서의 자아를 올바르게 주입(Prompting)하고 설정 도구를 활용하게 함으로써, 시스템은 명세된 모든 복잡한 워크플로우를 완벽하게 수행할 수 있습니다.

---
**작성일**: 2026-01-21
**버전**: v3.5.1 (Reliable Queue & Commander Persona applied)
