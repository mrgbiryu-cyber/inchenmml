'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useProjectStore } from '@/store/projectStore';
import api from '@/lib/axios-config';
import { Folder, MessageSquare, Settings, Shield, Menu, X } from 'lucide-react';
import clsx from 'clsx';

export default function Sidebar() {
    const pathname = usePathname();
    const router = useRouter();
    const { currentProjectId, setCurrentProjectId, projects, setProjects } = useProjectStore();
    const [loading, setLoading] = useState(false);
    const [isOpen, setIsOpen] = useState(false); // Mobile state

    useEffect(() => {
        fetchProjects();
    }, []);

    const fetchProjects = async () => {
        try {
            setLoading(true);
            const response = await api.get('/projects/');
            setProjects(response.data);
        } catch (error) {
            console.error("Failed to fetch projects in sidebar", error);
        } finally {
            setLoading(false);
        }
    };

    const isActive = (path: string) => {
        return pathname.startsWith(path) ? 'bg-zinc-800 text-white shadow-sm' : 'text-zinc-400 hover:bg-zinc-800/50 hover:text-white';
    };

    return (
        <>
            {/* Mobile Toggle Button */}
            <button 
                onClick={() => setIsOpen(!isOpen)}
                className="fixed top-4 left-4 z-[60] p-2 bg-zinc-900 border border-zinc-800 rounded-lg text-white lg:hidden shadow-xl"
            >
                {isOpen ? <X size={20} /> : <Menu size={20} />}
            </button>

            {/* Backdrop */}
            {isOpen && (
                <div 
                    className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[50] lg:hidden"
                    onClick={() => setIsOpen(false)}
                />
            )}

            <div className={clsx(
                "fixed inset-y-0 left-0 z-[55] w-64 bg-zinc-950 border-r border-zinc-800 flex flex-col transition-transform duration-300 lg:static lg:translate-x-0",
                isOpen ? "translate-x-0" : "-translate-x-full"
            )}>
                <div className="p-6">
                    <Link href="/projects" className="flex items-center gap-2 group" onClick={() => setIsOpen(false)}>
                        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-600 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-900/20 group-hover:scale-105 transition-transform">
                            <span className="text-white font-bold text-xs">B</span>
                        </div>
                        <h1 className="text-lg font-bold text-white tracking-tight">BUJA Platform</h1>
                    </Link>
                </div>

                <div className="flex-1 px-4 space-y-6 overflow-y-auto scrollbar-hide">
                    {/* Main Navigation */}
                    <nav className="space-y-1">
                        <Link
                            href="/projects"
                            onClick={() => setIsOpen(false)}
                            className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-all text-sm font-medium ${isActive('/projects') && !pathname.includes('master-settings') ? 'bg-zinc-800 text-white' : 'text-zinc-400 hover:bg-zinc-800/50 hover:text-white'}`}
                        >
                            <Folder size={18} />
                            Projects
                        </Link>
                        <Link
                            href="/chat"
                            onClick={() => setIsOpen(false)}
                            className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-all text-sm font-medium ${isActive('/chat')}`}
                        >
                            <MessageSquare size={18} />
                            Global Chat
                        </Link>
                    </nav>

                    {/* Projects Section */}
                    <div>
                        <div className="px-3 mb-2 flex items-center justify-between">
                            <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">Active Projects</span>
                        </div>
                        <div className="space-y-0.5">
                            {loading ? (
                                <div className="px-3 py-2 text-xs text-zinc-600 animate-pulse italic">Loading projects...</div>
                            ) : projects.length === 0 ? (
                                <div className="px-3 py-2 text-xs text-zinc-600 italic">No projects found</div>
                            ) : (
                                projects.map((project) => (
                                    <button
                                        key={project.id}
                                        onClick={() => {
                                            setCurrentProjectId(project.id);
                                            setIsOpen(false);
                                            router.push(`/projects/${project.id}`);
                                        }}
                                        className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-all text-sm font-medium text-left ${currentProjectId === project.id ? 'bg-indigo-600/10 text-indigo-400' : 'text-zinc-500 hover:bg-zinc-800/50 hover:text-zinc-300'}`}
                                    >
                                        <div className={`w-1.5 h-1.5 rounded-full ${currentProjectId === project.id ? 'bg-indigo-500' : 'bg-zinc-700'}`}></div>
                                        <span className="truncate">{project.name}</span>
                                    </button>
                                ))
                            )}
                        </div>
                    </div>

                    {/* System Section */}
                    <div>
                        <div className="px-3 mb-2">
                            <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">System</span>
                        </div>
                        <nav className="space-y-1">
                            <Link
                                href="/master-settings"
                                onClick={() => setIsOpen(false)}
                                className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-all text-sm font-medium ${isActive('/master-settings')}`}
                            >
                                <Shield size={18} />
                                Master Butler
                            </Link>
                        </nav>
                    </div>
                </div>

                <div className="p-4 mt-auto border-t border-zinc-800/50">
                    <div className="flex items-center gap-3 p-2 rounded-xl bg-zinc-900/50 border border-zinc-800/50">
                        <div className="w-10 h-10 rounded-lg bg-gradient-to-tr from-zinc-800 to-zinc-700 flex items-center justify-center">
                            <span className="text-zinc-400 font-bold">U</span>
                        </div>
                        <div className="flex-1 min-w-0">
                            <div className="text-xs font-bold text-white truncate">Administrator</div>
                            <div className="text-[10px] text-zinc-500 font-medium">Pro Plan</div>
                        </div>
                        <button className="p-1.5 text-zinc-500 hover:text-white transition-colors">
                            <Settings size={16} />
                        </button>
                    </div>
                </div>
            </div>
        </>
    );
}
