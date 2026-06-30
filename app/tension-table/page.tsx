import { redirect } from "next/navigation";
import { getTensionInputs, getKhetSnapshots } from "@/lib/listings-db";
import TensionTable from "@/components/TensionTable";
import { isAuthed } from "@/lib/auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function TensionTablePage() {
  if (!(await isAuthed())) redirect("/login?next=/tension-table");
  const [inputs, snapshots] = await Promise.all([
    getTensionInputs(),
    getKhetSnapshots(),
  ]);
  return <TensionTable inputs={inputs} snapshots={snapshots} />;
}
