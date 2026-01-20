'use client';

import React, { useState, useEffect } from 'react';
import { Send, CheckCircle2, Circle, Loader2, Bot, User } from 'lucide-react';
import api from '@/lib/axios-config';
import { AgentDefinition } from '@/types/project';

interface AgentTestGroupProps {
    projectId: string;
}

export default function AgentTestGroup({ projectId }: AgentTestGroupProps) {
    const [agents, setAgents] = useState<AgentDefinition[]>([]);
    const [selectedAgentIds, setSelectedAgentIds] = useState<string[]>([]);
    const [message, setMessage] = useState('');
    const [loading, setLoading] = useState(false);
    const [results, setResults] = useState<any[]>([]);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        fetchAgents();
    }, [projectId]);

    const fetchAgents = async () => {
        try {
            const response = await api.get(`/projects/${projectId}/agents`);
            if (response.data && response.data.agents) {
                setAgents(response.data.agents);
                // Select all by default
                setSelectedAgentIds(response.data.agents.map((a: any) => a.agent_id));
            }
        } catch (error) {
            console.error("Failed to fetch agents", error);
        }
    };

    const toggleAgent = (id: string) => {
        setSelectedAgentIds(prev =>
            prev.includes(id) ? prev.filter(a => a !== id) : [...prev, id]
        );
    };

    const handleSend = async () => {
        if (!message.trim() || selectedAgentIds.length === 0) return;

        setLoading(true);
        setError(null);
        try {
            const response = await api.post(`/projects/${projectId}/test-agents`, {
                message,
                agent_ids: selectedAgentIds
            });
            setResults(response.data);
        } catch (error: any) {
            console.error("Failed to test agents", error);
            setError("Failed to get responses from agents. Check if providers are connected.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full bg-zinc-950">
            {/* Header: Agent Selection */}
            <div className="p-4 border-b border-zinc-800 bg-zinc-900/50">
                <h3 className="text-sm font-semibold text-zinc-400 mb-3 uppercase tracking-wider">Select Agents to Test</h3>
                <div className="flex flex-wrap gap-2">
                    {agents.map((agent) => (
                        <button
                            key={agent.agent_id}
                            onClick={() => toggleAgent(agent.agent_id)}
                            className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition-all border ${
                                selectedAgentIds.includes(agent.agent_id)
                                    ? 'bg-indigo-600 border-indigo-500 text-white'
                                    : 'bg-zinc-800 border-zinc-700 text-zinc-400 hover:border-zinc-600'
                            }`}
                        >
                            {selectedAgentIds.includes(agent.agent_id) ? <CheckCircle2 size={12} /> : <Circle size={12} />}
                            {agent.role}
                        </button>
                    ))}
                    {agents.length === 0 && <span className="text-zinc-500 text-xs italic">No agents configured for this project.</span>}
                </div>
            </div>

            {/* Content: Results */}
            <div className="flex-1 overflow-y-auto p-4 space-y-6 scrollbar-thin scrollbar-thumb-zinc-800 scrollbar-track-transparent">
                {results.length === 0 && !loading && (
                    <div className="h-full flex flex-col items-center justify-center text-zinc-500 space-y-4">
                        <Bot size={48} className="opacity-20" />
                        <p className="text-sm italic">Send a message to compare responses from your agents.</p>
                    </div>
                )}

                {loading && (
                    <div className="flex flex-col items-center justify-center py-12 space-y-4">
                        <Loader2 size={32} className="animate-spin text-indigo-500" />
                        <p className="text-sm text-zinc-400">Agents are thinking...</p>
                    </div>
                )}

                {error && (
                    <div className="p-4 bg-red-900/20 border border-red-900/50 rounded-lg text-red-400 text-sm">
                        {error}
                    </div>
                )}

                {!loading && results.map((result, idx) => (
                    <div key={idx} className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden shadow-lg">
                        <div className="px-4 py-2 bg-zinc-800/50 border-b border-zinc-800 flex justify-between items-center">
                            <div className="flex items-center gap-2">
                                <span className="w-2 h-2 rounded-full bg-indigo-500"></span>
                                <span className="text-xs font-bold text-zinc-200 uppercase tracking-tight">{result.role}</span>
                            </div>
                            <span className={`text-[10px] px-1.5 py-0.5 rounded ${result.status === 'success' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}`}>
                                {result.status.toUpperCase()}
                            </span>
                        </div>
                        <div className="p-4 text-sm text-zinc-300 whitespace-pre-wrap leading-relaxed">
                            {result.response}
                        </div>
                    </div>
                ))}
            </div>

            {/* Footer: Input */}
            <div className="p-4 bg-zinc-900 border-t border-zinc-800">
                <div className="max-w-4xl mx-auto flex gap-2">
                    <input
                        type="text"
                        value={message}
                        onChange={(e) => setMessage(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                        placeholder="Enter a test prompt (e.g., 'What is your role?')"
                        className="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-3 text-sm focus:outline-none focus:border-indigo-500 transition-colors"
                        disabled={loading || selectedAgentIds.length === 0}
                    />
                    <button
                        onClick={handleSend}
                        disabled={loading || !message.trim() || selectedAgentIds.length === 0}
                        className="p-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-indigo-900/20"
                    >
                        {loading ? <Loader2 size={20} className="animate-spin" /> : <Send size={20} />}
                    </button>
                </div>
                <div className="mt-2 text-center">
                    <span className="text-[10px] text-zinc-500">
                        Selected: {selectedAgentIds.length} agents | Mode: Parallel Comparison
                    </span>
                </div>
            </div>
        </div>
    );
}
