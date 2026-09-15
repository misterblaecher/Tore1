import { Link, useParams } from "react-router-dom";
import { ArrowLeft, ShieldCheck } from "lucide-react";
import ChannelAclSettings from "@/components/ChannelAclSettings";
import { structurePath } from "@/lib/forum-navigation";

export default function ChannelAclPage() {
  const { slug = "" } = useParams();
  return <main className="forum-main">
    <div className="forum-main__head">
      <div><span className="forum-eyebrow">Permissions fines</span><h1>Accès aux salons</h1><p>Les ACL explicites remplacent les niveaux génériques pour les salons qui les activent.</p></div>
      <ShieldCheck size={24} />
    </div>
    <ChannelAclSettings slug={slug} />
    <Link className="forum-button forum-button--ghost" to={structurePath(slug, "discussions")}><ArrowLeft size={15} />Retour aux discussions</Link>
  </main>;
}
