export function normalizeTreeText(value) {
  return String(value || "")
    .replace(/ي/g, "ی")
    .replace(/ك/g, "ک")
    .replace(/[\u200c\u200d]/g, " ")
    .trim()
    .toLowerCase();
}
export function categoryAncestors(options, values) {
  const byValue = new Map(options.map((row) => [row.value, row]));
  const found = new Set();
  for (const value of values) {
    const seen = new Set([value]);
    let current = byValue.get(value);
    while (
      current?.parent &&
      byValue.has(current.parent) &&
      !seen.has(current.parent)
    ) {
      seen.add(current.parent);
      found.add(current.parent);
      current = byValue.get(current.parent);
    }
  }
  return found;
}
export function categoryTreeRows(options, expanded, query = "") {
  const byValue = new Map(options.map((row) => [row.value, row]));
  const children = new Map(),
    roots = [];
  for (const row of options) {
    if (row.parent && row.parent !== row.value && byValue.has(row.parent)) {
      if (!children.has(row.parent)) children.set(row.parent, []);
      children.get(row.parent).push(row);
    } else roots.push(row);
  }
  const term = normalizeTreeText(query);
  let included = null;
  if (term) {
    const matches = options.filter((row) => {
      const ancestors = categoryAncestors(options, [row.value]);
      return normalizeTreeText(
        [
          row.label,
          ...[...ancestors].map((value) => byValue.get(value)?.label),
        ].join(" "),
      ).includes(term);
    });
    included = new Set(matches.map((row) => row.value));
    for (const value of categoryAncestors(
      options,
      matches.map((row) => row.value),
    ))
      included.add(value);
  }
  const result = [],
    seen = new Set();
  function walk(row, depth, siblings, at) {
    if (seen.has(row.value)) return;
    seen.add(row.value);
    if (included && !included.has(row.value)) return;
    const next = children.get(row.value) || [];
    const isExpanded =
      next.length > 0 && (Boolean(term) || expanded.has(row.value));
    result.push({
      ...row,
      depth,
      hasChildren: next.length > 0,
      expanded: isExpanded,
      pos: at + 1,
      total: siblings.length,
    });
    if (isExpanded) next.forEach((child, i) => walk(child, depth + 1, next, i));
  }
  roots.forEach((row, i) => walk(row, 0, roots, i));
  // Corrupt cycles are not expected from the API; never recurse forever or hide every node.
  for (const row of options)
    if (
      !seen.has(row.value) &&
      !result.some((item) => item.value === row.parent) &&
      !roots.includes(row)
    ) {
      const parents = categoryAncestors(options, [row.value]);
      if (![...parents].some((value) => seen.has(value)))
        walk(row, 0, [row], 0);
    }
  return result;
}
