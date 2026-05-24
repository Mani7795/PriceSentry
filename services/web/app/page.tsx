import { redirect } from "next/navigation";

// The app opens directly to the public dashboard — no login required.
export default function RootPage() {
  redirect("/dashboard");
}
