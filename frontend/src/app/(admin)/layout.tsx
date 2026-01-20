import React from 'react';
import FloatingChatbot from '@/components/master/FloatingChatbot';

export default function AdminLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="flex h-screen bg-gray-900 text-white">
            {/* Sidebar Area */}
            <div className="w-64 border-r border-gray-800">
                <div className="p-4 text-xl font-bold border-b border-gray-800">
                    BUJA Admin
                </div>
                <nav className="mt-4">
                    <a href="/admin/dashboard" className="block px-4 py-2 hover:bg-gray-800">Dashboard</a>
                    <a href="/admin/users" className="block px-4 py-2 hover:bg-gray-800">Users</a>
                    <a href="/admin/domains" className="block px-4 py-2 hover:bg-gray-800">Domains</a>
                    <a href="/admin/audit" className="block px-4 py-2 hover:bg-gray-800">Audit Log</a>
                    <div className="border-t border-gray-800 my-2"></div>
                    <a href="/settings" className="block px-4 py-2 hover:bg-gray-800 text-purple-400">Settings</a>
                    <a href="/" className="block px-4 py-2 hover:bg-gray-800 text-gray-400">Back to App</a>
                </nav>
            </div>

            {/* Main Content */}
            <div className="flex-1 overflow-auto">
                <header className="h-16 border-b border-gray-800 flex items-center px-6">
                    <h1 className="text-lg font-semibold">Admin Console</h1>
                </header>
                <main className="p-6">
                    {children}
                </main>
            </div>
            <FloatingChatbot />
        </div>
    );
}
