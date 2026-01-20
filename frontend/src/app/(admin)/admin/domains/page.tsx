'use client';

import React, { useEffect, useState } from 'react';
import api from '@/lib/axios-config';

interface Domain {
    id: string;
    name: string;
    repo_root: string;
    description?: string;
    owner_id: string;
    is_active: boolean;
    agent_config: {
        model?: string;
        provider?: string;
        [key: string]: any;
    };
}

export default function DomainsPage() {
    const [domains, setDomains] = useState<Domain[]>([]); // Currently no API to list domains, using mock or need to add endpoint?
    // Wait, admin.py doesn't have list_domains endpoint! It has create_domain.
    // I should add list_domains to admin.py or just show created ones if I can't fetch.
    // For now, I'll assume I can't fetch list unless I add the endpoint.
    // But the user asked to "create domain form".
    // I will implement the form first.

    const [form, setForm] = useState({
        id: '',
        name: '',
        repo_root: '',
        description: '',
        owner_id: 'admin', // Default to admin for now
        agent_model: 'gemini-pro',
        agent_provider: 'OPENROUTER'
    });

    const handleCreateDomain = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const payload = {
                id: form.id,
                name: form.name,
                repo_root: form.repo_root,
                description: form.description,
                owner_id: form.owner_id,
                agent_config: {
                    model: form.agent_model,
                    provider: form.agent_provider
                }
            };

            await api.post('/admin/domains', payload);
            alert("Domain registered successfully");
            setForm({ ...form, id: '', name: '', repo_root: '', description: '' });
            // Refresh list if available
        } catch (error) {
            console.error("Failed to create domain", error);
            alert("Failed to create domain");
        }
    };

    return (
        <div>
            <h2 className="text-2xl font-bold mb-6">Domain Management</h2>

            <div className="bg-gray-800 p-6 rounded-lg border border-gray-700 max-w-2xl">
                <h3 className="text-xl font-semibold mb-4">Register New Domain</h3>
                <form onSubmit={handleCreateDomain} className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm text-gray-400 mb-1">Domain ID</label>
                            <input
                                type="text"
                                value={form.id}
                                onChange={(e) => setForm({ ...form, id: e.target.value })}
                                placeholder="e.g. project-alpha"
                                className="w-full bg-gray-700 border border-gray-600 rounded p-2 text-white"
                                required
                            />
                        </div>
                        <div>
                            <label className="block text-sm text-gray-400 mb-1">Project Name</label>
                            <input
                                type="text"
                                value={form.name}
                                onChange={(e) => setForm({ ...form, name: e.target.value })}
                                placeholder="My Project"
                                className="w-full bg-gray-700 border border-gray-600 rounded p-2 text-white"
                                required
                            />
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm text-gray-400 mb-1">Repository Root Path</label>
                        <input
                            type="text"
                            value={form.repo_root}
                            onChange={(e) => setForm({ ...form, repo_root: e.target.value })}
                            placeholder="/path/to/project"
                            className="w-full bg-gray-700 border border-gray-600 rounded p-2 text-white"
                            required
                        />
                    </div>

                    <div>
                        <label className="block text-sm text-gray-400 mb-1">Description</label>
                        <textarea
                            value={form.description}
                            onChange={(e) => setForm({ ...form, description: e.target.value })}
                            className="w-full bg-gray-700 border border-gray-600 rounded p-2 text-white h-20"
                        />
                    </div>

                    <div className="border-t border-gray-700 pt-4 mt-4">
                        <h4 className="text-lg font-medium mb-3">Agent Configuration</h4>
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Provider</label>
                                <select
                                    value={form.agent_provider}
                                    onChange={(e) => setForm({ ...form, agent_provider: e.target.value })}
                                    className="w-full bg-gray-700 border border-gray-600 rounded p-2 text-white"
                                >
                                    <option value="OPENROUTER">OpenRouter</option>
                                    <option value="OLLAMA">Ollama (Local)</option>
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Model</label>
                                <select
                                    value={form.agent_model}
                                    onChange={(e) => setForm({ ...form, agent_model: e.target.value })}
                                    className="w-full bg-gray-700 border border-gray-600 rounded p-2 text-white"
                                >
                                    <option value="gemini-pro">Google Gemini Pro</option>
                                    <option value="gpt-4-turbo">GPT-4 Turbo</option>
                                    <option value="claude-3-opus">Claude 3 Opus</option>
                                    <option value="llama3">Llama 3 (Local)</option>
                                    <option value="mistral">Mistral (Local)</option>
                                </select>
                            </div>
                        </div>
                    </div>

                    <div className="flex justify-end mt-6">
                        <button
                            type="submit"
                            className="px-6 py-2 bg-purple-600 hover:bg-purple-500 rounded text-white font-medium"
                        >
                            Register Domain
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
