'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Search, ChevronDown, Check, Loader2 } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}

interface Model {
    id: string;
    name: string;
}

interface ModelSelectorProps {
    value: string;
    onChange: (value: string) => void;
    provider: 'OLLAMA' | 'OPENROUTER';
    className?: string;
}

import api from '@/lib/axios-config';

export default function ModelSelector({ value, onChange, provider, className }: ModelSelectorProps) {
    const [isOpen, setIsOpen] = useState(false);
    const [models, setModels] = useState<Model[]>([]);
    const [loading, setLoading] = useState(false);
    const [search, setSearch] = useState('');
    const dropdownRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        fetchModels();
    }, [provider]);

    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const fetchModels = async () => {
        try {
            setLoading(true);
            const endpoint = provider === 'OLLAMA' ? '/models/ollama' : '/models/openrouter';
            const response = await api.get(endpoint);
            setModels(response.data);
        } catch (error) {
            console.error("Failed to fetch models", error);
            setModels([]);
        } finally {
            setLoading(false);
        }
    };

    const filteredModels = models.filter(m => 
        m.name.toLowerCase().includes(search.toLowerCase()) || 
        m.id.toLowerCase().includes(search.toLowerCase())
    );

    const selectedModel = models.find(m => m.id === value);

    return (
        <div className={cn("relative w-full", className)} ref={dropdownRef}>
            <button
                type="button"
                onClick={() => setIsOpen(!isOpen)}
                className="w-full flex items-center justify-between bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-left hover:border-zinc-700 transition-all focus:ring-1 focus:ring-indigo-500 outline-none"
            >
                <span className="truncate">
                    {loading ? 'Loading models...' : (selectedModel?.name || value || 'Select a model')}
                </span>
                {loading ? <Loader2 size={16} className="animate-spin text-zinc-500" /> : <ChevronDown size={16} className="text-zinc-500" />}
            </button>

            {isOpen && (
                <div className="absolute z-50 mt-1 w-full bg-zinc-900 border border-zinc-800 rounded-xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-100">
                    <div className="p-2 border-b border-zinc-800 flex items-center gap-2">
                        <Search size={14} className="text-zinc-500" />
                        <input
                            type="text"
                            placeholder="Search models..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            className="flex-1 bg-transparent text-sm focus:outline-none placeholder:text-zinc-600"
                            autoFocus
                        />
                    </div>
                    
                    <div className="max-h-60 overflow-y-auto scrollbar-thin scrollbar-thumb-zinc-800 scrollbar-track-transparent">
                        {loading ? (
                            <div className="p-4 text-center text-xs text-zinc-500">Fetching list from {provider}...</div>
                        ) : filteredModels.length === 0 ? (
                            <div className="p-4 text-center text-xs text-zinc-500">No models found.</div>
                        ) : (
                            filteredModels.map((model) => (
                                <button
                                    key={model.id}
                                    type="button"
                                    onClick={() => {
                                        onChange(model.id);
                                        setIsOpen(false);
                                        setSearch('');
                                    }}
                                    className={cn(
                                        "w-full flex items-center justify-between px-3 py-2 text-sm text-left hover:bg-zinc-800 transition-colors",
                                        value === model.id ? "text-indigo-400 bg-indigo-500/5" : "text-zinc-300"
                                    )}
                                >
                                    <div className="flex flex-col">
                                        <span className="font-medium">{model.name}</span>
                                        {model.id !== model.name && <span className="text-[10px] text-zinc-500 font-mono truncate">{model.id}</span>}
                                    </div>
                                    {value === model.id && <Check size={14} />}
                                </button>
                            ))
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
