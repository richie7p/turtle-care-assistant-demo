import { defineConfig, devices } from "@playwright/test";

const turtleModule = process.env.E2E_TURTLE_MODULE ?? "true";
const edition = turtleModule === "true" ? "turtle" : "core";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: {
    baseURL: "http://127.0.0.1:8000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], channel: "chrome" } },
    { name: "mobile", use: { ...devices["Pixel 7"], channel: "chrome" } },
  ],
  webServer: {
    command: "..\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 8000",
    url: "http://127.0.0.1:8000/api/health",
    reuseExistingServer: false,
    timeout: 60_000,
    env: {
      DATABASE_URL: `sqlite:///./data/e2e-${edition}.db`,
      UPLOAD_DIR: "./uploads-e2e",
      APP_ORIGIN: "http://127.0.0.1:8000",
      SESSION_SECRET: "e2e-only-session-secret-at-least-32-characters",
      ENABLE_TURTLE_MODULE: turtleModule,
      APP_NAME: turtleModule === "true" ? "烏龜飼養小助手" : "NVIDIA NIM RAG Platform",
      APP_SHORT_NAME: turtleModule === "true" ? "烏龜飼養" : "NIM RAG",
      APP_ICON: turtleModule === "true" ? "龜" : "AI",
      ASSISTANT_NAME: turtleModule === "true" ? "烏龜飼養小助手" : "AI 知識助理",
      KNOWLEDGE_LABEL: turtleModule === "true" ? "飼養知識" : "組織知識庫",
      PROFILE_LABEL: turtleModule === "true" ? "我的龜龜" : "Profile",
    },
  },
});
