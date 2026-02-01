'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Send, Paperclip, FileText, Bot, User as UserIcon, Loader2, Zap, AtSign, Search, ExternalLink, FolderUp } from 'lucide-react';
import { useRouter } from 'next/navigation'; // [v4.2] Use Next.js router for proper state sync
import api from '@/lib/axios-config';
import LogConsole from '@/components/chat/LogConsole';
import { useDomainStore } from '@/store/useDomainStore';
import { useProjectStore } from '@/store/projectStore';
import { useAuthStore } from '@/store/useAuthStore';

interface Message {
    id: string;
    role: 'user' | 'assistant' | 'system';
    content: string;
    hasLogs?: boolean;
    timestamp?: string;
    thread_id?: string;
    request_id?: string; // [v4.2] 검증용 Request ID
}

// [v4.0] Conversation Modes
type ConversationMode = 'NATURAL' | 'REQUIREMENT' | 'FUNCTION';

const MODE_CONFIG = {
    NATURAL: { label: '자유대화', color: 'indigo', border: 'border-indigo-500', bg: 'bg-indigo-500', text: 'text-indigo-500' },
    REQUIREMENT: { label: '기획대화', color: 'emerald', border: 'border-emerald-500', bg: 'bg-emerald-500', text: 'text-emerald-500' },
    FUNCTION: { label: '기능대화', color: 'violet', border: 'border-violet-500', bg: 'bg-violet-500', text: 'text-violet-500' },
};

interface ChatInterfaceProps {
    projectId?: string;
    threadId?: string;
}

