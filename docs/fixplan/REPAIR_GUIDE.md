# 🛠️ BUJA v5.0 Frontend Repair Guide (Precision Surgery Map)

본 문서는 '수석 감사관'의 감사 결과에 따라 발견된 **3대 치명적 결함**을 즉시 수정하기 위한 정밀 수술 지침서입니다.

---

## 1. 🔌 채팅창 단일 파일 첨부 기능 복구 (Broken Wire)

**진단**: `ChatInterface.tsx` 내 `Paperclip` 아이콘이 이벤트 핸들러 없이 껍데기만 존재함.
**목표**: 단일 파일 업로드 API (`/files/upload`) 연동 및 UI 피드백 구현.

### 📍 Target: `frontend/src/components/chat/ChatInterface.tsx`

#### [Step 1] State & Ref 추가
```typescript
// [Insert at Line 201]
const fileInputRef = useRef<HTMLInputElement>(null);
const [isUploading, setIsUploading] = useState(false);
```

#### [Step 2] `handleFileUpload` 함수 구현
```typescript
// [Insert at Line 248]
const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    const formData = new FormData();
    formData.append('file', file);
    formData.append('project_id', projectId || 'system-master');

    setIsUploading(true);
    try {
        const response = await api.post('/files/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });
        
        // UI Feedback (System Message)
        setMessages(prev => [...prev, {
            id: Date.now().toString(),
            role: 'assistant',
            content: `📎 **File Uploaded**: \`${file.name}\`\n(ID: \`${response.data.file_id}\`)`
        }]);
    } catch (err: any) {
        console.error("File upload failed", err);
        setMessages(prev => [...prev, {
            id: Date.now().toString(),
            role: 'assistant',
            content: `❌ **Upload Failed**: ${err.response?.data?.detail || err.message}`
        }]);
    } finally {
        setIsUploading(false);
        if (e.target) e.target.value = '';
    }
};
```

#### [Step 3] JSX 배선 (Wiring)
```typescript
// [Replace Lines 763-765]
<input
    type="file"
    ref={fileInputRef}
    onChange={handleFileUpload}
    className="hidden"
/>
<button 
    onClick={() => fileInputRef.current?.click()}
    disabled={isUploading}
    className={`p-2.5 text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 rounded-xl transition-colors flex-shrink-0 ${isUploading ? 'animate-pulse opacity-50' : ''}`}
>
    <Paperclip size={20} />
</button>
```

---

## 2. 🧭 사이드바 전면 개편 (Legacy Menu Removal)

**진단**: `Sidebar.tsx`에 구버전 'Resources' (LangGraph, Knowledge Graph, Vector DB) 메뉴가 하드코딩되어 있음. 정작 중요한 '대화방 목록(Chat Sessions)'이 없음.
**목표**: 레거시 메뉴 제거 및 `ChatHistoryList` 컴포넌트 주입.

### 📍 Target: `frontend/src/components/layout/Sidebar.tsx`

#### [Step 1] `ChatHistoryList` 컴포넌트 준비 (Inline or Import)
*편의상 `Sidebar.tsx` 내부에 인라인으로 구현하거나 별도 파일로 분리.*

```typescript
// [Insert Logic inside Sidebar component]
const [threads, setThreads] = useState<any[]>([]);

useEffect(() => {
    if (currentProjectId) {
        // Fetch threads for project
        api.get(`/projects/${currentProjectId}/threads`).then(res => setThreads(res.data)).catch(console.error);
    }
}, [currentProjectId]);
```

#### [Step 2] Legacy Menu 제거 및 Session List 주입
```typescript
// [Replace Lines 115-145 (Resources Section)]
{currentProjectId && (
    <div className="mb-6">
        <div className="px-3 mb-2 flex items-center justify-between">
            <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">Chat Sessions</span>
        </div>
        <div className="space-y-1 max-h-60 overflow-y-auto scrollbar-thin scrollbar-thumb-zinc-800">
            {threads.map(thread => (
                <Link
                    key={thread.id}
                    href={`/chat?projectId=${currentProjectId}&threadId=${thread.id}`}
                    className={`block px-3 py-2 rounded-lg text-sm truncate ${searchParams.get('threadId') === thread.id ? 'bg-zinc-800 text-white' : 'text-zinc-400 hover:text-white'}`}
                >
                    {thread.title || "New Conversation"}
                </Link>
            ))}
        </div>
    </div>
)}
```

---

## 3. 🛡️ GNB/Sidebar 권한 필터링 (Security Patch)

**진단**: `Sidebar.tsx` 및 `ProjectsPage`에서 관리자 전용 메뉴(Master Butler, System Settings)가 일반 유저에게도 노출됨.
**목표**: `user.role === 'super_admin'` 체크 로직 추가.

### 📍 Target: `frontend/src/components/layout/Sidebar.tsx`

#### [Step 1] System Menu 권한 가드
```typescript
// [Modify Lines 147-162]
{user?.role === 'super_admin' && (
    <div>
        <div className="px-3 mb-2">
            <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">System Admin</span>
        </div>
        <nav className="space-y-1">
            <Link
                href="/master-settings"
                className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-all text-sm font-medium ${isActive('/master-settings')}`}
            >
                <Shield size={18} />
                Master Butler
            </Link>
            {/* Add Graph/Vector links here ONLY for Admin if needed for debugging */}
        </nav>
    </div>
)}
```

### 📍 Target: `frontend/src/app/projects/page.tsx`

#### [Step 2] Command Center 권한 가드
```typescript
// [Wrap Lines 43-75]
{user?.role === 'super_admin' && (
    <div className="mb-12">
        {/* ... Master Butler Card Content ... */}
    </div>
)}
```

---

## 4. 🚨 추가 발견된 잠재 결함 (Bonus Audit)

### 4.1. `ChatInterface.tsx`의 `handleSend` 중복 호출 위험
- **진단**: `handleSend` 함수 내에서 `loading` 상태를 체크하지만, 비동기 처리 중 엔터키 연타 시 중복 전송 가능성 존재.
- **처방**: `isComposing` (IME 입력 중 상태) 체크 로직 추가 필요. (한글 입력 시 엔터 두 번 눌리는 현상 방지)

```typescript
// ChatInterface.tsx Line 787
onKeyDown={(e) => {
    if (e.nativeEvent.isComposing) return; // [Fix] IME 중복 전송 방지
    // ... existing logic
}}
```
