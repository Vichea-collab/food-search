import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { I18nProvider } from "./i18n/I18nContext";
import { ThemeProvider } from "./theme/ThemeContext";

// Each page is its own download: the Telegram Mini App (chat) never loads the demo's code.
const ChatPage = lazy(() => import("./features/chat/ChatPage").then((m) => ({ default: m.ChatPage })));
const DemoPage = lazy(() => import("./features/demo/DemoPage").then((m) => ({ default: m.DemoPage })));

export function App() {
  return (
    <ThemeProvider>
      <I18nProvider>
        <BrowserRouter>
          <Suspense fallback={null}>
            <Routes>
              <Route path="/" element={<ChatPage />} />
              <Route path="/demo" element={<DemoPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </I18nProvider>
    </ThemeProvider>
  );
}
