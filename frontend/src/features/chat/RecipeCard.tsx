import { ExternalLink } from "../../components/ExternalLink";
import { useI18n } from "../../i18n/I18nContext";
import type { StringKey } from "../../i18n/strings";
import { minutesText } from "../../lib/format";
import type { Recipe } from "../../lib/types";

const WAIT_KEYS: Record<string, StringKey> = {
  chill: "waitChill", marinate: "waitMarinate", rise: "waitRise", freeze: "waitFreeze", rest: "waitRest", soak: "waitSoak",
};
const DIFFICULTY_KEYS: Record<string, StringKey> = { easy: "diffEasy", medium: "diffMedium", hard: "diffHard" };

/** A recipe in a reply: the times at a glance, then ingredients and steps that open on demand.
 *  `focus` opens the part the question was about ("what are the ingredients?" -> ingredients). */
export function RecipeCard({ recipe: r, focus }: { recipe: Recipe; focus?: "ingredients" | "steps" | null }) {
  const { t } = useI18n();
  const minutes = (n: number) => minutesText(n, t);
  const waits = r.waiting.map((w) => WAIT_KEYS[w]).filter(Boolean).map((k) => t(k));
  return (
    <section className="recipe" aria-label={`${t("recipe")}: ${r.title}`}>
      <header className="recipe-head">
        <p className="recipe-kicker">{t("recipe")}</p>
        <h3 className="recipe-title">{r.title}</h3>
        {r.description && <p className="recipe-desc">{r.description}</p>}
      </header>
      <dl className="recipe-stats">
        <div>
          <dt>{t("recipePrep")}</dt>
          <dd>{minutes(r.prep_minutes)}</dd>
        </div>
        <div>
          <dt>{t("recipeCook")}</dt>
          <dd>{minutes(r.cook_minutes)}</dd>
        </div>
        <div className="total">
          <dt>{t("recipeTotal")}</dt>
          <dd>{minutes(r.total_minutes)}</dd>
        </div>
        {r.servings != null && (
          <div>
            <dt>{t("recipeServes")}</dt>
            <dd>{r.servings}</dd>
          </div>
        )}
      </dl>
      {waits.length > 0 && <p className="recipe-note">{t("recipeWait", { what: waits.join(", ") })}</p>}
      <details className="recipe-part" open={focus === "ingredients"}>
        <summary>{t("recipeIngredients", { n: r.ingredients.length })}</summary>
        <ul>
          {r.ingredients.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      </details>
      <details className="recipe-part" open={focus === "steps"}>
        <summary>{t("recipeSteps", { n: r.steps.length })}</summary>
        <ol>
          {r.steps.map((step, i) => (
            <li key={i}>{step}</li>
          ))}
        </ol>
      </details>
      <footer className="recipe-foot">
        {r.difficulty && DIFFICULTY_KEYS[r.difficulty] && (
          <span className="fact-badge">{t(DIFFICULTY_KEYS[r.difficulty])}</span>
        )}
        {r.calories != null && <span className="fact-badge">{t("recipeKcal", { n: r.calories })}</span>}
        {r.source_url && (
          <ExternalLink href={r.source_url} className="act src">
            {t("recipeSource", { s: r.source })}
          </ExternalLink>
        )}
      </footer>
    </section>
  );
}
