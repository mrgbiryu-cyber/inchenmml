import axios from 'axios';
import { useAuthStore } from '@/store/useAuthStore';

// Helper to get base URL dynamically
const getBaseURL = () => {
    if (typeof window !== 'undefined') {
        // [v4.2 Revert] Use window.location.hostname to support remote access (Tailscale, etc.)
        const hostname = (window.location.hostname === 'localhost' || window.location.hostname === '0.0.0.0') 
            ? '127.0.0.1' 
            : window.location.hostname;
        return `http://${hostname}:8002/api/v1`;
    }
    // Fallback for SSR
    return process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8002/api/v1';
};

// Create axios instance
const api = axios.create({
    baseURL: getBaseURL(),
    headers: {
        'Content-Type': 'application/json',
    },
});

// Request interceptor to add JWT token
api.interceptors.request.use(
    (config) => {
        const token = useAuthStore.getState().token;
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// Response interceptor to handle 401 (Unauthorized) and 403 (Forbidden)
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            // Token expired or invalid
            useAuthStore.getState().logout();
            // Optional: Redirect to login page if not already there
            if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
                window.location.href = '/login';
            }
        } else if (error.response?.status === 403) {
            // Permission denied
            // We can use a toast library here if available, or just log it
            // For now, we'll assume a simple alert or console error as requested "toast notification"
            // Since we don't have the toast library import here, we might need to inject it or use a global event
            console.error("Access Denied: You do not have permission to perform this action.");
            // Ideally: toast.error("권한이 없습니다");
        }
        return Promise.reject(error);
    }
);

export default api;
