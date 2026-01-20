'use client';

import { useState, useEffect, useRef } from 'react';
import { ChevronUp, ChevronDown, X, Terminal } from 'lucide-react';
import clsx from 'clsx';
import api from '@/lib/axios-config';

interface LogConsoleProps {
    isOpen: boolean;
    onClose: () => void;
    jobId?: string | null;
    logs?: string[]; // Added logs prop
}

interface LogEntry {
    timestamp: string;
    level: 'INFO' | 'WARN' | 'ERROR';
    message: string;
}

export default function LogConsole({ isOpen, onClose, jobId, logs: externalLogs }: LogConsoleProps) {
    const [isExpanded, setIsExpanded] = useState(false);
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const scrollRef = useRef<HTMLDivElement>(null);

    // Sync external logs
    useEffect(() => {
        if (externalLogs) {
            const formattedLogs: LogEntry[] = externalLogs.map(msg => ({
                timestamp: new Date().toISOString(),
                level: 'INFO',
                message: msg
            }));
            setLogs(formattedLogs);
        }
    }, [externalLogs]);

    // Fetch logs (only if jobId is present and no external logs)
    useEffect(() => {
        if (!isOpen || !jobId || externalLogs) return;

        const fetchLogs = async () => {
            try {
                // Mock data
                const mockLogs: LogEntry[] = [
                    { timestamp: new Date().toISOString(), level: 'INFO', message: 'Job started' },
                    { timestamp: new Date().toISOString(), level: 'INFO', message: 'Planner agent analyzing request...' },
                    { timestamp: new Date().toISOString(), level: 'WARN', message: 'Complexity high, breaking down tasks' },
                ];
                setLogs(prev => [...prev, ...mockLogs]);
            } catch (err) {
                console.error("Failed to fetch logs", err);
            }
        };

        fetchLogs();
        const interval = setInterval(fetchLogs, 5000);
        return () => clearInterval(interval);
    }, [isOpen, jobId, externalLogs]);

    // Auto-scroll to bottom
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [logs]);

    if (!isOpen) return null;

    return (
        <div
            className={clsx(
                "absolute bottom-0 left-0 right-0 bg-zinc-900 border-t border-zinc-700 shadow-2xl transition-all duration-300 ease-in-out z-20",
                isExpanded ? "h-2/3" : "h-48"
            )}
        >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-2 bg-zinc-800 border-b border-zinc-700">
                <div className="flex items-center gap-2 text-zinc-300">
                    <Terminal size={16} />
                    <span className="text-sm font-medium">Execution Logs</span>
                    <span className="text-xs bg-zinc-700 px-2 py-0.5 rounded-full text-zinc-400">{logs.length} lines</span>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setIsExpanded(!isExpanded)}
                        className="p-1 hover:bg-zinc-700 rounded text-zinc-400 hover:text-white"
                    >
                        {isExpanded ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
                    </button>
                    <button
                        onClick={onClose}
                        className="p-1 hover:bg-zinc-700 rounded text-zinc-400 hover:text-white"
                    >
                        <X size={16} />
                    </button>
                </div>
            </div>

            {/* Log Content */}
            <div ref={scrollRef} className="h-full overflow-y-auto p-4 font-mono text-xs space-y-1 pb-12">
                {logs.length === 0 ? (
                    <div className="text-zinc-500 italic">No logs available...</div>
                ) : (
                    logs.map((log, i) => (
                        <div key={i} className="text-zinc-300 border-b border-zinc-800/50 pb-0.5 flex gap-2">
                            <span className="text-zinc-500 shrink-0">[{new Date(log.timestamp).toLocaleTimeString()}]</span>
                            <span className={clsx(
                                "font-bold shrink-0",
                                log.level === 'INFO' && "text-blue-400",
                                log.level === 'WARN' && "text-yellow-400",
                                log.level === 'ERROR' && "text-red-400"
                            )}>{log.level}</span>
                            <span>{log.message}</span>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}
