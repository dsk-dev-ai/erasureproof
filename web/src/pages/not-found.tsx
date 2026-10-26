import { Link } from "react-router-dom";
import { Home } from "lucide-react";
import { Logo } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 px-6 text-center">
      <Logo />
      <p className="font-mono text-xs uppercase tracking-[0.3em] text-primary">Error 404</p>
      <h1 className="font-display text-4xl font-bold">This record no longer exists.</h1>
      <p className="max-w-md text-muted-foreground">
        The page you requested is absent — proof that deletion can work, if not that this URL ever existed.
      </p>
      <Link to="/">
        <Button variant="brand">
          <Home className="h-4 w-4" /> Return home
        </Button>
      </Link>
    </div>
  );
}
