/** A link to another site (Google Maps, a Facebook page, OpenStreetMap). Inside Telegram it opens in the
 *  phone's browser or maps app instead of Telegram's small in-app browser. */
import type { ReactNode } from "react";
import { openExternal } from "../lib/telegram";

export function ExternalLink({ href, className, children }: { href: string; className?: string; children: ReactNode }) {
  const external = /^https?:/i.test(href);
  return (
    <a
      href={href}
      className={className}
      {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
      onClick={external ? (e) => openExternal(e, href) : undefined}
    >
      {children}
    </a>
  );
}
