import React from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { formatDate } from "../utils/formatters";

export const AuditLog: React.FC = () => {
  const { data: logs = [], isLoading } = useQuery({
    queryKey: ["auditLog"],
    queryFn: api.getAuditLog,
  });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Activity log</h2>
        <p className="text-sm text-slate-500 mt-1">
          A record of user actions and reviews in CloudCost Copilot.
        </p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-900">Action History</h3>
          <span className="text-xs text-slate-400">{logs.length} actions</span>
        </div>

        {isLoading ? (
          <div className="p-8 space-y-3">
            <div className="h-6 bg-slate-100 rounded w-full animate-pulse" />
            <div className="h-6 bg-slate-100 rounded w-full animate-pulse" />
          </div>
        ) : logs.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-500">
            No activity recorded yet. Actions like accepting ideas or previewing fixes will appear here.
          </div>
        ) : (
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold">
                <th className="py-3 px-4">Time</th>
                <th className="py-3 px-4">Actor</th>
                <th className="py-3 px-4">Action</th>
                <th className="py-3 px-4">Target Item</th>
                <th className="py-3 px-4">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {logs.map((log) => (
                <tr key={log.id} className="hover:bg-slate-50">
                  <td className="py-3 px-4 text-slate-500 font-mono">
                    {formatDate(log.ts)}
                  </td>
                  <td className="py-3 px-4 font-medium text-slate-800">{log.actor}</td>
                  <td className="py-3 px-4 capitalize font-semibold text-slate-900">
                    {log.action.replace(/_/g, " ")}
                  </td>
                  <td className="py-3 px-4 text-slate-600 font-mono">{log.entity_id}</td>
                  <td className="py-3 px-4 text-slate-500 font-mono text-[11px]">
                    {log.payload ? JSON.stringify(log.payload) : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
