'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Send, Paperclip, FileText, Bot, User as UserIcon, Loader2, Zap, AtSign, Search } from 'lucide-react';
import api from '@/lib/axios-config';
import LogConsole from '@/components/chat/LogConsole';
import { useDomainStore } from '@/store/useDomainStore';
import { useProjectStore } from '@/store/projectStore';

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
    const [logs, setLogs] = useState<string[]>([]);
    const [limit, setLimit] = useState(20);
    const [hasMore, setHasMore] = useState(true);
    
    // Mention State
    const [showMentions, setShowMentions] = useState(false);
    const [mentionSearch, setMentionSearch] = useState('');
    const [cursorPos, setCursorPos] = useState(0);
    
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLTextAreaElement>(null);
    const currentDomain = useDomainStore((state) => state.currentDomain);

    const activeProject = projects.find(p => p.id === projectId);

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
                setMessages([]); // Reset messages when project changes
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
        try {
            const params: any = { limit: currentLimit };
            if (threadId) params.thread_id = threadId;
            
            const response = await api.get(`/projects/${projectId}/chat-history`, { params });
            
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
            if (error.response?.status === 404) {
                console.warn("Project not found in backend. Resetting context.");
                setCurrentProjectId(null);
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
        if (!input.trim() || loading) return;

        const effectiveProjectId = projectId || 'system-master';
        
        const userMsg: Message = { 
            id: Date.now().toString(), 
            role: 'user', 
            content: input,
            thread_id: threadId 
        };
        
        setMessages(prev => [...prev, userMsg]);
        setInput('');
        setLoading(true);

        try {
            if (type === 'job') {
                // 1. Check if graph exists/needs save (For now, assume it's saved)
                // 2. Start Task
                const response = await api.post(`/projects/${effectiveProjectId}/execute`);
                
                const aiMsg: Message = {
                    id: (Date.now() + 1).toString(),
                    role: 'assistant',
                    content: `🚀 Workflow started for project **${activeProject?.name || effectiveProjectId}**.\nExecution ID: \`${response.data.execution_id}\`\nMonitoring real-time logs below.`,
                    hasLogs: true
                };
                setMessages(prev => [...prev, aiMsg]);
                setLogs(prev => [...prev, `Workflow initiated`, `Checking agent configurations...`, `Connected to local worker`]);
                setShowLogs(true);
            } else {
                // Regular Chat
                const response = await api.post('/master/chat', {
                    message: userMsg.content,
                    history: messages.map(m => ({ role: m.role, content: m.content })),
                    project_id: effectiveProjectId,
                    thread_id: threadId
                });

                const aiMsg: Message = {
                    id: (Date.now() + 1).toString(),
                    role: 'assistant',
                    content: response.data.message,
                    hasLogs: false,
                    thread_id: threadId
                };
                setMessages(prev => [...prev, aiMsg]);
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
                                    <div className="whitespace-pre-wrap text-sm leading-relaxed">{msg.content}</div>
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
                            <button
                                onClick={() => handleSend('job')}
                                disabled={!input.trim() || loading || !projectId}
                                className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 text-white rounded-xl hover:bg-indigo-500 disabled:opacity-20 disabled:grayscale transition-all font-bold text-xs shadow-lg shadow-indigo-900/40"
                            >
                                <Zap size={14} />
                                <span>START TASK</span>
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            {/* Log Console */}
            <LogConsole isOpen={showLogs} onClose={() => setShowLogs(false)} logs={logs} />
        </div>
    );
}
