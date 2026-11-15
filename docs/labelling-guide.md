# Labelling guide: is this place a good answer?

You get `data/eval/labelling/annotator_A.csv` (or `_B`): for each question, the places that our search methods ranked in
their top 5. Fill the **`label`** column of every row with **1** (a good answer) or **0** (not), and use `notes` for
doubts. Label alone: do not ask the other person and do not look at the search results. Do not change other columns.
About 1,260 places, 2-3 hours. 508 of the rows are labelled by both of you; that is how we measure agreement.

## The rule: would you send a hungry person to this place for this question?

Use what the row shows (`name`, `category`, `tags`, `menu`) and, when unsure, the `link` (Facebook or Foodpanda page).

| Question is about | Label 1 when | Label 0 when |
|---|---|---|
| a specific dish ("kuy teav", "lok lak", "amok") | the name or menu says they serve it, or it clearly is that kind of shop | only a similar dish (udon for kuy teav), or only the category text says it |
| a kind of venue ("coffee", "pizza", "bbq") | the place is that kind of venue | it merely sells something related |
| a cuisine ("japanese food") | the place serves that cuisine | no sign of it |
| a meaning ("something sweet", "healthy food") | it clearly fits the idea | it does not |
| a typo ("piza", "kofee") | judge it as the corrected word | |
| "... in <khan>" | it fits the dish AND the `khan` column is that khan | wrong khan: always 0 |
| "... near <landmark>" | it fits the dish AND `km_from_landmark` is 3.0 or less | farther, or the column is empty (distance unknown): 0 |
| a named place or chain ("kfc") | it is that place or one of its branches | a different place |

Not sure after looking at the link? Pick the more likely answer and write `unsure` in `notes`. Do not leave `label` empty.

## After you both finish

    venv/bin/python scrapers/eval_agree.py data/eval/labelling/annotator_A.csv data/eval/labelling/annotator_B.csv

It prints agreement and Cohen's kappa, and writes `data/eval/labelling/disagreements.csv`. Settle those rows together and
fill `final` (1 or 0), run the command again, then score the search on the human labels:

    venv/bin/python scrapers/eval_run.py --queries data/eval/queries_human.csv --tag human

The report should give both: the scores on the word-rule labels (`results/eval_results.csv`) and on the human labels
(`results/eval_results_human.csv`), and the kappa between the two of you.
