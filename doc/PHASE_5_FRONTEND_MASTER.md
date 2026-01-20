AI-UI 시스템 프론트엔드 전체 명세서 (최종 정리 - 보완판)

본 문서는 AI와 UI 관련 논의를 통해 확정된 프론트엔드 명세를 종합적으로 정리한 것입니다. 누락된 기능을 보완하여 완성도 있는 참조 문서로 제공합니다.

📁 프로젝트 개요

프로젝트 명: MyLLM Management System

기술 스택: Next.js(App Router), TypeScript, Tailwind CSS

주요 특징: 반응형 디자인, JWT 인증, 실시간 상태 모니터링, 다중 시각화 인터페이스

🎯 Phase 5: Frontend UI 전체 명세

기본 원칙

반응형(Responsive) 디자인 기본 적용

Tailscale 접속 환경 최적화 (모바일 우선)

다크 모드 기준 디자인

레이아웃 구조 (3-Column Design)



[좌측 Navigation] | [중앙 Main View] | [우측 Status]

좌측 패널 (Navigation)

도메인 셀렉터 (프로젝트/저장소 선택) + 신규 프로젝트 생성 버튼

대화 히스토리 목록

Super Admin 메뉴 (권한 있을 시 표시)

중앙 패널 (Main View) - 가변적 컨텐츠

지식 그래프, 랭그래프, 벡터 맵, 랭퓨즈 탭 간 전환 지원

지식 그래프 모드: Neo4j 기반 시각화 인터페이스

채팅창 모드: AI 대화 인터페이스

랭그래프(LangGraph) 뷰: AI 워크플로우 실시간 시각화

벡터 맵(Vector Map) 뷰: 개인 지식 벡터 공간 분포도

랭퓨즈(LangFuse) 대시보드: 모델 분석 및 모니터링

우측 패널 (Status)

워커(Worker) 연결 상태 실시간 표시

현재 할당된 AI 모델 정보 상시 노출

진행 중인 작업에 대한 강제 중단(Abort) 버튼

시스템 상태 모니터링

2.1 로그인 및 권한 관리 (/login)

기능 명세

JWT(JSON Web Token) 기반 인증 시스템

로그인 성공 시 사용자 Role(USER/SUPER_ADMIN)에 따른 동적 메뉴 렌더링

토큰 만료 시 자동 로그아웃 및 리다이렉트

UI/UX 설계

심플한 다크 모드 카드 UI

아이디/비밀번호 입력 폼

로그인 상태 유지 옵션

에러 메시지 표시 영역

2.2 도메인 사령부 (메인 채팅 & 그래프)

도메인 선택 인터페이스

상단 드롭다운으로 현재 프로젝트(repo_root) 선택 및 전환

신규 프로젝트(도메인) 생성 및 경로 설정 기능 (관리자 전용)

도메인 변경 시 관련 데이터 자동 갱신

지식 그래프 인터페이스

Neo4j 기반 시각화 (react-force-graph 활용)

노드 클릭 시 컬럼명/엔터티명도 선택하여 프롬프트에 자동 입력

노드 클릭 시 해당 파일 경로 클립보드 복사 기능

그래프 확대/축소/이동 등 인터랙션 지원

랭그래프(LangGraph) 뷰

AI의 실시간 생각 과정(Node) 시각화

워크플로우 분기점 및 진행 상태 표시

각 단계별 상세 정보 툴팁 제공

벡터 맵(Vector Map) 뷰

개인 지식/메모의 벡터 공간 3D/2D 분포도 시각화

유사도 기반 클러스터링 표현

데이터 포인트 호버 시 상세 내용 확인

랭퓨즈(LangFuse) 대시보드

모델별 비용, 응답속도, 품질 지표 통합 분석

사용자 피드백 트렌드 시각화

성능 비교 및 최적화 인사이트 제공

명령 채팅 인터페이스

말풍선 형태의 대화 UI

사용자 질문과 AI 응답 시각적 구분

답변 하단에 [작업 로그 보기] 버튼 배치

실시간 타이핑 인디케이터

로그 콘솔 인터페이스

하단 슬라이딩 업 창 형태

실시간 주요 실행 단계(Summary) 출력

로그 레벨별 색상 구분 (INFO, WARN, ERROR 등)

2.3 Super Admin 제어판 (/admin)

