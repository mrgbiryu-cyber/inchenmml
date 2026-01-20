import { useState, useEffect } from 'react';
import api from '@/lib/axios-config';

interface WorkerStatus {
    status: 'online' | 'offline' | 'busy';
    lastHeartbeat: string;
    workerId: string;
}

export function useWorker() {
    const [status, setStatus] = useState<WorkerStatus['status']>('offline');
    const [lastHeartbeat, setLastHeartbeat] = useState<string | null>(null);

    useEffect(() => {
        const checkStatus = async () => {
            try {
                // In real app: GET /api/v1/workers/status
                // For now, mock it or try to hit a real endpoint if available
                // Since we don't have a status endpoint, we'll mock it based on success
                // But wait, we have /api/v1/workers/heartbeat (POST). 
                // We need a GET endpoint to check status.
                // Let's assume we implement GET /api/v1/workers/active later.
                // For now, we'll simulate "online" if backend is reachable.

                // Simple health check to backend
                await api.get('/health');
                setStatus('online');
                setLastHeartbeat(new Date().toISOString());
            } catch (error) {
                setStatus('offline');
            }
        };

        // Check immediately
        checkStatus();

        // Poll every 5 seconds
        const interval = setInterval(checkStatus, 5000);

        return () => clearInterval(interval);
    }, []);

    return { status, lastHeartbeat };
}
