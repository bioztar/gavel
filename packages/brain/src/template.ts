/** `{{name}}` placeholders. Unknown or empty values render as nothing; spacing is tidied. */
export function render(template: string, vars: Record<string, string | number | undefined | null>): string {
  return template
    .replace(/\{\{\s*(\w+)\s*\}\}/g, (_, key: string) => {
      const value = vars[key];
      return value === undefined || value === null ? "" : String(value);
    })
    .replace(/[ \t]{2,}/g, " ")
    .replace(/\s+([.,:;?!])/g, "$1")
    .replace(/([.:?!]){2,}/g, "$1")
    .trim();
}
