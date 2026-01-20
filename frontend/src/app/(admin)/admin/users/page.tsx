'use client';

import React, { useEffect, useState } from 'react';
import api from '@/lib/axios-config';

interface UserQuota {
    max_daily_jobs: number;
    max_concurrent_jobs: number;
    max_storage_mb: number;
    current_daily_jobs: number;
    current_storage_mb: number;
}

interface User {
    id: string;
    username: string;
    email: string;
    role: string;
    is_active: boolean;
    quota: UserQuota;
    allowed_domains: string[];
}

export default function UsersPage() {
    const [users, setUsers] = useState<User[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedUser, setSelectedUser] = useState<User | null>(null);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [quotaForm, setQuotaForm] = useState<UserQuota>({
        max_daily_jobs: 100,
        max_concurrent_jobs: 5,
        max_storage_mb: 1024,
        current_daily_jobs: 0,
        current_storage_mb: 0
    });

    const fetchUsers = async () => {
        try {
            const response = await api.get('/admin/users');
            setUsers(response.data);
        } catch (error) {
            console.error("Failed to fetch users", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchUsers();
    }, []);

    const handleEditQuota = (user: User) => {
        setSelectedUser(user);
        setQuotaForm(user.quota);
        setIsModalOpen(true);
    };

    const handleSaveQuota = async () => {
        if (!selectedUser) return;
        try {
            await api.patch(`/admin/users/${selectedUser.id}/quota`, quotaForm);
            setIsModalOpen(false);
            fetchUsers(); // Refresh list
            alert("Quota updated successfully");
        } catch (error) {
            console.error("Failed to update quota", error);
            alert("Failed to update quota");
        }
    };

    if (loading) return <div>Loading users...</div>;

    return (
        <div>
            <h2 className="text-2xl font-bold mb-6">User Management</h2>

            <div className="bg-gray-800 rounded-lg overflow-hidden">
                <table className="w-full text-left">
                    <thead className="bg-gray-700">
                        <tr>
                            <th className="p-4">ID</th>
                            <th className="p-4">Username</th>
                            <th className="p-4">Role</th>
                            <th className="p-4">Quota (Daily/Concurrent)</th>
                            <th className="p-4">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {users.map(user => (
                            <tr key={user.id} className="border-t border-gray-700 hover:bg-gray-750">
                                <td className="p-4">{user.id}</td>
                                <td className="p-4">{user.username}</td>
                                <td className="p-4">
                                    <span className={`px-2 py-1 rounded text-xs ${user.role === 'super_admin' ? 'bg-purple-900 text-purple-200' : 'bg-blue-900 text-blue-200'}`}>
                                        {user.role}
                                    </span>
                                </td>
                                <td className="p-4">
                                    {user.quota.max_daily_jobs} / {user.quota.max_concurrent_jobs}
                                </td>
                                <td className="p-4">
                                    <button
                                        onClick={() => handleEditQuota(user)}
                                        className="bg-blue-600 hover:bg-blue-500 text-white px-3 py-1 rounded text-sm"
                                    >
                                        Edit Quota
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Edit Quota Modal */}
            {isModalOpen && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                    <div className="bg-gray-800 p-6 rounded-lg w-96 border border-gray-700">
                        <h3 className="text-xl font-bold mb-4">Edit Quota: {selectedUser?.username}</h3>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Max Daily Jobs</label>
                                <input
                                    type="number"
                                    value={quotaForm.max_daily_jobs}
                                    onChange={(e) => setQuotaForm({ ...quotaForm, max_daily_jobs: parseInt(e.target.value) })}
                                    className="w-full bg-gray-700 border border-gray-600 rounded p-2 text-white"
                                />
                            </div>
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Max Concurrent Jobs</label>
                                <input
                                    type="number"
                                    value={quotaForm.max_concurrent_jobs}
                                    onChange={(e) => setQuotaForm({ ...quotaForm, max_concurrent_jobs: parseInt(e.target.value) })}
                                    className="w-full bg-gray-700 border border-gray-600 rounded p-2 text-white"
                                />
                            </div>
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Max Storage (MB)</label>
                                <input
                                    type="number"
                                    value={quotaForm.max_storage_mb}
                                    onChange={(e) => setQuotaForm({ ...quotaForm, max_storage_mb: parseInt(e.target.value) })}
                                    className="w-full bg-gray-700 border border-gray-600 rounded p-2 text-white"
                                />
                            </div>
                        </div>

                        <div className="flex justify-end mt-6 space-x-2">
                            <button
                                onClick={() => setIsModalOpen(false)}
                                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-white"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleSaveQuota}
                                className="px-4 py-2 bg-green-600 hover:bg-green-500 rounded text-white"
                            >
                                Save
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
