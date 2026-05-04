export type ThemeRegistry = Record<string, Record<string, unknown>>;

type ResolveThemeInput = {
  theme: string;
  theme_overrides?: Record<string, unknown>;
};

export function resolveTheme(
  input: ResolveThemeInput,
  registry: ThemeRegistry,
): Record<string, unknown> {
  const base = registry[input.theme];
  if (!base) {
    throw new Error(`Theme "${input.theme}" is not installed.`);
  }

  return {
    ...base,
    ...(input.theme_overrides ?? {}),
  };
}
