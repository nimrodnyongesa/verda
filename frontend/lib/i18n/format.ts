/**
 * Tiny message formatter — handles two needs without pulling in
 * `intl-messageformat` / `next-intl` / `react-intl`:
 *
 *   1. Dotted-path lookup against the JSON catalog (`header.cases`).
 *   2. `{name}` placeholder substitution with stringified values.
 *
 * Anything more elaborate (plurals, gender, nested choices) is out of
 * scope for the current chrome surfaces. When a feature shows up that
 * needs ICU plural rules we can graduate to `Intl.MessageFormat` in
 * isolation without touching call sites — `t(key, vars)` stays the
 * same.
 */

export type MessageBag = Readonly<Record<string, unknown>>;
export type Vars = Readonly<Record<string, string | number>>;

/**
 * Walk a dotted key (e.g. `userMenu.signOutBody`) through the catalog
 * tree. Returns `undefined` if any segment is missing or terminal value
 * is not a string — the caller decides how to fall back.
 */
export function lookup(bag: MessageBag, key: string): string | undefined {
  let cur: unknown = bag;
  for (const part of key.split(".")) {
    if (typeof cur !== "object" || cur === null) return undefined;
    cur = (cur as Record<string, unknown>)[part];
  }
  return typeof cur === "string" ? cur : undefined;
}

/**
 * Substitute `{name}` placeholders. Unknown placeholders are left
 * intact so a missing `vars.name` is loudly visible during dev rather
 * than silently producing an empty string.
 */
export function interpolate(template: string, vars?: Vars): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (whole, name: string) => {
    const v = vars[name];
    return v === undefined || v === null ? whole : String(v);
  });
}

/**
 * Resolve `key` against `bag` and substitute `vars`. If the key is
 * missing in the active locale, fall back to the English catalog —
 * if that's also missing we return the key itself so QA spots gaps
 * immediately rather than seeing a blank.
 */
export function format(
  bag: MessageBag,
  fallback: MessageBag,
  key: string,
  vars?: Vars,
): string {
  const tmpl = lookup(bag, key) ?? lookup(fallback, key);
  if (tmpl === undefined) return key;
  return interpolate(tmpl, vars);
}
