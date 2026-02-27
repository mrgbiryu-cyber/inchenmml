'use client';

import { useEffect, useMemo, useState } from 'react';
import api from '@/lib/axios-config';

type RuleSet = {
  ruleset_id: string;
  version: string;
  status: 'draft' | 'active' | 'archived';
  description?: string;
  author?: string;
  updated_at?: string;
  [key: string]: unknown;
};

const DEFAULT_RULESET_ID = 'company-growth-default';

export default function RulesAdminPage() {
  const [rulesets, setRulesets] = useState<RuleSet[]>([]);
  const [selected, setSelected] = useState<RuleSet | null>(null);
  const [jsonText, setJsonText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [preview, setPreview] = useState<string>('');
  const parseVersionKey = (version: string): Array<number | string> => {
    const normalized = (version || '').toLowerCase().replace(/^v/, '').trim();
    if (!normalized) {
      return [0];
    }
    const parts = normalized.split(/[._-]/);
    return parts.map((part) => {
      const numeric = Number(part);
      return Number.isFinite(numeric) ? numeric : part;
    });
  };

  const makeNextVersion = (baseVersion: string) => {
    const base = (baseVersion || 'v1.0').toLowerCase().trim();
    const normalized = base.startsWith('v') ? base.slice(1) : base;
    const parts = normalized.split('.');

    if (parts.every((part) => part && /^\d+$/.test(part))) {
      if (parts.length === 1) {
        const major = Number(parts[0]);
        return `v${Number.isFinite(major) ? major + 1 : 1}.0`;
      }

      const updated = [...parts];
      const idx = updated.length - 1;
      const last = Number(updated[idx]);
      if (Number.isFinite(last)) {
        updated[idx] = String(last + 1);
        return `v${updated.join('.')}`;
      }
    }

    return `${base}-copy`;
  };

  const compareVersions = (left: string, right: string) => {
    const a = parseVersionKey(left);
    const b = parseVersionKey(right);
    const maxLen = Math.max(a.length, b.length);

    for (let i = 0; i < maxLen; i++) {
      const aItem = a[i];
      const bItem = b[i];

      if (aItem === undefined) return -1;
      if (bItem === undefined) return 1;

      const isANumber = typeof aItem === 'number';
      const isBNumber = typeof bItem === 'number';

      if (isANumber && isBNumber) {
        if (aItem !== bItem) return aItem - bItem;
        continue;
      }
      if (!isANumber && !isBNumber) {
        if (aItem !== bItem) return String(aItem).localeCompare(String(bItem));
        continue;
      }
      return isANumber ? -1 : 1;
    }

    return 0;
  };

  const sorted = useMemo(
    () => [...rulesets].sort((a, b) => compareVersions(a.version, b.version)),
    [rulesets]
  );

  const loadRulesets = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get(`/admin/rulesets?ruleset_id=${DEFAULT_RULESET_ID}`);
      setRulesets(res.data || []);
      if (res.data?.length > 0) {
        const first = res.data[res.data.length - 1];
        setSelected(first);
        setJsonText(JSON.stringify(first, null, 2));
      }
    } catch {
      setError('Failed to load rulesets');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRulesets();
  }, []);

  const onSelect = (item: RuleSet) => {
    setSelected(item);
    setJsonText(JSON.stringify(item, null, 2));
    setPreview('');
  };

  const onSave = async () => {
    if (!selected) return;
    try {
      const payload = JSON.parse(jsonText);
      setError('');
      await api.patch(`/admin/rulesets/${selected.ruleset_id}/${selected.version}`, payload);
      await loadRulesets();
    } catch (err: any) {
      if (err?.response?.data?.detail) {
        setError(`Save failed: ${err.response.data.detail}`);
      } else if (err instanceof SyntaxError) {
        setError('Save failed: invalid JSON');
      } else {
        setError('Save failed: API error');
      }
    }
  };

  const onCreate = async () => {
    const base = selected || sorted[sorted.length - 1];
    if (!base) {
      setError('Create failed: no ruleset template');
      return;
    }

    const defaultVersion = makeNextVersion(base.version);
    const next = prompt('New version (e.g., v1.2)', defaultVersion);
    if (!next) return;

    const payload: RuleSet = {
      ...base,
      version: next,
      status: 'draft',
    };

    try {
      setError('');
      await api.post('/admin/rulesets', payload);
      await loadRulesets();
    } catch (err: any) {
      if (err?.response?.data?.detail) {
        setError(`Create failed: ${err.response.data.detail}`);
      } else {
        setError('Create failed');
      }
    }
  };

  const onActivate = async () => {
    if (!selected) return;
    try {
      await api.post(`/admin/rulesets/${selected.ruleset_id}/${selected.version}/activate`);
      await loadRulesets();
      setError('');
    } catch (err: any) {
      if (err?.response?.data?.detail) {
        setError(`Activate failed: ${err.response.data.detail}`);
      } else {
        setError('Activate failed');
      }
    }
  };

  const onClone = async () => {
    if (!selected) return;
    const next = prompt('New version (e.g., v1.1)');
    if (!next) return;
    try {
      await api.post(`/admin/rulesets/${selected.ruleset_id}/${selected.version}/clone`, {
        version: next,
      });
      await loadRulesets();
      setError('');
    } catch (err: any) {
      if (err?.response?.data?.detail) {
        setError(`Clone failed: ${err.response.data.detail}`);
      } else {
        setError('Clone failed');
      }
    }
  };

  const onPreview = async () => {
    if (!selected) return;
    try {
      const sample = {
        company_name: 'Sample Co',
        years_in_business: 0,
        annual_revenue: 0,
        employee_count: 1,
        item_description: 'AI-based workflow assistant',
        has_corporation: false,
      };
      const res = await api.post(
        `/admin/rulesets/${selected.ruleset_id}/${selected.version}/preview`,
        { profile: sample }
      );
      setPreview(JSON.stringify(res.data, null, 2));
      setError('');
    } catch (err: any) {
      if (err?.response?.data?.detail) {
        setError(`Preview failed: ${err.response.data.detail}`);
      } else {
        setError('Preview failed');
      }
    }
  };

  return (
    <div className="p-6 space-y-4 text-zinc-100">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">RuleSet Tuning</h1>
        <button
          onClick={loadRulesets}
          className="px-3 py-2 rounded bg-zinc-800 hover:bg-zinc-700"
        >
          Refresh
        </button>
      </div>

      {error && <div className="text-red-400">{error}</div>}
      {loading && <div className="text-zinc-400">Loading...</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 min-h-[640px]">
        <div className="border border-zinc-800 rounded p-3 overflow-y-auto">
          <div className="font-semibold mb-2">Versions</div>
          <div className="space-y-2">
            {sorted.map((item) => (
              <button
                key={`${item.ruleset_id}-${item.version}`}
                onClick={() => onSelect(item)}
                className={`w-full text-left p-2 rounded border ${
                  selected?.version === item.version
                    ? 'border-green-500 bg-zinc-800'
                    : 'border-zinc-800 hover:bg-zinc-900'
                }`}
              >
                <div className="font-mono text-sm">{item.version}</div>
                <div className="text-xs text-zinc-400">{item.status}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="lg:col-span-2 border border-zinc-800 rounded p-3 flex flex-col gap-3">
          <div className="flex gap-2">
            <button onClick={onSave} className="px-3 py-2 rounded bg-blue-700 hover:bg-blue-600">Save</button>
            <button onClick={onCreate} className="px-3 py-2 rounded bg-zinc-700 hover:bg-zinc-600">Create</button>
            <button onClick={onClone} className="px-3 py-2 rounded bg-zinc-700 hover:bg-zinc-600">Clone</button>
            <button onClick={onActivate} className="px-3 py-2 rounded bg-green-700 hover:bg-green-600">Activate</button>
            <button onClick={onPreview} className="px-3 py-2 rounded bg-indigo-700 hover:bg-indigo-600">Preview</button>
          </div>

          <textarea
            value={jsonText}
            onChange={(e) => setJsonText(e.target.value)}
            className="flex-1 min-h-[340px] bg-zinc-950 border border-zinc-800 rounded p-3 font-mono text-xs"
          />

          <div className="border border-zinc-800 rounded p-3 bg-zinc-950">
            <div className="font-semibold mb-2">Decision Preview</div>
            <pre className="text-xs whitespace-pre-wrap">{preview || 'Run preview to inspect trace and reason codes.'}</pre>
          </div>
        </div>
      </div>
    </div>
  );
}
