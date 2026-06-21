import { redirect } from "next/navigation";
import MapShell from "@/components/MapShell";
import { isAuthed } from "@/lib/auth";

export const dynamic = "force-dynamic";

export default async function Home() {
  if (!(await isAuthed())) redirect("/login?next=/");
  return (
    <div className="h-full w-full bg-anthracite-deep">
      <MapShell />
    </div>
  );
}
