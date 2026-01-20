import { useState, useEffect, useCallback } from 'react';
import { Node, Edge } from 'reactflow';
import { useWorker } from './useWorker';

// Define types for our graph data (adjust based on actual backend response)
interface GraphNode {
    id: string;
    type: string;
    label: string;
    status: 'pending' | 'active' | 'completed' | 'failed';
}

interface GraphEdge {
    source: string;
    target: string;
}

interface GraphData {
    nodes: GraphNode[];
    edges: GraphEdge[];
}

export function useLangGraph(jobId: string | null) {
    const [nodes, setNodes] = useState<Node[]>([]);
    const [edges, setEdges] = useState<Edge[]>([]);
    const [loading, setLoading] = useState(false);
    const { status } = useWorker(); // Assuming useWorker might provide some context

    const fetchGraphData = useCallback(async () => {
        if (!jobId) return;

        try {
            setLoading(true);
            // TODO: Replace with actual API call
            // const response = await fetch(`/api/v1/jobs/${jobId}/graph`);
            // const data: GraphData = await response.json();

            // Mock data for now to simulate dynamic updates
            const mockData: GraphData = {
                nodes: [
                    { id: '1', type: 'input', label: 'User Request', status: 'completed' },
                    { id: '2', type: 'default', label: 'Planner Agent', status: 'active' },
                    { id: '3', type: 'default', label: 'Coder Agent', status: 'pending' },
                    { id: '4', type: 'default', label: 'Reviewer Agent', status: 'pending' },
                    { id: '5', type: 'output', label: 'Execution', status: 'pending' },
                ],
                edges: [
                    { source: '1', target: '2' },
                    { source: '1', target: '3' },
                    { source: '2', target: '4' },
                    { source: '3', target: '4' },
                    { source: '4', target: '5' },
                ]
            };

            // Transform to ReactFlow format
            const flowNodes: Node[] = mockData.nodes.map((node, index) => ({
                id: node.id,
                type: node.type === 'input' || node.type === 'output' ? node.type : 'default',
                data: { label: node.label, status: node.status },
                position: { x: 250 + (index % 2 === 0 ? -100 : 100), y: index * 100 }, // Simple auto-layout
                style: {
                    background: node.status === 'active' ? '#3b82f6' :
                        node.status === 'completed' ? '#10b981' :
                            '#1f2937',
                    color: '#fff',
                    border: '1px solid #374151'
                }
            }));

            const flowEdges: Edge[] = mockData.edges.map((edge, index) => ({
                id: `e${index}`,
                source: edge.source,
                target: edge.target,
                animated: true,
                style: { stroke: '#4b5563' }
            }));

            setNodes(flowNodes);
            setEdges(flowEdges);
        } catch (error) {
            console.error("Failed to fetch graph data:", error);
        } finally {
            setLoading(false);
        }
    }, [jobId]);

    // Poll for updates
    useEffect(() => {
        if (jobId) {
            fetchGraphData();
            const interval = setInterval(fetchGraphData, 3000); // Poll every 3 seconds
            return () => clearInterval(interval);
        }
    }, [jobId, fetchGraphData]);

    return { nodes, edges, loading };
}
