export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-bg px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-semibold tracking-tight">PriceSentry</h1>
          <p className="text-sm text-muted mt-1">Customer-review intelligence for pet brands</p>
        </div>
        <div className="bg-surface border border-border rounded-2xl shadow-sm p-8">
          {children}
        </div>
      </div>
    </div>
  );
}
