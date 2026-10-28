import {
  Activity,
  BookOpen,
  Cable,
  Database,
  FileSearch,
  KeyRound,
  LayoutDashboard,
  ScanSearch,
  Settings,
  Users,
} from "lucide-react";

export const navItems = [
  { href: "/app", label: "Overview", icon: LayoutDashboard, end: true },
  { href: "/app/requests", label: "Requests", icon: FileSearch },
  { href: "/app/subjects", label: "Subjects", icon: Users },
  { href: "/app/connectors", label: "Connectors", icon: Cable },
  { href: "/app/exposure", label: "Exposure", icon: ScanSearch },
  { href: "/app/evidence", label: "Evidence & ledger", icon: Database },
  { href: "/app/api-keys", label: "API keys", icon: KeyRound },
  { href: "/app/docs", label: "Documentation", icon: BookOpen },
  { href: "/app/settings", label: "Settings", icon: Settings },
];

export const activityIcon = Activity;
