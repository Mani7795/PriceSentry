import { PublicNav } from "@/components/public-nav";

// Public shell — NO auth gate. Dashboard + product pages are open to everyone.
export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen w-screen overflow-hidden">
      <PublicNav />
      <main className="flex-1 overflow-y-auto bg-bg">{children}</main>
    </div>
  );
}
