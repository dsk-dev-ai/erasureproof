import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/app-shell";
import { TenantProvider } from "@/components/tenant-provider";
import { Logo } from "@/components/brand/logo";

const LandingPage = lazy(() => import("@/pages/landing").then((module) => ({ default: module.LandingPage })));
const DashboardPage = lazy(() => import("@/pages/dashboard").then((module) => ({ default: module.DashboardPage })));
const RequestsPage = lazy(() => import("@/pages/requests").then((module) => ({ default: module.RequestsPage })));
const RequestDetailPage = lazy(() => import("@/pages/request-detail").then((module) => ({ default: module.RequestDetailPage })));
const SubjectsPage = lazy(() => import("@/pages/subjects").then((module) => ({ default: module.SubjectsPage })));
const ConnectorsPage = lazy(() => import("@/pages/connectors").then((module) => ({ default: module.ConnectorsPage })));
const ExposurePage = lazy(() => import("@/pages/exposure").then((module) => ({ default: module.ExposurePage })));
const EvidencePage = lazy(() => import("@/pages/evidence").then((module) => ({ default: module.EvidencePage })));
const SettingsPage = lazy(() => import("@/pages/settings").then((module) => ({ default: module.SettingsPage })));
const DocsPage = lazy(() => import("@/pages/docs").then((module) => ({ default: module.DocsPage })));
const NotFoundPage = lazy(() => import("@/pages/not-found").then((module) => ({ default: module.NotFoundPage })));

function PageLoader() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4">
      <Logo markOnly />
      <span className="h-1 w-32 overflow-hidden rounded-full bg-muted">
        <span className="block h-full w-1/2 animate-shimmer rounded-full bg-primary" />
      </span>
      <span className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
        Loading control plane
      </span>
    </div>
  );
}

export function App() {
  return (
    <TenantProvider>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/app" element={<AppShell />}>
            <Route index element={<DashboardPage />} />
            <Route path="requests" element={<RequestsPage />} />
            <Route path="requests/:id" element={<RequestDetailPage />} />
            <Route path="subjects" element={<SubjectsPage />} />
            <Route path="connectors" element={<ConnectorsPage />} />
            <Route path="exposure" element={<ExposurePage />} />
            <Route path="evidence" element={<EvidencePage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="docs" element={<DocsPage />} />
            <Route path="docs/:slug" element={<DocsPage />} />
          </Route>
          <Route path="/console" element={<Navigate to="/app" replace />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </TenantProvider>
  );
}
