export default function DashboardPage() {
    return (
        <div>
            <h2 className="text-2xl font-bold mb-4">Dashboard</h2>
            <p className="text-gray-400">Welcome to the Super Admin Dashboard.</p>
            <div className="grid grid-cols-3 gap-6 mt-6">
                <div className="bg-gray-800 p-6 rounded-lg border border-gray-700">
                    <h3 className="text-lg font-semibold mb-2">System Status</h3>
                    <div className="text-green-400">Operational</div>
                </div>
                <div className="bg-gray-800 p-6 rounded-lg border border-gray-700">
                    <h3 className="text-lg font-semibold mb-2">Active Jobs</h3>
                    <div className="text-2xl font-bold">12</div>
                </div>
                <div className="bg-gray-800 p-6 rounded-lg border border-gray-700">
                    <h3 className="text-lg font-semibold mb-2">Total Users</h3>
                    <div className="text-2xl font-bold">5</div>
                </div>
            </div>
        </div>
    );
}
