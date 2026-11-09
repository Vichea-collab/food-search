import { useState } from "react";
import { ExternalLink } from "../../components/ExternalLink";
import { Icon } from "../../components/Icon";
import { useI18n } from "../../i18n/I18nContext";
import { distanceText, hoursText, telLink } from "../../lib/format";
import type { Place } from "../../lib/types";

const PAGE = 5;

/** One place in a reply: name, dish, kind and area, open now / hours / price / rating when known, and actions. */
export function PlaceCard({ place: p, rank }: { place: Place; rank: number }) {
  const { t } = useI18n();
  const showKind = p.kind && p.kind.toLowerCase() !== (p.dish || "").toLowerCase();
  const isTopRank = rank <= 3;
  const facts = [
    p.open_now === true && (
      <span key="open" className="fact-badge open">
        <span className="dot" aria-hidden="true" />
        {t("openNow")}
      </span>
    ),
    p.open_now === false && (
      <span key="closed" className="fact-badge closed">
        <span className="dot" aria-hidden="true" />
        {t("closedNow")}
      </span>
    ),
    p.rating != null && (
      <span key="rating" className="fact-badge rating">
        ⭐ {p.rating.toFixed(1)}
      </span>
    ),
    p.price_usd != null && (
      <span key="price" className="fact-badge price">
        💵 ${p.price_usd.toFixed(2)}
      </span>
    ),
    p.open_hour != null && p.close_hour != null && (
      <span key="hours" className="fact-badge hours">
        🕒 {hoursText(p.open_hour, p.close_hour, t("allDay"))}
      </span>
    ),
  ].filter(Boolean);

  return (
    <li className={`place${isTopRank ? ` top-place rank-${rank}` : ""}`}>
      <span className={`place-rank${isTopRank ? ` top-rank rank-${rank}` : ""}`} aria-hidden="true">
        {rank}
      </span>
      <div className="place-main">
        <h3 className="place-name">{p.name}</h3>
        {p.dish && <p className="place-dish">{p.dish}</p>}
        {(showKind || p.area) && (
          <p className="place-sub">
            {showKind && <span>{p.kind}</span>}
            {p.area && <span>{p.area}</span>}
          </p>
        )}
        {p.matched && p.matched.length > 0 && (
          <p className="place-match" aria-label={t("menuTitle")}>
            {p.matched.map((m, i) => (
              <span key={i}>
                🍽 {m.name}
                {m.price_usd > 0 && <b> ${m.price_usd.toFixed(2)}</b>}
              </span>
            ))}
          </p>
        )}
      </div>
      <div className="place-side">
        {p.image_url && (
          <img className="place-thumb" src={p.image_url} alt={p.name} loading="lazy" />
        )}
        {p.distance_km != null && (
          <div className="place-dist">
            <b>{distanceText(p.distance_km)}</b>
            <small>{t("away")}</small>
          </div>
        )}
      </div>
      {facts.length > 0 && <p className="facts">{facts}</p>}
      {p.menu && p.menu.length > 0 && (
        <div className="place-menu">
          <span className="menu-heading">{t("menuTitle")}</span>
          <div className="menu-chips">
            {p.menu.map((dish, i) => (
              <div key={i} className="menu-chip">
                <span className="menu-dish-name">• {dish.name}</span>
                <span className="menu-dish-dots" aria-hidden="true" />
                {dish.price_usd > 0 && <span className="menu-dish-price">${dish.price_usd.toFixed(2)}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
      <div className="actions">
        <ExternalLink href={p.maps_url} className="act primary">
          <Icon name="pin" />
          {t("directions")}
        </ExternalLink>
        {p.phone && (
          <a href={telLink(p.phone)} className="act">
            <Icon name="phone" />
            {t("call")}
          </a>
        )}
        {p.delivery?.map((d) => (
          <ExternalLink key={d.platform} href={d.url} className="act">
            {d.platform}
          </ExternalLink>
        ))}
        {p.page_url && (
          <ExternalLink href={p.page_url} className="act">
            {t(p.page_kind === "facebook" ? "pageFacebook" : "pageWebsite")}
          </ExternalLink>
        )}
      </div>
    </li>
  );
}

/** The ranked places of one reply, five at a time ("Show more"). */
export function PlaceList({ places, numbers }: { places: Place[]; numbers?: number[] }) {
  const { t } = useI18n();
  const [shown, setShown] = useState(PAGE);
  return (
    <ol className="places">
      {places.slice(0, shown).map((p, i) => (
        <PlaceCard key={p.id} place={p} rank={numbers?.[i] ?? i + 1} />
      ))}
      {shown < places.length && (
        <li className="more-row">
          <button type="button" className="more" onClick={() => setShown((n) => n + PAGE)}>
            {t("more")}
          </button>
        </li>
      )}
    </ol>
  );
}
