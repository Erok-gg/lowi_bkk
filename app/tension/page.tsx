import { redirect } from "next/navigation";
import { getTensionInputs, getKhetSnapshots } from "@/lib/listings-db";
import TensionMapShell from "@/components/TensionMapShell";
import { isAuthed } from "@/lib/auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function TensionPage() {
  if (!(await isAuthed())) redirect("/login?next=/tension");
  const [inputs, snapshots] = await Promise.all([
    getTensionInputs(),
    getKhetSnapshots(),
  ]);
  return <TensionMapShell inputs={inputs} snapshots={snapshots} />;
}