Agent Config 관리

도메인별 YAML 설정 파일 편집기

AI 모델(Claude, Gemini 등) 고정 할당 설정

신규 프로젝트(도메인) 생성 및 경로 설정 기능

설정 적용/취소/저장 기능

User/Quota Control

사용자 목록 및 현재 활동 상태 표시

사용량 모니터링 (API Call, Storage 등)

사용자별 제한(Quota) 설정 및 조정

Audit Viewer

시스템 전체에서 생성된 TASK.md 및 결과 문서 실시간 열람

Read-only 모드로 안전성 확보

문서 검색 및 필터링 기능

2.4 개인 지식 관리 시스템

지식 등록 인터페이스

아이템 정보/메모 업로드(Uplaod/Paste) 전용 UI

텍스트, 파일, URL等多种 형식 지원

태그 기반 분류 및 검색 기능

도메인별 전용 모듈

블로그 관리 도메인: 포스팅 현황판, 예약 목록 위젯

프로젝트 유형에 따른 맞춤형 대시보드 중앙 상단 노출

컨텍스트 감지 자동 위젯 표시



myllm/frontend/

├── src/

│ ├── app/ # Next.js App Router

│ │ ├── (auth)/

│ │ │ └── login/ # 로그인 페이지

│ │ ├── (main)/

│ │ │ └── chat/ # 메인 채팅 및 그래프 페이지

│ │ └── (admin)/

│ │ └── dashboard/ # 슈퍼 어드민 대시보드

│ ├── components/

│ │ ├── graph/ # 지식 그래프 관련 컴포넌트

│ │ ├── langgraph/ # 랭그래프 시각화 컴포넌트

│ │ ├── vectormap/ # 벡터 맵 시각화 컴포넌트

│ │ ├── langfuse/ # 랭퓨즈 대시보드 컴포넌트

│ │ ├── chat/ # 채팅창 및 관련 UI 컴포넌트

│ │ └── shared/ # 공통 UI 컴포넌트

│ │ ├── sidebar/ # 사이드바 네비게이션

│ │ ├── status-card/ # 상태 표시 카드

│ │ ├── knowledge-mgr/ # 개인 지식 관리 컴포넌트

│ │ └── layout/ # 레이아웃 컴포넌트

│ ├── store/ # 상태 관리 (Zustand)

│ │ ├── useAuthStore.ts # 유저 정보 및 JWT 토큰 관리

│ │ ├── useDomainStore.ts # 현재 선택된 도메인 및 대화 히스토리

│ │ └── useKnowledgeStore.ts # 개인 지식 데이터 관리

│ ├── hooks/ # 커스텀 훅

│ │ ├── usePolling.ts # Job 상태 주기적 체크 로직

│ │ ├── useWorker.ts # 워커 상태 모니터링 로직

│ │ └── useAbortTask.ts # 작업 강제 중단 훅

│ └── lib/

│ └── axios-config.ts # Axios 인스턴스 및 JWT Interceptor 설정

├── public/ # 정적 리소스

└── package.json # 의존성 관리

실시간 제어 기능

작업 강제 중단(Kill Switch): 무한 루프 등 비상 상황 즉시 대응

노드 인터랙션: 그래프 노드 클릭 시 컨텍스트 자동 입력

다중 뷰 전환: 4가지 시각화 모드 간 seamless 전환

개인 지식 워크플로우

지식 등록: Upload/Paste 인터페이스 통해 데이터 입력

벡터화: 자동 벡터 변환 및 저장

시각화: 벡터 맵에서 공간적 관계 확인

활용: 채팅에서 관련 지식 컨텍스트로 활용

관리자 특권 기능

도메인 생성: 새 프로젝트 환경 즉시 구축

실시간 모니터링: 랭퓨즈 대시보드 통해 전 시스템 감시

긴급 조치: 작업 중단으로 시스템 보호

📊 개발 진척 현황

완료된 Phase

✅ Phase 1-4: Backend, Worker, Integration 완료

✅ Phase 5: Frontend Planning 및 명세서 확정 (보완 완료)

다음 단계: Phase 5-1

목표: Next.js 스캐폴딩 및 로그인 구현

접근 방식: AS-IS → TO-BE 형태로 점진적 개발

우선 순위: Layout 기반 → Login 로직 순차 구현