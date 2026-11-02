import React, { createContext, useContext, useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type DatasetItem, type DatasetSummary } from "../api/client";

interface DatasetContextType {
  activeDatasetId: string | null;
  setActiveDatasetId: (id: string) => void;
  datasets: DatasetItem[];
  isLoadingDatasets: boolean;
  activeDataset: DatasetItem | undefined;
  summary: DatasetSummary | undefined;
  isLoadingSummary: boolean;
  refreshDatasets: () => void;
}

const DatasetContext = createContext<DatasetContextType | undefined>(undefined);

export const DatasetProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [activeDatasetId, setActiveDatasetId] = useState<string | null>(null);

  const {
    data: datasets = [],
    isLoading: isLoadingDatasets,
    refetch: refreshDatasets,
  } = useQuery({
    queryKey: ["datasets"],
    queryFn: api.getDatasets,
  });

  // Automatically select the first dataset when loaded if none is active
  useEffect(() => {
    if (datasets.length > 0 && !activeDatasetId) {
      setActiveDatasetId(datasets[0].id);
    }
  }, [datasets, activeDatasetId]);

  const activeDataset = datasets.find((d) => d.id === activeDatasetId);

  const { data: summary, isLoading: isLoadingSummary } = useQuery({
    queryKey: ["datasetSummary", activeDatasetId],
    queryFn: () => (activeDatasetId ? api.getDatasetSummary(activeDatasetId) : Promise.reject()),
    enabled: !!activeDatasetId,
  });

  return (
    <DatasetContext.Provider
      value={{
        activeDatasetId,
        setActiveDatasetId,
        datasets,
        isLoadingDatasets,
        activeDataset,
        summary,
        isLoadingSummary,
        refreshDatasets,
      }}
    >
      {children}
    </DatasetContext.Provider>
  );
};

export const useDataset = () => {
  const context = useContext(DatasetContext);
  if (!context) {
    throw new Error("useDataset must be used within a DatasetProvider");
  }
  return context;
};
