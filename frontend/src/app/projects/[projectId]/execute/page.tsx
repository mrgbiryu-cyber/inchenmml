'use client';

import React, { useEffect, useState, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import api from '@/lib/axios-config';
import { ProjectAgentConfig } from '@/types/project';
import WorkflowVisualizer from '@/components/workflow/WorkflowVisualizer';
import GitDiffViewer from '@/components/workflow/GitDiffViewer';

export default function ExecutionPage() {
    const params = useParams();
    const router = useRouter();
    const projectId = params.projectId as string;

    const [config, setConfig] = useState<ProjectAgentConfig | undefined>(undefined);
    const [status, setStatus] = useState<string>('IDLE');
    const [activeAgent, setActiveAgent] = useState<string | undefined>(undefined);
    const [logs, setLogs] = useState<string[]>([]);
    const [executionId, setExecutionId] = useState<string | null>(null);
    const [gitDiff, setGitDiff] = useState<string>('');
    const [filesModified, setFilesModified] = useState<string[]>([]);

    const wsRef = useRef<WebSocket | null>(null);

    useEffect(() => {
        if (projectId) {
            fetchConfig();
            connectWebSocket();
        }
        return () => {
            if (wsRef.current) wsRef.current.close();
        };
    }, [projectId]);

    const fetchConfig = async () => {
        try {
            const response = await api.get(`/projects/${projectId}/agents`);
            setConfig(response.data);
        } catch (error) {
            console.error("Failed to fetch agent config", error);
        }
    };

    const connectWebSocket = () => {
        const host = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
        const wsUrl = `ws://${host}:8002/api/v1/orchestration/ws/${projectId}`;
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log("Connected to WebSocket");
            addLog("🔌 Connected to orchestration server");
        };

        ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                handleWebSocketMessage(message);
            } catch (e) {
                console.error("Failed to parse WS message", e);
            }
        };

        ws.onclose = () => {
            console.log("Disconnected from WebSocket");
            addLog("🔌 Disconnected from orchestration server");
        };

        wsRef.current = ws;
    };

    const handleWebSocketMessage = (message: any) => {
        const { type, data, timestamp } = message;

        switch (type) {
            case 'WORKFLOW_STARTED':
                setStatus('RUNNING');
                addLog("🚀 Workflow started");
                break;
            case 'AGENT_STARTED':
                setActiveAgent(data.agent_id);
                addLog(`🔄 Agent ${data.agent_id} (${data.role}) started`);
                break;
            case 'JOB_CREATED':
                addLog(`   📝 Job created: ${data.job_id}`);
                break;
            case 'AGENT_COMPLETED':
                addLog(`✅ Agent ${data.agent_id} completed`);
                if (data.output?.diff) {
                    setGitDiff(data.output.diff);
                    setFilesModified(data.output.files_modified || []);
                }
                break;
            case 'AGENT_FAILED':
                addLog(`❌ Agent ${data.agent_id} failed: ${data.error}`);
                break;
            case 'WORKFLOW_COMPLETED':
                setStatus('COMPLETED');
                setActiveAgent(undefined);
                addLog("🎉 Workflow execution finished successfully");
                break;
            case 'WORKFLOW_FAILED':
                setStatus('FAILED');
                setActiveAgent(undefined);
                addLog(`❌ Workflow failed: ${data.error}`);
                break;
            default:
                console.log("Unknown message type:", type);
        }
    };

    const handleStartExecution = async () => {
        try {
            setLogs([]); // Clear logs
            setGitDiff('');
            setFilesModified([]);
            addLog("🚀 Requesting execution...");
            const response = await api.post(`/projects/${projectId}/execute`);
            setExecutionId(response.data.execution_id);
        } catch (error) {
            console.error("Failed to start execution", error);
            addLog("❌ Failed to start execution request");
        }
    };

    const addLog = (message: string) => {
        setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${message}`]);
    };

    return (
        <div className="h-full flex flex-col space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-2xl font-bold">Workflow Execution</h1>
                    <p className="text-zinc-400">Monitor your agent workflow in real-time.</p>
                </div>
                <div className="flex space-x-3">
                    <button
                        onClick={() => router.back()}
                        className="px-4 py-2 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded transition-colors"
                    >
                        Back
                    </button>
                    {status === 'IDLE' && (
                        <button
                            onClick={handleStartExecution}
                            className="px-6 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg font-bold transition-colors shadow-lg shadow-green-900/20"
                        >
                            Start Execution
                        </button>
                    )}
                    {status === 'RUNNING' && (
                        <div className="px-6 py-2 bg-zinc-800 text-green-400 rounded-lg font-bold border border-green-900/50 flex items-center">
                            <span className="w-2 h-2 bg-green-500 rounded-full mr-2 animate-pulse"></span>
                            Running...
                        </div>
                    )}
                    {status === 'COMPLETED' && (
                        <div className="px-6 py-2 bg-zinc-800 text-blue-400 rounded-lg font-bold border border-blue-900/50">
                            Completed
                        </div>
                    )}
                    {status === 'FAILED' && (
                        <div className="px-6 py-2 bg-zinc-800 text-red-400 rounded-lg font-bold border border-red-900/50">
                            Failed
                        </div>
                    )}
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 min-h-0">
                {/* Visualizer */}
                <div className="lg:col-span-2 bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden flex flex-col">
                    <div className="p-4 border-b border-zinc-800 font-semibold">Workflow Visualization</div>
                    <div className="flex-1">
                        <WorkflowVisualizer
                            initialConfig={config}
                            activeNodeId={activeAgent}
                            readOnly={true}
                        />
                    </div>
                    {/* Git Diff Viewer (Bottom of Visualizer) */}
                    {gitDiff && (
                        <div className="h-64 border-t border-zinc-800">
                            <GitDiffViewer diff={gitDiff} filesModified={filesModified} />
                        </div>
                    )}
                </div>

                {/* Logs */}
                <div className="bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden flex flex-col">
                    <div className="p-4 border-b border-zinc-800 font-semibold bg-zinc-900">Execution Logs</div>
                    <div className="flex-1 p-4 overflow-y-auto font-mono text-sm space-y-2">
                        {logs.length === 0 ? (
                            <div className="text-zinc-600 italic">Waiting for execution to start...</div>
                        ) : (
                            logs.map((log, i) => (
                                <div key={i} className="text-zinc-300 border-b border-zinc-900/50 pb-1 last:border-0">
                                    {log}
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
