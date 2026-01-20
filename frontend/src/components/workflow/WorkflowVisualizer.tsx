'use client';

import React, { useCallback, useEffect, useState } from 'react';
import ReactFlow, {
    Node,
    Edge,
    Controls,
    Background,
    useNodesState,
    useEdgesState,
    addEdge,
    Connection,
    Panel
} from 'reactflow';
import 'reactflow/dist/style.css';
import AgentNode from './AgentNode';
import { ProjectAgentConfig, AgentDefinition } from '@/types/project';

const nodeTypes = {
    agentNode: AgentNode,
};

interface WorkflowVisualizerProps {
    initialConfig?: ProjectAgentConfig;
    onSave?: (config: ProjectAgentConfig) => void;
    activeNodeId?: string;
    readOnly?: boolean;
}

export default function WorkflowVisualizer({ initialConfig, onSave, activeNodeId, readOnly = false }: WorkflowVisualizerProps) {
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [selectedNode, setSelectedNode] = useState<Node | null>(null);

    // Initialize graph from config
    useEffect(() => {
        if (initialConfig?.agents) {
            const newNodes: Node[] = initialConfig.agents.map((agent, index) => {
                const isActive = agent.agent_id === activeNodeId;
                return {
                    id: agent.agent_id,
                    type: 'agentNode',
                    position: { x: 250 * index, y: 100 }, // Simple layout
                    data: {
                        label: agent.agent_id,
                        role: agent.role,
                        model: agent.model,
                        onEdit: readOnly ? undefined : () => handleEditNode(agent.agent_id)
                    },
                    style: isActive ? {
                        border: '2px solid #a855f7',
                        boxShadow: '0 0 15px rgba(168, 85, 247, 0.6)',
                        borderRadius: '10px'
                    } : undefined
                };
            });

            const newEdges: Edge[] = [];
            initialConfig.agents.forEach(agent => {
                agent.next_agents.forEach(nextId => {
                    newEdges.push({
                        id: `${agent.agent_id}-${nextId}`,
                        source: agent.agent_id,
                        target: nextId,
                        animated: true,
                        style: {
                            stroke: activeNodeId === agent.agent_id ? '#a855f7' : '#555',
                            strokeWidth: activeNodeId === agent.agent_id ? 2 : 1
                        }
                    });
                });
            });

            setNodes(newNodes);
            setEdges(newEdges);
        }
    }, [initialConfig, activeNodeId, readOnly]);

    const onConnect = useCallback(
        (params: Connection) => {
            if (!readOnly) {
                setEdges((eds) => addEdge(params, eds));
            }
        },
        [setEdges, readOnly],
    );

    const handleEditNode = (nodeId: string) => {
        const node = nodes.find(n => n.id === nodeId);
        if (node) setSelectedNode(node);
    };

    const handleSave = () => {
        if (!onSave) return;

        // Convert graph back to config
        const agents: AgentDefinition[] = nodes.map(node => {
            const connectedEdges = edges.filter(e => e.source === node.id);
            const nextAgents = connectedEdges.map(e => e.target);

            return {
                agent_id: node.id,
                role: node.data.role,
                model: node.data.model,
                provider: 'OPENROUTER',
                system_prompt: 'Default prompt',
                next_agents: nextAgents
            };
        });

        const config: ProjectAgentConfig = {
            workflow_type: 'CUSTOM',
            agents: agents,
            entry_agent_id: agents.length > 0 ? agents[0].agent_id : ''
        };

        onSave(config);
    };

    const addAgent = (role: string) => {
        const id = `${role.toLowerCase()}-${nodes.length + 1}`;
        const newNode: Node = {
            id,
            type: 'agentNode',
            position: { x: 100, y: 100 },
            data: {
                label: id,
                role: role,
                model: 'gpt-4',
                onEdit: () => handleEditNode(id)
            },
        };
        setNodes((nds) => nds.concat(newNode));
    };

    return (
        <div className="h-[600px] w-full bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden flex">
            <div className="flex-1 relative">
                <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={readOnly ? undefined : onNodesChange}
                    onEdgesChange={readOnly ? undefined : onEdgesChange}
                    onConnect={onConnect}
                    nodeTypes={nodeTypes}
                    fitView
                    nodesDraggable={!readOnly}
                    nodesConnectable={!readOnly}
                >
                    <Background color="#333" gap={16} />
                    <Controls />
                    {!readOnly && (
                        <Panel position="top-left" className="bg-zinc-800 p-2 rounded border border-zinc-700 flex gap-2">
                            <button onClick={() => addAgent('PLANNER')} className="px-2 py-1 bg-zinc-700 rounded text-xs hover:bg-zinc-600">Add Planner</button>
                            <button onClick={() => addAgent('CODER')} className="px-2 py-1 bg-zinc-700 rounded text-xs hover:bg-zinc-600">Add Coder</button>
                            <button onClick={() => addAgent('REVIEWER')} className="px-2 py-1 bg-zinc-700 rounded text-xs hover:bg-zinc-600">Add Reviewer</button>
                            <button onClick={() => addAgent('QA')} className="px-2 py-1 bg-zinc-700 rounded text-xs hover:bg-zinc-600">Add QA</button>
                            <div className="w-px bg-zinc-600 mx-1"></div>
                            <button onClick={handleSave} className="px-3 py-1 bg-purple-600 text-white rounded text-xs hover:bg-purple-500 font-bold">Save Workflow</button>
                        </Panel>
                    )}
                </ReactFlow>
            </div>

            {/* Simple Property Editor Sidebar */}
            {selectedNode && !readOnly && (
                <div className="w-64 bg-zinc-800 border-l border-zinc-700 p-4 overflow-y-auto">
                    <h3 className="font-bold mb-4">Edit Agent</h3>
                    <div className="space-y-4">
                        <div>
                            <label className="block text-xs text-zinc-400 mb-1">ID</label>
                            <input type="text" value={selectedNode.id} disabled className="w-full bg-zinc-900 border border-zinc-700 rounded p-2 text-sm text-zinc-500" />
                        </div>
                        <div>
                            <label className="block text-xs text-zinc-400 mb-1">Role</label>
                            <select
                                value={selectedNode.data.role}
                                onChange={(e) => {
                                    const newRole = e.target.value;
                                    setNodes(nds => nds.map(n => n.id === selectedNode.id ? { ...n, data: { ...n.data, role: newRole } } : n));
                                    setSelectedNode(prev => prev ? { ...prev, data: { ...prev.data, role: newRole } } : null);
                                }}
                                className="w-full bg-zinc-900 border border-zinc-700 rounded p-2 text-sm text-white"
                            >
                                <option value="PLANNER">PLANNER</option>
                                <option value="CODER">CODER</option>
                                <option value="REVIEWER">REVIEWER</option>
                                <option value="QA">QA</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-xs text-zinc-400 mb-1">Model</label>
                            <select
                                value={selectedNode.data.model}
                                onChange={(e) => {
                                    const newModel = e.target.value;
                                    setNodes(nds => nds.map(n => n.id === selectedNode.id ? { ...n, data: { ...n.data, model: newModel } } : n));
                                    setSelectedNode(prev => prev ? { ...prev, data: { ...prev.data, model: newModel } } : null);
                                }}
                                className="w-full bg-zinc-900 border border-zinc-700 rounded p-2 text-sm text-white"
                            >
                                <option value="gpt-4">GPT-4</option>
                                <option value="claude-3-opus">Claude 3 Opus</option>
                                <option value="deepseek-chat">DeepSeek Chat</option>
                                <option value="mimo-v2-flash">Mimo v2 Flash</option>
                            </select>
                        </div>
                        <button onClick={() => setSelectedNode(null)} className="w-full py-2 bg-zinc-700 hover:bg-zinc-600 rounded text-sm mt-4">Close</button>
                    </div>
                </div>
            )}
        </div>
    );
}