// [v4.2 UX] MessageAuditBar Component for Lazy Loading Stats
function MessageAuditBar({ requestId, projectId, onTabChange }: { requestId: string, projectId?: string, onTabChange: (tab: string, reqId: string, nodeId?: string) => void }) {
    const [stats, setStats] = useState<{ topScore: number | string, chunkCount: number, nodeCount: number | string, topNodeId?: string } | null>(null);
    const [loading, setLoading] = useState(true);
    const { token } = useAuthStore();

    useEffect(() => {
        let isMounted = true;
        let retryCount = 0;
        
        const fetchStats = async () => {
            try {
                // Use Query Param
                const response = await api.get(`/master/chat_debug`, {
                    params: { request_id: requestId },
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                
                // [v5.0] Retry logic for 404 Race Condition
                // If 200 but empty/null, it might be partial. But if 404, axios throws.
                const chunks = response.data.debug_info.retrieval.chunks || [];
                const topScore = chunks.length > 0 ? Math.max(...chunks.map((c: any) => c.score)).toFixed(4) : '-';
                const topNodeId = chunks.length > 0 ? chunks[0].node_id : undefined; // [v5.0] Top chunk's node_id

                // [v5.0 DEBUG] Log node_id extraction
                if (chunks.length > 0) {
                    console.log(`[v5.0 MessageAuditBar] Top chunk node_id: ${topNodeId}, title: ${chunks[0].title?.substring(0, 30)}`);
                }

                if (isMounted) {
                    setStats({
                        topScore,
                        chunkCount: chunks.length,
                        nodeCount: '-',
                        topNodeId
                    });
                    setLoading(false);
                }
            } catch (err: any) {
                // [v5.0] Retry if 404 (Data might be syncing)
                if (err.response?.status === 404 && retryCount < 2) {
                    retryCount++;
                    setTimeout(fetchStats, 1500); // Wait 1.5s and retry
                } else {
                    if (isMounted) {
                        setStats(null);
                        setLoading(false);
                    }
                }
            }
        };
        
        // Initial delay to allow backend to persist
        setTimeout(fetchStats, 1000);
        
        return () => { isMounted = false; };
    }, [requestId, token]);

    if (loading) return <div className="mt-2 pt-2 border-t border-zinc-800/50 text-[10px] text-zinc-600 animate-pulse">Verifying sources...</div>;
    if (!stats) return null; // Hide if no data or error

    return (
        <div className="mt-2 pt-2 border-t border-zinc-800/50 flex items-center gap-3 text-[10px] font-mono text-zinc-500 whitespace-nowrap overflow-hidden text-ellipsis">
            <span className="uppercase tracking-wider font-bold text-zinc-600">출처</span>
            <span>·</span>
            <span title={`Top Similarity Score: ${stats.topScore}`}>Top1 {stats.topScore}</span>
            <span>·</span>
            <span title={`Retrieved Chunks: ${stats.chunkCount}`}>Chunks {stats.chunkCount}</span>
            <span>·</span>
            <span title="Graph Nodes Linked">Nodes {stats.nodeCount}</span>

            <button
                onClick={() => {
                    console.log(`[v5.0 Vector Button] Navigating with nodeId: ${stats.topNodeId}`);
                    onTabChange('vector', requestId, stats.topNodeId);
                }}
                className="ml-2 text-indigo-400 hover:text-indigo-300 hover:underline"
                title={stats.topNodeId ? `Navigate to node: ${stats.topNodeId}` : 'View vector map'}
            >
                [Vector]
            </button>
            <button
                onClick={() => {
                    console.log(`[v5.0 Graph Button] Navigating with nodeId: ${stats.topNodeId}`);
                    onTabChange('graph', requestId, stats.topNodeId);
                }}
                className="text-emerald-400 hover:text-emerald-300 hover:underline"
                title={stats.topNodeId ? `Navigate to node: ${stats.topNodeId}` : 'View knowledge graph'}
            >
                [Graph]
            </button>
        </div>
    );
}

export default function ChatInterface({ projectId: propProjectId, threadId }: ChatInterfaceProps) {
    const { currentProjectId, setCurrentProjectId, projects, setProjects } = useProjectStore();
    const { user } = useAuthStore(); // [v4.2] Admin check
    const projectId = propProjectId || currentProjectId;

    // [v4.2] Router for tab switching
    const router = useRouter();

    const [input, setInput] = useState('');
    const [messages, setMessages] = useState<Message[]>([]);
    const [loading, setLoading] = useState(false);
    const [showLogs, setShowLogs] = useState(false);
    const [taskStarted, setTaskStarted] = useState(false);
    const [logs, setLogs] = useState<string[]>([]);
    const [socket, setSocket] = useState<WebSocket | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [isUploading, setIsUploading] = useState(false);

    // [v5.0] Folder Upload State
    const [uploadProgress, setUploadProgress] = useState<{ processed: number, total: number } | null>(null);

    // [v4.0] Conversation Mode State
    const [mode, setMode] = useState<ConversationMode>('NATURAL');
    const [showModeMenu, setShowModeMenu] = useState(false);

    // WebSocket for real-time logs
    useEffect(() => {
        if (taskStarted && projectId && !socket) {
            const currentHostname = (window.location.hostname === 'localhost' || window.location.hostname === '0.0.0.0')
                ? '127.0.0.1'
                : window.location.hostname;
            const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${wsProtocol}//${currentHostname}:8002/api/v1/orchestration/ws/${projectId}`;

            // console.log(`DEBUG: Connecting to WebSocket: ${wsUrl}`);
            const newSocket = new WebSocket(wsUrl);

            newSocket.onopen = () => {
                // console.log("DEBUG: WebSocket Connected");
                setLogs(prev => [...prev, "📡 실시간 로그 연결 성공"]);
            };

            newSocket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    // console.log("DEBUG: WS Message", data);
                    if (data.data?.message) {
                        setLogs(prev => [...prev, data.data.message]);
                    }
                    if (data.type === 'WORKFLOW_FINISHED' || data.type === 'WORKFLOW_FAILED') {
                        // [Fix] Unlock UI to allow re-triggering START TASK after finish or failure
                        setTaskStarted(false);
                        setReadyToStart(false);
                        // console.log(`DEBUG: Workflow ${data.type} - UI Unlocked`);
                    }
                } catch (e) {
                    console.error("Failed to parse WS message", e);
                    setLogs(prev => [...prev, event.data]);
                }
            };

            newSocket.onclose = () => {
                // console.log("DEBUG: WebSocket Disconnected");
                setSocket(null);
            };

            setSocket(newSocket);
        }

        return () => {
            if (socket) {
                socket.close();
            }
        };
    }, [taskStarted, projectId]);
    const [limit, setLimit] = useState(20);
    const [hasMore, setHasMore] = useState(true);

    // [Fix] Thread ID Management
    const [currentThreadId, setCurrentThreadId] = useState<string | undefined>(threadId);

    useEffect(() => {
        if (threadId) {
            setCurrentThreadId(threadId);
        }
    }, [threadId]);

    // START TASK Gate State
    const [readyToStart, setReadyToStart] = useState(false);
    const [finalSummary, setFinalSummary] = useState('');

    // Mention State
    const [showMentions, setShowMentions] = useState(false);
    const [mentionSearch, setMentionSearch] = useState('');
    const [cursorPos, setCursorPos] = useState(0);

    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const folderInputRef = useRef<HTMLInputElement>(null); // [v5.0] Folder Upload
    const currentDomain = useDomainStore((state) => state.currentDomain);
    const activeProject = projects.find(p => p.id === projectId);

    // [v5.0] Single File Upload Handler
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

    // [v5.0] Folder Upload Handler
    const handleFolderUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files || e.target.files.length === 0) return;

        const files = Array.from(e.target.files);
        const formData = new FormData();
        files.forEach(file => {
            formData.append('files', file);
        });
        formData.append('project_id', projectId || 'system-master');

        setLoading(true);
        setUploadProgress({ processed: 0, total: files.length });

        try {
            const response = await api.post('/files/upload-folder', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
                onUploadProgress: (progressEvent) => {
                    // This tracks bytes, but we want file count which is returned by server
                    // Ideally we could stream file status, but for MVP we wait for response
                }
            });
            
            const processed = response.data.processed || 0;
            const total = response.data.total || files.length;
            setUploadProgress({ processed, total });

            setMessages(prev => [...prev, {
                id: Date.now().toString(),
                role: 'assistant', // Use assistant role to be visible and distinct
                content: `📁 **Folder Upload Complete**\n- Total Files: ${total}\n- Processed: ${processed}\n- Status: Queued for Knowledge Ingestion`
            }]);
        } catch (err: any) {
            console.error("Folder upload failed", err);
            setMessages(prev => [...prev, {
                id: Date.now().toString(),
                role: 'assistant',
                content: `❌ **Folder Upload Failed**\n${err.response?.data?.detail || err.message}`
            }]);
        } finally {
            setLoading(false);
            setTimeout(() => setUploadProgress(null), 3000); // Hide after 3s
            if (e.target) e.target.value = ''; // Reset input
        }
    };

    // [Fix] 메시지 목록이 바뀔 때마다 마지막 메시지에서 READY_TO_START 신호를 찾아 버튼을 복구합니다.
    useEffect(() => {
        if (messages.length > 0) {
            const lastMsg = messages[messages.length - 1];
            if (lastMsg.role === 'assistant') {
                const jsonMatch = lastMsg.content.match(/\{[\s\S]*?"status"\s*:\s*"READY_TO_START"[\s\S]*?\}/);
                if (jsonMatch) {
                    try {
                        const signal = JSON.parse(jsonMatch[0]);
                        setReadyToStart(true);
                        setFinalSummary(signal.final_summary);
                    } catch (e) {
                        console.error("Failed to parse existing signal", e);
                    }
                }
            }
        }
    }, [messages]);

    const scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
        messagesEndRef.current?.scrollIntoView({ behavior, block: 'nearest' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    // [v5.0] State Cleanup and Initialization on Project Change
    useEffect(() => {
        const initChat = async () => {
            // Reset state on project change
            setMessages([]);
            setLogs([]);
            setReadyToStart(false);
            setUploadProgress(null);
            setHasMore(true);
            
            // If projectId changed, we must ensure threadId is valid or fetch default
            if (projectId) {
                if (!threadId) {
                    // [CRITICAL FIX] If no threadId in URL, fetch threads and auto-select first one
                    console.log("DEBUG: [Init] No threadId in URL, fetching threads...");
                    try {
                        const threadsRes = await api.get(`/projects/${projectId}/threads`);
                        console.log("DEBUG: [Init] Threads fetched:", threadsRes.data.length);
                        
                        if (threadsRes.data && threadsRes.data.length > 0) {
                            // Auto-select first thread
                            const firstThread = threadsRes.data[0];
                            console.log("DEBUG: [Init] Auto-selecting first thread:", firstThread.thread_id);
                            
                            // Update URL
                            router.replace(`?projectId=${projectId}&threadId=${firstThread.thread_id}`);
                            
                            // [CRITICAL FIX] Immediately set state and fetch history
                            setCurrentThreadId(firstThread.thread_id);
                            setReadyToStart(false);
                            setFinalSummary('');
                            
                            // Fetch history immediately
                            console.log("DEBUG: [Init] Calling fetchHistory for thread:", firstThread.thread_id);
                            await fetchHistory(20, firstThread.thread_id);
                        } else {
                            // No threads, create default
                            console.log("DEBUG: [Init] No threads found, creating default...");
                            try {
                                const newThreadRes = await api.post(`/projects/${projectId}/threads`, { title: "기본 대화방" });
                                const newThreadId = newThreadRes.data.thread_id;
                                console.log("DEBUG: [Init] Created default thread:", newThreadId);
                                
                                router.replace(`?projectId=${projectId}&threadId=${newThreadId}`);
                                setCurrentThreadId(newThreadId);
                                // Empty history for new thread
                                setMessages([]);
                            } catch (createErr) {
                                console.error("Failed to auto-create default thread", createErr);
                            }
                        }
                    } catch (e) {
                        console.warn("Failed to check threads for default redirection", e);
                    }
                } else {
                    // Have threadId, set it and fetch history
                    console.log("DEBUG: [Init] ThreadId present in URL:", threadId);
                    setCurrentThreadId(threadId);
                    setReadyToStart(false);
                    setFinalSummary('');
                    await fetchHistory(20, threadId); // Pass threadId explicitly
                }
            }
        };
        
        initChat();
    }, [projectId, threadId]);

    const fetchHistory = async (currentLimit: number, specificThreadId?: string) => {
        if (!projectId) return;
        
        // Use provided threadId or fall back to state (but state might be stale in useEffect)
        // So we prefer explicit argument
        const targetThreadId = specificThreadId || currentThreadId;
        
        if (!targetThreadId) {
            console.warn("Skipping fetchHistory: No threadId available");
            console.error("DEBUG: [Audit] Race Condition Detected - fetchHistory called without threadId. Current State:", { projectId, currentThreadId, specificThreadId });
            return;
        }

        console.log(`DEBUG: [History] Fetching messages for Thread: ${targetThreadId} in Project: ${projectId}`);
        console.log(`DEBUG: [Audit] Requesting GET /projects/${projectId}/threads/${targetThreadId}/messages`);

        try {
            // [Fix] Use dedicated thread message endpoint
            const response = await api.get(`/projects/${projectId}/threads/${targetThreadId}/messages`, { 
                params: { limit: currentLimit } 
            });

            // [Audit] Log Raw Response for Data Mapping Check
            console.log("DEBUG: [History] Raw API Response:", response.data);

            const historyMessages: Message[] = response.data.map((msg: any) => ({
                id: msg.id || Math.random().toString(),
                role: msg.role,
                content: msg.content, // [Check] Backend sends 'content', Frontend uses 'content'. OK.
                timestamp: msg.created_at,
                thread_id: msg.thread_id,
                request_id: msg.request_id // Ensure request_id is passed for audit bar
            }));

            setMessages(historyMessages);
            setHasMore(response.data.length === currentLimit);
        } catch (error: any) {
            console.error("Failed to fetch chat history", error);
            if (error.response?.status === 404) {
                console.warn("Project or Thread not found. Resetting context.");
                // Handle 404 gracefully?
            }
        }
    };

    const handleLoadMore = () => {
        const newLimit = limit + 20;
        setLimit(newLimit);
        fetchHistory(newLimit);
    };

    const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        const value = e.target.value;
        const position = e.target.selectionStart;
        setInput(value);
        setCursorPos(position);

        // Check for '@' mention
        const lastAtPos = value.lastIndexOf('@', position - 1);
        if (lastAtPos !== -1 && (lastAtPos === 0 || value[lastAtPos - 1] === ' ')) {
            const query = value.substring(lastAtPos + 1, position);
            if (!query.includes(' ')) {
                setMentionSearch(query);
                setShowMentions(true);
                return;
            }
        }
        setShowMentions(false);
    };

    const selectProjectMention = (proj: any) => {
        const lastAtPos = input.lastIndexOf('@', cursorPos - 1);
        const newValue = input.substring(0, lastAtPos) + `@${proj.name} ` + input.substring(cursorPos);
        setInput(newValue);
        setShowMentions(false);
        // We could also set a target_project_id state here
        if (inputRef.current) inputRef.current.focus();
    };

    const handleSend = async (type: 'chat' | 'job' = 'chat') => {
        if (!input.trim() && type === 'chat') return;
        if (loading) return;

        const effectiveProjectId = projectId || 'system-master';

        // Clear input for chat type
        if (type === 'chat') {
            setInput('');
            setReadyToStart(false); // Reset gate on new chat
            setTaskStarted(false);  // Reset task state
        }

        const userMsg: Message = {
            id: Date.now().toString(),
            role: 'user',
            content: type === 'job' ? '🚀 START TASK' : input,
            thread_id: currentThreadId
        };

        setMessages(prev => [...prev, userMsg]);
        setLoading(true);

        try {
            if (type === 'job') {
                // Show logs window immediately
                setTaskStarted(true);
                setShowLogs(true);
                setLogs(['Initializing workflow execution...', 'Authenticating context...']);
                setReadyToStart(false);

                try {
                    const response = await api.post(`/projects/${effectiveProjectId}/execute`);

                    const aiMsg: Message = {
                        id: (Date.now() + 1).toString(),
                        role: 'assistant',
                        content: `🚀 Workflow started for project **${activeProject?.name || effectiveProjectId}**.\nExecution ID: \`${response.data.execution_id}\`\nMonitoring real-time logs in the console.`,
                        hasLogs: true
                    };
                    setMessages(prev => [...prev, aiMsg]);
                    setLogs(prev => [...prev, `Workflow accepted by engine. Execution ID: ${response.data.execution_id}`, `Streaming real-time logs...`]);
                } catch (execError: any) {
                    console.error("Execution trigger failed", execError);
                    setLogs(prev => [...prev, `❌ FAILED: ${execError.response?.data?.detail || execError.message}`]);
                    setMessages(prev => [...prev, {
                        id: Date.now().toString(),
                        role: 'assistant',
                        content: `⚠️ 작업 시작 중 오류가 발생했습니다: ${execError.response?.data?.detail || execError.message}`
                    }]);
                }
            } else {
                // [TODO 8] Streaming Chat with Tool Call Interceptor (2nd Layer Protection)
                const token = useAuthStore.getState().token;
                if (!token) {
                    console.error("Auth token is missing!");
                    throw new Error("Authentication token is missing. Please log in again.");
                }
                const authHeader = `Bearer ${token}`;

                // Use absolute URL from axios config or fallback
                const currentHostname = (window.location.hostname === 'localhost' || window.location.hostname === '0.0.0.0')
                    ? '127.0.0.1'
                    : window.location.hostname;
                const baseURL = api.defaults.baseURL || `http://${currentHostname}:8002/api/v1`;

                const response = await fetch(`${baseURL}/master/chat-stream`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': authHeader
                    },
                    body: JSON.stringify({
                        message: userMsg.content,
                        history: messages.map(m => ({ role: m.role, content: m.content })),
                        project_id: effectiveProjectId,
                        thread_id: currentThreadId,
                        mode: mode // [v4.0] Pass current mode
                    })
                });

                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

                // [v4.2] Extract Request ID for Admin Debugging
                const requestId = response.headers.get('X-Request-Id') || undefined;
                
                // [v5.0 DEBUG] Log request_id extraction
                console.log(`[v5.0 handleSend] New message request_id: ${requestId || 'MISSING'}`);
                if (!requestId) {
                    console.warn('[v5.0 handleSend] ⚠️ X-Request-Id header not found! Check backend CORS settings.');
                }

                const reader = response.body?.getReader();
                const decoder = new TextDecoder();

                // [Fix] 스트리밍 시작 시 로딩 상태 해제 (중복 아이콘 방지)
                setLoading(false);

                let accumulatedContent = '';
                const aiMsgId = (Date.now() + 1).toString();

                // Initialize assistant message
                const aiMsg: Message = {
                    id: aiMsgId,
                    role: 'assistant',
                    content: '',
                    hasLogs: false,
                    thread_id: currentThreadId,
                    request_id: requestId // [v4.2]
                };
                setMessages(prev => [...prev, aiMsg]);

                if (reader) {
                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;

                        const chunk = decoder.decode(value, { stream: true });

                        // [TODO 8] Frontend 2차 안전망: Tool 토큰 필터링
                        // ASCII 및 유니코드 변형 포함 필터링
                        let filteredChunk = chunk.replace(/<[|｜]tool[▁_]calls[▁_]begin[|｜]>|<[|｜]tool[▁_]calls[▁_]end[|｜]>|<[|｜]tool[▁_]result[▁_]begin[|｜]>|<[|｜]tool[▁_]result[▁_]end[|｜]>/g, '');

                        // [v4.0] Handle Mode Switch Signal
                        // Format: {"type": "MODE_SWITCH", "mode": "REQUIREMENT", "reason": "..."}
                        const modeSignalMatch = filteredChunk.match(/\{"type":\s*"MODE_SWITCH"[\s\S]*?\}/);
                        if (modeSignalMatch) {
                            try {
                                const signal = JSON.parse(modeSignalMatch[0]);
                                if (signal.mode && MODE_CONFIG[signal.mode as ConversationMode]) {
                                    const newMode = signal.mode as ConversationMode;
                                    setMode(newMode);
                                    // console.log(`[Mode Switch] Auto-switched to ${signal.mode}`);
                                    // Remove signal from content
                                    filteredChunk = filteredChunk.replace(modeSignalMatch[0], '').trim();

                                    // [v5.0] Auto-Revert Logic (Visual/Functional Recovery)
                                    // If mode switched to FUNCTION, we assume it's temporary for the tool call
                                    // But if it's REQUIREMENT, it might be persistent.
                                    // For now, we ensure the UI updates immediately (setMode does this).
                                    // If we wanted to "revert" after 5 seconds, we could:
                                    /*
                                    if (newMode === 'FUNCTION') {
                                        setTimeout(() => setMode('NATURAL'), 5000);
                                    }
                                    */
                                }
                            } catch (e) {
                                console.error("Failed to parse mode signal", e);
                            }
                        }

                        accumulatedContent += filteredChunk;

                        // [Fix] 정규식 강화: 공백, 줄바꿈, 따옴표 종류에 유연하게 대응
                        const jsonMatch = accumulatedContent.match(/\{[\s\S]*?"status"\s*:\s*"READY_TO_START"[\s\S]*?\}/);
                        if (jsonMatch) {
                            try {
                                // console.log("DEBUG: READY_TO_START detected!");
                                const signal = JSON.parse(jsonMatch[0]);
                                setReadyToStart(true);
                                setFinalSummary(signal.final_summary);

                                // Update UI message (hide JSON)
                                const cleanContent = accumulatedContent.replace(jsonMatch[0], '').trim();
                                setMessages(prev => prev.map(m =>
                                    m.id === aiMsgId ? { ...m, content: cleanContent || "설정이 완료되었습니다. 아래 [START TASK] 버튼을 눌러 작업을 시작해 주세요." } : m
                                ));
                            } catch (e) {
                                // JSON이 아직 덜 받아와졌을 수 있으므로 무시하고 다음 청크 대기
                            }
                        } else {
                            setMessages(prev => prev.map(m =>
                                m.id === aiMsgId ? { ...m, content: accumulatedContent } : m
                            ));
                        }
                    }
                }
            }
        } catch (error: any) {
            console.error('Failed to send message', error);
            setMessages(prev => [...prev, {
                id: Date.now().toString(),
                role: 'assistant',
                content: `Error: ${error.response?.data?.detail || error.message}`
            }]);
        } finally {
            setLoading(false);
        }
    };

    const handleTabChange = (tab: string, reqId: string, nodeId?: string) => {
        // [v5.0] URL 파라미터 확장: nodeId 추가로 탭에서 자동 노드 선택
        const params = new URLSearchParams();
        params.set('tab', tab);
        params.set('request_id', reqId);
        if (nodeId) params.set('nodeId', nodeId);
        if (projectId) params.set('projectId', projectId);
        
        router.push(`?${params.toString()}`, { scroll: false });
    };

    const filteredProjects = projects.filter(p =>
        p.name.toLowerCase().includes(mentionSearch.toLowerCase())
    );

    return (
        <div className="flex flex-col h-dvh relative bg-zinc-950 text-white overflow-hidden">
            {/* Header / Project Badge */}
            <div className="px-4 py-2 border-b border-zinc-800 bg-zinc-900/30 flex items-center justify-between">
                {/* [v5.0] Swipe Navigation Container */}
                <div 
                    className="flex items-center gap-2 flex-1 overflow-hidden"
                    onTouchStart={(e) => {
                        const touchStart = e.targetTouches[0].clientX;
                        e.currentTarget.setAttribute('data-touch-start', touchStart.toString());
                    }}
                    onTouchEnd={(e) => {
                        const touchStart = parseFloat(e.currentTarget.getAttribute('data-touch-start') || '0');
                        const touchEnd = e.changedTouches[0].clientX;
                        const diff = touchStart - touchEnd;
                        
                        if (Math.abs(diff) > 50) { // Threshold 50px
                            const currentIndex = projects.findIndex(p => p.id === projectId);
                            if (currentIndex === -1) return;
                            
                            if (diff > 0) { // Swipe Left -> Next Project
                                const nextProject = projects[currentIndex + 1];
                                if (nextProject) router.push(`?projectId=${nextProject.id}`);
                            } else { // Swipe Right -> Prev Project
                                const prevProject = projects[currentIndex - 1];
                                if (prevProject) router.push(`?projectId=${prevProject.id}`);
                            }
                        }
                    }}
                >
                    <div className={`w-2 h-2 rounded-full ${projectId ? 'bg-indigo-500 animate-pulse' : 'bg-zinc-600'}`}></div>
                    <span className="text-xs font-bold text-zinc-400 uppercase tracking-widest flex items-center gap-2 select-none cursor-ew-resize">
                        {activeProject ? (
                            <>
                                <span className="text-indigo-400">{activeProject.name}</span>
                                <span className="text-zinc-600">/</span>
                                <span>Chat Room</span>
                            </>
                        ) : 'Global System Context'}
                    </span>
                    {threadId && (
                        <span className="text-[10px] bg-zinc-800 px-2 py-0.5 rounded text-zinc-500 font-mono ml-2">
                            #{threadId.slice(-6)}
                        </span>
                    )}
                </div>
                
                {/* [v5.0] Upload Progress Bar */}
                {uploadProgress && (
                    <div className="mr-4 flex items-center gap-2 text-[10px] font-mono text-emerald-400 animate-pulse bg-emerald-900/20 px-2 py-1 rounded">
                        <FolderUp size={12} />
                        <span>{uploadProgress.processed}/{uploadProgress.total} Files</span>
                    </div>
                )}

                {hasMore && (
                    <button
                        onClick={handleLoadMore}
                        className="text-[10px] text-zinc-500 hover:text-indigo-400 transition-colors"
                    >
                        Load Previous Messages
                    </button>
                )}
            </div>

            {/* Chat Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-6 min-h-0 scrollbar-thin scrollbar-thumb-zinc-800 scrollbar-track-transparent">
                {messages.length === 0 && !loading ? (
                    <div className="flex flex-col items-center justify-center h-full text-center space-y-6 opacity-30">
                        <Bot size={64} className="text-indigo-500" />
                        <div>
                            <h2 className="text-xl font-bold text-zinc-200">Ready to assist</h2>
                            <p className="text-sm text-zinc-500 mt-2">Mention projects with @ or start a task.</p>
                        </div>
                    </div>
                ) : (
                    messages.map((msg) => (
                        <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                            <div className={`flex gap-3 max-w-[85%] ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                                <div className={`w-8 h-8 rounded-lg flex-shrink-0 flex items-center justify-center ${msg.role === 'user' ? 'bg-indigo-600' : 'bg-zinc-800 border border-zinc-700'
                                    }`}>
                                    {msg.role === 'user' ? <UserIcon size={16} /> : <Bot size={16} className="text-indigo-400" />}
                                </div>
                                <div className={`rounded-2xl px-4 py-2.5 ${msg.role === 'user'
                                    ? 'bg-indigo-600/10 text-zinc-100 border border-indigo-500/30'
                                    : 'bg-zinc-900 text-zinc-300 border border-zinc-800 shadow-sm'
                                    }`}>
                                    <div className="whitespace-pre-wrap text-sm leading-relaxed">
                                        {/* [Fix] 렌더링 시 JSON 신호를 숨깁니다. */}
                                        {msg.role === 'assistant'
                                            ? msg.content.replace(/\{[\s\S]*?"status"\s*:\s*"READY_TO_START"[\s\S]*?\}/, '').trim()
                                            : msg.content
                                        }
                                    </div>

                                    {/* [v4.2 UX] Admin-Only Source Bar (Enhanced) */}
                                    {/* Removed !loading check to show bar immediately if request_id is present */}
                                    {msg.role === 'assistant' && user?.role === 'super_admin' && msg.request_id && (() => {
                                        // [v5.0 DEBUG] Log each message's request_id when rendering
                                        console.log(`[v5.0 MessageRender] Message ID: ${msg.id}, request_id: ${msg.request_id?.substring(0, 8)}..., content preview: ${msg.content.substring(0, 30)}...`);
                                        return (
                                            <MessageAuditBar
                                                requestId={msg.request_id}
                                                projectId={projectId}
                                                onTabChange={handleTabChange}
                                            />
                                        );
                                    })()}

                                    {msg.hasLogs && (
                                        <button
                                            onClick={() => setShowLogs(true)}
                                            className="mt-3 flex items-center gap-1.5 text-[10px] text-indigo-400 hover:text-indigo-300 font-bold uppercase bg-indigo-500/10 px-2 py-1 rounded transition-all"
                                        >
                                            <Zap size={10} />
                                            Live Execution Logs
                                        </button>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))
                )}
                {loading && (
                    <div className="flex justify-start gap-3">
                        <div className="w-8 h-8 rounded-lg bg-zinc-800 border border-zinc-700 flex items-center justify-center">
                            <Bot size={16} className="text-indigo-400" />
                        </div>
                        <div className="bg-zinc-900 rounded-2xl px-4 py-3 border border-zinc-800">
                            <Loader2 size={16} className="animate-spin text-zinc-500" />
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Mention UI */}
            {showMentions && (
                <div className="absolute bottom-24 left-4 w-64 bg-zinc-900 border border-zinc-800 rounded-xl shadow-2xl overflow-hidden z-50 animate-in slide-in-from-bottom-2">
                    <div className="p-2 border-b border-zinc-800 bg-zinc-950/50 flex items-center gap-2">
                        <AtSign size={14} className="text-indigo-500" />
                        <span className="text-[10px] font-bold text-zinc-400 uppercase">Mention Project</span>
                    </div>
                    <div className="max-h-48 overflow-y-auto">
                        {filteredProjects.length === 0 ? (
                            <div className="p-4 text-xs text-zinc-600 italic">No matches found</div>
                        ) : (
                            filteredProjects.map(proj => (
                                <button
                                    key={proj.id}
                                    onClick={() => selectProjectMention(proj)}
                                    className="w-full flex items-center gap-3 px-3 py-2 hover:bg-zinc-800 transition-colors text-left"
                                >
                                    <div className="w-2 h-2 rounded-full bg-indigo-500"></div>
                                    <div className="flex flex-col">
                                        <span className="text-sm text-zinc-200 font-medium">{proj.name}</span>
                                        <span className="text-[10px] text-zinc-500 font-mono">{proj.id}</span>
                                    </div>
                                </button>
                            ))
                        )}
                    </div>
                </div>
            )}

            {/* Input Area */}
            <div className="p-4 border-t border-zinc-800/50 bg-zinc-950">
                <div className="max-w-4xl mx-auto">
                    <div className={`relative flex items-end gap-2 rounded-2xl border bg-zinc-900/30 p-2 shadow-inner transition-all ${MODE_CONFIG[mode].border} focus-within:ring-1 focus-within:ring-opacity-20`}>
                        {/* [v4.0] Mode Switcher */}
                        <div className="relative">
                            <button
                                onClick={() => setShowModeMenu(!showModeMenu)}
                                className={`p-2.5 rounded-xl transition-colors flex-shrink-0 ${MODE_CONFIG[mode].text} hover:bg-zinc-800`}
                                title={`Current Mode: ${MODE_CONFIG[mode].label}`}
                            >
                                <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${MODE_CONFIG[mode].border}`}>
                                    <div className={`w-2.5 h-2.5 rounded-full ${MODE_CONFIG[mode].bg}`}></div>
                                </div>
                            </button>

                            {showModeMenu && (
                                <div className="absolute bottom-12 left-0 w-48 bg-zinc-900 border border-zinc-800 rounded-xl shadow-xl overflow-hidden z-50 animate-in slide-in-from-bottom-2">
                                    <div className="p-2 text-[10px] font-bold text-zinc-500 uppercase bg-zinc-950/50 border-b border-zinc-800">
                                        Select Conversation Mode
                                    </div>
                                    {Object.entries(MODE_CONFIG).map(([key, config]) => (
                                        <button
                                            key={key}
                                            onClick={() => {
                                                setMode(key as ConversationMode);
                                                setShowModeMenu(false);
                                            }}
                                            className={`w-full text-left px-4 py-3 text-sm hover:bg-zinc-800 transition-colors flex items-center gap-3 ${mode === key ? 'bg-zinc-800/50' : ''}`}
                                        >
                                            <div className={`w-3 h-3 rounded-full ${config.bg}`}></div>
                                            <span className={mode === key ? 'text-white font-medium' : 'text-zinc-400'}>
                                                {config.label}
                                            </span>
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>

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
                        
                        {/* [v5.0] Folder Upload Button */}
                        <input
                            type="file"
                            ref={folderInputRef}
                            onChange={handleFolderUpload}
                            className="hidden"
                            {...({ webkitdirectory: "", directory: "", multiple: true } as any)}
                        />
                        <button 
                            onClick={() => folderInputRef.current?.click()}
                            className="p-2.5 text-zinc-500 hover:text-indigo-400 hover:bg-zinc-800 rounded-xl transition-colors flex-shrink-0"
                            title="Upload Folder (Recursive)"
                        >
                            <FolderUp size={20} />
                        </button>

                        <textarea
                            ref={inputRef}
                            value={input}
                            onChange={handleInput}
                            onKeyDown={(e) => {
                                // [Mobile Guard] Prevent Enter submission on mobile devices
                                if (e.nativeEvent.isComposing) return; // [Fix] IME 중복 전송 방지

                                const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent) || window.innerWidth < 768;

                                if (e.key === 'Enter' && !e.shiftKey) {
                                    if (isMobile) return;
                                    e.preventDefault();
                                    handleSend('chat');
                                }
                            }}
                            placeholder={projectId ? `Chatting in context of ${activeProject?.name}...` : "Type a message or use @ to mention projects..."}
                            className="flex-1 max-h-40 min-h-[2.75rem] bg-transparent py-3 px-1 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none resize-none scrollbar-hide"
                            rows={1}
                        />

                        <div className="flex items-center gap-2 p-1">
                            <button
                                onClick={() => handleSend('chat')}
                                disabled={!input.trim() || loading}
                                className="p-2 text-zinc-500 hover:text-white hover:bg-zinc-800 rounded-xl transition-colors disabled:opacity-30"
                            >
                                <Send size={20} />
                            </button>
                        </div>
                    </div>

                    {/* Action Area for Dynamic Buttons */}
                    {(readyToStart || taskStarted) && (
                        <div className="mt-4 p-4 bg-indigo-600/10 border border-indigo-500/30 rounded-2xl flex items-center justify-between animate-in fade-in slide-in-from-bottom-2 duration-500">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-indigo-600 rounded-lg">
                                    <Zap size={18} className="text-white" />
                                </div>
                                <div className="flex flex-col">
                                    <span className="text-xs font-bold text-indigo-400 uppercase tracking-wider">
                                        {taskStarted ? "Task in Progress" : "Ready to Execute"}
                                    </span>
                                    <p className="text-sm text-zinc-300 line-clamp-1">
                                        {taskStarted ? "Execution logs are being generated." : (finalSummary || "Plan completed. Ready to start task.")}
                                    </p>
                                </div>
                            </div>
                            {taskStarted ? (
                                <button
                                    onClick={() => setShowLogs(true)}
                                    className="flex items-center gap-2 px-6 py-2.5 bg-zinc-800 text-white rounded-xl hover:bg-zinc-700 transition-all font-bold text-sm border border-zinc-700 shadow-lg"
                                >
                                    <FileText size={16} />
                                    <span>VIEW LOGS</span>
                                </button>
                            ) : (
                                <button
                                    onClick={() => handleSend('job')}
                                    disabled={loading}
                                    className="flex items-center gap-2 px-6 py-2.5 bg-indigo-600 text-white rounded-xl hover:bg-indigo-500 transition-all font-bold text-sm shadow-lg shadow-indigo-900/40"
                                >
                                    <Zap size={16} />
                                    <span>START TASK</span>
                                </button>
                            )}
                        </div>
                    )}
                </div>
            </div>

            {/* Log Console */}
            <LogConsole isOpen={showLogs} onClose={() => setShowLogs(false)} logs={logs} />
        </div>
    );
}