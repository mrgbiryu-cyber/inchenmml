'use client';

import { useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { Loader2, AlertTriangle, Monitor } from 'lucide-react';

// Dynamically import ForceGraph with SSR disabled
const ForceGraph3D = dynamic(() => import('react-force-graph-3d'), {
    ssr: false,
    loading: () => <GraphLoader mode="3D" />
});

const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), {
    ssr: false,
    loading: () => <GraphLoader mode="2D" />
});

function GraphLoader({ mode }: { mode: string }) {
    return (
        <div className="flex flex-col items-center justify-center h-full text-zinc-500 bg-zinc-950">
            <Loader2 className="animate-spin mb-2" size={32} />
            <span className="text-sm font-medium">Initializing {mode} Vector Map...</span>
        </div>
    );
}

export default function VectorMapView() {
    const [data, setData] = useState({ nodes: [], links: [] });
    const [use2D, setUse2D] = useState(false);
    const [renderError, setRenderError] = useState<string | null>(null);

    useEffect(() => {
        // Detect mobile or low-end device to prefer 2D
        if (typeof window !== 'undefined') {
            const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
            if (isMobile) {
                console.log("Mobile detected, falling back to 2D Graph");
                setUse2D(true);
            }
        }

        // Meaningful labels for Vector Data
        const concepts = [
            "Transformer", "Attention Mechanism", "Encoder-Decoder", "LLM Fine-tuning",
            "Vector Embeddings", "Cosine Similarity", "RAG Pipeline", "Knowledge Graph",
            "Agentic Workflow", "Planning Agent", "Memory Management", "Prompt Engineering",
            "Zero-shot Learning", "Few-shot Prompting", "Reinforcement Learning", "RLHF",
            "Docker Execution", "Local Worker Hub", "Neo4j Storage", "FastAPI Backend",
            "Next.js Frontend", "Ed25519 Signing", "Path Validation", "Job Queue",
            "LangGraph Context", "Tool Interceptor", "System Master", "Streaming API",
            "JWT Auth", "RBAC Policy", "Redis Cache", "Model Quantization",
            "Ollama Runtime", "OpenRouter Proxy", "Context Window", "Tokenization",
            "Semantic Search", "Metadata Filtering", "Database Indexing", "Async Tasks",
            "Error Handling", "Log Monitoring", "User Feedback Loop", "System Butler",
            "Planning Mode", "Execution Gate", "Dynamic Toolsets", "Agent Registry",
            "Schema Validation", "JSON Parsing", "State Persistence", "Mobile Responsive",
            "Tailwind Styling", "Lucide Icons", "Three.js Canvas", "Force-directed Graph",
            "Node Connectivity", "Edge Relationship", "Cluster Analysis", "Dimensionality Reduction",
            "PCA Projection", "t-SNE Mapping", "Embedding Space", "High-dimensional Vectors",
            "Similarity Search", "HNSW Index", "FAISS Library", "Pinecone Cloud",
            "Local Chroma DB", "Document Chunking", "Overlap Strategy", "Recursive Splitting",
            "PDF Extraction", "Markdown Parsing", "OCR Processing", "Speech Recognition",
            "Vision Models", "Multimodal AI", "Cross-lingual Learning", "Bias Mitigation"
        ];

        const N = concepts.length;
        const gData = {
            nodes: concepts.map((name, i) => ({
                id: i,
                name: name,
                group: Math.floor(Math.random() * 8),
                val: 5 + Math.random() * 15
            })),
            links: [...Array(N).keys()]
                .filter(id => id > 0)
                .map(id => ({
                    source: id,
                    target: Math.floor(Math.pow(Math.random(), 2) * id) // Connect to previous nodes biased towards older ones
                }))
        };
        setData(gData as any);
    }, []);

    if (renderError) {
        return (
            <div className="flex flex-col items-center justify-center h-full text-red-400 bg-zinc-950 p-6 text-center">
                <AlertTriangle size={48} className="mb-4 opacity-50" />
                <h3 className="text-lg font-bold mb-2">3D Rendering Failed</h3>
                <p className="text-sm text-zinc-500 max-w-xs mb-6">
                    Your device or browser might not support WebGL. 
                    {renderError}
                </p>
                <button 
                    onClick={() => { setUse2D(true); setRenderError(null); }}
                    className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg transition-colors text-sm font-medium"
                >
                    Switch to 2D Mode
                </button>
            </div>
        );
    }

    return (
        <div className="w-full h-full bg-zinc-950 relative group">
            <div className="absolute top-4 left-4 z-10 flex gap-2">
                <button 
                    onClick={() => setUse2D(!use2D)}
                    className="px-3 py-1.5 bg-black/50 backdrop-blur-md border border-zinc-800 rounded-md text-[10px] font-bold text-zinc-400 hover:text-white hover:border-zinc-600 transition-all flex items-center gap-2 uppercase tracking-widest"
                >
                    <Monitor size={12} />
                    {use2D ? 'Switch to 3D' : 'Switch to 2D'}
                </button>
            </div>

            {use2D ? (
                <ForceGraph2D
                    graphData={data}
                    nodeLabel="name"
                    nodeAutoColorBy="group"
                    backgroundColor="#09090b"
                />
            ) : (
                <ForceGraph3D
                    graphData={data}
                    nodeLabel="name"
                    nodeAutoColorBy="group"
                    backgroundColor="#09090b"
                    linkOpacity={0.5}
                    nodeResolution={16}
                    onRenderError={(err: any) => {
                        console.error("3D Render Error:", err);
                        setRenderError(err.message || "WebGL Error");
                    }}
                />
            )}
        </div>
    );
}
