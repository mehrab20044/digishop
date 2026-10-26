import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import './index.css';
import CustomerPortal from './CustomerPortal';
import ManagementLogin from './ManagementLogin';
import ManagementWorkspace from './ManagementWorkspace';
import Storefront from './Storefront';

const pathname = window.location.pathname.replace(/\/+$/, '') || '/';
let screen;

if (pathname === '/login' || pathname === '/account') {
  screen = <CustomerPortal />;
} else if (pathname === '/management/login') {
  screen = <ManagementLogin />;
} else if (pathname === '/dashboard' || pathname.startsWith('/dashboard/')) {
  screen = <ManagementWorkspace />;
} else {
  screen = <Storefront />;
}

createRoot(document.getElementById('root')).render(
  <StrictMode>{screen}</StrictMode>,
);
