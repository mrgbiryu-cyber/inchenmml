import React, { memo } from 'react';
import { Handle, Position } from 'reactflow';

interface AgentNodeProps {
    data: {
        label: string;
        role: string;
        model: string;
        onEdit?: () => void;
    };
}

export default memo(function AgentNode({ data }: AgentNodeProps) {
    return (
        <div className="bg-zinc-900 border-2 border-zinc-700 rounded-lg p-4 min-w-[200px] shadow-lg hover:border-purple-500 transition-colors">
            <Handle type="target" position={Position.Top} className="w-3 h-3 bg-zinc-500" />

            <div className="flex justify-between items-start mb-2">
                <div className="font-bold text-white">{data.label}</div>
                <span className="text-xs px-2 py-0.5 rounded bg-purple-900 text-purple-200">
                    {data.role}
                </span>
            </div>

            <div className="text-xs text-zinc-400 mb-3">
                Model: {data.model}
            </div>

            {data.onEdit && (
                <button
                    onClick={data.onEdit}
                    className="w-full py-1 text-xs bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded transition-colors"
                >
                    Edit Configuration
                </button>
            )}

            <Handle type="source" position={Position.Bottom} className="w-3 h-3 bg-zinc-500" />
        </div>
    );
});
