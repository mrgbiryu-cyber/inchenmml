'use client';

import React from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import LangGraphView from '@/components/langgraph/LangGraphView';

export default function AgentsPage() {
    const params = useParams();
    const router = useRouter();
    const projectId = params.projectId as string;

    return (
        <div className="h-screen flex flex-col bg-zinc-950">
            <div className="flex items-center justify-between p-4 border-b border-zinc-800 bg-zinc-900">
                <div className="flex items-center gap-4">
                    <button
                        onClick={() => router.back()}
                        className="p-2 hover:bg-zinc-800 rounded-lg transition-colors text-zinc-400 hover:text-white"
                    >
                        <ArrowLeft size={20} />
                    </button>
                    <h1 className="text-xl font-bold text-white">Agent Workflow Editor</h1>
                </div>
                <div className="text-sm text-zinc-500">
                    Project ID: {projectId}
                </div>
            </div>

            <div className="flex-1 relative">
                <LangGraphView projectId={projectId} />
            </div>
        </div>
    );
}
