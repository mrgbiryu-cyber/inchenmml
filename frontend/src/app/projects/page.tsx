'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import api from '@/lib/axios-config';
import { Project } from '@/types/project';

export default function ProjectsPage() {
    const [projects, setProjects] = useState<Project[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchProjects();
    }, []);

    const fetchProjects = async () => {
        try {
            const response = await api.get('/projects/');
            setProjects(response.data);
        } catch (error) {
            console.error("Failed to fetch projects", error);
        } finally {
            setLoading(false);
        }
    };

    if (loading) return <div className="p-8 text-zinc-400">Loading projects...</div>;

    return (
        <div className="p-8">
            <div className="flex justify-between items-center mb-8">
                <h1 className="text-3xl font-bold text-white">Project Dashboard</h1>
                <Link
                    href="/projects/new"
                    className="bg-indigo-600 hover:bg-indigo-500 text-white px-6 py-2.5 rounded-xl font-bold transition-all shadow-lg shadow-indigo-900/20 flex items-center gap-2"
                >
                    <span>+ New Project</span>
                </Link>
            </div>

            {/* Master Butler Section - Separate from projects */}
            <div className="mb-12">
                <h2 className="text-sm font-bold text-zinc-500 uppercase tracking-widest mb-4">Command Center</h2>
                <Link
                    href="/master-settings"
                    className="group block max-w-xl bg-gradient-to-br from-indigo-900/40 to-purple-900/20 border border-indigo-500/30 rounded-2xl p-6 hover:border-indigo-500/60 transition-all relative overflow-hidden shadow-2xl"
                >
                    <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                        <svg width="120" height="120" viewBox="0 0 24 24" fill="currentColor" className="text-indigo-400">
                            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm0-14c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6-2.69-6-6-6zm0 10c-2.21 0-4-1.79-4-4s1.79-4 4-4 4 1.79 4 4-1.79 4-4 4z" />
                        </svg>
                    </div>
                    <div className="relative z-10">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="p-2 bg-indigo-600 rounded-lg">
                                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white"><path d="M12 2a10 10 0 1 0 10 10H12V2z"></path><path d="M12 12L2.69 7"></path><path d="M12 22V12"></path><path d="M21.31 7L12 12"></path></svg>
                            </div>
                            <div>
                                <h3 className="text-xl font-bold text-white group-hover:text-indigo-300 transition-colors">
                                    System Master Butler
                                </h3>
                                <div className="text-xs font-mono text-indigo-400/80">GLOBAL_MASTER_CONTROL</div>
                            </div>
                        </div>
                        <p className="text-zinc-400 text-sm mb-6 max-w-md">
                            Configure the global Master Agent's persona, core models, and system-wide capabilities. This is the 사령부(Master) configuration.
                        </p>
                        <div className="flex items-center gap-2 text-indigo-400 font-bold text-sm">
                            <span>Enter Command Center</span>
                            <span className="group-hover:translate-x-1 transition-transform">&rarr;</span>
                        </div>
                    </div>
                </Link>
            </div>

            <h2 className="text-sm font-bold text-zinc-500 uppercase tracking-widest mb-4">Active Projects</h2>
            {projects.length === 0 ? (
                <div className="text-center py-20 bg-zinc-900 rounded-lg border border-zinc-800">
                    <h3 className="text-xl font-medium text-zinc-300 mb-2">No projects found</h3>
                    <p className="text-zinc-500 mb-6">Get started by creating your first AI project.</p>
                    <Link
                        href="/projects/new"
                        className="text-purple-400 hover:text-purple-300 font-medium"
                    >
                        Create Project &rarr;
                    </Link>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {projects.map(project => (
                        <Link
                            key={project.id}
                            href={`/projects/${project.id}`}
                            className="block bg-zinc-900 border border-zinc-800 rounded-lg p-6 hover:border-purple-500 transition-colors group"
                        >
                            <div className="flex justify-between items-start mb-4">
                                <h3 className="text-xl font-semibold group-hover:text-purple-400 transition-colors">
                                    {project.name}
                                </h3>
                                <span className={`text-xs px-2 py-1 rounded ${project.project_type === 'NEW' ? 'bg-green-900 text-green-200' : 'bg-blue-900 text-blue-200'
                                    }`}>
                                    {project.project_type}
                                </span>
                            </div>
                            <p className="text-zinc-400 text-sm mb-4 line-clamp-2">
                                {project.description || "No description"}
                            </p>
                            <div className="flex items-center text-xs text-zinc-500">
                                <span>Updated {new Date(project.updated_at).toLocaleDateString()}</span>
                            </div>
                        </Link>
                    ))}
                </div>
            )}
        </div>
    );
}
