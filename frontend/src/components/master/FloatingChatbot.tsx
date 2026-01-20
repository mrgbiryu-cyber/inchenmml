'use client';

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';

interface ChatMessage {
    role: 'user' | 'assistant';
    content: string;
}

interface QuickLink {
    label: string;
    url: string;
}

export default function FloatingChatbot() {
    const [isOpen, setIsOpen] = useState(false);
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [input, setInput] = useState('');
    const [quickLinks, setQuickLinks] = useState<QuickLink[]>([]);
    const [isConnected, setIsConnected] = useState(false);

    const wsRef = useRef<WebSocket | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (isOpen && !wsRef.current) {
            connectWebSocket();
        }
    }, [isOpen]);

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const connectWebSocket = () => {
        const host = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
        const wsUrl = `ws://${host}:8002/api/v1/master/ws/chat`;
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log("Master Chat Connected");
            setIsConnected(true);
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                setMessages(prev => [...prev, { role: 'assistant', content: data.message }]);
                if (data.quick_links && data.quick_links.length > 0) {
                    setQuickLinks(data.quick_links);
                }
            } catch (e) {
                console.error("Failed to parse chat message", e);
            }
        };

        ws.onclose = () => {
            console.log("Master Chat Disconnected");
            setIsConnected(false);
            wsRef.current = null;
        };

        wsRef.current = ws;
    };

    const sendMessage = () => {
        if (!input.trim() || !wsRef.current) return;

        const userMsg = input.trim();
        setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
        wsRef.current.send(JSON.stringify({ message: userMsg }));
        setInput('');
        setQuickLinks([]); // Clear old links
    };

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    return (
        <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end">
            {/* Chat Window */}
            {isOpen && (
                <div className="mb-4 w-96 h-[500px] bg-zinc-900 border border-zinc-700 rounded-xl shadow-2xl flex flex-col overflow-hidden animate-in slide-in-from-bottom-10 fade-in duration-200">
                    {/* Header */}
                    <div className="p-4 bg-zinc-950 border-b border-zinc-800 flex justify-between items-center">
                        <div className="flex items-center space-x-2">
                            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
                            <span className="font-bold text-white">System Butler</span>
                        </div>
                        <button onClick={() => setIsOpen(false)} className="text-zinc-400 hover:text-white">
                            ✕
                        </button>
                    </div>

                    {/* Messages */}
                    <div className="flex-1 overflow-y-auto p-4 space-y-4">
                        {messages.length === 0 && (
                            <div className="text-center text-zinc-500 text-sm mt-10">
                                <p>Hello! I am your System Butler.</p>
                                <p>Ask me anything about your projects.</p>
                            </div>
                        )}
                        {messages.map((msg, idx) => (
                            <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                <div
                                    className={`max-w-[80%] rounded-lg px-4 py-2 text-sm ${msg.role === 'user'
                                        ? 'bg-purple-600 text-white'
                                        : 'bg-zinc-800 text-zinc-200'
                                        }`}
                                >
                                    {msg.content}
                                </div>
                            </div>
                        ))}

                        {/* Quick Links */}
                        {quickLinks.length > 0 && (
                            <div className="flex flex-wrap gap-2 mt-2">
                                {quickLinks.map((link, idx) => (
                                    <Link
                                        key={idx}
                                        href={link.url}
                                        className="text-xs bg-zinc-800 hover:bg-zinc-700 border border-zinc-600 text-blue-400 px-3 py-1 rounded-full transition-colors"
                                    >
                                        {link.label} ↗
                                    </Link>
                                ))}
                            </div>
                        )}
                        <div ref={messagesEndRef} />
                    </div>

                    {/* Input */}
                    <div className="p-4 bg-zinc-950 border-t border-zinc-800">
                        <div className="flex space-x-2">
                            <input
                                type="text"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
                                placeholder="Type a message..."
                                className="flex-1 bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500"
                            />
                            <button
                                onClick={sendMessage}
                                disabled={!isConnected}
                                className="bg-purple-600 hover:bg-purple-500 text-white rounded-lg px-4 py-2 text-sm font-bold disabled:opacity-50"
                            >
                                Send
                            </button>
                            <button
                                onClick={() => {
                                    if (wsRef.current) {
                                        wsRef.current.send(JSON.stringify({ action: "start_task" }));
                                    }
                                }}
                                disabled={!isConnected}
                                className="bg-green-600 hover:bg-green-500 text-white rounded-lg px-4 py-2 text-sm font-bold disabled:opacity-50"
                                title="Start Task based on conversation"
                            >
                                🚀 Start Task
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Toggle Button */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="w-14 h-14 bg-purple-600 hover:bg-purple-500 text-white rounded-full shadow-lg flex items-center justify-center transition-transform hover:scale-105"
            >
                {isOpen ? (
                    <span className="text-2xl">✕</span>
                ) : (
                    <span className="text-2xl">💬</span>
                )}
            </button>
        </div>
    );
}
