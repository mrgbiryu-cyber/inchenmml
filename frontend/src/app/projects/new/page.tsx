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
        project_type: 'GROWTH_SUPPORT',
        repo_path: ''
    });

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        try {
            const res = await api.post('/projects/', form);
            // Redirect straight to project chat for Interview
            router.push(`/chat?projectId=${res.data.id}`);
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
