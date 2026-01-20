'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import ChatInterface from '@/components/chat/ChatInterface';
import KnowledgeGraph from '@/components/graph/KnowledgeGraph';
import LangGraphView from '@/components/langgraph/LangGraphView';
import VectorMapView from '@/components/vectormap/VectorMapView';
import AgentTestGroup from '@/components/chat/AgentTestGroup';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useProjectStore } from '@/store/projectStore';
import api from '@/lib/axios-config';
import { Project } from '@/types/project';

export default function ProjectDetailPage() {
    const params = useParams();
    const router = useRouter();
    const searchParams = useSearchParams();
    const projectId = params.projectId as string;
    const tab = searchParams.get('tab');

    const [project, setProject] = useState<Project | null>(null);
    const [loading, setLoading] = useState(true);

    const { setCurrentProjectId } = useProjectStore();

    useEffect(() => {
        if (projectId) {
            fetchProject();
            setCurrentProjectId(projectId);
        }
    }, [projectId]);

    const fetchProject = async () => {
        try {
            const response = await api.get(`/projects/${projectId}`);
            setProject(response.data);
        } catch (error) {
            console.error("Failed to fetch project", error);
            // router.push('/projects'); // Redirect if not found?
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async () => {
        if (!confirm("Are you sure you want to delete this project?")) return;
        try {
            await api.delete(`/projects/${projectId}`);
            router.push('/projects');
        } catch (error) {
            console.error("Failed to delete project", error);
            alert("Failed to delete project");
        }
    };

    if (loading) return <div>Loading project...</div>;
    if (!project) return <div>Project not found</div>;

    // Render Tab Content
    if (tab === 'chat') {
        return (
            <div className="h-full flex flex-col">
                <div className="flex justify-between items-center mb-4 px-4 pt-4">
                    <h2 className="text-xl font-bold text-white">Project Chat: {project.name}</h2>
                    <button onClick={() => router.push(`/projects/${projectId}`)} className="text-zinc-400 hover:text-white">
                        Back to Dashboard
                    </button>
                </div>
                <div className="h-[calc(100vh-200px)] overflow-hidden rounded-lg border border-zinc-800">
                    <ChatInterface projectId={projectId} />
                </div>
            </div>
        );
    }

    if (tab === 'graph') {
        return (
            <div className="h-full flex flex-col">
                <div className="flex justify-between items-center mb-4 px-4 pt-4">
                    <h2 className="text-xl font-bold text-white">Knowledge Graph: {project.name}</h2>
                    <button onClick={() => router.push(`/projects/${projectId}`)} className="text-zinc-400 hover:text-white">Back</button>
                </div>
                <div className="flex-1 overflow-hidden rounded-lg border border-zinc-800 relative">
                    <KnowledgeGraph />
                </div>
            </div>
        );
    }

    if (tab === 'langgraph') {
        return (
            <div className="h-full flex flex-col">
                <div className="flex justify-between items-center mb-4 px-4 pt-4">
                    <h2 className="text-xl font-bold text-white">LangGraph: {project.name}</h2>
                    <button onClick={() => router.push(`/projects/${projectId}`)} className="text-zinc-400 hover:text-white">Back</button>
                </div>
                <div className="flex-1 overflow-hidden rounded-lg border border-zinc-800 relative">
                    <LangGraphView projectId={projectId} />
                </div>
            </div>
        );
    }

    if (tab === 'vector') {
        return (
            <div className="h-full flex flex-col">
                <div className="flex justify-between items-center mb-4 px-4 pt-4">
                    <h2 className="text-xl font-bold text-white">Vector Map: {project.name}</h2>
                    <button onClick={() => router.push(`/projects/${projectId}`)} className="text-zinc-400 hover:text-white">Back</button>
                </div>
                <div className="flex-1 overflow-hidden rounded-lg border border-zinc-800 relative">
                    <VectorMapView />
                </div>
            </div>
        );
    }

    if (tab === 'test-group') {
        return (
            <div className="h-full flex flex-col">
                <div className="flex justify-between items-center mb-4 px-4 pt-4">
                    <h2 className="text-xl font-bold text-white">Agent Test Group: {project.name}</h2>
                    <button onClick={() => router.push(`/projects/${projectId}`)} className="text-zinc-400 hover:text-white">Back</button>
                </div>
                <div className="flex-1 overflow-hidden rounded-lg border border-zinc-800 relative">
                    <AgentTestGroup projectId={projectId} />
                </div>
            </div>
        );
    }

    // Default Dashboard View
    return (
        <div>
            <div className="flex justify-between items-start mb-8">
                <div>
                    <div className="flex items-center space-x-3 mb-2">
                        <h1 className="text-3xl font-bold">{project.name}</h1>
                        <span className={`text-xs px-2 py-1 rounded ${project.project_type === 'NEW' ? 'bg-green-900 text-green-200' : 'bg-blue-900 text-blue-200'
                            }`}>
                            {project.project_type}
                        </span>
                    </div>
                    <p className="text-zinc-400">{project.description}</p>
                </div>
                <div className="flex space-x-3">
                    <button
                        onClick={handleDelete}
                        className="px-4 py-2 bg-red-900/30 text-red-400 border border-red-900 rounded-lg hover:bg-red-900/50 transition-colors"
                    >
                        Delete Project
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
                {/* Quick Actions */}
                <div className="bg-zinc-900 p-6 rounded-lg border border-zinc-800">
                    <h3 className="text-lg font-semibold mb-4">Actions</h3>
                    <div className="space-y-3">
                        <Link
                            href={`/projects/${projectId}/agents`}
                            className="block w-full text-center py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg transition-colors"
                        >
                            Configure Agents
                        </Link>
                        <Link
                            href={`/projects/${projectId}/execute`}
                            className="block w-full text-center py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg transition-colors"
                        >
                            Start Workflow
                        </Link>
                        <Link
                            href={`/projects/${projectId}?tab=test-group`}
                            className="block w-full text-center py-2 bg-indigo-900/40 hover:bg-indigo-800/60 text-indigo-300 border border-indigo-500/30 rounded-lg transition-colors"
                        >
                            Agent Test Group
                        </Link>
                        <Link
                            href={`/projects/${projectId}/traces`}
                            className="block w-full text-center py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg transition-colors"
                        >
                            View Traces
                        </Link>
                    </div>
                </div>

                {/* Stats / Info */}
                <div className="bg-zinc-900 p-6 rounded-lg border border-zinc-800 col-span-2">
                    <h3 className="text-lg font-semibold mb-4">Project Info</h3>
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <div className="text-sm text-zinc-500">Project ID</div>
                            <div className="font-mono text-sm">{project.id}</div>
                        </div>
                        <div>
                            <div className="text-sm text-zinc-500">Created At</div>
                            <div>{new Date(project.created_at).toLocaleString()}</div>
                        </div>
                        {project.repo_path && (
                            <div className="col-span-2">
                                <div className="text-sm text-zinc-500">Local Path</div>
                                <div className="font-mono text-sm bg-zinc-950 p-2 rounded border border-zinc-800">
                                    {project.repo_path}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Recent Activity Placeholder */}
            <div className="bg-zinc-900 p-6 rounded-lg border border-zinc-800">
                <h3 className="text-lg font-semibold mb-4">Recent Activity</h3>
                <div className="text-zinc-500 text-center py-8 italic">
                    No recent activity
                </div>
            </div>
        </div>
    );
}
