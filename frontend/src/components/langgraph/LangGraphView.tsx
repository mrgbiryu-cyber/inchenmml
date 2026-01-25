'use client';

import { useCallback, useState, useMemo, useEffect } from 'react';
import ReactFlow, {
    MiniMap,
    Controls,
    Background,
    useNodesState,
    useEdgesState,
    addEdge,
    Connection,
    Edge,
    Handle,
    Position,
    NodeProps
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Settings, X, Search } from 'lucide-react';
import api from '@/lib/axios-config';
import ModelSelector from '@/components/shared/ModelSelector';
import { useProjectStore } from '@/store/projectStore';
import { useAuthStore } from '@/store/useAuthStore';

// Custom Agent Node Component
const AgentNode = ({ data, id }: NodeProps) => {
    return (
        <div className="px-4 py-2 shadow-md rounded-md bg-zinc-800 border-2 border-zinc-600 min-w-[150px]">
            <Handle type="target" position={Position.Top} className="w-3 h-3 bg-zinc-400" />
            <div className="flex items-center justify-between">
                <div className="font-bold text-zinc-200">{data.label}</div>
                <button
                    className="p-1 hover:bg-zinc-700 rounded text-zinc-400 hover:text-white"
                    onClick={(e) => {
                        e.stopPropagation();
                        data.onEdit(id, data);
                    }}
                >
                    <Settings size={14} />
                </button>
            </div>
            <div className="text-xs text-zinc-500 mt-1">{data.model || 'Default Model'}</div>
            <Handle type="source" position={Position.Bottom} className="w-3 h-3 bg-zinc-400" />
        </div>
    );
};

function cn(...inputs: any[]) {
    return inputs.filter(Boolean).join(' ');
}

interface LangGraphViewProps {
    projectId?: string;
}

