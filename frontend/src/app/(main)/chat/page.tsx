'use client';

import MainLayout from '@/components/shared/layout/MainLayout';
import KnowledgeGraph from '@/components/graph/KnowledgeGraph';
import LangGraphView from '@/components/langgraph/LangGraphView';
import VectorMapView from '@/components/vectormap/VectorMapView';
import LogConsole from '@/components/chat/LogConsole';
import { Send, Paperclip, Mic, FileText } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import api from '@/lib/axios-config';
import { useDomainStore } from '@/store/useDomainStore';

interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    hasLogs?: boolean;
}

import ChatInterface from '@/components/chat/ChatInterface';

export default function ChatPage() {
    const [activeTab, setActiveTab] = useState('chat'); // 'chat' | 'graph' | 'langgraph' | 'vector'
    const [showLogs, setShowLogs] = useState(false);
    const [logs, setLogs] = useState<string[]>([]); // Still needed for LogConsole if used elsewhere, but ChatInterface has its own.

    // ... (keep activeTab logic)

    return (
        <MainLayout>
            <div className="flex flex-col h-full relative bg-black text-white">

                {/* View Switcher Removed */}

                {/* Content Area */}
                <div className="flex-1 overflow-hidden relative">
                    {/* GRAPH VIEW */}
                    <div className={`absolute inset-0 transition-opacity duration-300 ${activeTab === 'graph' ? 'opacity-100 z-10' : 'opacity-0 z-0 pointer-events-none'}`}>
                        <KnowledgeGraph />
                    </div>

                    {/* LANGGRAPH VIEW */}
                    <div className={`absolute inset-0 transition-opacity duration-300 ${activeTab === 'langgraph' ? 'opacity-100 z-10' : 'opacity-0 z-0 pointer-events-none'}`}>
                        <LangGraphView />
                    </div>

                    {/* VECTOR MAP VIEW */}
                    <div className={`absolute inset-0 transition-opacity duration-300 ${activeTab === 'vector' ? 'opacity-100 z-10' : 'opacity-0 z-0 pointer-events-none'}`}>
                        <VectorMapView />
                    </div>

                    {/* CHAT VIEW */}
                    <div className={`absolute inset-0 flex flex-col transition-opacity duration-300 ${activeTab === 'chat' ? 'opacity-100 z-10' : 'opacity-0 z-0 pointer-events-none'}`}>
                        <ChatInterface />
                    </div>
                </div>
            </div>
        </MainLayout>
    );
}

