'use client';

import { useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { useDomainStore } from '@/store/useDomainStore';
import { Loader2 } from 'lucide-react';

// Dynamically import ForceGraph2D to avoid SSR issues
const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), {
    ssr: false,
    loading: () => <div className="flex items-center justify-center h-full text-zinc-500"><Loader2 className="animate-spin mr-2" /> Loading Graph...</div>
});

export default function KnowledgeGraph() {
    const containerRef = useRef<HTMLDivElement>(null);
    const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
    const currentDomain = useDomainStore((state) => state.currentDomain);
    const [data, setData] = useState({ nodes: [], links: [] });

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
        // Mock Data Generation based on domain
        // In real app, fetch from /api/v1/jobs/graph
        const generateMockData = () => {
            const nodes = [];
            const links = [];

            // Root node
            nodes.push({ id: 'root', name: currentDomain?.name || 'Root', val: 20, color: '#3b82f6' });

            // Sub modules
            const modules = ['Auth', 'Worker', 'Backend', 'Frontend', 'Database'];
            modules.forEach((mod, i) => {
                const modId = `mod_${i}`;
                nodes.push({ id: modId, name: mod, val: 10, color: '#8b5cf6' });
                links.push({ source: 'root', target: modId });

                // Files
                for (let j = 0; j < 3; j++) {
                    const fileId = `file_${i}_${j}`;
                    nodes.push({ id: fileId, name: `${mod}File${j}.ts`, val: 5, color: '#10b981' });
                    links.push({ source: modId, target: fileId });
                }
            });

            return { nodes, links };
        };

        setData(generateMockData() as any);
    }, [currentDomain]);

    const handleNodeClick = (node: any) => {
        // Copy path to clipboard
        const path = `/src/${node.name}`; // Mock path
        navigator.clipboard.writeText(path);
        // Optional: Show toast
        console.log(`Copied path: ${path}`);
    };

    return (
        <div ref={containerRef} className="w-full h-full bg-zinc-950 overflow-hidden">
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
