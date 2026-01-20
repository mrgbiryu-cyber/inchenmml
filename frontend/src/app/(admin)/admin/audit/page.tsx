export default function AuditPage() {
    return (
        <div>
            <h2 className="text-2xl font-bold mb-4">Audit Log</h2>
            <p className="text-gray-400">System audit logs will be displayed here.</p>
            <div className="mt-6 bg-gray-800 rounded-lg p-4 border border-gray-700">
                <div className="text-sm text-gray-500 italic">No logs found.</div>
            </div>
        </div>
    );
}
