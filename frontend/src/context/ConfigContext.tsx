import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import type { PublicConfig } from "../types";


const fallbackConfig: PublicConfig = {
  app_name: "NVIDIA NIM RAG Platform",
  app_short_name: "NIM RAG",
  app_icon: "AI",
  app_tagline: "可自行替換知識庫的 AI 助理平台",
  app_description: "結合自訂知識庫與 NVIDIA NIM 的可部署 RAG 系統。",
  assistant_name: "AI 知識助理",
  knowledge_label: "知識庫",
  profile_label: "Profile",
  welcome_title: "今天想查詢什麼？",
  welcome_description: "我會先檢索管理員提供的知識庫，再整理成附有來源的回答。",
  disclaimer: "AI 可能會出錯，重要決策請由資料負責人覆核。",
  enable_turtle_module: false,
  ai_provider: "nvidia-nim",
  ai_configured: false,
};

interface ConfigContextValue {
  config: PublicConfig;
  loading: boolean;
}

const ConfigContext = createContext<ConfigContextValue>({ config: fallbackConfig, loading: true });

export function ConfigProvider({ children }: { children: React.ReactNode }) {
  const [config, setConfig] = useState(fallbackConfig);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api<PublicConfig>("/public/config").then((data) => {
      setConfig(data);
      document.title = data.app_name;
      document.querySelector('meta[name="description"]')?.setAttribute("content", data.app_description);
    }).catch(() => undefined).finally(() => setLoading(false));
  }, []);
  const value = useMemo(() => ({ config, loading }), [config, loading]);
  return <ConfigContext.Provider value={value}>{children}</ConfigContext.Provider>;
}

export function useAppConfig() {
  return useContext(ConfigContext);
}
