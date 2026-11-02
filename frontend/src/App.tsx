import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DatasetProvider } from "./context/DatasetContext";
import { ChatProvider } from "./context/ChatContext";
import { Layout } from "./components/Layout";
import { Overview } from "./pages/Overview";
import { Recommendations } from "./pages/Recommendations";
import { CostExplorer } from "./pages/CostExplorer";
import { Copilot } from "./pages/Copilot";
import { DataManagement } from "./pages/DataManagement";
import { Anomalies } from "./pages/Anomalies";
import { Evaluation } from "./pages/Evaluation";
import { AuditLog } from "./pages/AuditLog";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      refetchOnWindowFocus: false,
    },
  },
});

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <DatasetProvider>
        <ChatProvider>
          <BrowserRouter>
            <Layout>
              <Routes>
                <Route path="/" element={<Overview />} />
                <Route path="/recommendations" element={<Recommendations />} />
                <Route path="/explorer" element={<CostExplorer />} />
                <Route path="/copilot" element={<Copilot />} />
                <Route path="/data" element={<DataManagement />} />
                <Route path="/anomalies" element={<Anomalies />} />
                <Route path="/eval" element={<Evaluation />} />
                <Route path="/audit" element={<AuditLog />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Layout>
          </BrowserRouter>
        </ChatProvider>
      </DatasetProvider>
    </QueryClientProvider>
  );
};

export default App;
