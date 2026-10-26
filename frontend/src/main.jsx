import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "./index.css";
import CustomerPortal from "./CustomerPortal";
import ManagementLogin from "./ManagementLogin";
import ManagementWorkspace from "./ManagementWorkspace";

const pathname =
  window.location.pathname.replace(/\/+$/, "") || "/";

const customerPage =
  pathname === "/login" || pathname === "/account";

let screen;

if (customerPage) {
  screen = <CustomerPortal />;
} else if (pathname === "/management/login") {
  screen = <ManagementLogin />;
} else {
  screen = <ManagementWorkspace />;
}

createRoot(document.getElementById("root")).render(
  <StrictMode>{screen}</StrictMode>,
);