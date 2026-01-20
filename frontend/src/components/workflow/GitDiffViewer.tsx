import React from 'react';

interface GitDiffViewerProps {
    diff: string;
    filesModified: string[];
}

export default function GitDiffViewer({ diff, filesModified }: GitDiffViewerProps) {
    if (!diff) return null;

    return (
        <div className="bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden flex flex-col h-full">
            <div className="p-4 border-b border-zinc-800 font-semibold bg-zinc-900 flex justify-between items-center">
                <span>Git Changes</span>
                <span className="text-xs text-zinc-400">{filesModified.length} files modified</span>
            </div>
            <div className="flex-1 overflow-auto p-4">
                <pre className="font-mono text-xs text-zinc-300 whitespace-pre-wrap">
                    {diff.split('\n').map((line, i) => {
                        let colorClass = "text-zinc-300";
                        if (line.startsWith('+') && !line.startsWith('+++')) colorClass = "text-green-400 bg-green-900/20";
                        if (line.startsWith('-') && !line.startsWith('---')) colorClass = "text-red-400 bg-red-900/20";
                        if (line.startsWith('@@')) colorClass = "text-blue-400";

                        return (
                            <div key={i} className={`${colorClass} px-1`}>
                                {line}
                            </div>
                        );
                    })}
                </pre>
            </div>
        </div>
    );
}
