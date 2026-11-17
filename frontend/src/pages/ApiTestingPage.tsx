import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FolderOpen, Loader2, Play, Plus, Save, Send, Trash2 } from 'lucide-react';
import { ErrorBanner } from '../components/FeedbackStates';
import { useToast } from '../components/ToastProvider';
import { extractErrorMessage, payguardApi } from '../services/api';
import type { ApiRequestItem, ConsoleExecutionResult } from '../types';

type KeyValue = { key: string; value: string };

const METHOD_COLORS: Record<string, string> = {
  GET: 'text-emerald-400',
  POST: 'text-sky-400',
  PUT: 'text-amber-400',
  PATCH: 'text-purple-400',
  DELETE: 'text-red-400',
};

export const ApiTestingPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const [requestName, setRequestName] = useState('Create Payment');
  const [method, setMethod] = useState<'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'>('POST');
  const [endpoint, setEndpoint] = useState('/api/v1/payments');
  const [headers, setHeaders] = useState<KeyValue[]>([{ key: 'Content-Type', value: 'application/json' }]);
  const [queryParams, setQueryParams] = useState<KeyValue[]>([]);
  const [bodyText, setBodyText] = useState(
    JSON.stringify(
      {
        order_id: 'ORD-CONSOLE-2001',
        amount: '899.00',
        currency: 'INR',
        payment_method: 'UPI',
        customer_reference: 'cust_api_tester',
        idempotency_key: `idem-console-${Date.now().toString(36)}`,
        scenario: 'successful_payment',
      },
      null,
      2,
    ),
  );
  const [signWebhook, setSignWebhook] = useState(false);
  const [invalidSignature, setInvalidSignature] = useState(false);
  const [activeEditorTab, setActiveEditorTab] = useState<'body' | 'headers' | 'params'>('body');
  const [activeResponseTab, setActiveResponseTab] = useState<'body' | 'headers'>('body');
  const [response, setResponse] = useState<ConsoleExecutionResult | null>(null);
  const [saveTargetColId, setSaveTargetColId] = useState<string>('new');
  const [newCollectionName, setNewCollectionName] = useState('');
  const [showSaveBox, setShowSaveBox] = useState(false);

  const { data: collections = [], isError, error } = useQuery({
    queryKey: ['api-collections'],
    queryFn: payguardApi.listCollections,
  });

  const executeMutation = useMutation({
    mutationFn: () => {
      let parsedBody: unknown = null;
      if (['POST', 'PUT', 'PATCH'].includes(method) && bodyText.trim()) {
        try {
          parsedBody = JSON.parse(bodyText);
        } catch {
          throw new Error('Request JSON body is malformed. Please fix JSON syntax before sending.');
        }
      }
      const headersObj = Object.fromEntries(headers.filter((h) => h.key.trim()).map((h) => [h.key.trim(), h.value]));
      const paramsObj = Object.fromEntries(
        queryParams.filter((p) => p.key.trim()).map((p) => [p.key.trim(), p.value]),
      );

      return payguardApi.executeConsoleRequest({
        method,
        endpoint: endpoint.trim(),
        headers: headersObj,
        query_params: paramsObj,
        body: parsedBody,
        sign_webhook: signWebhook,
        invalid_signature: invalidSignature,
      });
    },
    onSuccess: (res) => {
      setResponse(res);
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['webhooks'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
    onError: (err) => {
      addToast('error', 'Request Execution Error', extractErrorMessage(err));
    },
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      let parsedBody: unknown = null;
      if (bodyText.trim()) {
        try {
          parsedBody = JSON.parse(bodyText);
        } catch {
          parsedBody = bodyText;
        }
      }
      const item: ApiRequestItem = {
        id: `req-${Date.now().toString(36)}`,
        name: requestName.trim() || `${method} ${endpoint}`,
        method,
        endpoint: endpoint.trim(),
        headers: Object.fromEntries(headers.filter((h) => h.key.trim()).map((h) => [h.key.trim(), h.value])),
        query_params: Object.fromEntries(queryParams.filter((p) => p.key.trim()).map((p) => [p.key.trim(), p.value])),
        body: parsedBody,
        sign_webhook: signWebhook,
        invalid_signature: invalidSignature,
      };

      if (saveTargetColId === 'new') {
        const name = newCollectionName.trim() || 'CUSTOM COLLECTION';
        return payguardApi.createCollection({
          collection_name: name,
          description: 'Saved from API Testing Console',
          requests: [item],
        });
      }
      const existing = collections.find((c) => String(c.id) === saveTargetColId);
      if (!existing) throw new Error('Selected collection not found');
      return payguardApi.updateCollection(existing.id, {
        requests: [...(existing.configuration.requests || []), item],
      });
    },
    onSuccess: () => {
      addToast('success', 'Saved to Collection', `Request "${requestName}" persisted to database.`);
      setShowSaveBox(false);
      setNewCollectionName('');
      queryClient.invalidateQueries({ queryKey: ['api-collections'] });
    },
    onError: (err) => addToast('error', 'Save Failed', extractErrorMessage(err)),
  });

  const loadPreset = (req: ApiRequestItem) => {
    setRequestName(req.name);
    setMethod(req.method);
    setEndpoint(req.endpoint);
    setHeaders(Object.entries(req.headers || {}).map(([key, value]) => ({ key, value })));
    setQueryParams(Object.entries(req.query_params || {}).map(([key, value]) => ({ key, value })));
    setBodyText(req.body !== null && req.body !== undefined ? JSON.stringify(req.body, null, 2) : '');
    setSignWebhook(Boolean(req.sign_webhook));
    setInvalidSignature(Boolean(req.invalid_signature));
    setResponse(null);
  };

  const statusColor = !response
    ? 'text-slate-400'
    : response.status_code >= 200 && response.status_code < 300
      ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
      : response.status_code >= 400 && response.status_code < 500
        ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
        : 'bg-red-500/15 text-red-400 border-red-500/30';

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-semibold tracking-tight text-slate-100">API Testing Console</h1>
        <p className="text-xs text-slate-400 mt-0.5">
          Interactive HTTP client sending real requests to the FastAPI backend with persistent collections and server-side HMAC webhook signing.
        </p>
      </div>

      {isError && <ErrorBanner message={extractErrorMessage(error)} />}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Collections Sidebar */}
        <div className="pg-card p-3.5 lg:col-span-4 space-y-3 max-h-[760px] overflow-y-auto">
          <div className="flex items-center justify-between border-b border-[#222836] pb-2">
            <span className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
              <FolderOpen className="h-3.5 w-3.5 text-emerald-400" />
              API Collections ({collections.length})
            </span>
          </div>

          {collections.map((col) => (
            <div key={col.id} className="space-y-1">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 px-1 pt-1">
                {col.collection_name}
              </p>
              {(col.configuration?.requests || []).map((req) => (
                <button
                  key={req.id}
                  onClick={() => loadPreset(req)}
                  className="w-full text-left px-2.5 py-1.5 rounded hover:bg-[#181E2B] flex items-center gap-2 text-xs transition-colors"
                >
                  <span className={`font-mono text-[10px] font-semibold w-10 shrink-0 ${METHOD_COLORS[req.method]}`}>
                    {req.method}
                  </span>
                  <span className="text-slate-200 truncate">{req.name}</span>
                </button>
              ))}
            </div>
          ))}
        </div>

        {/* Request Builder & Response Viewer */}
        <div className="lg:col-span-8 space-y-4">
          <div className="pg-card p-4 space-y-3.5">
            <div className="flex flex-col sm:flex-row gap-2">
              <select
                value={method}
                onChange={(e) => setMethod(e.target.value as any)}
                className="pg-select font-mono text-xs font-semibold sm:w-28"
                aria-label="HTTP method"
              >
                <option value="GET">GET</option>
                <option value="POST">POST</option>
                <option value="PUT">PUT</option>
                <option value="PATCH">PATCH</option>
                <option value="DELETE">DELETE</option>
              </select>
              <input
                type="text"
                value={endpoint}
                onChange={(e) => setEndpoint(e.target.value)}
                placeholder="/api/v1/payments"
                className="pg-input font-mono text-xs flex-1"
                aria-label="Endpoint URL"
              />
              <button
                type="button"
                onClick={() => executeMutation.mutate()}
                disabled={executeMutation.isPending}
                className="pg-btn-primary text-xs shrink-0"
              >
                {executeMutation.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Send className="h-3.5 w-3.5" />
                )}
                RUN REQUEST
              </button>
              <button
                type="button"
                onClick={() => setShowSaveBox((s) => !s)}
                className="pg-btn-secondary text-xs shrink-0"
              >
                <Save className="h-3.5 w-3.5" />
                SAVE TO COLLECTION
              </button>
            </div>

            {showSaveBox && (
              <div className="rounded-md bg-[#0D1016] border border-[#2A3244] p-3 grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
                <input
                  type="text"
                  value={requestName}
                  onChange={(e) => setRequestName(e.target.value)}
                  placeholder="Request Name"
                  className="pg-input text-xs"
                />
                <select
                  value={saveTargetColId}
                  onChange={(e) => setSaveTargetColId(e.target.value)}
                  className="pg-select text-xs"
                >
                  <option value="new">+ Create New Collection</option>
                  {collections.map((c) => (
                    <option key={c.id} value={String(c.id)}>
                      {c.collection_name}
                    </option>
                  ))}
                </select>
                {saveTargetColId === 'new' ? (
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newCollectionName}
                      onChange={(e) => setNewCollectionName(e.target.value)}
                      placeholder="New Collection Name"
                      className="pg-input text-xs"
                    />
                    <button
                      type="button"
                      onClick={() => saveMutation.mutate()}
                      disabled={saveMutation.isPending}
                      className="pg-btn-primary text-xs shrink-0"
                    >
                      Save
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => saveMutation.mutate()}
                    disabled={saveMutation.isPending}
                    className="pg-btn-primary text-xs"
                  >
                    Save Request
                  </button>
                )}
              </div>
            )}

            {/* Webhook HMAC Signing Options */}
            {endpoint.includes('/webhooks/') && (
              <div className="flex flex-wrap items-center gap-4 text-xs bg-[#0D1016] border border-[#222836] rounded px-3 py-2">
                <label className="inline-flex items-center gap-1.5 text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={signWebhook}
                    onChange={(e) => {
                      setSignWebhook(e.target.checked);
                      if (e.target.checked) setInvalidSignature(false);
                    }}
                    className="accent-emerald-500"
                  />
                  Auto-sign with server HMAC-SHA256 secret
                </label>
                <label className="inline-flex items-center gap-1.5 text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={invalidSignature}
                    onChange={(e) => {
                      setInvalidSignature(e.target.checked);
                      if (e.target.checked) setSignWebhook(false);
                    }}
                    className="accent-red-500"
                  />
                  Send invalid HMAC signature
                </label>
              </div>
            )}

            {/* Editor Tabs */}
            <div className="border-b border-[#222836] flex gap-4 text-xs">
              {(
                [
                  ['body', 'JSON Body'],
                  ['headers', `Headers (${headers.length})`],
                  ['params', `Query Params (${queryParams.length})`],
                ] as const
              ).map(([tab, label]) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setActiveEditorTab(tab)}
                  className={`pb-2 border-b-2 font-medium ${
                    activeEditorTab === tab
                      ? 'border-emerald-500 text-emerald-400'
                      : 'border-transparent text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {activeEditorTab === 'body' && (
              <textarea
                rows={9}
                value={bodyText}
                onChange={(e) => setBodyText(e.target.value)}
                placeholder='{ "order_id": "ORD-1001" }'
                className="pg-input font-mono text-xs leading-relaxed"
              />
            )}

            {activeEditorTab === 'headers' && (
              <div className="space-y-2">
                {headers.map((h, idx) => (
                  <div key={idx} className="flex gap-2">
                    <input
                      value={h.key}
                      onChange={(e) =>
                        setHeaders((prev) => prev.map((row, i) => (i === idx ? { ...row, key: e.target.value } : row)))
                      }
                      placeholder="Header name"
                      className="pg-input font-mono text-xs"
                    />
                    <input
                      value={h.value}
                      onChange={(e) =>
                        setHeaders((prev) =>
                          prev.map((row, i) => (i === idx ? { ...row, value: e.target.value } : row)),
                        )
                      }
                      placeholder="Header value"
                      className="pg-input font-mono text-xs"
                    />
                    <button
                      type="button"
                      onClick={() => setHeaders((prev) => prev.filter((_, i) => i !== idx))}
                      className="p-2 text-slate-500 hover:text-red-400"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => setHeaders((prev) => [...prev, { key: '', value: '' }])}
                  className="pg-btn-secondary text-xs py-1"
                >
                  <Plus className="h-3.5 w-3.5" /> Add Header
                </button>
              </div>
            )}

            {activeEditorTab === 'params' && (
              <div className="space-y-2">
                {queryParams.map((p, idx) => (
                  <div key={idx} className="flex gap-2">
                    <input
                      value={p.key}
                      onChange={(e) =>
                        setQueryParams((prev) =>
                          prev.map((row, i) => (i === idx ? { ...row, key: e.target.value } : row)),
                        )
                      }
                      placeholder="Param key"
                      className="pg-input font-mono text-xs"
                    />
                    <input
                      value={p.value}
                      onChange={(e) =>
                        setQueryParams((prev) =>
                          prev.map((row, i) => (i === idx ? { ...row, value: e.target.value } : row)),
                        )
                      }
                      placeholder="Param value"
                      className="pg-input font-mono text-xs"
                    />
                    <button
                      type="button"
                      onClick={() => setQueryParams((prev) => prev.filter((_, i) => i !== idx))}
                      className="p-2 text-slate-500 hover:text-red-400"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => setQueryParams((prev) => [...prev, { key: '', value: '' }])}
                  className="pg-btn-secondary text-xs py-1"
                >
                  <Plus className="h-3.5 w-3.5" /> Add Query Param
                </button>
              </div>
            )}
          </div>

          {/* Live Response Panel */}
          <div className="pg-card p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-[#222836]">
              <div className="flex items-center gap-3">
                <span className="text-xs font-semibold text-slate-200">HTTP Response</span>
                {response && (
                  <>
                    <span className={`px-2 py-0.5 rounded border font-mono text-[11px] font-semibold ${statusColor}`}>
                      {response.status_code} {response.reason_phrase}
                    </span>
                    <span className="font-mono text-xs text-slate-400">{response.duration_ms} ms</span>
                  </>
                )}
              </div>
              {response && (
                <div className="flex gap-3 text-xs">
                  <button
                    onClick={() => setActiveResponseTab('body')}
                    className={activeResponseTab === 'body' ? 'text-emerald-400 font-medium' : 'text-slate-400'}
                  >
                    Body
                  </button>
                  <button
                    onClick={() => setActiveResponseTab('headers')}
                    className={activeResponseTab === 'headers' ? 'text-emerald-400 font-medium' : 'text-slate-400'}
                  >
                    Headers ({Object.keys(response.headers).length})
                  </button>
                </div>
              )}
            </div>

            {!response ? (
              <p className="text-xs text-slate-500 py-8 text-center">
                Select a request from a collection or configure one above and click <strong>RUN REQUEST</strong>.
              </p>
            ) : activeResponseTab === 'body' ? (
              <pre className="p-3 rounded-md bg-[#0A0C10] border border-[#222836] text-[11px] font-mono text-slate-200 overflow-x-auto max-h-80">
                {typeof response.body === 'string' ? response.body : JSON.stringify(response.body, null, 2)}
              </pre>
            ) : (
              <div className="rounded-md bg-[#0A0C10] border border-[#222836] p-3 text-[11px] font-mono space-y-1 max-h-64 overflow-y-auto">
                {Object.entries(response.headers).map(([k, v]) => (
                  <div key={k} className="flex gap-2">
                    <span className="text-slate-500 shrink-0">{k}:</span>
                    <span className="text-slate-200 break-all">{v}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

