import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "./index.css";
import CustomerPortal from "./CustomerPortal";
import ManagementLogin from "./ManagementLogin";
import ManagementWorkspace from "./ManagementWorkspace";
import Storefront, { StoreLayout } from "./Storefront";
import CustomerHub from "./customer-hub/CustomerHub";

const pathname = window.location.pathname.replace(/\/+$/, "") || "/";
let screen;

if (pathname === "/login") {
  screen = (
    <StoreLayout>
      <CustomerPortal />
    </StoreLayout>
  );
} else if (
  pathname === "/account" ||
  pathname.startsWith("/account/") ||
  pathname === "/orders" ||
  pathname.startsWith("/orders/")
) {
  screen = (
    <StoreLayout>
      <CustomerHub />
    </StoreLayout>
  );
} else if (pathname === "/management/login") {
  screen = <ManagementLogin />;
} else if (pathname === "/dashboard" || pathname.startsWith("/dashboard/")) {
  screen = <ManagementWorkspace />;
} else {
  screen = <Storefront />;
}

createRoot(document.getElementById("root")).render(
  <StrictMode>{screen}</StrictMode>,
);
