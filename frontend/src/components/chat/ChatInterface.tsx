'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Send, Paperclip, FileText, Bot, User as UserIcon, Loader2, Zap, AtSign, Search } from 'lucide-react';
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
}

interface ChatInterfaceProps {
    projectId?: string;
    threadId?: string;
}

export default function ChatInterface({ projectId: propProjectId, threadId }: ChatInterfaceProps) {
    const { currentProjectId, setCurrentProjectId, projects, setProjects } = useProjectStore();
    const projectId = propProjectId || currentProjectId;
    
    const [input, setInput] = useState('');
    const [messages, setMessages] = useState<Message[]>([]);
    const [loading, setLoading] = useState(false);
    const [showLogs, setShowLogs] = useState(false);
    const [taskStarted, setTaskStarted] = useState(false);
    const [logs, setLogs] = useState<string[]>([]);
    const [socket, setSocket] = useState<WebSocket | null>(null);

    // WebSocket for real-time logs
    useEffect(() => {
        if (taskStarted && projectId && !socket) {
            const currentHostname = (window.location.hostname === 'localhost' || window.location.hostname === '0.0.0.0') 
                ? '127.0.0.1' 
                : window.location.hostname;
            const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${wsProtocol}//${currentHostname}:8002/api/v1/orchestration/ws/${projectId}`;
            
            console.log(`DEBUG: Connecting to WebSocket: ${wsUrl}`);
            const newSocket = new WebSocket(wsUrl);

            newSocket.onopen = () => {
                console.log("DEBUG: WebSocket Connected");
                setLogs(prev => [...prev, "📡 실시간 로그 연결 성공"]);
            };

            newSocket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    console.log("DEBUG: WS Message", data);
                    if (data.data?.message) {
                        setLogs(prev => [...prev, data.data.message]);
                    }
                    if (data.type === 'WORKFLOW_FINISHED' || data.type === 'WORKFLOW_FAILED') {
                        // [Fix] Unlock UI to allow re-triggering START TASK after finish or failure
                        setTaskStarted(false);
                        setReadyToStart(false);
                        console.log(`DEBUG: Workflow ${data.type} - UI Unlocked`);
                    }
                } catch (e) {
                    console.error("Failed to parse WS message", e);
                    setLogs(prev => [...prev, event.data]);
                }
            };

            newSocket.onclose = () => {
                console.log("DEBUG: WebSocket Disconnected");
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
    
    // START TASK Gate State
    const [readyToStart, setReadyToStart] = useState(false);
    const [finalSummary, setFinalSummary] = useState('');
    
    // Mention State
    const [showMentions, setShowMentions] = useState(false);
    const [mentionSearch, setMentionSearch] = useState('');
    const [cursorPos, setCursorPos] = useState(0);
    
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const currentDomain = useDomainStore((state) => state.currentDomain);
    const activeProject = projects.find(p => p.id === projectId);

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

    // Fetch history AND projects on mount
    useEffect(() => {
        const initChat = async () => {
            if (projectId) {
                // [Fix] 화면 전환 시 메시지가 깜빡이며 사라지는 것을 방지하기 위해 
                // 즉시 초기화하지 않고 데이터 로딩 후 교체합니다.
                setReadyToStart(false); 
                setFinalSummary('');
                fetchHistory(20);
            }
            // If projects list is empty, fetch it to enable mentions
            if (projects.length === 0) {
                try {
                    const response = await api.get('/projects/');
                    setProjects(response.data);
                } catch (err) {
                    console.error("Failed to sync projects for mentions", err);
                }
            }
        };
        initChat();
    }, [projectId, threadId, projects.length]); // Added projects.length as dependency to trigger if empty

    const fetchHistory = async (currentLimit: number) => {
        if (!projectId) return;
        try {
            console.log(`DEBUG: Fetching global history for project=${projectId}, limit=${currentLimit}`);
            // [Fix] thread_id를 보내지 않고 프로젝트 ID 기반의 전체 타임라인을 요청함
            const params: any = { limit: currentLimit };
            
            const response = await api.get(`/projects/${projectId}/chat-history`, { params });
            console.log(`DEBUG: History received: ${response.data.length} messages`);
            
            const historyMessages: Message[] = response.data.map((msg: any) => ({
                id: msg.id || Math.random().toString(),
                role: msg.role,
                content: msg.content,
                timestamp: msg.created_at,
                thread_id: msg.thread_id
            }));
            
            setMessages(historyMessages);
            setHasMore(response.data.length === currentLimit);
        } catch (error: any) {
            console.error("Failed to fetch chat history", error);
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
            thread_id: threadId 
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
                        thread_id: threadId
                    })
                });

                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

                const reader = response.body?.getReader();
                const decoder = new TextDecoder();
                
                let accumulatedContent = '';
                const aiMsgId = (Date.now() + 1).toString();
                
                // Initialize assistant message
                const aiMsg: Message = {
                    id: aiMsgId,
                    role: 'assistant',
                    content: '',
                    hasLogs: false,
                    thread_id: threadId
                };
                setMessages(prev => [...prev, aiMsg]);

                if (reader) {
                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;
                        
                        const chunk = decoder.decode(value, { stream: true });
                        
                        // [TODO 8] Frontend 2차 안전망: Tool 토큰 필터링
                        // ASCII 및 유니코드 변형 포함 필터링
                        const filteredChunk = chunk.replace(/<[|｜]tool[▁_]calls[▁_]begin[|｜]>|<[|｜]tool[▁_]calls[▁_]end[|｜]>|<[|｜]tool[▁_]result[▁_]begin[|｜]>|<[|｜]tool[▁_]result[▁_]end[|｜]>/g, '');
                        
                        accumulatedContent += filteredChunk;
                        
                        // [Fix] 정규식 강화: 공백, 줄바꿈, 따옴표 종류에 유연하게 대응
                        const jsonMatch = accumulatedContent.match(/\{[\s\S]*?"status"\s*:\s*"READY_TO_START"[\s\S]*?\}/);
                        if (jsonMatch) {
                            try {
                                console.log("DEBUG: READY_TO_START detected!");
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

    const filteredProjects = projects.filter(p => 
        p.name.toLowerCase().includes(mentionSearch.toLowerCase())
    );

    return (
        <div className="flex flex-col h-full relative bg-zinc-950 text-white overflow-hidden">
            {/* Header / Project Badge */}
            <div className="px-4 py-2 border-b border-zinc-800 bg-zinc-900/30 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${projectId ? 'bg-indigo-500 animate-pulse' : 'bg-zinc-600'}`}></div>
                    <span className="text-xs font-bold text-zinc-400 uppercase tracking-widest">
                        Context: {activeProject?.name || 'Global System'}
                    </span>
                    {threadId && (
                        <span className="text-[10px] bg-zinc-800 px-2 py-0.5 rounded text-zinc-500 font-mono">
                            Thread: {threadId}
                        </span>
                    )}
                </div>
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
                                <div className={`w-8 h-8 rounded-lg flex-shrink-0 flex items-center justify-center ${
                                    msg.role === 'user' ? 'bg-indigo-600' : 'bg-zinc-800 border border-zinc-700'
                                }`}>
                                    {msg.role === 'user' ? <UserIcon size={16} /> : <Bot size={16} className="text-indigo-400" />}
                                </div>
                                <div className={`rounded-2xl px-4 py-2.5 ${
                                    msg.role === 'user'
                                        ? 'bg-indigo-600/10 text-zinc-100 border border-indigo-500/30'
                                        : 'bg-zinc-900 text-zinc-300 border border-zinc-800 shadow-sm'
                                }`}>
                                    <div className="whitespace-pre-wrap text-sm leading-relaxed">
                                        {/* [Fix] 렌더링 시 JSON 신호를 숨깁니다. */}
                                        {msg.role === 'assistant' 
                                            ? msg.content.replace(/\{[\s\S]*?"status"\s*:\s*"READY_TO_START"[\s\S]*?\}/, '').trim() || "설정이 완료되었습니다. 아래 [START TASK] 버튼을 눌러 작업을 시작해 주세요."
                                            : msg.content
                                        }
                                    </div>
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
                    <div className="relative flex items-end gap-2 rounded-2xl border border-zinc-800 bg-zinc-900/30 p-2 shadow-inner focus-within:border-indigo-500/50 focus-within:ring-1 focus-within:ring-indigo-500/20 transition-all">
                        <button className="p-2.5 text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 rounded-xl transition-colors flex-shrink-0">
                            <Paperclip size={20} />
                        </button>

                        <textarea
                            ref={inputRef}
                            value={input}
                            onChange={handleInput}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' && !e.shiftKey) {
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
