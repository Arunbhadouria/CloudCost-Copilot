import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";
import { API_BASE } from "../api/client";
import { useDataset } from "./DatasetContext";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sqlQueries?: string[];
  toolData?: any[];
  faithfulnessPassed?: boolean;
  timestamp: number;
}

interface ChatContextType {
  messages: Message[];
  isStreaming: boolean;
  sendMessage: (questionText: string) => Promise<void>;
  clearChat: () => void;
  activeDetailsIndex: number | null;
  setActiveDetailsIndex: React.Dispatch<React.SetStateAction<number | null>>;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

const STORAGE_PREFIX = "cloudcost_chat_v1_";

export const ChatProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { activeDatasetId } = useDataset();
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeDetailsIndex, setActiveDetailsIndex] = useState<number | null>(null);

  const activeDatasetIdRef = useRef(activeDatasetId);
  useEffect(() => {
    activeDatasetIdRef.current = activeDatasetId;
  }, [activeDatasetId]);

  // Load messages from localStorage whenever activeDatasetId changes
  useEffect(() => {
    if (!activeDatasetId) {
      setMessages([]);
      return;
    }
    const key = `${STORAGE_PREFIX}${activeDatasetId}`;
    try {
      const stored = localStorage.getItem(key);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed)) {
          setMessages(parsed);
          return;
        }
      }
    } catch (e) {
      console.warn("Failed to read chat history from localStorage", e);
    }
    setMessages([]);
  }, [activeDatasetId]);

  // Save messages to localStorage helper
  const saveMessages = useCallback((datasetId: string | null, msgs: Message[]) => {
    if (!datasetId) return;
    try {
      const key = `${STORAGE_PREFIX}${datasetId}`;
      localStorage.setItem(key, JSON.stringify(msgs));
    } catch (e) {
      console.warn("Failed to save chat history to localStorage", e);
    }
  }, []);

  const clearChat = useCallback(() => {
    if (activeDatasetId) {
      try {
        localStorage.removeItem(`${STORAGE_PREFIX}${activeDatasetId}`);
      } catch (e) {
        console.warn("Failed to remove chat history from localStorage", e);
      }
    }
    setMessages([]);
    setActiveDetailsIndex(null);
  }, [activeDatasetId]);

  const sendMessage = useCallback(
    async (text: string) => {
      const currentDatasetId = activeDatasetIdRef.current;
      if (!text.trim() || !currentDatasetId || isStreaming) return;

      const userMsg: Message = {
        id: `user-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
        role: "user",
        content: text.trim(),
        timestamp: Date.now(),
      };

      setMessages((prev) => {
        const updated = [...prev, userMsg];
        saveMessages(currentDatasetId, updated);
        return updated;
      });

      setIsStreaming(true);

      const assistantMsgId = `asst-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`;
      const assistantMsg: Message = {
        id: assistantMsgId,
        role: "assistant",
        content: "",
        sqlQueries: [],
        toolData: [],
        faithfulnessPassed: true,
        timestamp: Date.now(),
      };

      // Append assistant placeholder
      setMessages((prev) => [...prev, assistantMsg]);

      try {
        const response = await fetch(`${API_BASE}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ dataset_id: currentDatasetId, message: text.trim() }),
        });

        if (!response.body) throw new Error("No response stream");

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const blocks = buffer.split(/\r?\n\r?\n/);
          buffer = blocks.pop() || "";

          for (const block of blocks) {
            const lines = block.split(/\r?\n/);
            for (const line of lines) {
              const trimmed = line.trim();
              if (trimmed.startsWith("data:")) {
                const dataStr = trimmed.slice(5).trim();
                if (!dataStr) continue;
                try {
                  const event = JSON.parse(dataStr);
                  if (event.type === "token") {
                    assistantMsg.content += event.text;
                    setMessages((prev) => {
                      const updated = [...prev];
                      updated[updated.length - 1] = { ...assistantMsg };
                      return updated;
                    });
                  } else if (event.type === "tool_result") {
                    if (event.sql) {
                      assistantMsg.sqlQueries = assistantMsg.sqlQueries || [];
                      assistantMsg.sqlQueries.push(event.sql);
                    }
                    if (event.rows) {
                      assistantMsg.toolData = assistantMsg.toolData || [];
                      assistantMsg.toolData.push(...event.rows);
                    }
                  } else if (event.type === "final") {
                    if (event.answer) {
                      assistantMsg.content = event.answer;
                    }
                    assistantMsg.faithfulnessPassed = event.faithfulness?.passed;
                    if (
                      event.sql &&
                      (!assistantMsg.sqlQueries || assistantMsg.sqlQueries.length === 0)
                    ) {
                      assistantMsg.sqlQueries = Array.isArray(event.sql) ? event.sql : [event.sql];
                    }
                    setMessages((prev) => {
                      const updated = [...prev];
                      updated[updated.length - 1] = { ...assistantMsg };
                      saveMessages(currentDatasetId, updated);
                      return updated;
                    });
                  }
                } catch (err) {
                  console.error("SSE parse error", err);
                }
              }
            }
          }
        }

        // Final save
        setMessages((prev) => {
          const updated = [...prev];
          saveMessages(currentDatasetId, updated);
          return updated;
        });
      } catch (err: any) {
        const errorMsg: Message = {
          id: assistantMsgId,
          role: "assistant",
          content:
            "Sorry, I could not complete that request. Please try again or ask in a different way.",
          faithfulnessPassed: false,
          timestamp: Date.now(),
        };
        setMessages((prev) => {
          const updated = [...prev.slice(0, -1), errorMsg];
          saveMessages(currentDatasetId, updated);
          return updated;
        });
      } finally {
        setIsStreaming(false);
      }
    },
    [isStreaming, saveMessages]
  );

  return (
    <ChatContext.Provider
      value={{
        messages,
        isStreaming,
        sendMessage,
        clearChat,
        activeDetailsIndex,
        setActiveDetailsIndex,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
};

export const useChat = () => {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error("useChat must be used within a ChatProvider");
  }
  return context;
};