export default function LangGraphView({ projectId }: LangGraphViewProps) {
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [loading, setLoading] = useState(false);

    // Modal State
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [isRegistryModalOpen, setIsRegistryModalOpen] = useState(false);
    const [registryAgents, setRegistryAgents] = useState<any[]>([]);
    const [editingNodeId, setEditingNodeId] = useState<string | null>(null);
    const [editConfig, setEditConfig] = useState<any>({});

    const token = useAuthStore((state) => state.token);
    const { setCurrentConfig } = useProjectStore();

    const nodeTypes = useMemo(() => ({ agent: AgentNode }), []);

    const fetchRegistryAgents = async () => {
        try {
            setLoading(true);
            const response = await api.get('/agents/');
            setRegistryAgents(response.data);
            setIsRegistryModalOpen(true);
        } catch (error) {
            console.error("Failed to fetch registry agents", error);
            alert("에이전트 목록을 불러오지 못했습니다. (401/403 확인)");
        } finally {
            setLoading(false);
        }
    };

    const loadAgentFromRegistry = (agent: any) => {
        const id = `${agent.agent_id}_${Date.now()}`;
        const newNode = {
            id,
            type: 'agent',
            data: {
                label: agent.name || agent.role,
                type: agent.type,
                model: agent.model,
                provider: agent.provider,
                system_prompt: agent.system_prompt,
                config: agent.config,
                onEdit: handleEditNode
            },
            position: { x: Math.random() * 400, y: Math.random() * 400 },
        };
        setNodes((nds) => nds.concat(newNode));
        setIsRegistryModalOpen(false);
    };

    const handleEditNode = useCallback((id: string, data: any) => {
        setEditingNodeId(id);
        setEditConfig({
            label: data.label,
            type: data.type || 'CUSTOM',
            model: data.model || 'google/gemini-2.0-flash-001',
            provider: data.provider || 'OPENROUTER',
            system_prompt: data.system_prompt || '',
            config: data.config || {}
        });
        setIsModalOpen(true);
    }, []);

    // Fetch agents from backend
    useEffect(() => {
        if (projectId && projectId !== 'undefined' && projectId !== 'null') {
            fetchAgents();
        }
    }, [projectId]);

    const fetchAgents = async () => {
        if (!projectId || projectId === 'undefined' || projectId === 'null') return;
        
        try {
            setLoading(true);
            const response = await api.get(`/projects/${projectId}/agents`);
            const config = response.data;
            
            if (config && config.agents) {
                setCurrentConfig(config);
                const initialNodes: any[] = [];
                const initialEdges: any[] = [];
                
                config.agents.forEach((agent: any, index: number) => {
                    initialNodes.push({
                        id: agent.agent_id,
                        type: 'agent',
                        data: {
                            label: agent.role,
                            model: agent.model,
                            provider: agent.provider || 'OLLAMA',
                            system_prompt: agent.system_prompt,
                            onEdit: handleEditNode
                        },
                        position: { x: 250, y: 100 + index * 150 }
                    });
                    
                    if (agent.next_agents) {
                        agent.next_agents.forEach((nextId: string) => {
                            initialEdges.push({
                                id: `e-${agent.agent_id}-${nextId}`,
                                source: agent.agent_id,
                                target: nextId,
                                animated: true
                            });
                        });
                    }
                });
                
                setNodes(initialNodes);
                setEdges(initialEdges);
            }
        } catch (error) {
            console.error("Failed to fetch agents", error);
        } finally {
            setLoading(false);
        }
    };

    const saveGraph = async () => {
        console.log("DEBUG: saveGraph called. ProjectId:", projectId);
        if (!projectId) {
            console.error("DEBUG: Cannot save graph - ProjectId is missing");
            return;
        }
        
        try {
            setLoading(true);
            const agentConfig = {
                workflow_type: 'SEQUENTIAL',
                entry_agent_id: nodes.find(n => n.type === 'agent')?.id || nodes[0]?.id || '',
                agents: nodes
                    .filter(node => node.type === 'agent')
                    .map(node => ({
                        agent_id: node.id,
                        role: node.data.label,
                        type: node.data.type || 'CUSTOM',
                        model: node.data.model,
                        provider: node.data.provider || 'OLLAMA',
                        system_prompt: node.data.system_prompt,
                        config: node.data.config || {},
                        next_agents: edges
                            .filter(edge => edge.source === node.id)
                            .map(edge => edge.target)
                    }))
            };
            
            await api.post(`/projects/${projectId}/agents`, agentConfig);
            setCurrentConfig(agentConfig as any);
            alert("Graph saved successfully!");
        } catch (error) {
            console.error("Failed to save graph", error);
            alert("Failed to save graph");
        } finally {
            setLoading(false);
        }
    };

    const onConnect = useCallback(
        (params: Connection | Edge) => {
            setEdges((eds) => addEdge({ 
                ...params, 
                animated: true,
                style: { stroke: '#6366f1', strokeWidth: 2 } 
            }, eds));
        },
        [setEdges],
    );

    const onEdgeClick = useCallback(
        (event: React.MouseEvent, edge: Edge) => {
            if (window.confirm("이 연결 선을 삭제하시겠습니까?")) {
                setEdges((eds) => eds.filter((e) => e.id !== edge.id));
            }
        },
        [setEdges]
    );

    const saveNodeConfig = () => {
        setNodes((nds) => nds.map((node) => {
            if (node.id === editingNodeId) {
                return {
                    ...node,
                    data: {
                        ...node.data,
                        label: editConfig.label,
                        type: editConfig.type,
                        model: editConfig.model,
                        provider: editConfig.provider,
                        system_prompt: editConfig.system_prompt,
                        config: editConfig.config
                    }
                };
            }
            return node;
        }));
        setIsModalOpen(false);
    };

    const deleteNode = (id: string) => {
        setNodes((nds) => nds.filter((node) => node.id !== id));
        setEdges((eds) => eds.filter((edge) => edge.source !== id && edge.target !== id));
    };

    const addAgentNode = (role: 'Planner' | 'Coder' | 'General') => {
        const id = `${role.toLowerCase()}_${Date.now()}`;
        const newNode = {
            id,
            type: 'agent',
            data: {
                label: role === 'General' ? `New Agent` : role,
                model: 'mimo-v2-flash',
                provider: 'OLLAMA',
                system_prompt: role === 'Planner' 
                    ? 'You are a Master Planner.' 
                    : role === 'Coder' 
                        ? 'You are a Senior Coder.' 
                        : '',
                onEdit: handleEditNode
            },
            position: { x: Math.random() * 400, y: Math.random() * 400 },
        };
        setNodes((nds) => nds.concat(newNode));
    };

    return (
        <div className="w-full h-full bg-zinc-950 relative">
            <div className="absolute top-4 right-4 z-10 flex gap-2">
                <button
                    onClick={() => addAgentNode('Planner')}
                    className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-500 transition-colors shadow-lg text-sm font-medium border border-indigo-400/30"
                >
                    + Add Planner
                </button>
                <button
                    onClick={() => addAgentNode('Coder')}
                    className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-500 transition-colors shadow-lg text-sm font-medium border border-emerald-400/30"
                >
                    + Add Coder
                </button>
                
                {/* [TODO 7] Agent List Button */}
                <button
                    className="px-4 py-2 bg-zinc-800 text-zinc-300 rounded-lg hover:bg-zinc-700 transition-colors shadow-lg text-sm font-medium border border-zinc-700 flex items-center gap-2"
                    onClick={fetchRegistryAgents}
                >
                    <Search size={14} />
                    Agent List
                </button>

                <button
                    onClick={saveGraph}
                    disabled={loading}
                    className="px-4 py-2 bg-white text-black rounded-lg hover:bg-zinc-200 transition-colors shadow-lg text-sm font-bold ml-4"
                >
                    {loading ? 'Saving...' : 'Save Graph'}
                </button>
            </div>

            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                onEdgeClick={onEdgeClick}
                nodeTypes={nodeTypes}
                fitView
                className="bg-zinc-950"
                defaultEdgeOptions={{
                    animated: true,
                    style: { stroke: '#6366f1', strokeWidth: 2 }
                }}
            >
                <Controls className="bg-zinc-800 border-zinc-700 fill-zinc-400" />
                <MiniMap className="bg-zinc-900 border-zinc-800" nodeColor="#3b82f6" />
                <Background color="#3f3f46" gap={16} />
            </ReactFlow>

            {/* Edit Modal */}
            {isModalOpen && (
                <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
                    <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-[500px] shadow-2xl flex flex-col max-h-[90vh]">
                        <div className="flex items-center justify-between p-4 border-b border-zinc-800">
                            <h3 className="text-lg font-bold text-white">Edit Agent Node</h3>
                            <button onClick={() => setIsModalOpen(false)} className="text-zinc-400 hover:text-white">
                                <X size={20} />
                            </button>
                        </div>

                        <div className="p-6 space-y-4 overflow-y-auto">
                            <div>
                                <label className="block text-sm font-medium text-zinc-400 mb-1">Agent Name</label>
                                <input
                                    type="text"
                                    value={editConfig.label}
                                    onChange={(e) => setEditConfig({ ...editConfig, label: e.target.value })}
                                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm focus:border-indigo-500 outline-none"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-zinc-400 mb-1">Agent Type (Schema Selector)</label>
                                <select
                                    value={editConfig.type}
                                    onChange={(e) => setEditConfig({ ...editConfig, type: e.target.value, config: {} })}
                                    className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm focus:border-indigo-500 outline-none text-zinc-200"
                                >
                                    <option value="MASTER">MASTER</option>
                                    <option value="PLANNER">PLANNER</option>
                                    <option value="CODER">CODER</option>
                                    <option value="QA">QA</option>
                                    <option value="GIT">GIT</option>
                                    <option value="CUSTOM">CUSTOM</option>
                                </select>
                                <p className="text-[10px] text-zinc-500 mt-1 italic">Note: Type determines required configuration fields, not runtime behavior.</p>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-zinc-400 mb-2">Provider</label>
                                <div className="grid grid-cols-2 gap-2 bg-zinc-950 p-1 rounded-lg border border-zinc-800">
                                    <button
                                        type="button"
                                        onClick={() => setEditConfig({ ...editConfig, provider: 'OPENROUTER' })}
                                        className={cn(
                                            "py-1.5 text-xs font-medium rounded-md transition-all",
                                            editConfig.provider === 'OPENROUTER' ? "bg-indigo-600 text-white shadow-sm" : "text-zinc-500 hover:text-zinc-300"
                                        )}
                                    >
                                        OpenRouter
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => setEditConfig({ ...editConfig, provider: 'OLLAMA' })}
                                        className={cn(
                                            "py-1.5 text-xs font-medium rounded-md transition-all",
                                            editConfig.provider === 'OLLAMA' ? "bg-emerald-600 text-white shadow-sm" : "text-zinc-500 hover:text-zinc-300"
                                        )}
                                    >
                                        Ollama
                                    </button>
                                </div>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-zinc-400 mb-1">Model</label>
                                <ModelSelector
                                    value={editConfig.model}
                                    onChange={(val) => setEditConfig({ ...editConfig, model: val })}
                                    provider={editConfig.provider}
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-zinc-400 mb-1">System Prompt</label>
                                <textarea
                                    value={editConfig.system_prompt}
                                    onChange={(e) => setEditConfig({ ...editConfig, system_prompt: e.target.value })}
                                    className="w-full h-32 bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm font-mono focus:border-indigo-500 outline-none resize-none"
                                    placeholder="You are a helpful assistant..."
                                />
                            </div>

                            {/* Dynamic Config Fields */}
                            <div className="pt-4 border-t border-zinc-800 space-y-4">
                                <h4 className="text-xs font-bold text-indigo-400 uppercase tracking-widest">Configuration ({editConfig.type})</h4>
                                
                                {editConfig.type === 'CODER' && (
                                    <>
                                        <div>
                                            <label className="block text-xs font-medium text-zinc-500 mb-1">Repo Root (Absolute Path)</label>
                                            <input 
                                                type="text" 
                                                value={editConfig.config?.repo_root || ''} 
                                                onChange={(e) => setEditConfig({...editConfig, config: {...editConfig.config, repo_root: e.target.value}})}
                                                className="w-full bg-zinc-950 border border-zinc-800 rounded px-2 py-1.5 text-xs text-zinc-300"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-xs font-medium text-zinc-500 mb-1">Allowed Paths (Comma separated)</label>
                                            <input 
                                                type="text" 
                                                value={editConfig.config?.allowed_paths?.join(', ') || ''} 
                                                onChange={(e) => setEditConfig({...editConfig, config: {...editConfig.config, allowed_paths: e.target.value.split(',').map(s => s.trim())}})}
                                                className="w-full bg-zinc-950 border border-zinc-800 rounded px-2 py-1.5 text-xs text-zinc-300"
                                            />
                                        </div>
                                    </>
                                )}

                                {editConfig.type === 'QA' && (
                                    <>
                                        <div>
                                            <label className="block text-xs font-medium text-zinc-500 mb-1">Test Command</label>
                                            <input 
                                                type="text" 
                                                value={editConfig.config?.test_command || ''} 
                                                onChange={(e) => setEditConfig({...editConfig, config: {...editConfig.config, test_command: e.target.value}})}
                                                className="w-full bg-zinc-950 border border-zinc-800 rounded px-2 py-1.5 text-xs text-zinc-300"
                                                placeholder="e.g. pytest or npm test"
                                            />
                                        </div>
                                    </>
                                )}

                                {editConfig.type === 'CUSTOM' && (
                                    <>
                                        <div>
                                            <label className="block text-xs font-medium text-zinc-500 mb-1">Tool Allowlist (Comma separated)</label>
                                            <input 
                                                type="text" 
                                                value={editConfig.config?.tool_allowlist?.join(', ') || ''} 
                                                onChange={(e) => setEditConfig({...editConfig, config: {...editConfig.config, tool_allowlist: e.target.value.split(',').map(s => s.trim())}})}
                                                className="w-full bg-zinc-950 border border-zinc-800 rounded px-2 py-1.5 text-xs text-zinc-300"
                                            />
                                        </div>
                                    </>
                                )}
                            </div>
                        </div>

                        <div className="p-4 border-t border-zinc-800 flex justify-between items-center">
                            <button
                                onClick={() => {
                                    if (editingNodeId) deleteNode(editingNodeId);
                                    setIsModalOpen(false);
                                }}
                                className="px-4 py-2 text-red-500 hover:bg-red-900/20 rounded-lg transition-colors text-sm"
                            >
                                Delete Agent
                            </button>
                            <div className="flex gap-2">
                                <button
                                    onClick={() => setIsModalOpen(false)}
                                    className="px-4 py-2 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={saveNodeConfig}
                                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition-colors"
                                >
                                    Save Changes
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* [TODO 7] Agent Registry Modal */}
            {isRegistryModalOpen && (
                <div className="absolute inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-md">
                    <div className="bg-zinc-900 border border-zinc-800 rounded-2xl w-[600px] shadow-2xl flex flex-col max-h-[80vh]">
                        <div className="flex items-center justify-between p-5 border-b border-zinc-800">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-indigo-600/20 rounded-lg">
                                    <Search size={20} className="text-indigo-400" />
                                </div>
                                <h3 className="text-xl font-bold text-white">Agent Registry</h3>
                            </div>
                            <button onClick={() => setIsRegistryModalOpen(false)} className="text-zinc-400 hover:text-white transition-colors">
                                <X size={24} />
                            </button>
                        </div>

                        <div className="p-2 overflow-y-auto">
                            {registryAgents.length === 0 ? (
                                <div className="p-10 text-center text-zinc-500 italic">저장된 에이전트가 없습니다.</div>
                            ) : (
                                <div className="grid grid-cols-1 gap-2 p-2">
                                    {registryAgents.map((agent) => (
                                        <div key={agent.agent_id} className="flex items-center justify-between p-4 bg-zinc-950/50 border border-zinc-800 rounded-xl hover:border-indigo-500/50 transition-all group">
                                            <div className="flex flex-col">
                                                <span className="text-sm font-bold text-zinc-200 group-hover:text-indigo-400 transition-colors">{agent.name || agent.role}</span>
                                                <div className="flex items-center gap-2 mt-1">
                                                    <span className="text-[10px] bg-zinc-800 px-2 py-0.5 rounded text-zinc-400 font-mono">{agent.type}</span>
                                                    <span className="text-[10px] text-zinc-500">{agent.model}</span>
                                                </div>
                                            </div>
                                            <button 
                                                onClick={() => loadAgentFromRegistry(agent)}
                                                className="px-4 py-1.5 bg-indigo-600 text-white text-xs font-bold rounded-lg hover:bg-indigo-500 transition-all shadow-lg shadow-indigo-900/20"
                                            >
                                                Load
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                        
                        <div className="p-4 border-t border-zinc-800 text-center">
                            <p className="text-[10px] text-zinc-500 italic">v3.5.1 Registry Engine - Multi-tenant aware</p>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
