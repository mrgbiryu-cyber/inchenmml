import React from 'react';
import Sidebar from '@/components/layout/Sidebar';

export default function ProjectsLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="flex h-screen bg-zinc-950 text-zinc-50 overflow-hidden">
            <Sidebar />
            <main className="flex-1 overflow-auto p-4 md:p-8 pt-16 lg:pt-8">
                {children}
            </main>
        </div>
    );
}
