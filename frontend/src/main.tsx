import React from "react";
import ReactDOM from "react-dom/client";
import { FluentProvider } from "@fluentui/react-components";
import { App } from "./App";
import { ThemeWrapper } from "./ThemeWrapper";
import { initializeNotifications } from "./utils/notifications";
import "./index.css";

initializeNotifications();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeWrapper>
      <App />
    </ThemeWrapper>
  </React.StrictMode>,
);
