'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/axios-config';

export default function NewProjectPage() {
    const router = useRouter();
    const [loading, setLoading] = useState(false);
    const [form, setForm] = useState({
        name: '',
        description: '',
        project_type: 'NEW', // 'NEW' | 'EXISTING'
        repo_path: ''
    });

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        try {
            await api.post('/projects/', form);
            router.push('/projects');
        } catch (error) {
            console.error("Failed to create project", error);
            alert("Failed to create project");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="max-w-2xl mx-auto">
            <h1 className="text-3xl font-bold mb-8">Create New Project</h1>

            <form onSubmit={handleSubmit} className="space-y-6 bg-zinc-900 p-8 rounded-lg border border-zinc-800">
                <div>
                    <label className="block text-sm font-medium text-zinc-400 mb-2">Project Name</label>
                    <input
                        type="text"
                        value={form.name}
                        onChange={(e) => setForm({ ...form, name: e.target.value })}
                        className="w-full bg-zinc-800 border border-zinc-700 rounded-lg p-3 text-white focus:ring-2 focus:ring-purple-500 focus:outline-none"
                        placeholder="My Awesome AI Project"
                        required
                    />
                </div>

                <div>
                    <label className="block text-sm font-medium text-zinc-400 mb-2">Description</label>
                    <textarea
                        value={form.description}
                        onChange={(e) => setForm({ ...form, description: e.target.value })}
                        className="w-full bg-zinc-800 border border-zinc-700 rounded-lg p-3 text-white h-32 focus:ring-2 focus:ring-purple-500 focus:outline-none"
                        placeholder="Describe your project..."
                    />
                </div>

                <div>
                    <label className="block text-sm font-medium text-zinc-400 mb-2">Project Type</label>
                    <div className="grid grid-cols-2 gap-4">
                        <button
                            type="button"
                            onClick={() => setForm({ ...form, project_type: 'NEW' })}
                            className={`p-4 rounded-lg border text-center transition-colors ${form.project_type === 'NEW'
                                    ? 'bg-purple-900/30 border-purple-500 text-white'
                                    : 'bg-zinc-800 border-zinc-700 text-zinc-400 hover:bg-zinc-750'
                                }`}
                        >
                            <div className="font-semibold mb-1">New Project</div>
                            <div className="text-xs opacity-70">Start from scratch</div>
                        </button>
                        <button
                            type="button"
                            onClick={() => setForm({ ...form, project_type: 'EXISTING' })}
                            className={`p-4 rounded-lg border text-center transition-colors ${form.project_type === 'EXISTING'
                                    ? 'bg-purple-900/30 border-purple-500 text-white'
                                    : 'bg-zinc-800 border-zinc-700 text-zinc-400 hover:bg-zinc-750'
                                }`}
                        >
                            <div className="font-semibold mb-1">Existing Codebase</div>
                            <div className="text-xs opacity-70">Import local repository</div>
                        </button>
                    </div>
                </div>

                {form.project_type === 'EXISTING' && (
                    <div>
                        <label className="block text-sm font-medium text-zinc-400 mb-2">Local Repository Path</label>
                        <input
                            type="text"
                            value={form.repo_path}
                            onChange={(e) => setForm({ ...form, repo_path: e.target.value })}
                            className="w-full bg-zinc-800 border border-zinc-700 rounded-lg p-3 text-white focus:ring-2 focus:ring-purple-500 focus:outline-none"
                            placeholder="/path/to/your/project"
                            required
                        />
                        <p className="text-xs text-zinc-500 mt-1">
                            The worker must have access to this path.
                        </p>
                    </div>
                )}

                <div className="flex justify-end space-x-4 pt-4 border-t border-zinc-800">
                    <button
                        type="button"
                        onClick={() => router.back()}
                        className="px-6 py-2 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        type="submit"
                        disabled={loading}
                        className="px-6 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
                    >
                        {loading ? 'Creating...' : 'Create Project'}
                    </button>
                </div>
            </form>
        </div>
    );
}
