'use client';

import { useState, useEffect } from 'react';
import {
    MessageSquare,
    Share2,
    Workflow,
    Map,
    Activity,
    Settings,
    LogOut,
    Plus,
    Search,
    Menu,
    X,
    Cpu,
    StopCircle,
    CheckCircle2,
    AlertCircle
} from 'lucide-react';
import { useAuthStore } from '@/store/useAuthStore';
import { useRouter } from 'next/navigation';
import clsx from 'clsx';
import { useWorker } from '@/hooks/useWorker';
import Link from 'next/link';
import { useParams, usePathname } from 'next/navigation';
import api from '@/lib/axios-config';
import { Project } from '@/types/project';
import Sidebar from '@/components/layout/Sidebar';

interface MainLayoutProps {
    children: React.ReactNode;
}

export default function MainLayout({ children }: MainLayoutProps) {
    const params = useParams();
    const pathname = usePathname();
    const projectId = params.projectId as string;

    return (
        <div className="flex h-screen w-full bg-zinc-950 text-zinc-50 overflow-hidden">
            {/* Unified Sidebar component which handles mobile responsive */}
            <Sidebar />

            {/* CENTER PANEL (Main Content) */}
            <main className="flex flex-1 flex-col min-w-0 bg-zinc-950 relative">
                {/* Top Navigation Tabs */}
                <header className="flex h-14 items-center justify-center border-b border-zinc-800 px-4 bg-zinc-950/50 backdrop-blur-md z-40">
                    <div className="flex items-center gap-1 overflow-x-auto no-scrollbar pl-12 lg:pl-0">
                        {[
                            { id: 'chat', label: 'Chat', icon: MessageSquare, href: `/projects/${projectId}?tab=chat` },
                            { id: 'graph', label: 'Graph', icon: Share2, href: `/projects/${projectId}?tab=graph` },
                            { id: 'langgraph', label: 'LangGraph', icon: Workflow, href: `/projects/${projectId}?tab=langgraph` },
                            { id: 'vector', label: 'Vector Map', icon: Map, href: `/projects/${projectId}?tab=vector` },
                            { id: 'langfuse', label: 'LangFuse', icon: Activity, href: `/projects/${projectId}/traces` },
                        ].map((tab) => (
                            projectId ? (
                                <Link
                                    key={tab.id}
                                    href={tab.href!}
                                    className={clsx(
                                        "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors whitespace-nowrap",
                                        (pathname.includes(tab.id) || (typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('tab') === tab.id))
                                            ? "bg-zinc-800 text-zinc-100"
                                            : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900"
                                    )}
                                >
                                    <tab.icon size={16} />
                                    <span className="hidden sm:inline">{tab.label}</span>
                                </Link>
                            ) : null
                        ))}
                    </div>
                </header>

                {/* Content Area */}
                <div className="flex-1 overflow-hidden relative">
                    {children}
                </div>
            </main>
        </div>
    );
}
