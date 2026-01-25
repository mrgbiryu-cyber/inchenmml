'use client';

import { useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { useDomainStore } from '@/store/useDomainStore';
import { Loader2 } from 'lucide-react';
import api from '@/lib/axios-config';

// Dynamically import ForceGraph2D to avoid SSR issues
const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), {
    ssr: false,
    loading: () => <div className="flex items-center justify-center h-full text-zinc-500"><Loader2 className="animate-spin mr-2" /> Loading Graph...</div>
});

interface KnowledgeGraphProps {
    projectId?: string;
}

export default function KnowledgeGraph({ projectId }: KnowledgeGraphProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
    const currentDomain = useDomainStore((state) => state.currentDomain);
    const [data, setData] = useState({ nodes: [], links: [] });
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        // Update dimensions on resize
        const updateDimensions = () => {
            if (containerRef.current) {
                setDimensions({
                    width: containerRef.current.clientWidth,
                    height: containerRef.current.clientHeight
                });
            }
        };

        window.addEventListener('resize', updateDimensions);
        updateDimensions();

        return () => window.removeEventListener('resize', updateDimensions);
    }, []);

    useEffect(() => {
        const fetchGraph = async () => {
            const effectiveProjectId = projectId || 'system-master';
            setLoading(true);
            try {
                const response = await api.get(`/projects/${effectiveProjectId}/knowledge-graph`);
                setData(response.data);
            } catch (err) {
                console.error("Failed to fetch knowledge graph:", err);
            } finally {
                setLoading(false);
            }
        };

        fetchGraph();
    }, [projectId, currentDomain]);

    const handleNodeClick = (node: any) => {
        // Copy summary/content to clipboard
        const content = node.name || node.id;
        
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(content)
                .then(() => console.log(`Copied content: ${content}`))
                .catch(err => console.error('Failed to copy: ', err));
        } else {
            console.warn('Clipboard API not available');
        }
    };

    if (loading && data.nodes.length === 0) {
        return (
            <div className="flex items-center justify-center h-full text-zinc-500 bg-zinc-950">
                <Loader2 className="animate-spin mr-2" /> Loading Knowledge Graph...
            </div>
        );
    }

    return (
        <div ref={containerRef} className="w-full h-full bg-zinc-950 overflow-hidden relative">
            {loading && (
                <div className="absolute top-4 right-4 z-20">
                    <Loader2 className="animate-spin text-zinc-500" />
                </div>
            )}
            <ForceGraph2D
                width={dimensions.width}
                height={dimensions.height}
                graphData={data}
                nodeLabel="name"
                nodeColor="color"
                nodeRelSize={6}
                linkColor={() => '#3f3f46'}
                backgroundColor="#09090b"
                onNodeClick={handleNodeClick}
                cooldownTicks={100}
            />
        </div>
    );
}
